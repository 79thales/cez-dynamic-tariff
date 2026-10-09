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
    advance_paid_amount,
    automatic_from,
    confirm_due_advances,
    default_period,
    parse_advances,
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
        default_start, default_end = default_period(dt_util.now().date())
        try:
            start = date.fromisoformat(values.get("billing_start") or default_start)
            end = date.fromisoformat(values.get("billing_end") or default_end)
            month = date.fromisoformat(call.data["month"] + "-01")
            if not start.replace(day=1) <= month <= end:
                raise ValueError
            rows = parse_advances(values.get("monthly_advances", "[]"), start, end)
            saved = next((r for r in rows if r["month"] == call.data["month"]), None)
            row = dict(saved) if saved else {"month": call.data["month"], "paid": False}
            if "amount" in call.data:
                row["amount"] = call.data["amount"]
            if "amount" not in row:
                raise ValueError
            paid = advance_paid_amount(saved) if saved else 0
            if "paid_amount" in call.data:
                paid = call.data["paid_amount"]
            if "confirm" in call.data:
                paid = row["amount"] if call.data["confirm"] else 0
            row.update(paid_amount=paid, paid=paid == row["amount"])
            if "paid_amount" in call.data or "confirm" in call.data:
                undone = ("confirm" in call.data and not call.data["confirm"]) or (
                    "paid_amount" in call.data
                    and paid == 0
                    and saved
                    and advance_paid_amount(saved) > 0
                )
                row.update(
                    paid_source="manual"
                    if paid > 0 or undone
                    else row.get("paid_source", "planned"),
                    confirmed_on=dt_util.now().date().isoformat() if paid else None,
                    auto_skip=bool(row.get("auto_skip") or undone or paid > 0),
                )
            candidate = [r for r in rows if r["month"] != row["month"]] + [row]
            parse_advances(json.dumps(candidate), start, end)
        except (ValueError, KeyError, TypeError):
            raise ServiceValidationError(
                "Enter a month within the period and 0 <= paid amount <= advance amount"
            ) from None
        # Annual totals cannot be silently reassigned to fabricated months.
        # A monthly action edits its row but changes accounting mode only when
        # the caller explicitly chooses the monthly workflow.
        changes = {
            "monthly_advances": json.dumps(sorted(candidate, key=lambda r: r["month"]))
        }
        if call.data.get("use_monthly"):
            changes["advance_mode"] = "monthly"
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
    rows = parse_advances(
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
        text = json.dumps(rows)
        values["monthly_advances"] = text
        coordinator.hass.config_entries.async_update_entry(
            coordinator.entry,
            options={**coordinator.entry.options, "monthly_advances": text},
        )
