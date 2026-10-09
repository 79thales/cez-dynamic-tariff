"""Full-price lifecycle and public-entity input tests in real Home Assistant."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.pricing import PROFILE_DEFAULTS
from custom_components.cez_dynamic_tariff.schedule import (
    DEFAULT_SCHEDULES,
    format_schedule,
)

HDO = "binary_sensor.cez_hdo_lowtariffactive_test"
VALID = "binary_sensor.cez_hdo_data_valid_test"
SCHEDULE = "sensor.cez_hdo_schedule_test"
METER = "sensor.grid_import"


async def test_full_price_meter_events_reload_and_source_failure(
    hass: HomeAssistant, freezer
):
    """No lifetime charge, signed comparisons, persisted totals, original IDs."""
    freezer.move_to("2026-10-09T01:00:00+00:00")
    await hass.config.async_set_time_zone("Europe/Prague")
    now = datetime.now(UTC)
    rows = [
        {
            "start": (now - timedelta(hours=3)).isoformat(),
            "end": (now + timedelta(days=3)).isoformat(),
            "tariff": "NT",
        }
    ]
    hass.states.async_set(HDO, "on")
    hass.states.async_set(VALID, "on")
    hass.states.async_set(
        SCHEDULE, "ready", {"schedule": rows, "last_update": now.isoformat()}
    )
    hass.states.async_set(
        METER, "17000", {"unit_of_measurement": "kWh", "device_class": "energy"}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Tariff",
        unique_id=DOMAIN,
        data={"name": "Tariff", "base_price_kwh": 4.5},
        options={
            **PROFILE_DEFAULTS,
            "pricing_enabled": True,
            "dynamic_pricing": True,
            "hdo_entity": HDO,
            "hdo_valid_entity": VALID,
            "hdo_schedule_entity": SCHEDULE,
            "import_energy_entity": METER,
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.cez_dynamic_tariff.coordinator.holidays.country_holidays",
        return_value=set(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        prefix = f"sensor.{DOMAIN}_"
        assert float(hass.states.get(prefix + "total_price").state) == 1.89894
        assert float(hass.states.get(prefix + "effective_price").state) == 2.25
        assert hass.states.get(prefix + "actual_cost").state == "0.0"
        assert hass.states.get(prefix + "price_forecast").state == "complete"
        assert len(hass.states.get(prefix + "total_price").attributes["forecast"]) > 1
        freezer.tick(timedelta(minutes=1))
        hass.states.async_set(
            METER, "17002", {"unit_of_measurement": "kWh", "device_class": "energy"}
        )
        await hass.async_block_till_done()
        assert float(hass.states.get(prefix + "actual_cost").state) == 3.79788
        assert float(hass.states.get(prefix + "realized_savings").state) == 3.05
        assert float(hass.states.get(prefix + "daily_cost").state) == pytest.approx(
            3.79788 + 850.47 / 31, abs=1e-6
        )
        assert (
            hass.states.get(prefix + "daily_cost").attributes["last_reset"] is not None
        )
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert float(hass.states.get(prefix + "actual_cost").state) == 3.79788
        # Switch actual mode without changing either old effective price or HDO.
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, "dynamic_pricing": False}
        )
        await hass.async_block_till_done()
        assert float(hass.states.get(prefix + "total_price").state) == 3.42394
        assert float(hass.states.get(prefix + "effective_price").state) == 2.25
        assert hass.states.get(HDO).state == "on"
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, "include_standing_fees": False}
        )
        await hass.async_block_till_done()
        assert float(hass.states.get(prefix + "daily_cost").state) == 3.79788
        assert float(hass.states.get(prefix + "total_cost").state) == 3.79788
        hass.states.async_set(VALID, "off")
        await hass.async_block_till_done()
        assert hass.states.get(prefix + "total_price").state == "unknown"
        assert hass.states.get(prefix + "price_forecast").state == "incomplete"
        assert hass.states.get(prefix + "current_modifier").state == "-50"
        freezer.tick(timedelta(minutes=1))
        hass.states.async_set(METER, "17004", {"unit_of_measurement": "kWh"})
        await hass.async_block_till_done()
        await entry.runtime_data.async_refresh()
        assert float(hass.states.get(prefix + "unpriced_energy").state) == 2
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_options_pricing_steps_preserve_existing_values(hass: HomeAssistant):
    """Configure both variants through native selectors without rewriting old prices."""
    hass.states.async_set(HDO, "on")
    hass.states.async_set(VALID, "on")
    hass.states.async_set(SCHEDULE, "ready", {})
    hass.states.async_set(METER, "17000", {"unit_of_measurement": "kWh"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Tariff",
        unique_id=DOMAIN,
        data={"name": "Tariff", "base_price_kwh": 4.5},
        options={"base_price_kwh": 4.5, "include_holidays": False},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.cez_dynamic_tariff.async_reload_entry"):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "general"})
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "base_price_kwh": 4.5,
                "include_holidays": False,
                "reset_schedules": False,
                "configure_pricing": True,
            },
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "cheap_threshold": -10,
                "super_cheap_threshold": -50,
                "expensive_threshold": 10,
                "very_expensive_threshold": 25,
            },
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                key: format_schedule(value) for key, value in DEFAULT_SCHEDULES.items()
            },
        )
        assert result["step_id"] == "pricing"
        choices = {
            key: PROFILE_DEFAULTS[key]
            for key in (
                "pricing_enabled",
                "dynamic_pricing",
                "distribution_rate",
                "breaker_amperes",
                "breaker_phases",
                "annual_import_kwh",
            )
        }
        choices.update(
            {
                "pricing_enabled": True,
                "dynamic_pricing": True,
                "hdo_entity": HDO,
                "hdo_valid_entity": VALID,
                "hdo_schedule_entity": SCHEDULE,
                "import_energy_entity": METER,
            }
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=choices
        )
        assert result["step_id"] == "price_rates"
        rates = {
            key: value
            for key, value in PROFILE_DEFAULTS.items()
            if isinstance(value, float) and key != "annual_import_kwh"
        }
        with pytest.raises(InvalidData):
            await hass.config_entries.options.async_configure(
                result["flow_id"], user_input={**rates, "trade_nt": float("nan")}
            )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={**rates, "trade_nt": float("inf")}
        )
        assert result["errors"] == {"trade_nt": "invalid_price"}
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=rates
        )
        assert result["type"] == "create_entry"
        assert entry.options["dynamic_pricing"] is True
        assert entry.options["base_price_kwh"] == 4.5
        assert entry.options["trade_nt"] == 3.05
        assert "configure_pricing" not in entry.options
