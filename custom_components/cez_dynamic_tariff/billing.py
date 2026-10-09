"""Home Assistant adapter for full prices, forecasts and persisted estimates."""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime, time, timedelta

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .accounting import CostLedger
from .const import DOMAIN
from .pricing import (
    PROFILE_DEFAULTS,
    PROFILE_REVISION,
    PriceProfile,
    finite_number,
    parse_hdo_schedule,
    price_timeline,
    tariff_at,
)


class ElectricityBilling:
    """Read public entity states only; do not modify cez_hdo or energy settings."""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self.values = {
            k: coordinator._option(k, v) for k, v in PROFILE_DEFAULTS.items()
        }
        self.profile = PriceProfile(self.values)
        self.store = Store(
            self.hass, 1, f"{DOMAIN}.billing_{coordinator.entry.entry_id}"
        )
        self.ledger = CostLedger()
        self.last_fixed = None
        self.timeline = []
        self.minimum = None
        self.status = "initializing"
        self.settlement = None
        if coordinator._option("accounting_enabled", False):
            from .settlement_history import SettlementHistory

            self.settlement = SettlementHistory(self)

    async def async_setup(self):
        """Restore totals, subscribe to source events and flush on unload."""
        self.ledger = CostLedger(await self.store.async_load())
        source_ids = [
            self.values[k]
            for k in (
                "hdo_entity",
                "hdo_schedule_entity",
                "hdo_valid_entity",
                "import_energy_entity",
            )
            if self.values[k]
        ]
        self.coordinator.entry.async_on_unload(
            async_track_state_change_event(self.hass, source_ids, self._source_changed)
        )

    @callback
    def _source_changed(self, event):
        """Capture each meter delta immediately, without coordinator debouncing."""
        if event.data["entity_id"] == self.values["import_energy_entity"]:
            state = event.data.get("new_state")
            energy = self._meter_value(state)
            self.ledger.sample(
                event.time_fired,
                energy,
                self.timeline,
                self.minimum,
                self.coordinator._local_tz(),
            )
            self._save()
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @staticmethod
    def _meter_value(state):
        if state is None:
            return None
        factors = {"Wh": 0.001, "kWh": 1, "MWh": 1000}
        factor = factors.get(state.attributes.get("unit_of_measurement"))
        value = finite_number(state.state)
        if factor is None or value is None or value < 0:
            return None
        return value * factor

    @callback
    def _save(self):
        self.store.async_delay_save(self.ledger.as_dict, 10)

    async def async_close(self):
        await self.store.async_save(self.ledger.as_dict())

    def _state(self, key):
        entity = self.values[key]
        return self.hass.states.get(entity) if entity else None

    def calculate(self, now, modifier):
        """Return separate actual, baseline and simulated price series."""
        tz = self.coordinator._local_tz()
        now = now.astimezone(tz)
        utc = now.astimezone(UTC)
        dynamic = self.values["dynamic_pricing"]
        valid = self._state("hdo_valid_entity")
        live = self._state("hdo_entity")
        schedule = self._state("hdo_schedule_entity")
        intervals = []
        self.status = "hdo_unavailable"
        if (
            valid
            and valid.state == "on"
            and schedule
            and schedule.state not in ("unknown", "unavailable")
        ):
            try:
                updated = datetime.fromisoformat(schedule.attributes["last_update"])
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=tz)
                expires = updated.astimezone(UTC) + timedelta(days=6)
                if updated.astimezone(UTC) <= utc < expires:
                    intervals = parse_hdo_schedule(
                        schedule.attributes.get("schedule"), tz, expires
                    )
                    self.status = "ok" if intervals else "invalid_hdo_schedule"
                else:
                    self.status = "expired_hdo_schedule"
            except (KeyError, TypeError, ValueError):
                self.status = "invalid_hdo_schedule"
        live_tariff = (
            ("NT" if live.state == "on" else "VT")
            if live and live.state in ("on", "off") and valid and valid.state == "on"
            else None
        )
        if intervals and live_tariff != tariff_at(intervals, utc):
            intervals = []
            self.status = "hdo_state_schedule_mismatch"
        if self.status in ("expired_hdo_schedule", "hdo_state_schedule_mismatch"):
            live_tariff = None
        start = datetime.combine(now.date(), time.min, tzinfo=tz)
        end = datetime.combine(now.date() + timedelta(days=2), time.min, tzinfo=tz)
        self.timeline = price_timeline(
            start,
            end,
            intervals,
            self.profile,
            lambda when: (
                self.coordinator._current_window(when.astimezone(tz)).modifier_percent
            ),
            dynamic,
        )
        future = [r for r in self.timeline if r["end"] > utc]
        complete = bool(future) and all(r["price_kwh"] is not None for r in future)
        known = [r for r in future if r["price_kwh"] is not None]
        best = min(known, key=lambda r: r["price_kwh"]) if complete else None
        self.minimum = best["price_kwh"] if best else None
        current = (
            self.profile.price(live_tariff, modifier, dynamic) if live_tariff else None
        )
        baseline = (
            self.profile.price(live_tariff, modifier, False) if live_tariff else None
        )
        simulated = (
            self.profile.price(live_tariff, modifier, True) if live_tariff else None
        )
        # Preserve observed past prices, and replace only the future of the
        # active meter interval. Unknown periods remain visible as unpriced kWh.
        if self.ledger.previous is not None:
            observed_at, previous_energy, previous_rows, previous_best = (
                self.ledger.previous
            )
            past = [
                {**row, "end": min(row["end"], utc)}
                for row in previous_rows
                if row["start"] < utc and row["end"] > observed_at
            ]
            upcoming = [
                {**row, "start": max(row["start"], utc)}
                for row in self.timeline
                if row["end"] > utc
            ]
            self.ledger.previous = (
                observed_at,
                previous_energy,
                past + upcoming,
                previous_best,
            )
        energy = self._meter_value(self._state("import_energy_entity"))
        if self.ledger.previous is None:
            self.ledger.sample(utc, energy, self.timeline, self.minimum, tz)
        if self.last_fixed is not None:
            self.ledger.accrue_fixed(self.last_fixed, utc, self.profile.monthly, tz)
        self.last_fixed = utc
        self._save()
        totals = self.ledger.totals
        today = self.ledger.days.get(now.date().isoformat(), {})
        daily_fixed = self.profile.monthly / monthrange(now.year, now.month)[1]
        include_fixed = self.values["include_standing_fees"]
        meter_configured = bool(self.values["import_energy_entity"])
        result = {
            "total_price": current,
            "price_without_dynamic": baseline,
            "price_with_dynamic": simulated,
            "allocated_price": (current + self.profile.allocation)
            if current is not None and self.profile.allocation is not None
            else None,
            "monthly_fixed_cost": self.profile.monthly,
            "daily_fixed_cost": daily_fixed,
            "daily_cost": today.get("actual_cost", 0)
            + (daily_fixed if include_fixed else 0)
            if meter_configured
            else None,
            "daily_savings": today.get("without_cost", 0) - today.get("actual_cost", 0)
            if meter_configured
            else None,
            "minimum_price": self.minimum,
            "best_price_start": max(best["start"], utc) if best else None,
            "next_price_change": next(
                (
                    r["start"]
                    for r in future
                    if r["start"] > utc
                    and r["price_kwh"] is not None
                    and current is not None
                    and abs(r["price_kwh"] - current) > 1e-9
                ),
                None,
            )
            if complete
            else None,
            "price_forecast": "complete" if complete else "incomplete",
            "actual_cost": totals["actual_cost"] if meter_configured else None,
            "total_cost": totals["actual_cost"]
            + (totals["fixed_cost"] if include_fixed else 0)
            if meter_configured
            else None,
            "dynamic_savings": totals["without_cost"] - totals["dynamic_cost"]
            if meter_configured
            else None,
            "realized_savings": totals["without_cost"] - totals["actual_cost"]
            if meter_configured
            else None,
            "potential_savings": totals["potential_savings"]
            if meter_configured
            else None,
            "unpriced_energy": totals["unpriced_kwh"] if meter_configured else None,
            "metadata": {
                "pricing_status": self.status,
                "dynamic_pricing": dynamic,
                "include_standing_fees": include_fixed,
                "day": now.date().isoformat(),
                "daily_variable_cost": today.get("actual_cost", 0),
                "daily_standing_fee": daily_fixed,
                "daily_cost_method": "measured_import_plus_full_calendar_day_fee",
                "distribution_rate": self.values["distribution_rate"],
                "breaker_amperes": self.values["breaker_amperes"],
                "breaker_phases": self.values["breaker_phases"],
                "vat_included": True,
                "price_list": {
                    key.removeprefix("price_list_"): self.coordinator._option(key, None)
                    for key in (
                        "price_list_source",
                        "price_list_sha256",
                        "price_list_trade_effective",
                        "price_list_distribution_effective",
                        "price_list_imported_at",
                        "price_list_poze_estimated",
                        "price_list_rates_edited",
                    )
                },
                "profile_revision": PROFILE_REVISION
                if all(
                    self.values[k] == v
                    for k, v in PROFILE_DEFAULTS.items()
                    if isinstance(v, float) and k != "annual_import_kwh"
                )
                and all(
                    self.values[k] == PROFILE_DEFAULTS[k]
                    for k in ("distribution_rate", "breaker_amperes", "breaker_phases")
                )
                else "custom",
                "rates": dict(self.values),
                "monitored_energy_kwh": totals["energy_kwh"],
                "unpriced_energy_kwh": totals["unpriced_kwh"],
                "accounting_method": "meter_deltas_uniform_within_15_minutes",
                "potential_method": "all_import_shifted_to_best_known_price_before_end_of_tomorrow",
                "hdo_entity": self.values["hdo_entity"],
                "forecast_complete": complete,
            },
            "forecast": [
                {**r, "start": r["start"].isoformat(), "end": r["end"].isoformat()}
                for r in self.timeline
            ],
        }
        return result
