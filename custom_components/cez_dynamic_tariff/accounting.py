"""Consumption-based estimates with explicit data gaps and signed savings."""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime, timedelta

TOTAL_KEYS = (
    "energy_kwh",
    "unpriced_kwh",
    "actual_cost",
    "without_cost",
    "dynamic_cost",
    "potential_savings",
    "fixed_cost",
)


class CostLedger:
    """Integrate meter deltas; never charge a lifetime reading on startup."""

    def __init__(self, saved=None):
        self.totals = {key: float((saved or {}).get(key, 0)) for key in TOTAL_KEYS}
        self.days = dict((saved or {}).get("days", {}))
        self.previous = None

    def as_dict(self):
        """Persist totals and recent calendar days, without a live meter baseline."""
        return {**self.totals, "days": self.days}

    def _add(self, day, key, value):
        self.totals[key] += value
        bucket = self.days.setdefault(day, {key: 0.0 for key in TOTAL_KEYS})
        bucket[key] += value
        for old in sorted(self.days)[:-7]:
            self.days.pop(old)

    @staticmethod
    def _day_parts(start, end, tz):
        """Split real elapsed time at local midnight, including DST days."""
        cursor = start
        while cursor < end:
            local = cursor.astimezone(tz)
            following = datetime.combine(
                local.date() + timedelta(days=1), datetime.min.time(), tzinfo=tz
            ).astimezone(UTC)
            stop = min(end, following)
            yield local.date().isoformat(), cursor, stop
            cursor = stop

    def sample(self, when, energy, timeline, minimum=None, tz=UTC, known_costs=None):
        """Use uniform consumption within a meter interval, capped at 15 minutes.

        Price data is captured at the previous reading, so later HDO changes
        cannot reprice consumed electricity. Resets and unavailable samples
        start a new baseline. Negative savings are intentionally retained.
        """
        when = when.astimezone(UTC)
        previous = self.previous
        self.previous = (
            (when, energy, timeline, minimum) if energy is not None else None
        )
        if previous is None or energy is None:
            return
        start, before, rows, best = previous
        seconds = (when - start).total_seconds()
        delta = energy - before
        if seconds <= 0 or delta < 0:
            return
        if seconds > 900:
            self._add(when.astimezone(tz).date().isoformat(), "unpriced_kwh", delta)
            return
        if known_costs is not None:
            # Historical accounting can reuse monetary increments which this
            # integration has already calculated. Do not price them again.
            for day, left, right in self._day_parts(start, when, tz):
                fraction = (right - left).total_seconds() / seconds
                self._add(day, "energy_kwh", delta * fraction)
                for key, amount in known_costs.items():
                    self._add(day, key, amount * fraction)
            return
        covered = 0.0
        for row in rows:
            overlap = (min(when, row["end"]) - max(start, row["start"])).total_seconds()
            if overlap <= 0 or row["price_kwh"] is None:
                continue
            for day, left, right in self._day_parts(
                max(start, row["start"]), min(when, row["end"]), tz
            ):
                fraction = (right - left).total_seconds() / seconds
                kwh = delta * fraction
                covered += fraction
                self._add(day, "energy_kwh", kwh)
                for target, source in (
                    ("actual_cost", "price_kwh"),
                    ("without_cost", "without_dynamic_kwh"),
                    ("dynamic_cost", "with_dynamic_kwh"),
                ):
                    self._add(day, target, kwh * row[source])
                if best is not None:
                    self._add(
                        day, "potential_savings", kwh * max(0, row["price_kwh"] - best)
                    )
        self._add(
            when.astimezone(tz).date().isoformat(),
            "unpriced_kwh",
            delta * max(0, 1 - covered),
        )

    def accrue_fixed(self, start: datetime, end: datetime, monthly: float, tz):
        """Accrue only the monitored time using actual local calendar months."""
        for day, left, right in self._day_parts(
            start.astimezone(UTC), end.astimezone(UTC), tz
        ):
            local = left.astimezone(tz)
            midnight = datetime.combine(
                local.date(), datetime.min.time(), tzinfo=tz
            ).astimezone(UTC)
            following = datetime.combine(
                local.date() + timedelta(days=1), datetime.min.time(), tzinfo=tz
            ).astimezone(UTC)
            amount = monthly / monthrange(local.year, local.month)[1]
            self._add(
                day,
                "fixed_cost",
                amount
                * (right - left).total_seconds()
                / (following - midnight).total_seconds(),
            )
