"""Read VAT-inclusive ČEZ household PDF tables; never guess missing cells."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from io import BytesIO
from itertools import pairwise
from urllib.parse import urlsplit

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 6
AMOUNT = re.compile(r"\d{1,3}(?: \d{3})*,\d{2}|\d+,\d{2}|[–—−-]")
RATE = re.compile(r"D\d{2}d", re.IGNORECASE)


class PriceListError(ValueError):
    """An error code safe to translate in the options form."""


@dataclass(frozen=True)
class ImportedPriceList:
    rates: dict[str, float]
    trade_effective: str
    distribution_effective: str
    digest: str
    poze_estimated: bool


def normalize(text: str) -> str:
    text = text.replace("\xad", "").replace("\xa0", " ")
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).lower()


def validate_cez_url(url: str) -> str:
    """Only HTTPS PDFs on the official ČEZ site, including every redirect."""
    try:
        parts = urlsplit(url.strip())
        if (
            parts.scheme != "https"
            or parts.hostname not in ("cez.cz", "www.cez.cz")
            or parts.port not in (None, 443)
            or parts.username is not None
            or parts.password is not None
            or not parts.path.lower().endswith(".pdf")
            or parts.fragment
        ):
            raise PriceListError("invalid_price_list_url")
    except ValueError as err:
        raise PriceListError("invalid_price_list_url") from err
    return url.strip()


def _date(text: str, section: str) -> str:
    matches = re.findall(
        rf"ucinnost {section} cen\s*:\s*od\s*(\d{{1,2}})\s*\.\s*"
        r"(\d{1,2})\s*\.\s*(\d{4})",
        normalize(text),
    )
    if len(set(matches)) != 1:
        raise PriceListError("unsupported_price_list")
    day, month, year = matches[0]
    return date(int(year), int(month), int(day)).isoformat()


def _cells(text: str) -> list[float | None]:
    # Amounts in parentheses are WITHOUT VAT. Do not multiply VAT again.
    text = re.sub(r"\([^)]*\)", "", text).replace("\xa0", " ")
    return [
        None if token in "–—−-" else float(token.replace(" ", "").replace(",", "."))
        for token in AMOUNT.findall(text)
    ]


def _read_table(page) -> tuple[list[str], dict[int, list[float | None]]]:
    """Anchor prices to numbered rows rather than PDF drawing order.

    ČEZ draws some numbers after all the labels. Plain text extraction therefore
    disconnects them. Baselines also differ between VAT and net prices.
    """
    fragments = []

    def visit(text, cm, tm, font, size):
        text = text.strip()
        if text and "\n" not in text:
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            fragments.append((x, y, text))

    text = page.extract_text(visitor_text=visit)
    header = re.search(r"Distribuční sazba([^\n]+)", text)
    if header is None:
        raise PriceListError("unsupported_price_list")
    columns = [r.lower() for r in RATE.findall(header[1])]
    if not columns or len(columns) != len(set(columns)):
        raise PriceListError("unsupported_price_list")
    anchors = [
        (x, y, int(t)) for x, y, t in fragments if t.isdigit() and 1 <= int(t) <= 30
    ]
    tables = {}
    for x, y, number in anchors:
        if number in tables:
            raise PriceListError("ambiguous_price_list")
        parts = sorted(
            (fx, t) for fx, fy, t in fragments if fx > x + 60 and y - 1 <= fy <= y + 5
        )
        cells = _cells(" ".join(t for _, t in parts))
        if len(cells) == len(columns):
            tables[number] = cells
    # Assert the exact supported table semantics, including units.
    plain = normalize(text)
    expected = {
        1: "Vysoký tarif Kč/MWh",
        2: "Nízký tarif Kč/MWh",
        3: "Stálá platba Kč/měsíc",
        4: "Vysoký tarif Kč/MWh",
        5: "Nízký tarif Kč/MWh",
        6: "do 3× 10 A a do 1× 25 A včetně Kč/měsíc",
        18: "nad 3× 160 A za každý 1 A Kč/měsíc",
        19: "nad 3× 63 A za každý 1 A Kč/měsíc",
        20: "nad 1× 25 A za každý 1 A Kč/měsíc",
        21: "Daň z elektřiny Kč/MWh",
        22: "Cena za systémové služby Kč/MWh",
        24: "Podle jističe Kč/A/počet fází",
        25: "Podle spotřeby Kč/MWh",
    }
    upper = (10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160)
    for row, (lower, higher) in enumerate(pairwise(upper), 7):
        expected[row] = f"nad 3× {lower} A do 3× {higher} A včetně Kč/měsíc"
    for number, label in expected.items():
        if f"{number} {normalize(label)}" not in plain:
            raise PriceListError("unsupported_price_list")
    if not re.search(r"23\s+cena za provoz nesitove\s+infrastruktury kc/mesic", plain):
        raise PriceListError("unsupported_price_list")
    return columns, tables


def parse_price_list(
    pdf: bytes,
    distribution_rate: str,
    amperes: int,
    phases: int,
    annual_import_kwh: float = 0,
) -> ImportedPriceList:
    """Parse the standard, single-period domestic ČEZ Prodej price list.

    An unsupported layout or multiple pricing periods is rejected. A review in
    the options flow must happen before any rates are saved.
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if len(pdf) > MAX_PDF_BYTES:
        raise PriceListError("price_list_too_large")
    if not pdf.startswith(b"%PDF-"):
        raise PriceListError("invalid_price_list_pdf")
    if phases not in (1, 3) or not isinstance(amperes, int) or amperes <= 0:
        raise PriceListError("invalid_breaker")
    try:
        reader = PdfReader(BytesIO(pdf))
        if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
            raise PriceListError("unsupported_price_list")
        pages = [(p, p.extract_text()) for p in reader.pages]
        all_text = "\n".join(t for _, t in pages)
        plain = normalize(all_text)
        if (
            "cez prodej" not in plain
            or "distribucni uzemi: cez distribuce" not in plain
            or not re.search(r"ceny jsou s\s*21\s*%\s*dph", plain)
        ):
            raise PriceListError("unsupported_price_list")
        candidates = [p for p, t in pages if "distribucni sazba" in normalize(t)]
        if len(candidates) != 1:
            raise PriceListError("ambiguous_price_list")
        columns, table = _read_table(candidates[0])
        rate = distribution_rate.strip().lower()
        if rate not in columns:
            raise PriceListError("rate_not_in_price_list")
        col = columns.index(rate)

        def value(row):
            if row not in table or table[row][col] is None:
                raise PriceListError("incomplete_price_list")
            return table[row][col]

        if phases == 1:
            breaker = value(6) if amperes <= 25 else value(20) * amperes
        elif amperes <= 160:
            upper = (10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160)
            row = 6 + next(i for i, a in enumerate(upper) if amperes <= a)
            # Most tariffs use a per-A charge above 63 A instead of rows 14–17.
            breaker = (
                value(19) * amperes if amperes > 63 and rate != "d57d" else value(row)
            )
        else:
            breaker = value(18 if rate == "d57d" else 19) * amperes
        capacity, consumption = value(24), value(25) / 1000
        if capacity > 0 and annual_import_kwh <= 0:
            raise PriceListError("poze_requires_annual_import")
        poze = (
            min(capacity * amperes * phases * 12 / annual_import_kwh, consumption)
            if capacity > 0
            else 0.0
        )
        rates = {
            "trade_vt": value(1) / 1000,
            "trade_nt": value(2) / 1000,
            "supplier_monthly": value(3),
            "distribution_vt": value(4) / 1000,
            "distribution_nt": value(5) / 1000,
            "breaker_monthly": breaker,
            "electricity_tax": value(21) / 1000,
            "system_services": value(22) / 1000,
            "infrastructure_monthly": value(23),
            "poze_kwh": poze,
        }
        # Cross-check both VAT totals published by ČEZ, allowing 0.05 CZK/MWh
        # component rounding. Reject shifted columns instead of showing a guess.
        for tariff, row in (("vt", 26), ("nt", 27)):
            total = sum(
                rates[k]
                for k in (
                    f"trade_{tariff}",
                    f"distribution_{tariff}",
                    "electricity_tax",
                    "system_services",
                )
            )
            if abs(total * 1000 - value(row)) > 0.05:
                raise PriceListError("inconsistent_price_list")
        return ImportedPriceList(
            rates,
            _date(all_text, "obchodnich"),
            _date(all_text, "distribucnich"),
            sha256(pdf).hexdigest(),
            capacity > 0,
        )
    except PriceListError:
        raise
    except (
        PdfReadError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        OverflowError,
    ) as err:
        raise PriceListError("invalid_price_list_pdf") from err
