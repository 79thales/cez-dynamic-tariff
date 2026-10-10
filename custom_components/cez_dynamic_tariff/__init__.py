from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .billing import ElectricityBilling
from .const import DOMAIN, PLATFORMS
from .coordinator import CezDynamicTariffCoordinator

type CezDynamicTariffConfigEntry = ConfigEntry[CezDynamicTariffCoordinator]

CONFIG_SCHEMA = vol.Schema({DOMAIN: cv.config_entry_only_config_schema}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration from YAML."""
    from .advance_payments import register_services

    register_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CezDynamicTariffConfigEntry,
) -> bool:
    """Set up ČEZ Dynamic Tariff from a config entry."""
    coordinator = CezDynamicTariffCoordinator(hass, entry)
    from .dashboard_api import async_setup_dashboard_generator
    from .frontend import async_register_card

    await async_register_card(hass)
    await async_setup_dashboard_generator(hass)
    if coordinator._option("pricing_enabled", False):
        coordinator.billing = ElectricityBilling(coordinator)
        await coordinator.billing.async_setup()
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

    if unload_ok and entry.runtime_data.billing is not None:
        await entry.runtime_data.billing.async_close()

    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: CezDynamicTariffConfigEntry,
) -> None:
    """Reload config entry."""
    from .advance_payments import PAYMENT_OPTIONS

    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is not None and coordinator.billing is not None:
        old = coordinator.options_snapshot
        new = dict(entry.options)
        changed = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
        obj = coordinator.billing.settlement
        if obj is not None and changed <= PAYMENT_OPTIONS:
            coordinator.options_snapshot = new
            for key in PAYMENT_OPTIONS:
                if key in new:
                    obj.values[key] = new[key]
            await coordinator.async_request_refresh()
            return
    await hass.config_entries.async_reload(entry.entry_id)
