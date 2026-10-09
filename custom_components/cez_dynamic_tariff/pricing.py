"""VAT-inclusive electricity prices and strict HDO schedule adaptation.

No network access and no dependency on another integration's private objects.
The bundled profile is a transcription of the user's 30 January 2026 price list.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from math import isfinite
from typing import Any

PROFILE_REVISION = "cez-2-years-promo-2026-01-30-d57d"
PROFILE_DEFAULTS = {
    "pricing_enabled": False,
    "dynamic_pricing": False,
    "include_standing_fees": True,
    "distribution_rate": "D57d",
    "breaker_amperes": 25,
    "breaker_phases": 3,
    "trade_vt": 3.18,
    "trade_nt": 3.05,
    "distribution_vt": 0.91327,
    "distribution_nt": 0.14097,
    "electricity_tax": 0.03424,
    "system_services": 0.19873,
    # min(capacity charge, consumption charge) is ZERO in this price list.
    "poze_kwh": 0.0,
    "supplier_monthly": 163.35,
    "breaker_monthly": 671.55,
    "infrastructure_monthly": 15.57,
    "other_kwh": 0.0,
    "other_monthly": 0.0,
    "annual_import_kwh": 0.0,
    "hdo_entity": "",
    "hdo_schedule_entity": "",
    "hdo_valid_entity": "",
    "import_energy_entity": "",
}


def finite_number(value: Any) -> float | None:
    """Reject unavailable states, infinities and NaNs."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


@dataclass(frozen=True)
class PriceProfile:
    """All amounts already include VAT; never apply VAT a second time."""

    values: dict[str, Any]

    def price(self, tariff: str, modifier: int, dynamic: bool) -> float:
        """Only the trading component receives the dynamic modifier."""
        suffix = tariff.lower()
        v = self.values
        return (
            v[f"trade_{suffix}"] * (1 + modifier / 100 if dynamic else 1)
            + v[f"distribution_{suffix}"]
            + v["electricity_tax"]
            + v["system_services"]
            + v["poze_kwh"]
            + v["other_kwh"]
        )

    @property
    def monthly(self) -> float:
        """Standing fees cannot be reduced by shifting consumption."""
        return sum(
            self.values[k]
            for k in (
                "supplier_monthly",
                "breaker_monthly",
                "infrastructure_monthly",
                "other_monthly",
            )
        )

    @property
    def allocation(self) -> float | None:
        """An explicitly estimated fixed-cost allocation per imported kWh."""
        annual = self.values["annual_import_kwh"]
        return self.monthly * 12 / annual if annual > 0 else None


@dataclass(frozen=True)
class HdoInterval:
    start: datetime
    end: datetime
    tariff: str


def parse_hdo_schedule(rows: Any, tz, valid_until: datetime) -> list[HdoInterval]:
    """Adapt cez_hdo schedule attributes, clipped to its six-day validity.

    Upstream uses 23:59:59 for an interval ending at midnight. Normalize that
    sentinel only. Reject overlaps and bad data instead of treating gaps as VT.
    """
    if not isinstance(rows, list):
        return []
    result = []
    try:
        for row in rows:
            start = datetime.fromisoformat(row["start"])
            end = datetime.fromisoformat(row["end"])
            if start.tzinfo is None:
                start = start.replace(tzinfo=tz)
            if end.tzinfo is None:
                end = end.replace(tzinfo=tz)
            if (end.hour, end.minute, end.second) == (23, 59, 59):
                end += timedelta(seconds=1)
            start, end = (
                start.astimezone(UTC),
                min(end.astimezone(UTC), valid_until.astimezone(UTC)),
            )
            tariff = row["tariff"]
            if tariff not in ("VT", "NT"):
                return []
            if start >= valid_until.astimezone(UTC):
                continue
            if end <= start:
                return []
            result.append(HdoInterval(start, end, tariff))
        result.sort(key=lambda r: r.start)
        if any(a.end > b.start for a, b in pairwise(result)):
            return []
    except (KeyError, ValueError, TypeError):
        return []
    return result


def tariff_at(intervals: list[HdoInterval], when: datetime) -> str | None:
    """A missing interval is unknown, not an assumed high tariff."""
    utc = when.astimezone(UTC)
    return next((r.tariff for r in intervals if r.start <= utc < r.end), None)


def price_timeline(
    start: datetime, end: datetime, intervals, profile, modifier_at, dynamic
):
    """Combine HDO and local-clock bands using real elapsed UTC minutes.

    This preserves both occurrences of the repeated hour and skips nonexistent
    local times. HDO edges can occur between minutes.
    """
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    edges = {start, end}
    cursor = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
    while cursor < end:
        edges.add(cursor)
        cursor += timedelta(minutes=1)
    for row in intervals:
        edges.update(e for e in (row.start, row.end) if start < e < end)
    ordered = sorted(edges)
    result = []
    for left, right in pairwise(ordered):
        tariff = tariff_at(intervals, left)
        modifier = modifier_at(left)
        price = profile.price(tariff, modifier, dynamic) if tariff else None
        baseline = profile.price(tariff, modifier, False) if tariff else None
        simulated = profile.price(tariff, modifier, True) if tariff else None
        values = (tariff, modifier, price, baseline, simulated)
        if result and result[-1]["_values"] == values:
            result[-1]["end"] = right
        else:
            result.append(
                {
                    "start": left,
                    "end": right,
                    "tariff": tariff,
                    "modifier_percent": modifier,
                    "price_kwh": price,
                    "without_dynamic_kwh": baseline,
                    "with_dynamic_kwh": simulated,
                    "_values": values,
                }
            )
    for row in result:
        row.pop("_values")
    return result
