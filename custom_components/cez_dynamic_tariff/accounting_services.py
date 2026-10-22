"""Akce pro stejný backfill jako tlačítko, s ověřenou instancí a rozsahem."""

from datetime import date

import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN


def register_services(hass):
    """Jedna registrace služby; runtime se hledá při každém volání.

    Bez entry_id lze vybrat pouze jedinou načtenou účetní instanci.
    Datum je v místním kalendáři, obě hranice včetně dne. Chybný rozsah
    se odmítá před spuštěním; úspěšné přijetí není dokončení backfillu.
    """

    async def backfill(call):
        entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if not call.data.get("entry_id") or e.entry_id == call.data["entry_id"]
        ]
        if len(entries) != 1:
            raise ServiceValidationError("Select exactly one Accounting entry")
        runtime = getattr(entries[0], "runtime_data", None)
        obj = runtime.billing.settlement if runtime and runtime.billing else None
        if obj is None:
            raise ServiceValidationError("Selected Accounting entry is not loaded")
        try:
            start = (
                date.fromisoformat(call.data["start"])
                if call.data.get("start")
                else None
            )
            end = date.fromisoformat(call.data["end"]) if call.data.get("end") else None
        except (ValueError, TypeError):
            raise ServiceValidationError("Use ISO calendar dates YYYY-MM-DD") from None
        obj.async_start_history_backfill(start=start, end=end)

    hass.services.async_register(
        DOMAIN,
        "backfill_accounting",
        backfill,
        schema=vol.Schema(
            {
                vol.Optional("entry_id"): str,
                vol.Optional("start"): str,
                vol.Optional("end"): str,
            }
        ),
    )
