"""Monthly advance bookkeeping, not bank payments or bank reconciliation."""

from __future__ import annotations

import json
from datetime import date

import voluptuous as vol
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .settlement import (
    automatic_from,
    confirm_due_advances,
    default_period,
    period_advances,
    stored_advances,
    update_advance_options,
)

PAYMENT_OPTIONS = {
    "advance_mode",
    "advance_total",
    "advance_paid",
    "monthly_advances",
    "automatic_advances",
    "automatic_advances_from",
}


def register_services(hass):
    """Expose scoped actions for the monthly dashboard editor."""

    def entry_for(call):
        entries = hass.config_entries.async_entries(DOMAIN)
        selected = [e for e in entries if e.entry_id == call.data.get("entry_id")]
        if not call.data.get("entry_id") and len(entries) == 1:
            selected = entries
        if len(selected) != 1 or not selected[0].options.get("accounting_enabled"):
            raise ServiceValidationError("Select an enabled Accounting entry")
        return selected[0]

    async def update(call: ServiceCall):
        entry = entry_for(call)
        if not any(k in call.data for k in ("amount", "paid_amount", "confirm")):
            raise ServiceValidationError("Enter an amount or a payment confirmation")
        values = dict(entry.options)
        try:
            changes = update_advance_options(values, call.data, dt_util.now().date())
        except (ValueError, KeyError, TypeError):
            raise ServiceValidationError(
                "Enter a month within the period and 0 <= paid amount <= advance amount"
            ) from None
        hass.config_entries.async_update_entry(entry, options={**values, **changes})

    async def automatic(call: ServiceCall):
        entry = entry_for(call)
        enabled = call.data["enabled"]
        old = bool(entry.options.get("automatic_advances"))
        if enabled == old:
            return
        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                "automatic_advances": enabled,
                "automatic_advances_from": automatic_from(dt_util.now().date())
                if enabled
                else "",
            },
        )

    entry_schema = {vol.Optional("entry_id"): str}
    hass.services.async_register(
        DOMAIN,
        "update_advance",
        update,
        schema=vol.Schema(
            {
                **entry_schema,
                vol.Required("month"): vol.Match(r"^\d{4}-\d{2}$"),
                vol.Optional("amount"): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=1e9)
                ),
                vol.Optional("paid_amount"): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=1e9)
                ),
                vol.Optional("confirm"): cv.boolean,
                vol.Optional("use_monthly", default=False): cv.boolean,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "set_automatic_advances",
        automatic,
        schema=vol.Schema(
            {
                **entry_schema,
                vol.Required("enabled"): cv.boolean,
            }
        ),
    )


async def process_due(coordinator, now):
    """Persist each due confirmation once; Recorder history stays cached."""
    obj = coordinator.billing.settlement if coordinator.billing else None
    if obj is None:
        return
    values = obj.values
    if not values["automatic_advances"]:
        return
    start, end = default_period(now.date())
    saved = stored_advances(values["monthly_advances"])
    rows = period_advances(
        values["monthly_advances"],
        date.fromisoformat(values["billing_start"] or start),
        date.fromisoformat(values["billing_end"] or end),
    )
    rows, changed = confirm_due_advances(
        rows,
        now.date(),
        values["automatic_advances"],
        values["automatic_advances_from"],
    )
    if changed:
        months = {r["month"] for r in rows}
        text = json.dumps(
            sorted(
                [r for r in saved if r["month"] not in months] + rows,
                key=lambda r: r["month"],
            )
        )
        values["monthly_advances"] = text
        coordinator.hass.config_entries.async_update_entry(
            coordinator.entry,
            options={**coordinator.entry.options, "monthly_advances": text},
        )
