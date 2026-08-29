"""Diagnostics support for ČEZ Dynamic Tariff."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import CezDynamicTariffConfigEntry
from .const import CONF_NAME

TO_REDACT = {CONF_NAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: CezDynamicTariffConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    snapshot = coordinator.data

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval is not None
                else None
            ),
            "data": asdict(snapshot) if snapshot is not None else None,
        },
    }
