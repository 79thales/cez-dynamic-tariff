"""Warn about an existing Energy income without changing financial settings."""

from copy import deepcopy
from unittest.mock import patch

from homeassistant.components.energy.data import async_get_manager
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.energy_preferences import (
    async_income_in_energy,
)


async def test_energy_warning_uses_statistic_identity_and_preserves_settings(hass):
    hass.config.components.add("energy")
    manager = await async_get_manager(hass)
    manager.data = {
        "energy_sources": [
            {"type": "grid", "stat_compensation": "edc_sharing:site_revenue"}
        ]
    }
    preferences = deepcopy(manager.data)
    hass.states.async_set(
        "sensor.site_edc_data_available_since",
        "2026-07-01",
        {
            "energy_revenue_statistic_id": "edc_sharing:site_revenue",
        },
    )
    original = {"pricing_enabled": True, "advance_total": 1000, "advance_paid": 400}
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=original)
    entry.add_to_hass(hass)
    flow = hass.config_entries.options
    menu = await flow.async_init(entry.entry_id)
    form = await flow.async_configure(menu["flow_id"], {"next_step_id": "accounting"})
    assert (
        "already selected as total compensation"
        in form["description_placeholders"]["energy_sharing_warning"]
    )
    assert not form["errors"]  # Informational: separate views may both deduct.
    assert dict(entry.options) == original
    assert manager.data == preferences
    assert await async_income_in_energy(hass, "sensor.import_cost") is False

    # The same statistic can be exposed by a differently named diagnostic entity.
    hass.states.async_set(
        "sensor.selected_income",
        "2026-07-01",
        {
            "energy_revenue_statistic_id": "edc_sharing:site_revenue",
        },
    )
    hass.config.language = "cs"
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={"shared_income_entity": "sensor.selected_income"},
    )
    entry2.add_to_hass(hass)
    menu = await flow.async_init(entry2.entry_id)
    form = await flow.async_configure(menu["flow_id"], {"next_step_id": "accounting"})
    assert (
        "už je v panelu Energie"
        in form["description_placeholders"]["energy_sharing_warning"]
    )

    # Removing the compensation clears the notice when settings are reopened.
    manager.data = {"energy_sources": []}
    menu = await flow.async_init(entry.entry_id)
    form = await flow.async_configure(menu["flow_id"], {"next_step_id": "accounting"})
    assert form["description_placeholders"]["energy_sharing_warning"] == ""


async def test_energy_check_failure_is_unknown_not_false(hass):
    hass.config.components.add("energy")
    with patch(
        "homeassistant.components.energy.data.async_get_manager", side_effect=OSError
    ):
        assert await async_income_in_energy(hass, "edc_sharing:site_revenue") is None
    hass.config.components.remove("energy")
    assert await async_income_in_energy(hass, "edc_sharing:site_revenue") is False
