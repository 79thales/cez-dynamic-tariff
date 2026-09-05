"""End-to-end config entry lifecycle tests against Home Assistant."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff.const import (
    ATTR_SCHEDULE_REVISION,
    ATTR_SCHEDULE_SOURCE_URL,
    CONF_BASE_PRICE_KWH,
    CONF_CHEAP_THRESHOLD,
    CONF_EXPENSIVE_THRESHOLD,
    CONF_INCLUDE_HOLIDAYS,
    CONF_NAME,
    CONF_SUPER_CHEAP_THRESHOLD,
    CONF_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_SCHEDULE_REVISION,
    DEFAULT_SCHEDULE_SOURCE_URL,
    DOMAIN,
)


def _entry() -> MockConfigEntry:
    """Create a representative config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="ČEZ Dynamic Tariff",
        unique_id=DOMAIN,
        data={
            CONF_NAME: "ČEZ Dynamic Tariff",
            CONF_BASE_PRICE_KWH: 4.5,
            CONF_INCLUDE_HOLIDAYS: True,
        },
        options={
            CONF_BASE_PRICE_KWH: 4.5,
            CONF_INCLUDE_HOLIDAYS: True,
            CONF_SUPER_CHEAP_THRESHOLD: -50,
            CONF_CHEAP_THRESHOLD: -10,
            CONF_EXPENSIVE_THRESHOLD: 10,
            CONF_VERY_EXPENSIVE_THRESHOLD: 25,
        },
    )


async def test_setup_repeated_reload_and_unload(hass: HomeAssistant) -> None:
    """Set up all entities, reload exactly once per update, then unload cleanly."""
    entry = _entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.cez_dynamic_tariff.coordinator.holidays.country_holidays",
        return_value=set(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        states = [
            state
            for state in hass.states.async_all()
            if state.entity_id.startswith((f"sensor.{DOMAIN}_", f"binary_sensor.{DOMAIN}_"))
        ]
        assert len(states) == 21
        assert hass.states.get(f"sensor.{DOMAIN}_current_cheap_end") is not None

        modifier = hass.states.get(f"sensor.{DOMAIN}_current_modifier")
        assert modifier is not None
        assert modifier.attributes[ATTR_SCHEDULE_REVISION] == DEFAULT_SCHEDULE_REVISION
        assert modifier.attributes[ATTR_SCHEDULE_SOURCE_URL] == DEFAULT_SCHEDULE_SOURCE_URL

        original_reload = hass.config_entries.async_reload
        with patch.object(
            hass.config_entries,
            "async_reload",
            wraps=original_reload,
        ) as reload_mock:
            for base_price in (4.6, 4.7):
                hass.config_entries.async_update_entry(
                    entry,
                    options={**entry.options, CONF_BASE_PRICE_KWH: base_price},
                )
                await hass.async_block_till_done()
                assert reload_mock.await_count == 1
                reload_mock.reset_mock()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    for entity_id in (
        f"sensor.{DOMAIN}_current_modifier",
        f"binary_sensor.{DOMAIN}_cheap_now",
    ):
        state = hass.states.get(entity_id)
        # Restore-state handling may retain an unloaded entity as unavailable.
        assert state is None or state.state == STATE_UNAVAILABLE
