"""Skutečný HA: plánovaná aktivace, restart, semafor a návaznost měření."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.cez_dynamic_tariff.band_pricing import record_change
from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.price_list import parse_price_list
from custom_components.cez_dynamic_tariff.pricing import PROFILE_DEFAULTS

spec = importlib.util.spec_from_file_location(
    "_band_lifecycle_fixture", Path(__file__).parents[1] / "tests/price_list_fixture.py"
)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


async def setup_pricing(hass: HomeAssistant, freezer, *, fixed=True, planned=True):
    """Měříme syntetický odběr jednoho NT, bez přístupu k živému HA či síti."""
    freezer.move_to("2026-10-22T01:00:00Z")
    await hass.config.async_set_time_zone("Europe/Prague")
    now = datetime.now(UTC)
    options = {
        **PROFILE_DEFAULTS,
        "pricing_enabled": True,
        "dynamic_pricing": True,
        "hdo_entity": "binary_sensor.test_hdo",
        "hdo_valid_entity": "binary_sensor.test_valid",
        "hdo_schedule_entity": "sensor.test_hdo_schedule",
        "import_energy_entity": "sensor.test_import",
    }
    hass.states.async_set(options["hdo_entity"], "on")
    hass.states.async_set(options["hdo_valid_entity"], "on")
    hass.states.async_set(
        options["hdo_schedule_entity"],
        "ready",
        {
            "last_update": now.isoformat(),
            "schedule": [
                {
                    "start": (now - timedelta(hours=3)).isoformat(),
                    "end": (now + timedelta(days=3)).isoformat(),
                    "tariff": "NT",
                }
            ],
        },
    )
    hass.states.async_set(
        options["import_energy_entity"],
        "100",
        {"unit_of_measurement": "kWh", "device_class": "energy"},
    )
    if fixed:
        result = parse_price_list(
            fixture.make_pdf(dynamic="2years", effective="1. 6. 2026"), "D57d", 25, 3
        )
        profile = {
            "id": "synthetic-two-years",
            "product": result.product,
            "schedules": result.schedules,
            "rates": result.rates,
            "trade_effective": result.trade_effective,
            "distribution_effective": result.distribution_effective,
            "annual_import_kwh": 10000,
        }
        options.update(
            {"fixed_price_profiles": [profile], "fixed_profile_id": profile["id"]}
        )
        if planned:
            options = record_change(
                options,
                {**options, "tariff_mode": "fixed_bands"},
                PROFILE_DEFAULTS,
                now,
                now + timedelta(seconds=77),
            )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        unique_id=DOMAIN,
        data={"name": "Test", "base_price_kwh": 2.5},
        options=options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_planned_activation_survives_reload_and_prices_crossing_sample(
    hass, freezer
):
    """Dvě kWh přes hranici 77 s mají dvě ceny; restart neztratí první odečet."""
    with patch(
        "custom_components.cez_dynamic_tariff.coordinator.holidays.country_holidays",
        return_value=set(),
    ):
        entry = await setup_pricing(hass, freezer)
        prefix = f"sensor.{DOMAIN}_"
        selection = f"select.{DOMAIN}_tariff_mode"
        assert hass.states.get(selection).state == "percentage"
        assert float(hass.states.get(prefix + "total_price").state) == 1.89894
        freezer.tick(timedelta(seconds=30))
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.billing.ledger.previous is not None
        freezer.tick(timedelta(seconds=90))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert hass.states.get(selection).state == "fixed_bands"
        assert float(hass.states.get(prefix + "total_price").state) == 2.22394
        assert float(hass.states.get(prefix + "allocated_price").state) == 3.244504
        assert hass.states.get(prefix + "active_price_level").state == "super_cheap"
        assert hass.states.get(prefix + "current_modifier").state == "-50"
        hass.states.async_set(
            "sensor.test_import",
            "102",
            {"unit_of_measurement": "kWh", "device_class": "energy"},
        )
        await hass.async_block_till_done()
        await entry.runtime_data.async_refresh()
        expected = 2 * (77 * 1.89894 + 43 * 2.22394) / 120
        assert (
            abs(entry.runtime_data.billing.ledger.totals["actual_cost"] - expected)
            < 1e-9
        )
        # Peněžní senzor publikuje šest desetinných míst; ledger je přesnější.
        assert float(hass.states.get(prefix + "actual_cost").state) == round(
            expected, 6
        )
        hass.states.async_set("binary_sensor.test_valid", "off")
        await hass.async_block_till_done()
        await entry.runtime_data.async_refresh()
        assert hass.states.get(prefix + "total_price").state == "unknown"
        assert hass.states.get(prefix + "active_price_level").state == "unknown"


async def test_selector_requires_profile(hass, freezer):
    with patch(
        "custom_components.cez_dynamic_tariff.coordinator.holidays.country_holidays",
        return_value=set(),
    ):
        entry = await setup_pricing(hass, freezer, fixed=False)
        selection = f"select.{DOMAIN}_tariff_mode"
        try:
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": selection, "option": "fixed_bands"},
                blocking=True,
            )
        except HomeAssistantError:
            pass
        else:
            raise AssertionError("Bez profilu se pevný režim nesmí aktivovat.")
        assert not entry.options.get("pricing_events")


async def test_same_selected_mode_can_be_activated_immediately(hass, freezer):
    with patch(
        "custom_components.cez_dynamic_tariff.coordinator.holidays.country_holidays",
        return_value=set(),
    ):
        entry = await setup_pricing(hass, freezer)
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": f"select.{DOMAIN}_tariff_mode", "option": "fixed_bands"},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(entry.options["pricing_events"]) == 1
        assert float(hass.states.get(f"sensor.{DOMAIN}_total_price").state) == 2.22394
