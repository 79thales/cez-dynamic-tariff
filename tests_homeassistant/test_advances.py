"""Persist real HA service updates, partial payments and opt-in boundaries."""

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff import async_reload_entry
from custom_components.cez_dynamic_tariff.advance_payments import (
    process_due,
    register_services,
)
from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.settlement import SETTLEMENT_DEFAULTS


def setup(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            **SETTLEMENT_DEFAULTS,
            "accounting_enabled": True,
            "billing_start": "2026-04-01",
            "billing_end": "2027-03-31",
            "advance_total": 30000,
            "advance_paid": 10000,
            "base_price_kwh": 4,
            "winter_workday_schedule": "00:00=-50",
        },
    )
    entry.add_to_hass(hass)
    register_services(hass)
    return entry


async def test_partial_edit_confirm_and_undo_preserve_annual_aggregate(hass):
    entry = setup(hass)
    await hass.services.async_call(
        DOMAIN,
        "update_advance",
        {
            "month": "2026-10",
            "amount": 2500,
            "paid_amount": 1700,
        },
        blocking=True,
    )
    row = json.loads(entry.options["monthly_advances"])[0]
    assert row["paid_amount"] == 1700 and not row["paid"]
    assert entry.options["advance_mode"] == "annual"
    assert entry.options["advance_paid"] == 10000
    await hass.services.async_call(
        DOMAIN,
        "update_advance",
        {
            "month": "2026-10",
            "confirm": True,
            "use_monthly": True,
        },
        blocking=True,
    )
    assert entry.options["advance_mode"] == "monthly"
    assert json.loads(entry.options["monthly_advances"])[0]["paid_amount"] == 2500
    await hass.services.async_call(
        DOMAIN, "update_advance", {"month": "2026-10", "confirm": False}, blocking=True
    )
    row = json.loads(entry.options["monthly_advances"])[0]
    assert row["paid_amount"] == 0 and row["auto_skip"]
    assert entry.options["base_price_kwh"] == 4
    assert entry.options["winter_workday_schedule"] == "00:00=-50"


async def test_invalid_payment_or_month_never_mutates_saved_values(hass):
    entry = setup(hass)
    original = dict(entry.options)
    for data in [
        {"month": "2026-03", "amount": 100},
        {"month": "2026-10", "amount": 100, "paid_amount": 101},
        {"month": "2026-10"},
    ]:
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN, "update_advance", data, blocking=True
            )
        assert dict(entry.options) == original


async def test_prospective_auto_confirm_and_restart_do_not_duplicate(hass, freezer):
    await hass.config.async_set_time_zone("Europe/Prague")
    freezer.move_to("2026-10-09T08:00:00Z")
    entry = setup(hass)
    for month in ["2026-10", "2026-11", "2026-12"]:
        await hass.services.async_call(
            DOMAIN,
            "update_advance",
            {"month": month, "amount": 100, "paid_amount": 0},
            blocking=True,
        )
    await hass.services.async_call(
        DOMAIN, "set_automatic_advances", {"enabled": True}, blocking=True
    )
    assert entry.options["automatic_advances_from"] == "2026-11"
    coordinator = SimpleNamespace(
        hass=hass,
        entry=entry,
        billing=SimpleNamespace(settlement=SimpleNamespace(values=dict(entry.options))),
    )
    await process_due(
        coordinator, datetime(2026, 12, 1, 0, 1, tzinfo=ZoneInfo("Europe/Prague"))
    )
    rows = json.loads(entry.options["monthly_advances"])
    assert not rows[0]["paid"] and rows[1]["paid"] and rows[2]["paid"]
    assert rows[1]["paid_source"] == "automatic"
    saved = dict(entry.options)
    coordinator.billing.settlement.values = dict(entry.options)
    await process_due(
        coordinator, datetime(2026, 12, 2, tzinfo=ZoneInfo("Europe/Prague"))
    )
    assert dict(entry.options) == saved


async def test_payment_edit_refreshes_cached_history_without_reload(hass):
    entry = setup(hass)
    raw = object()
    obj = SimpleNamespace(values=dict(entry.options), raw=raw)
    coordinator = SimpleNamespace(
        options_snapshot=dict(entry.options),
        billing=SimpleNamespace(settlement=obj),
        async_request_refresh=AsyncMock(),
    )
    entry.runtime_data = coordinator
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "advance_paid": 5000}
    )
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload:
        await async_reload_entry(hass, entry)
    reload.assert_not_called()
    coordinator.async_request_refresh.assert_awaited_once()
    assert obj.raw is raw and obj.values["advance_paid"] == 5000
