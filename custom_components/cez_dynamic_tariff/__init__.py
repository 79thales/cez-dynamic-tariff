from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .coordinator import CezDynamicTariffCoordinator

type CezDynamicTariffConfigEntry = ConfigEntry[CezDynamicTariffCoordinator]

CONFIG_SCHEMA = vol.Schema({DOMAIN: cv.config_entry_only_config_schema}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration from YAML."""
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CezDynamicTariffConfigEntry,
) -> bool:
    """Set up ČEZ Dynamic Tariff from a config entry."""
    coordinator = CezDynamicTariffCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: CezDynamicTariffConfigEntry,
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: CezDynamicTariffConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
