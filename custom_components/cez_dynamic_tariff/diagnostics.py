"""Diagnostics support for ČEZ Dynamic Tariff."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import CezDynamicTariffConfigEntry
from .const import CONF_NAME

TO_REDACT = {
    CONF_NAME,
    "advance_total",
    "advance_paid",
    "monthly_advances",
    "advance_common_amount",
    "settled_bills",
    "reference_energy",
    "reference_cost",
    "reference_date",
    "settlement",
    "historical_profiles",
    "shared_income_entity",
    "historical_cost_entity",
    "last_complete_forecast",
    "cost_actual_series",
    "cost_forecast_series",
    "known_period_cost",
    "known_period_energy",
    "months",
    "history_months",
    "advance_paid_series",
    "advance_planned_series",
}


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
        "accounting_recovery": {
            "backfill": coordinator.billing.settlement.backfill_state,
            "runs": coordinator.billing.settlement.archive.data["runs"],
            "reason_codes": sorted(coordinator.billing.settlement._reasons),
        } if coordinator.billing and coordinator.billing.settlement else None,
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval is not None
                else None
            ),
            "data": async_redact_data(asdict(snapshot), TO_REDACT)
            if snapshot is not None
            else None,
        },
    }
