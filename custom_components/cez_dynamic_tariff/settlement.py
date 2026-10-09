"""Settlement helpers using existing recorder increments, never meter totals."""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from math import isfinite

SETTLEMENT_DEFAULTS = {
    "accounting_enabled": False,
    "billing_start": "",
    "billing_end": "",
    "dynamic_start": "",
    "dynamic_contract_mode": "unknown",
    "current_price_start": "",
    "advance_mode": "annual",
    "advance_total": 0.0,
    "advance_paid": 0.0,
    "monthly_advances": "[]",
    "automatic_advances": False,
    "automatic_advances_from": "",
    "accounting_energy_entity": "",
    "deduct_shared_income": False,
    "shared_income_entity": "",
    "historical_cost_entity": "",
    "reference_date": "",
    "reference_period_start": "",
    "reference_energy": 0.0,
    "reference_cost": 0.0,
    "historical_profiles": "[]",
    "settled_bills": "[]",
}


def default_period(today: date) -> tuple[str, str]:
    year = today.year if today.month >= 4 else today.year - 1
    return f"{year}-04-01", f"{year + 1}-03-31"


def month_starts(start: date, end: date):
    cursor = start.replace(day=1)
    while cursor <= end:
        yield cursor
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)


def standing_fees(start: date, end: date, monthly_at) -> float:
    """Full calendar days, inclusive end; actual number of days in each month."""
    total = 0.0
    while start <= end:
        total += monthly_at(start) / monthrange(start.year, start.month)[1]
        start += timedelta(days=1)
    return total


def parse_advances(text: str, start: date, end: date) -> list[dict]:
    rows = json.loads(text)
    if not isinstance(rows, list) or len(rows) > 24:
        raise ValueError("invalid advances")
    seen = set()
    for row in rows:
        month = date.fromisoformat(row["month"] + "-01")
        amount = float(row["amount"])
        paid_amount = advance_paid_amount(row)
        if (
            not start.replace(day=1) <= month <= end
            or row["month"] in seen
            or not isfinite(amount)
            or amount < 0
            or not isinstance(row.get("paid"), bool)
            or not isfinite(paid_amount)
            or not 0 <= paid_amount <= amount
            or ("paid_amount" in row and row["paid"] != (paid_amount == amount))
        ):
            raise ValueError("invalid advances")
        seen.add(row["month"])
    return rows


def advances(values, start: date, end: date):
    if values["advance_mode"] == "annual":
        return float(values["advance_total"]), float(values["advance_paid"]), []
    rows = parse_advances(values["monthly_advances"], start, end)
    missing = [
        d.strftime("%Y-%m")
        for d in month_starts(start, end)
        if d.strftime("%Y-%m") not in {r["month"] for r in rows}
    ]
    return (
        sum(float(r["amount"]) for r in rows),
        sum(advance_paid_amount(r) for r in rows),
        missing,
    )


def advance_paid_amount(row):
    """Preserve legacy confirmed payments; support a partial payment once."""
    return float(row.get("paid_amount", row["amount"] if row.get("paid") else 0))


def automatic_from(today: date) -> str:
    """Opting in mid-month never confirms an earlier instalment retroactively."""
    first = today.replace(day=1)
    if today.day != 1:
        first = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first.strftime("%Y-%m")


def confirm_due_advances(rows, today: date, enabled: bool, enabled_from: str):
    """Catch up only scheduled months since opt-in, without overriding manual edits."""
    changed = False
    if not enabled or not enabled_from:
        return rows, changed
    current = today.strftime("%Y-%m")
    result = [dict(r) for r in rows]
    for row in result:
        if (
            enabled_from <= row["month"] <= current
            and not row.get("auto_skip")
            and not row.get("paid")
            and advance_paid_amount(row) == 0
            and row["amount"] > 0
        ):
            row.update(
                paid=True,
                paid_amount=float(row["amount"]),
                paid_source="automatic",
                confirmed_on=today.isoformat(),
                scheduled_on=row["month"] + "-01",
            )
            changed = True
    return result, changed


def consumption_profile(rows, now: datetime, tz):
    """Monthly seasonal daily means from complete historic days only.

    Recorder has already computed corrected increments and resets. Missing
    hours/days are excluded, not inserted as zero. The current partial day is
    not used to learn a consumption profile.
    """
    days = {}
    for row in rows:
        when = datetime.fromtimestamp(row["start"], tz)
        delta = row.get("change")
        if delta is None or not isfinite(delta) or delta < 0:
            continue
        bucket = days.setdefault(when.date(), {"energy": 0.0, "hours": set()})
        bucket["energy"] += delta
        bucket["hours"].add(row["start"])
    samples = {m: [] for m in range(1, 13)}
    for day, bucket in days.items():
        following = day + timedelta(days=1)
        left = datetime.combine(day, datetime.min.time(), tzinfo=tz)
        right = datetime.combine(following, datetime.min.time(), tzinfo=tz)
        hours = (right.timestamp() - left.timestamp()) / 3600
        if day < now.astimezone(tz).date() and len(bucket["hours"]) == hours:
            samples[day.month].append(bucket["energy"])
    return [
        {"month": m, "sample_days": len(v), "daily_kwh": sum(v) / len(v) if v else None}
        for m, v in samples.items()
    ]


def remaining_import(profile, start: date, end: date):
    """Do not invent winter consumption from a summer-only history."""
    means = {r["month"]: r["daily_kwh"] for r in profile}
    total = 0.0
    missing = set()
    while start <= end:
        mean = means.get(start.month)
        if mean is None:
            missing.add(start.month)
        else:
            total += mean
        start += timedelta(days=1)
    return (None if missing else total), sorted(missing)
