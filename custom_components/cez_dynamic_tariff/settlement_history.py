"""Read existing HA/EDC statistics and fill only missing electricity costs."""

from __future__ import annotations

import json
import logging
from bisect import bisect_right
from calendar import monthrange
from datetime import UTC, date, datetime, time, timedelta
from functools import partial

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.statistics import (
    get_metadata,
    statistics_during_period,
)

from .accounting import CostLedger
from .const import DOMAIN
from .pricing import PriceProfile, finite_number, parse_hdo_schedule, price_timeline
from .settlement import (
    SETTLEMENT_DEFAULTS,
    advance_paid_amount,
    advances,
    consumption_profile,
    default_period,
    parse_advances,
    remaining_import,
    standing_fees,
)

_LOGGER = logging.getLogger(__name__)


class SettlementHistory:
    """No statistics imports, no new energy meters, no writes to other integrations."""

    def __init__(self, billing):
        self.billing = billing
        self.coordinator = billing.coordinator
        self.hass = billing.hass
        self.values = {
            k: self.coordinator._option(k, v) for k, v in SETTLEMENT_DEFAULTS.items()
        }
        self.result = {}
        self.last_read = None
        self.raw = None

    @property
    def trial(self):
        return self.values["dynamic_contract_mode"] == "trial"

    @property
    def meter_id(self):
        return (
            self.values["accounting_energy_entity"]
            or self.billing.values["import_energy_entity"]
        )

    @property
    def contract_known(self):
        return (
            not self.billing.values["dynamic_pricing"]
            or self.values["dynamic_contract_mode"] != "unknown"
        )

    def _revenue_id(self):
        entity = self.values["shared_income_entity"]
        state = self.hass.states.get(entity) if entity else None
        # EDC exposes its existing financial Energy statistic. Prefer it over
        # multiplying shared kWh or summing receiver entities a second time.
        return (
            (
                state.attributes.get("energy_revenue_statistic_id")
                or state.attributes.get("hourly_statistic_id")
                or entity
            )
            if state
            else entity
        )

    def _read(self, now, start, revenue_id):
        meter = self.meter_id
        cost = self.values["historical_cost_entity"] or f"sensor.{DOMAIN}_actual_cost"
        ids = {meter, cost}
        unpriced_id = f"sensor.{DOMAIN}_unpriced_energy"
        savings_id = f"sensor.{DOMAIN}_realized_savings"
        if not self.values["historical_cost_entity"]:
            ids.add(unpriced_id)
            ids.add(savings_id)
        if revenue_id:
            ids.add(revenue_id)
        metadata = get_metadata(self.hass, statistic_ids=ids)
        valid_ids = {k for k, (_, meta) in metadata.items() if meta.get("has_sum")}
        # Never consume a monetary statistic as energy, or multiply an already
        # monetary EDC statistic by the selling price.
        units = {k: meta[1].get("unit_of_measurement") for k, meta in metadata.items()}
        reuse_default = meter == self.billing.values["import_energy_entity"]
        if not reuse_default and not self.values["historical_cost_entity"]:
            valid_ids.difference_update({cost, savings_id, unpriced_id})
        if units.get(meter) not in ("Wh", "kWh", "MWh"):
            valid_ids.discard(meter)
        for monetary in (cost, revenue_id, savings_id):
            if units.get(monetary) != "CZK":
                valid_ids.discard(monetary)
        horizon = min(start, now - timedelta(days=730))
        closed_hour = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        hourly = (
            statistics_during_period(
                self.hass,
                horizon,
                closed_hour,
                valid_ids,
                "hour",
                {"energy": "kWh"},
                {"change"},
            )
            if valid_ids
            else {}
        )
        # State history is used only for today's uncompiled tail and public HDO
        # schedules. Long-term energy deltas are already calculated by Recorder.
        midnight = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        short_today = (
            statistics_during_period(
                self.hass,
                midnight,
                closed_hour + timedelta(hours=1),
                valid_ids,
                "5minute",
                {"energy": "kWh"},
                {"change", "state"},
            )
            if valid_ids
            else {}
        )
        entities = [meter]
        if reuse_default or self.values["historical_cost_entity"]:
            entities.append(cost)
        if reuse_default and not self.values["historical_cost_entity"]:
            entities.append(savings_id)
        history = get_significant_states(
            self.hass,
            midnight - timedelta(minutes=15),
            now,
            entity_ids=[e for e in entities if e],
            significant_changes_only=False,
            minimal_response=False,
        )
        schedule_id = self.billing.values["hdo_schedule_entity"]
        if schedule_id:
            history.update(
                get_significant_states(
                    self.hass,
                    max(start, now - timedelta(days=14)),
                    now,
                    entity_ids=[schedule_id],
                    significant_changes_only=False,
                    minimal_response=False,
                )
            )
        return {
            "hourly": hourly,
            "history": history,
            "cost_id": cost,
            "revenue_id": revenue_id,
            "closed_hour": closed_hour,
            "midnight": midnight,
            "units": units,
            "unpriced_id": unpriced_id,
            "savings_id": savings_id,
            "short_today": short_today,
        }

    async def async_refresh(self, now):
        """Use Recorder's own executor, with a five-minute cache."""
        if not self.values["accounting_enabled"]:
            return
        tz = self.coordinator._local_tz()
        now = now.astimezone(tz)
        start_text, end_text = default_period(now.date())
        start = date.fromisoformat(self.values["billing_start"] or start_text)
        end = date.fromisoformat(self.values["billing_end"] or end_text)
        refresh = (
            self.last_read is None
            or self.last_read.date() != now.date()
            or (now - self.last_read).total_seconds() >= 300
        )
        if refresh:
            try:
                self.raw = await get_instance(self.hass).async_add_executor_job(
                    partial(
                        self._read,
                        now,
                        datetime.combine(start, time.min, tzinfo=tz),
                        self._revenue_id(),
                    )
                )
                self.last_read = now
                self.result = self._calculate(now, start, end)
            except Exception:  # Recorder may be disabled or still starting.
                _LOGGER.exception("Cannot read electricity accounting statistics")
                self.last_read = now
                self.result = {"accounting_status": "history_unavailable"}
                return

    def _intervals(self, now):
        schedule_id = self.billing.values["hdo_schedule_entity"]
        states = list(self.raw["history"].get(schedule_id, []))
        live = self.hass.states.get(schedule_id)
        if live:
            states.append(live)
        schedules = []
        for state in states:
            try:
                updated = datetime.fromisoformat(state.attributes["last_update"])
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=now.tzinfo)
                rows = parse_hdo_schedule(
                    state.attributes.get("schedule"),
                    now.tzinfo,
                    updated + timedelta(days=6),
                )
                schedules.append((updated, rows))
            except (KeyError, ValueError, TypeError):
                continue
        # Each day gets the newest public schedule which actually covers it.
        return sorted(schedules, key=lambda item: item[0], reverse=True)

    def _profile_at(self, day):
        current = self.values["current_price_start"] or self.coordinator._option(
            "price_list_trade_effective", ""
        )
        if current and day >= date.fromisoformat(current):
            return self.billing.profile
        for row in sorted(
            json.loads(self.values["historical_profiles"]),
            key=lambda r: r["start"],
            reverse=True,
        ):
            if (
                date.fromisoformat(row["start"])
                <= day
                <= date.fromisoformat(row["end"])
            ):
                return PriceProfile({**self.billing.values, **row["rates"]})
        return None

    def _timeline(self, day, schedules, now):
        left = datetime.combine(day, time.min, tzinfo=now.tzinfo)
        right = left + timedelta(days=1)
        profile = self._profile_at(day)
        intervals = next(
            (
                rows
                for _, rows in schedules
                if any(r.start <= left.astimezone(UTC) < r.end for r in rows)
            ),
            [],
        )
        dynamic_start = self.values["dynamic_start"]
        mode_known = (
            not self.billing.values["dynamic_pricing"]
            or bool(dynamic_start)
            or day == now.date()
        )
        dynamic = (
            self.billing.values["dynamic_pricing"]
            and (not dynamic_start or day >= date.fromisoformat(dynamic_start))
            and not self.trial
        )
        if profile is None or not mode_known:
            return []
        if not self.contract_known and dynamic:
            return []
        if day == now.date() and self.billing.status != "ok":
            return []
        return price_timeline(
            left,
            right,
            intervals,
            profile,
            lambda when: (
                self.coordinator._current_window(
                    when.astimezone(now.tzinfo)
                ).modifier_percent
            ),
            dynamic,
        )

    def _known_costs(self, left, right, costs, times, savings, saving_times):
        """Look up already calculated monetary increments before pricing anything."""
        if not self.contract_known and not self.values["historical_cost_entity"]:
            return None

        def pair(states, stamps):
            i = bisect_right(stamps, left + timedelta(seconds=2)) - 1
            j = bisect_right(stamps, right + timedelta(seconds=2)) - 1
            if i < 0 or j < 0 or i == j:
                return None
            a, b = states[i], states[j]
            if (
                abs((a.last_updated - left).total_seconds()) > 2
                or abs((b.last_updated - right).total_seconds()) > 2
            ):
                return None
            before, after = finite_number(a.state), finite_number(b.state)
            return after - before if before is not None and after is not None else None

        actual = pair(costs, times)
        if actual is None or actual < 0:
            return None
        saved = (
            pair(savings, saving_times)
            if not self.values["historical_cost_entity"]
            else None
        )
        baseline = actual + saved if saved is not None else None
        if self.trial and not self.values["historical_cost_entity"]:
            if baseline is None or baseline < 0:
                return None
            actual = baseline
        result = {"actual_cost": actual}
        if baseline is not None and baseline >= 0:
            result["without_cost"] = baseline
        return result

    def _today(self, now, schedules):
        """Reuse monetary readings where present; reconstruct earlier intervals.

        Replaying source samples into the same CostLedger preserves the existing
        15-minute gap, reset, DST and uniform-interval rules. Only missing costs
        are valued; this ledger is ephemeral and never added to live totals.
        """
        if self.raw.get("short_today", {}).get(self.meter_id):
            return self._today_statistics(now, schedules)
        midnight = self.raw["midnight"]
        meter_id = self.meter_id
        meter_states = list(self.raw["history"].get(meter_id, []))
        live = self.hass.states.get(meter_id)
        if live:
            meter_states.append(live)
        meter_states = sorted(
            {s.last_updated: s for s in meter_states}.values(),
            key=lambda s: s.last_updated,
        )
        before = [s for s in meter_states if s.last_updated <= midnight]
        selected = (before[-1:] if before else []) + [
            s for s in meter_states if s.last_updated > midnight
        ]
        costs = sorted(
            self.raw["history"].get(self.raw["cost_id"], []),
            key=lambda s: s.last_updated,
        )
        cost_times = [s.last_updated for s in costs]
        savings = sorted(
            self.raw["history"].get(self.raw.get("savings_id", ""), []),
            key=lambda s: s.last_updated,
        )
        saving_times = [s.last_updated for s in savings]
        ledger = CostLedger()
        timeline = self._timeline(now.date(), schedules, now)
        covered = bool(selected) and selected[0].last_updated <= midnight
        boundary_value = None
        if len(selected) > 1 and selected[0].last_updated < midnight:
            left, right = selected[:2]
            a, b = self.billing._meter_value(left), self.billing._meter_value(right)
            seconds = (right.last_updated - left.last_updated).total_seconds()
            if a is not None and b is not None and b >= a and 0 < seconds <= 900:
                boundary_value = (
                    a
                    + (b - a) * (midnight - left.last_updated).total_seconds() / seconds
                )
            else:
                covered = False
        previous_state = None
        reused = 0
        baseline_known = True
        for state in selected:
            when = (
                max(state.last_updated, midnight)
                if previous_state is None
                else state.last_updated
            )
            value = self.billing._meter_value(state)
            if previous_state is None and boundary_value is not None:
                value = boundary_value
            if value is None:
                covered = False
            known_costs = None
            if previous_state is not None:
                left = previous_state.last_updated
                previous_value = self.billing._meter_value(previous_state)
                if (state.last_updated - left).total_seconds() > 900 or (
                    value is not None
                    and previous_value is not None
                    and value < previous_value
                ):
                    covered = False
                if left >= midnight:
                    known_costs = self._known_costs(
                        left,
                        state.last_updated,
                        costs,
                        cost_times,
                        savings,
                        saving_times,
                    )
                    if (
                        value == previous_value
                        and known_costs
                        and known_costs["actual_cost"] != 0
                    ):
                        known_costs = None
                if known_costs is not None:
                    reused += 1
                    baseline_known = baseline_known and "without_cost" in known_costs
            ledger.sample(when, value, timeline, tz=now.tzinfo, known_costs=known_costs)
            previous_state = state
        if not selected or (now - selected[-1].last_updated).total_seconds() > 900:
            covered = False
        totals = ledger.totals
        totals["baseline_known"] = baseline_known
        totals["energy_complete"] = covered
        totals["through"] = selected[-1].last_updated.isoformat() if selected else None
        complete = covered and totals["unpriced_kwh"] < 1e-6
        return totals, complete, reused

    def _today_statistics(self, now, schedules):
        """Reuse existing five-minute increments, including valid zero import."""
        stats = self.raw["short_today"]
        rows = sorted(stats[self.meter_id], key=lambda r: r["start"])
        costs = {
            r["start"]: r.get("change") for r in stats.get(self.raw["cost_id"], [])
        }
        savings = {
            r["start"]: r.get("change") for r in stats.get(self.raw["savings_id"], [])
        }
        unpriced = {
            r["start"]: r.get("change") for r in stats.get(self.raw["unpriced_id"], [])
        }
        if costs and not self.values["historical_cost_entity"]:
            costs.pop(min(costs))
        if not self.contract_known and not self.values["historical_cost_entity"]:
            costs.clear()
        midnight = self.raw["midnight"].astimezone(UTC)
        ledger = CostLedger()
        energy = 0.0
        timeline = self._timeline(now.date(), schedules, now)
        ledger.sample(midnight, energy, timeline, tz=now.tzinfo)
        cursor, complete, reused, baseline_known = midnight, True, 0, True
        for row in rows:
            left = datetime.fromtimestamp(row["start"], UTC)
            right = datetime.fromtimestamp(row.get("end", row["start"] + 300), UTC)
            if right > now or left < midnight:
                continue
            amount = row.get("change")
            if (
                left != cursor
                or amount is None
                or amount < 0
                or ("state" in row and row["state"] is None)
            ):
                complete = False
                continue
            known = None
            cost = costs.get(row["start"])
            if (
                cost is not None
                and cost >= 0
                and (
                    self.values["historical_cost_entity"]
                    or unpriced.get(row["start"]) == 0
                )
            ):
                saved = savings.get(row["start"])
                baseline = cost + saved if saved is not None else None
                if self.trial and not self.values["historical_cost_entity"]:
                    cost = baseline
                if cost is not None and cost >= 0:
                    known = {"actual_cost": cost}
                    if baseline is not None:
                        known["without_cost"] = baseline
                    baseline_known = baseline_known and baseline is not None
                    reused += 1
            energy += amount
            ledger.sample(right, energy, timeline, tz=now.tzinfo, known_costs=known)
            cursor = right
        totals = ledger.totals
        totals["baseline_known"] = baseline_known
        totals["energy_complete"] = (
            complete and (now.astimezone(UTC) - cursor).total_seconds() <= 900
        )
        totals["through"] = cursor.isoformat()
        complete = (
            complete
            and (now.astimezone(UTC) - cursor).total_seconds() <= 900
            and totals["unpriced_kwh"] < 1e-6
        )
        return totals, complete, reused

    def _calculate(self, now, start, end):
        raw = self.raw
        meter = self.meter_id
        schedules = self._intervals(now)
        today, today_complete, reused = self._today(now, schedules)
        include_fixed = self.billing.values["include_standing_fees"]
        fixed = self.billing.profile.monthly
        daily_fee = (
            standing_fees(now.date(), now.date(), lambda _: fixed)
            if include_fixed
            else 0
        )
        paid_total, paid, missing_advances = advances(self.values, start, end)
        reference = (
            date.fromisoformat(self.values["reference_date"])
            if self.values["reference_date"]
            and self.values["reference_period_start"] == start.isoformat()
            else None
        )
        actual_energy = float(self.values["reference_energy"]) if reference else 0.0
        actual_cost = float(self.values["reference_cost"]) if reference else 0.0
        after = reference + timedelta(days=1) if reference else start
        missing_fee_days = 0
        if reference and not include_fixed:
            cursor = start
            while cursor <= reference:
                if self._profile_at(cursor) is None:
                    missing_fee_days += 1
                cursor += timedelta(days=1)
            actual_cost -= standing_fees(
                start,
                reference,
                lambda d: self._profile_at(d).monthly if self._profile_at(d) else 0,
            )
        cost_rows = {
            r["start"]: r.get("change") for r in raw["hourly"].get(raw["cost_id"], [])
        }
        if not self.contract_known and not self.values["historical_cost_entity"]:
            cost_rows.clear()
        if self.trial and not self.values["historical_cost_entity"]:
            saved_savings = {
                r["start"]: r.get("change")
                for r in raw["hourly"].get(raw.get("savings_id", ""), [])
            }
            cost_rows = {
                when: cost + saved_savings[when]
                for when, cost in cost_rows.items()
                if cost is not None and saved_savings.get(when) is not None
            }
        if not self.values["historical_cost_entity"]:
            # The first retained monetary bin may start halfway through an
            # import hour. Also never call partially unpriced ledger cost full.
            if cost_rows:
                cost_rows.pop(min(cost_rows))
            for row in raw["hourly"].get(raw["unpriced_id"], []):
                if row.get("change") is None or row["change"] > 1e-6:
                    cost_rows.pop(row["start"], None)
        energy_rows = raw["hourly"].get(meter, [])
        unknown_kwh = 0.0
        known_hours = set()
        reused_hours = 0
        timeline_cache = {}
        monthly = {}
        daily = {}
        for row in energy_rows:
            when = datetime.fromtimestamp(row["start"], now.tzinfo)
            energy = row.get("change")
            if (
                not after <= when.date() <= min(end, now.date() - timedelta(days=1))
                or energy is None
                or energy < 0
            ):
                continue
            known_hours.add(row["start"])
            actual_energy += energy
            variable = cost_rows.get(row["start"])
            bin_unpriced = 0.0
            if variable is not None and variable >= 0:
                reused_hours += 1
            else:
                if when.date() not in timeline_cache:
                    timeline_cache[when.date()] = self._timeline(
                        when.date(), schedules, now
                    )
                rows = timeline_cache[when.date()]
                left, right = (
                    when.astimezone(UTC),
                    when.astimezone(UTC) + timedelta(hours=1),
                )
                variable, seconds = 0.0, 0.0
                for price in rows:
                    overlap = max(
                        0,
                        (
                            min(right, price["end"]) - max(left, price["start"])
                        ).total_seconds(),
                    )
                    if price["price_kwh"] is not None:
                        variable += energy * overlap / 3600 * price["price_kwh"]
                        seconds += overlap
                if seconds < 3600:
                    bin_unpriced = energy * (1 - seconds / 3600)
                    unknown_kwh += bin_unpriced
            actual_cost += variable
            bucket = monthly.setdefault(
                when.strftime("%Y-%m"), {"kwh": 0.0, "known_variable_cost": 0.0}
            )
            bucket["kwh"] += energy
            bucket["known_variable_cost"] += variable
            day_bucket = daily.setdefault(
                when.date(), {"kwh": 0.0, "variable": 0.0, "hours": 0, "unpriced": 0.0}
            )
            day_bucket["kwh"] += energy
            day_bucket["variable"] += variable
            day_bucket["hours"] += 1
            day_bucket["unpriced"] += bin_unpriced
        past_end = min(end, now.date() - timedelta(days=1))
        required_hours = max(
            0,
            (
                datetime.combine(
                    past_end + timedelta(days=1), time.min, tzinfo=now.tzinfo
                ).timestamp()
                - datetime.combine(after, time.min, tzinfo=now.tzinfo).timestamp()
            )
            / 3600,
        )
        coverage = len(known_hours) / required_hours if required_hours else 1.0
        if include_fixed and after <= past_end:
            cursor = after
            while cursor <= past_end:
                if self._profile_at(cursor) is None:
                    missing_fee_days += 1
                cursor += timedelta(days=1)
            actual_cost += standing_fees(
                after,
                past_end,
                lambda d: self._profile_at(d).monthly if self._profile_at(d) else 0,
            )
        if after <= now.date() <= end:
            actual_energy += today["energy_kwh"] + today["unpriced_kwh"]
            actual_cost += today["actual_cost"] + daily_fee
        current_day_in_period = after <= now.date() <= end
        period_complete = (
            coverage >= 1
            and unknown_kwh < 1e-6
            and missing_fee_days == 0
            and (today_complete or not current_day_in_period)
        )
        revenue = raw["hourly"].get(raw["revenue_id"], [])
        period_revenue_rows = [
            r
            for r in revenue
            if start <= datetime.fromtimestamp(r["start"], now.tzinfo).date() <= end
            and r.get("change") is not None
        ]
        period_revenue = (
            sum(r["change"] for r in period_revenue_rows)
            if period_revenue_rows
            else None
        )
        revenue_until = max(
            (
                datetime.fromtimestamp(r["start"], now.tzinfo).isoformat()
                for r in period_revenue_rows
            ),
            default=None,
        )
        today_revenue_rows = [
            r
            for r in period_revenue_rows
            if datetime.fromtimestamp(r["start"], now.tzinfo).date() == now.date()
        ]
        today_revenue = (
            sum(r["change"] for r in today_revenue_rows) if today_revenue_rows else None
        )
        deduct = self.values["deduct_shared_income"]
        gross_today = today["actual_cost"] + daily_fee if today_complete else None
        net_today = (
            gross_today - (today_revenue if deduct else 0)
            if gross_today is not None and (not deduct or today_revenue is not None)
            else None
        )
        profile = consumption_profile(energy_rows, now, now.tzinfo)
        bills = json.loads(self.values["settled_bills"])
        history_months = {}
        for row in energy_rows:
            when = datetime.fromtimestamp(row["start"], now.tzinfo)
            if row.get("change") is None or row["change"] < 0:
                continue
            bucket = history_months.setdefault(
                when.strftime("%Y-%m"), {"kwh": 0.0, "hours": 0, "source": "recorder"}
            )
            bucket["kwh"] += row["change"]
            bucket["hours"] += 1
        for bill in bills:
            for row in bill.get("months", []):
                history_months[row["month"]] = {
                    "kwh": row["nt_kwh"] + row["vt_kwh"],
                    "nt_kwh": row["nt_kwh"],
                    "vt_kwh": row["vt_kwh"],
                    "source": "settled_bill",
                }
        for month, bucket in history_months.items():
            first = date.fromisoformat(month + "-01")
            last = first.replace(day=monthrange(first.year, first.month)[1])
            hours = (
                datetime.combine(
                    last + timedelta(days=1), time.min, tzinfo=now.tzinfo
                ).timestamp()
                - datetime.combine(first, time.min, tzinfo=now.tzinfo).timestamp()
            ) / 3600
            bucket["complete"] = (
                bucket["source"] == "settled_bill" or bucket.get("hours", 0) == hours
            )
            bucket["dynamic_active"] = bool(
                self.values["dynamic_start"]
                and last >= date.fromisoformat(self.values["dynamic_start"])
            )
        for item in profile:
            item["source"] = "recorder"
            if item["daily_kwh"] is None:
                matches = [
                    r
                    for b in bills
                    for r in b.get("months", [])
                    if date.fromisoformat(r["month"] + "-01").month == item["month"]
                ]
                if matches:
                    latest = max(matches, key=lambda r: r["month"])
                    year, month = map(int, latest["month"].split("-"))
                    item["daily_kwh"] = (
                        latest["nt_kwh"] + latest["vt_kwh"]
                    ) / monthrange(year, month)[1]
                    item["source"] = "settled_bill"
        settled = next(
            (
                b
                for b in bills
                if b["start"] == start.isoformat() and b["end"] == end.isoformat()
            ),
            None,
        )
        if settled:
            actual_energy = settled["energy_kwh"]
            actual_cost = settled["cost"] - (
                0 if include_fixed else settled.get("fixed_cost", 0)
            )
            period_complete = include_fixed or "fixed_cost" in settled
            coverage = 1.0
            unknown_kwh = 0.0
        remaining, missing_months = remaining_import(
            profile, max(start, now.date() + timedelta(days=1)), end
        )
        through = datetime.fromisoformat(
            today.get("through") or now.isoformat()
        ).astimezone(now.tzinfo)
        daily_means = {r["month"]: r["daily_kwh"] for r in profile}
        remaining_today = 0.0
        if start <= now.date() <= end:
            following = datetime.combine(
                now.date() + timedelta(days=1), time.min, tzinfo=now.tzinfo
            )
            midnight = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
            mean = daily_means[now.month]
            if mean is None:
                remaining = None
                missing_months = sorted(set(missing_months) | {now.month})
            else:
                remaining_today = (
                    mean
                    * max(0, following.timestamp() - through.timestamp())
                    / (following.timestamp() - midnight.timestamp())
                )
                if remaining is not None:
                    remaining += remaining_today
        # Future prices are estimates: historical seasonal demand plus a mean
        # of the known NT/VT forecast; no claimed knowledge of future HDO.
        price_key = "without_dynamic_kwh" if self.trial else "price_kwh"
        future_prices = [r for r in self.billing.timeline if r[price_key] is not None]
        duration = sum((r["end"] - r["start"]).total_seconds() for r in future_prices)
        forecast_complete = bool(future_prices) and all(
            r[price_key] is not None for r in self.billing.timeline if r["end"] > now
        )
        mean_price = (
            sum(
                r[price_key] * (r["end"] - r["start"]).total_seconds()
                for r in future_prices
            )
            / duration
            if duration and forecast_complete and self.contract_known
            else None
        )
        projection = (
            actual_cost + remaining * mean_price
            if period_complete and remaining is not None and mean_price is not None
            else None
        )
        if projection is not None and include_fixed:
            projection += standing_fees(
                max(start, now.date() + timedelta(days=1)), end, lambda _: fixed
            )
        actual_series = []
        if reference:
            timestamp = (
                datetime.combine(
                    reference + timedelta(days=1), time.min, tzinfo=now.tzinfo
                ).timestamp()
                * 1000
            )
            checkpoint_cost = float(self.values["reference_cost"])
            if not include_fixed:
                checkpoint_cost -= standing_fees(
                    start,
                    reference,
                    lambda d: self._profile_at(d).monthly if self._profile_at(d) else 0,
                )
            actual_series.append([timestamp, checkpoint_cost])
        else:
            checkpoint_cost = 0.0
        cursor = after
        prefix_complete = True
        while cursor <= past_end:
            data = daily.get(cursor)
            following = datetime.combine(
                cursor + timedelta(days=1), time.min, tzinfo=now.tzinfo
            )
            midnight = datetime.combine(cursor, time.min, tzinfo=now.tzinfo)
            hours = (following.timestamp() - midnight.timestamp()) / 3600
            price_profile = self._profile_at(cursor)
            if (
                not data
                or data["hours"] != hours
                or data["unpriced"] > 1e-6
                or (include_fixed and price_profile is None)
            ):
                prefix_complete = False
                break
            checkpoint_cost += data["variable"] + (
                price_profile.monthly / monthrange(cursor.year, cursor.month)[1]
                if include_fixed
                else 0
            )
            actual_series.append([following.timestamp() * 1000, checkpoint_cost])
            cursor += timedelta(days=1)
        if prefix_complete and current_day_in_period and today_complete:
            actual_series.append([through.timestamp() * 1000, actual_cost])
        forecast_series = []
        if settled:
            timestamp = (
                datetime.combine(
                    end + timedelta(days=1), time.min, tzinfo=now.tzinfo
                ).timestamp()
                * 1000
            )
            actual_series = [[timestamp, actual_cost]]
        if projection is not None and now.date() <= end:
            forecast_series.append([through.timestamp() * 1000, actual_cost])
            projected = actual_cost + remaining_today * mean_price
            cursor = max(start, now.date() + timedelta(days=1))
            while cursor <= end:
                projected += daily_means[cursor.month] * mean_price
                if include_fixed:
                    projected += fixed / monthrange(cursor.year, cursor.month)[1]
                if (
                    cursor.day == monthrange(cursor.year, cursor.month)[1]
                    or cursor == end
                ):
                    timestamp = (
                        datetime.combine(
                            cursor + timedelta(days=1), time.min, tzinfo=now.tzinfo
                        ).timestamp()
                        * 1000
                    )
                    forecast_series.append([timestamp, projected])
                cursor += timedelta(days=1)
        advance_paid_series, advance_planned_series = [], []
        planned_running, paid_running = 0.0, 0.0
        for row in sorted(
            json.loads(self.values["monthly_advances"]), key=lambda r: r["month"]
        ):
            month = date.fromisoformat(row["month"] + "-01")
            if not start.replace(day=1) <= month <= end:
                continue
            last = month.replace(day=monthrange(month.year, month.month)[1])
            timestamp = (
                datetime.combine(
                    last + timedelta(days=1), time.min, tzinfo=now.tzinfo
                ).timestamp()
                * 1000
            )
            planned_running += row["amount"]
            advance_planned_series.append([timestamp, planned_running])
            if advance_paid_amount(row) > 0:
                paid_running += advance_paid_amount(row)
                advance_paid_series.append([timestamp, paid_running])
        if self.values["advance_mode"] == "annual" and (
            abs(planned_running - paid_total) > 1e-6 or abs(paid_running - paid) > 1e-6
        ):
            advance_paid_series = [[now.timestamp() * 1000, paid]]
            advance_planned_series = [
                [
                    datetime.combine(
                        end + timedelta(days=1), time.min, tzinfo=now.tzinfo
                    ).timestamp()
                    * 1000,
                    paid_total,
                ]
            ]
        projected_net = (
            projection - (period_revenue if deduct else 0)
            if projection is not None and (not deduct or period_revenue is not None)
            else None
        )
        return {
            "daily_import_energy": today["energy_kwh"] + today["unpriced_kwh"]
            if today.get("energy_complete", today_complete)
            else None,
            "daily_import_cost_backfilled": today["actual_cost"]
            if today_complete
            else None,
            "daily_cost_backfilled": gross_today,
            "daily_savings_backfilled": today["without_cost"] - today["actual_cost"]
            if today_complete and not self.trial and today.get("baseline_known", True)
            else None,
            "daily_shared_income": today_revenue,
            "daily_net_cost": net_today,
            "period_import_energy": actual_energy
            if coverage >= 1
            and (
                today.get("energy_complete", today_complete)
                or not current_day_in_period
            )
            else None,
            "period_gross_cost": actual_cost if period_complete else None,
            "period_shared_income": period_revenue,
            "advance_payments_total": paid_total,
            "advance_payments_paid": paid,
            "forecast_import_energy": actual_energy + remaining
            if coverage >= 1
            and (
                today.get("energy_complete", today_complete)
                or not current_day_in_period
            )
            and remaining is not None
            else None,
            "forecast_gross_cost": projection,
            "forecast_net_cost": projected_net,
            "forecast_balance": paid_total - projected_net
            if projected_net is not None and not missing_advances
            else None,
            "consumption_profile": "complete" if not missing_months else "incomplete",
            "accounting_status": "contract_unconfirmed"
            if not self.contract_known
            else "complete"
            if period_complete
            else "incomplete",
            "metadata": {
                "billing_start": start.isoformat(),
                "entry_id": self.coordinator.entry.entry_id
                if hasattr(self.coordinator, "entry")
                else None,
                "advance_mode": self.values["advance_mode"],
                "monthly_advances": parse_advances(
                    self.values["monthly_advances"], start, end
                ),
                "automatic_advances": self.values["automatic_advances"],
                "automatic_advances_from": self.values["automatic_advances_from"]
                or None,
                "billing_end": end.isoformat(),
                "dynamic_start": self.values["dynamic_start"] or None,
                "dynamic_contract_mode": self.values["dynamic_contract_mode"],
                "trial_refund_included": False,
                "current_price_start": self.values["current_price_start"] or None,
                "reference_date": self.values["reference_date"] or None,
                "daily_complete": today_complete,
                "daily_energy_complete": today.get("energy_complete", today_complete),
                "today_through": today.get("through"),
                "daily_fixed_included": daily_fee,
                "include_standing_fees": include_fixed,
                "deduct_shared_income": deduct,
                "statistics_read_at": self.last_read.isoformat(),
                "period_energy_coverage": round(coverage, 6),
                "unpriced_period_kwh": unknown_kwh,
                "missing_fee_days": missing_fee_days,
                "known_period_cost": actual_cost,
                "known_period_energy": actual_energy,
                "daily_known_import_cost": today["actual_cost"],
                "daily_unpriced_kwh": today["unpriced_kwh"],
                "reused_cost_hours": reused_hours,
                "reused_today_intervals": reused,
                "energy_source": meter,
                "cost_source": raw["cost_id"],
                "default_cost_source_matches_energy": meter
                == self.billing.values["import_energy_entity"],
                "shared_income_statistic_id": raw["revenue_id"],
                "shared_income_known_until": revenue_until,
                "shared_income_forecast_method": "known_revenue_only_no_future_income_assumed",
                "missing_advance_months": missing_advances,
                "missing_profile_months": missing_months,
                "forecast_method": "seasonal_daily_demand_with_current_two_day_mean_price",
                "forecast_price_kwh": mean_price,
                "cost_actual_series": actual_series,
                "cost_forecast_series": forecast_series,
                "advance_paid_series": advance_paid_series,
                "advance_planned_series": advance_planned_series,
                "consumption_profile": profile,
                "months": monthly,
                "history_months": history_months,
                "settled_bills": bills,
                "historical_method": "existing_monetary_statistics_first_then_recorded_hdo_uniform_interval",
            },
        }
