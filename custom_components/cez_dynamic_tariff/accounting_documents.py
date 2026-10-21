"""Správa podkladů a náhradní ocenění; čisté funkce bez zápisu do HA.

Částky jsou vždy v Kč s DPH, energie v kWh. Původní neznámá pole
záznamů zachováváme při editaci, aby administrace neztratila starší metadata.
"""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import UTC, date, timedelta
from math import isclose

from .pricing import PROFILE_DEFAULTS, finite_number

RATE_KEYS = tuple(
    k
    for k, v in PROFILE_DEFAULTS.items()
    if isinstance(v, float) and k != "annual_import_kwh"
)


def records(value):
    """Načti stávající seznam; poškozená data nevracej jako prázdný seznam."""
    rows = json.loads(value)
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError("invalid_documents")
    return rows


def bill_key(row):
    """Stabilní odkaz na fakturu i pro starší záznamy bez interního ID."""
    return row["start"] + "/" + row["end"]


def number(value):
    """Přijmi jen konečné nezáporné číslo, nikoli bool, NaN ani neznámý stav."""
    result = finite_number(value)
    if isinstance(value, bool) or result is None or result < 0:
        raise ValueError("invalid_document_number")
    return result


def period(row):
    """Obě hranice jsou místní kalendářní dny včetně; nejvýše dva roky."""
    start, end = (date.fromisoformat(row[k]) for k in ("start", "end"))
    if start > end or (end - start).days > 731:
        raise ValueError("invalid_document_period")
    return start, end


def validate_document(row, others, kind, today, current_start=""):
    """Ověř formulář před jediným atomickým uložením options.

    Faktury jsou uzavřené a nesmějí se překrývat. Historické ceníky nesmějí
    překrýt ani aktivní ceník, jehož konec není znám. Mezery jsou dovolené,
    ale výpočet pro ně vrací neznámou cenu. Chyba ponechá options beze změny.
    """
    start, end = period(row)
    if not str(row.get("source", "")).strip():
        raise ValueError("invalid_documents")
    if end >= today and kind == "bill":
        raise ValueError("bill_not_closed")
    for other in others:
        left, right = period(other)
        if start <= right and left <= end:
            raise ValueError("document_overlap")
    if kind == "profile":
        if current_start and end >= date.fromisoformat(current_start):
            raise ValueError("current_price_overlap")
        if any(k not in row["rates"] for k in RATE_KEYS):
            raise ValueError("incomplete_document_rates")
        row["rates"] = {
            **row["rates"],
            **{k: number(row["rates"][k]) for k in RATE_KEYS},
        }
        return row
    for key in ("energy_kwh", "cost", "nt_kwh", "vt_kwh"):
        row[key] = number(row[key])
    if not isclose(
        row["energy_kwh"], row["nt_kwh"] + row["vt_kwh"], rel_tol=1e-6, abs_tol=0.01
    ):
        raise ValueError("bill_energy_mismatch")
    for key in ("paid", "fixed_cost"):
        if key in row:
            row[key] = number(row[key])
    if row.get("fixed_cost", 0) > row["cost"]:
        raise ValueError("invalid_document_number")
    months = row.get("months", [])
    seen = set()
    for item in months:
        first = date.fromisoformat(item["month"] + "-01")
        last = first.replace(day=monthrange(first.year, first.month)[1])
        # Měsíční profil smí reprezentovat pouze celé kalendářní měsíce.
        if first < start or last > end or first in seen:
            raise ValueError("invalid_bill_months")
        seen.add(first)
        for key in ("nt_kwh", "vt_kwh"):
            item[key] = number(item[key])
    for key in ("nt_kwh", "vt_kwh"):
        total = sum(m[key] for m in months)
        if total > row[key] + 0.01:
            raise ValueError("bill_months_mismatch")
        expected = []
        cursor = start.replace(day=1)
        while cursor <= end:
            expected.append(cursor)
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        if (
            months
            and len(months) == len(expected)
            and not isclose(total, row[key], rel_tol=1e-6, abs_tol=0.01)
        ):
            raise ValueError("bill_months_mismatch")
    return row


def selected_ratio(bills, selected, before):
    """Jen výslovně zvolená starší faktura; nulový odběr nemá poměr VT/NT."""
    bill = next(
        (
            b
            for b in bills
            if bill_key(b) == selected and date.fromisoformat(b["end"]) < before
        ),
        None,
    )
    if bill is None:
        return None, None
    nt, vt = bill.get("nt_kwh"), bill.get("vt_kwh")
    if nt is None or vt is None:
        nt = sum(m["nt_kwh"] for m in bill.get("months", []))
        vt = sum(m["vt_kwh"] for m in bill.get("months", []))
    nt, vt = number(nt), number(vt)
    if not isclose(nt + vt, number(bill.get("energy_kwh")), rel_tol=1e-6, abs_tol=0.01):
        return None, bill
    return (nt / (nt + vt), bill) if nt + vt > 0 else (None, bill)


def estimate_gaps(gaps, ratio, profile_at, modifier_at, dynamic):
    """Oceň jen neoceněné kWh; výstup nesmí vstoupit do ověřeného archivu.

    Čas mezery je aware datetime, energie je neoceněný zbytek intervalu.
    Poměr NT/VT z faktury aproximuje neznámé HDO. Minutový průměr obchodní
    přirážky zachová místní pásma i změnu času. I částečně známá hodina
    dostane náhradní cenu pouze pro zbylé kWh. Chybějící ceník výsledek zablokuje.
    """
    if ratio is None:
        return None
    total = 0.0
    for gap in gaps:
        local_left = gap["start"]
        tz = local_left.tzinfo
        left, right = local_left.astimezone(UTC), gap["end"].astimezone(UTC)
        profile = profile_at(local_left.date())
        if profile is None or right <= left:
            return None
        cost, seconds = 0.0, (right - left).total_seconds()
        cursor = left
        while cursor < right:
            finish = min(cursor + timedelta(minutes=1), right)
            local = cursor.astimezone(tz)
            modifier = modifier_at(local) if dynamic(local.date()) else 0
            price = ratio * profile.price("NT", modifier, True) + (
                1 - ratio
            ) * profile.price("VT", modifier, True)
            cost += price * (finish - cursor).total_seconds() / seconds
            cursor = finish
        total += number(gap["kwh"]) * cost
    return total
