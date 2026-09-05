"""Exercise installation, options validation, and reset via Home Assistant."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.schedule import DEFAULT_SCHEDULES


async def test_install_edit_and_reset(hass: HomeAssistant) -> None:
    """Persist valid options, reject malformed schedules, then restore defaults."""
    general = {"name": "Tariff", "base_price_kwh": 4.5, "include_holidays": False}
    thresholds = {
        "super_cheap_threshold": -50,
        "cheap_threshold": -10,
        "expensive_threshold": 10,
        "very_expensive_threshold": 25,
    }
    with patch(
        "custom_components.cez_dynamic_tariff.coordinator.holidays.country_holidays",
        return_value=set(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=general
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = result["result"]
        await hass.async_block_till_done()
        assert entry.unique_id == DOMAIN

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={
                "base_price_kwh": 5.0, "include_holidays": False,
                "reset_schedules": False,
            },
        )
        assert result["step_id"] == "thresholds"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={**thresholds, "cheap_threshold": 10}
        )
        assert result["errors"] == {"base": "cheap_not_below_expensive"}
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=thresholds
        )
        assert result["step_id"] == "schedules"
        schedules = {key: "00:00=-50, 06:00=10" for key in DEFAULT_SCHEDULES}
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={**schedules, "winter_workday_schedule": "bad"}
        )
        assert result["errors"] == {"winter_workday_schedule": "invalid_schedule"}
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=schedules
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert entry.options["base_price_kwh"] == 5.0
        assert entry.options["winter_workday_schedule"] == "00:00=-50, 06:00=+10"

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={
                "base_price_kwh": 5.0, "include_holidays": False,
                "reset_schedules": True,
            },
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=thresholds
        )
        assert result["step_id"] == "reset_schedules"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"confirm_reset": False}
        )
        assert result["errors"] == {"base": "confirm_reset"}
        assert "winter_workday_schedule" in entry.options
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"confirm_reset": True}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert not set(DEFAULT_SCHEDULES).intersection(entry.options)
        assert entry.options["base_price_kwh"] == 5.0
        assert entry.options["cheap_threshold"] == -10
        assert entry.unique_id == DOMAIN
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
