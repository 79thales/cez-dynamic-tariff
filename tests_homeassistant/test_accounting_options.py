"""Native financial settings save independently without losing existing data."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff.const import DOMAIN

OPTIONS = {
    "billing_start": "2026-04-01",
    "billing_end": "2027-03-31",
    "advance_mode": "annual",
    "advance_total": 1200,
    "advance_paid": 200,
    "base_price_kwh": 99,
    "winter_workday_schedule": "00:00=-50",
    "reference_date": "2026-09-30",
    "reference_period_start": "2026-04-01",
    "reference_energy": 10,
    "reference_cost": 50,
    "settled_bills": "[]",
    "historical_profiles": "[]",
}


async def choose(hass, entry, task):
    manager = hass.config_entries.options
    first = await manager.async_init(entry.entry_id)
    assert first["type"] == "menu"
    assert task in first["menu_options"]
    return await manager.async_configure(first["flow_id"], {"next_step_id": task})


async def test_native_month_partial_confirm_and_auto_preserve_other_options(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=OPTIONS)
    entry.add_to_hass(hass)
    manager = hass.config_entries.options
    with patch(
        "homeassistant.util.dt.now",
        return_value=datetime(2026, 10, 9, tzinfo=timezone.utc),
    ):
        form = await choose(hass, entry, "advance_month")
        form = await manager.async_configure(form["flow_id"], {"month": "2026-10"})
        assert form["step_id"] == "monthly_advances"
        assert form["description_placeholders"]["month"] == "2026-10"
        result = await manager.async_configure(
            form["flow_id"],
            {
                "amount": 100,
                "paid_amount": 40,
                "confirm_paid": False,
                "automatic_advances": True,
            },
        )
        assert result["type"] == "create_entry"
        rows = json.loads(entry.options["monthly_advances"])
        assert rows[0]["paid_amount"] == 40 and rows[0]["paid"] is False
        assert entry.options["advance_mode"] == "monthly"
        assert entry.options["automatic_advances_from"] == "2026-11"
        assert all(
            entry.options[k] == v for k, v in OPTIONS.items() if k != "advance_mode"
        )

        form = await choose(hass, entry, "advance_month")
        form = await manager.async_configure(form["flow_id"], {"month": "2026-10"})
        keys = {str(k): k for k in form["data_schema"].schema}
        assert keys["paid_amount"].default() == 40
        bad = await manager.async_configure(
            form["flow_id"],
            {
                "amount": 100,
                "paid_amount": 101,
                "confirm_paid": False,
                "automatic_advances": True,
            },
        )
        assert bad["errors"] == {"base": "invalid_advances"}
        assert json.loads(entry.options["monthly_advances"])[0]["paid_amount"] == 40
        result = await manager.async_configure(
            form["flow_id"],
            {
                "amount": 100,
                "paid_amount": 40,
                "confirm_paid": True,
                "automatic_advances": True,
            },
        )
        assert result["type"] == "create_entry"
        row = json.loads(entry.options["monthly_advances"])[0]
        assert row["paid_amount"] == 100 and row["paid"] is True
        assert entry.options["automatic_advances_from"] == "2026-11"


async def test_native_checkpoint_has_no_json_and_rejects_other_period(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={**OPTIONS, "reference_date": ""}
    )
    entry.add_to_hass(hass)
    manager = hass.config_entries.options
    form = await choose(hass, entry, "accounting_history")
    assert form["type"] == "menu"
    form = await manager.async_configure(
        form["flow_id"], {"next_step_id": "history_reading"}
    )
    keys = {str(k): k for k in form["data_schema"].schema}
    assert set(keys) == {"reference_date", "reference_energy", "reference_cost"}
    assert not keys["reference_energy"].description
    bad = await manager.async_configure(
        form["flow_id"],
        {
            "reference_date": "2025-03-31",
            "reference_energy": 20,
            "reference_cost": 100,
        },
    )
    assert bad["errors"] == {"base": "invalid_accounting_history"}
    assert entry.options["reference_date"] == ""
    result = await manager.async_configure(
        form["flow_id"],
        {
            "reference_date": "2026-09-30",
            "reference_energy": 20,
            "reference_cost": 100,
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options["reference_energy"] == 20
    assert entry.options["reference_period_start"] == "2026-04-01"
    assert entry.options["advance_paid"] == OPTIONS["advance_paid"]
    assert entry.options["settled_bills"] == OPTIONS["settled_bills"]


async def test_auto_history_only_disables_manual_checkpoint(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=OPTIONS)
    entry.add_to_hass(hass)
    manager = hass.config_entries.options
    form = await choose(hass, entry, "accounting_history")
    form = await manager.async_configure(
        form["flow_id"], {"next_step_id": "history_auto"}
    )
    assert not form["data_schema"].schema
    result = await manager.async_configure(form["flow_id"], {})
    assert result["type"] == "create_entry"
    assert entry.options["reference_date"] == ""
    assert all(
        entry.options[k] == v for k, v in OPTIONS.items() if k != "reference_date"
    )
