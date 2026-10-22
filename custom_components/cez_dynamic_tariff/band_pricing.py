"""Verzované cenové strategie bez závislosti na Home Assistantu.

Částky jsou Kč/kWh nebo Kč/měsíc včetně DPH. Importovaný profil nikdy
nenahrazuje standardní VT/NT. Události uchovávají celé cenové podklady;
budoucí aktivace se vyhodnocuje podle UTC i po restartu bez přepisování historie.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from calendar import monthrange
from datetime import UTC, datetime, timedelta
from itertools import pairwise

MODES = ("percentage", "fixed_bands")
PRODUCT_NAMES = {
    "fixed_2_years": "Dynamický tarif na 2 roky",
    "fixed_indefinite": "Dynamický tarif (doba neurčitá)",
    "standard_percentage": "Standardní ceník s procentními pásmy",
}
SCHEDULE_KEYS = (
    "summer_workday_schedule",
    "summer_offday_schedule",
    "winter_workday_schedule",
    "winter_offday_schedule",
)


def instant(value):
    """Vyžaduje jednoznačný okamžik s offsetem; místní nejasný čas odmítne."""
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("invalid_activation")
    return result.astimezone(UTC)


def validate_bands(schedules):
    """Ověří čtyři celé místní dny, nezáporné ceny a návaznost minut 0–1440."""
    if not isinstance(schedules, dict) or set(schedules) != set(SCHEDULE_KEYS):
        raise ValueError("incomplete_price_list")
    prices = set()
    for rows in schedules.values():
        edge = 0
        if not isinstance(rows, list) or not rows:
            raise ValueError("incomplete_price_list")
        for row in rows:
            start, end, price = row["start_minute"], row["end_minute"], row["price_kwh"]
            if (
                type(start) is not int
                or type(end) is not int
                or start != edge
                or not start < end <= 1440
                or isinstance(price, bool)
                or not isinstance(price, (int, float))
                or not math.isfinite(price)
                or price < 0
            ):
                raise ValueError("incomplete_price_list")
            prices.add(price)
            edge = end
        if edge != 1440:
            raise ValueError("incomplete_price_list")
    # Podporovaná šablona ČEZ má přesně čtyři cenové úrovně napříč sezónami.
    # Pořadí se nikdy neodvozuje jen od dne, který právě zobrazujeme.
    if len(prices) != 4:
        raise ValueError("unsupported_price_list")
    return dict(
        zip(
            sorted(prices),
            ("super_cheap", "cheap", "expensive", "very_expensive"),
            strict=True,
        )
    )


def snapshot(options, defaults):
    """Oddělí cenu od nastavení UI; nepoužívaný nahraný profil cenu nemění."""
    values = {k: options.get(k, v) for k, v in defaults.items()}
    values.update({k: options[k] for k in SCHEDULE_KEYS if k in options})
    values.update(
        {
            "tariff_mode": options.get("tariff_mode", "percentage"),
            "include_holidays": options.get("include_holidays", True),
            "fixed_profile": next(
                (
                    p
                    for p in options.get("fixed_price_profiles", [])
                    if p["id"] == options.get("fixed_profile_id")
                ),
                None,
            ),
        }
    )
    for key, default in (
        ("super_cheap_threshold", -50),
        ("cheap_threshold", -10),
        ("expensive_threshold", 10),
        ("very_expensive_threshold", 25),
    ):
        values[key] = options.get(key, default)
    return copy.deepcopy(values)


def record_change(
    old,
    new,
    defaults,
    now,
    activation=None,
    archive_revision=None,
    force=False,
    archive_identity=None,
):
    """Připojí revizi při změně ceny; explicitní nová volba nahradí budoucí plán.

    Předchozí konfigurace se zachová i před první událostí. Nejde o důkaz její
    smluvní platnosti v dávné minulosti; tu dál hlídá historické účetnictví.
    Nahrání nevybraného PDF nevytváří cenovou událost.
    """
    before, after = snapshot(old, defaults), snapshot(new, defaults)
    if before == after and activation is None and not force:
        return new
    starts = activation or now
    if starts < now:
        raise ValueError("activation_in_past")
    events = copy.deepcopy(old.get("pricing_events", []))
    if events:
        before = settings_at(
            old, defaults, now - timedelta(microseconds=1) if starts == now else now
        )
    # Historii ponecháme. Nový explicitní výběr ruší dosud nenastalé aktivace;
    # změny záloh nebo import nepoužitého PDF touto cestou neprocházejí.
    events = [
        e
        for e in events
        if instant(e["starts_at"]) <= now and instant(e["starts_at"]) < starts
    ]
    encoded = json.dumps(after, sort_keys=True, ensure_ascii=False).encode()
    events.append(
        {
            "starts_at": starts.astimezone(UTC).isoformat(),
            "id": hashlib.sha256(encoded).hexdigest(),
            "previous": before,
            "settings": after,
        }
    )
    identity_keys = (
        "import_energy_entity",
        "accounting_energy_entity",
        "hdo_entity",
        "hdo_schedule_entity",
        "hdo_valid_entity",
        "historical_cost_entity",
    )
    if (
        archive_revision
        and archive_identity
        and all(old.get(k) == new.get(k) for k in identity_keys)
    ):
        events[-1]["previous_archive_revision"] = archive_revision
        events[-1]["previous_archive_identity"] = copy.deepcopy(archive_identity)
    return {**new, "pricing_events": events}


def previous_archive_revision(options, start, end, identity=None):
    """Archiv před změnou je použitelný jen pro celou hodinu před aktivací.

    Přes hranici se cena počítá z měřené energie a časových revizí. Staré
    výsledky nikdy nepřebíráme pro jiný elektroměr nebo jiný zdroj HDO.
    """
    for event in sorted(
        options.get("pricing_events", []), key=lambda e: instant(e["starts_at"])
    ):
        edge = instant(event["starts_at"])
        if start < edge < end:
            return None
        if end <= edge:
            return (
                event.get("previous_archive_revision")
                if identity and identity == event.get("previous_archive_identity")
                else None
            )
    return None


def settings_at(options, defaults, when):
    """Vybere poslední účinnou revizi; budoucí konfiguraci nepoužije předčasně."""
    events = sorted(
        options.get("pricing_events", []), key=lambda e: instant(e["starts_at"])
    )
    values = events[0]["previous"] if events else snapshot(options, defaults)
    revision = "legacy"
    for event in events:
        if instant(event["starts_at"]) > when.astimezone(UTC):
            break
        values, revision = event["settings"], event["id"]
    return {**values, "pricing_revision": revision}


class BandPricing:
    """Společný výpočet živé ceny, předpovědi a historických cenových revizí.

    Funkce offday dostává datum a vrací víkend/svátek. Výchozí procentní
    rozvrhy dodává koordinátor; upravené rozvrhy jsou součástí každé revize.
    Žádná metoda neprovádí I/O ani neřídí spotřebiče.
    """

    def __init__(self, options, defaults, tz, offday, schedules):
        self.options, self.defaults, self.tz = options, defaults, tz
        self.offday, self.schedules = offday, schedules

    def settings(self, when):
        return settings_at(self.options, self.defaults, when)

    def edges(self, start, end):
        """Přesné okamžiky aktivace pro dělení i uvnitř jedné minuty."""
        return [
            instant(e["starts_at"])
            for e in self.options.get("pricing_events", [])
            if start < instant(e["starts_at"]) < end
        ]

    def quote(self, when, tariff, modifier, dynamic):
        """Vrátí obchodní pásmo a tři ceny Kč/kWh; neznámé HDO není VT.

        Baseline vždy používá standardní profil. Pevný produkt má vlastní
        distribuci a poplatky. Procentní údaj zůstává pouze v procentním
        režimu. Výstup obsahuje revizi pro audit a historické přepočty.
        """
        v = self.settings(when)
        if dynamic is None:
            dynamic = v["dynamic_pricing"]
        local = when.astimezone(self.tz)
        summer = 4 <= local.month <= 9
        fixed = v["tariff_mode"] == "fixed_bands"
        # Importovaný smluvní rozvrh vždy respektuje české svátky. Starší
        # volitelná výjimka zůstává pouze u původního procentního profilu.
        off = local.weekday() >= 5 or (
            (fixed or v["include_holidays"]) and self.offday(local.date())
        )
        key = f"{'summer' if summer else 'winter'}_{'offday' if off else 'workday'}_schedule"
        minute = local.hour * 60 + local.minute
        profile = v.get("fixed_profile") if fixed else None
        rates, trade, level, window, error = v, None, None, None, None
        if fixed:
            if profile is None:
                error = "fixed_profile_missing"
            elif local.date().isoformat() < max(
                profile["trade_effective"], profile["distribution_effective"]
            ):
                error = "price_list_not_effective"
            else:
                try:
                    levels = validate_bands(profile["schedules"])
                    window = next(
                        r
                        for r in profile["schedules"][key]
                        if r["start_minute"] <= minute < r["end_minute"]
                    )
                    trade = window["price_kwh"]
                    level = levels[trade]
                    rates = {**v, **profile["rates"]}
                except (KeyError, ValueError, StopIteration, TypeError):
                    error = "fixed_profile_invalid"
            modifier = None
        else:
            rows = self.schedules[key]
            if key in v:
                try:
                    parsed = []
                    parts = [
                        part.strip()
                        for part in re.split(r"[,;\n]+", v[key])
                        if part.strip()
                    ]
                    complete = ["=" in part for part in parts]
                    if any(complete) != all(complete) or (
                        not any(complete) and len(parts) != len(self.schedules[key])
                    ):
                        raise ValueError("invalid_schedule")
                    for i, part in enumerate(parts):
                        clock, _, value = part.strip().partition("=")
                        if not all(
                            component.isdigit()
                            for component in clock.strip().split(":")
                        ):
                            raise ValueError("invalid_schedule")
                        h, m = map(int, clock.split(":"))
                        if not 0 <= h < 24 or not 0 <= m < 60:
                            raise ValueError("invalid_schedule")
                        parsed.append(
                            (
                                h * 60 + m,
                                int(value)
                                if all(complete)
                                else self.schedules[key][i][1],
                            )
                        )
                    starts = [r[0] for r in parsed]
                    if not starts or starts[0] != 0 or starts != sorted(set(starts)):
                        raise ValueError("invalid_schedule")
                    rows = parsed
                except (ValueError, IndexError, TypeError):
                    # Stejně jako původní koordinátor zachováme jeho výchozí
                    # rozvrh, pokud byla starší uložená hodnota poškozená.
                    rows = self.schedules[key]
            start, modifier = next(r for r in reversed(rows) if r[0] <= minute)
            end = next((r[0] for r in rows if r[0] > minute), 1440)
            window = {"start_minute": start, "end_minute": end}
            if modifier <= v["super_cheap_threshold"]:
                level = "super_cheap"
            elif modifier <= v["cheap_threshold"]:
                level = "cheap"
            elif modifier < v["expensive_threshold"]:
                level = "normal"
            elif modifier < v["very_expensive_threshold"]:
                level = "expensive"
            else:
                level = "very_expensive"
            if tariff:
                trade = v[f"trade_{tariff.lower()}"] * (1 + modifier / 100)

        def total(values, business):
            if tariff is None or business is None:
                return None
            return business + sum(
                values[k]
                for k in (
                    f"distribution_{tariff.lower()}",
                    "electricity_tax",
                    "system_services",
                    "poze_kwh",
                    "other_kwh",
                )
            )

        baseline = total(v, v[f"trade_{tariff.lower()}"] if tariff else None)
        simulated = total(rates, trade)
        return {
            "price_kwh": simulated if dynamic else baseline,
            "without_dynamic_kwh": baseline,
            "with_dynamic_kwh": simulated,
            "trade_price": trade,
            "price_level": level,
            "modifier_percent": modifier,
            "tariff_mode": v["tariff_mode"],
            "pricing_revision": v["pricing_revision"],
            "fixed_profile_id": profile["id"] if profile else None,
            "product": PRODUCT_NAMES.get(profile["product"], profile["product"])
            if profile
            else PRODUCT_NAMES["standard_percentage"],
            "window": window,
            "strategy_status": error or "ok",
        }

    def monthly(self, when, dynamic):
        """Stálé platby odpovídají smluvní variantě; procenta je nikdy nesnižují."""
        v = self.settings(when)
        if dynamic is None:
            dynamic = v["dynamic_pricing"]
        if dynamic and v["tariff_mode"] == "fixed_bands":
            p = v.get("fixed_profile")
            if p is None or when.astimezone(self.tz).date().isoformat() < max(
                p["trade_effective"], p["distribution_effective"]
            ):
                return None
            v = {**v, **p["rates"]}
        return sum(
            v[k]
            for k in (
                "supplier_monthly",
                "breaker_monthly",
                "infrastructure_monthly",
                "other_monthly",
            )
        )

    def daily_fee(self, start, end, dynamic):
        """Poměr denní platby podle skutečných sekund včetně 23/25hodinového dne."""
        edges = sorted({start, end, *self.edges(start, end)})
        total = 0.0
        for left, right in pairwise(edges):
            monthly = self.monthly(left, dynamic)
            if monthly is None:
                return None
            local = left.astimezone(self.tz)
            total += (
                monthly
                / monthrange(local.year, local.month)[1]
                * (right - left).total_seconds()
                / (end - start).total_seconds()
            )
        return total
