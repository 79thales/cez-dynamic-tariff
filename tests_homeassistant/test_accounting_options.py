"""Native financial settings save independently without losing existing data."""

import json
from datetime import UTC, datetime
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


async def test_one_page_common_individual_confirmation_and_atomic_save(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=OPTIONS)
    entry.add_to_hass(hass)
    manager = hass.config_entries.options
    with patch(
        "homeassistant.util.dt.now",
        return_value=datetime(2026, 10, 9, tzinfo=UTC),
    ):
        form = await choose(hass, entry, "monthly_advances")
        assert form["step_id"] == "monthly_advances"
        keys = {str(k): k for k in form["data_schema"].schema}
        assert "month" not in keys
        assert all(
            f"month_{i}_amount" in keys and f"month_{i}_confirm" in keys
            for i in range(1, 13)
        )
        assert form["description_placeholders"]["month_7"] == "10/2026"
        result = await manager.async_configure(
            form["flow_id"],
            {
                "same_amount": True,
                "common_amount": 100,
                "month_7_paid_amount": 40,
                "automatic_advances": True,
            },
        )
        assert result["type"] == "create_entry"
        rows = json.loads(entry.options["monthly_advances"])
        assert len(rows) == 12 and all(r["amount"] == 100 for r in rows)
        assert rows[6]["paid_amount"] == 40 and rows[6]["paid"] is False
        assert entry.options["advance_mode"] == "monthly"
        assert entry.options["automatic_advances_from"] == "2026-11"
        assert all(
            entry.options[k] == v for k, v in OPTIONS.items() if k != "advance_mode"
        )

        form = await choose(hass, entry, "monthly_advances")
        result = await manager.async_configure(
            form["flow_id"],
            {
                "same_amount": False,
                "month_2_amount": 160,
                "month_2_paid_amount": 80,
                "month_7_confirm": True,
                "automatic_advances": True,
            },
        )
        assert result["type"] == "create_entry"
        rows = json.loads(entry.options["monthly_advances"])
        assert rows[1]["amount"] == 160 and rows[1]["paid_amount"] == 80
        assert rows[6]["paid_amount"] == 100 and rows[6]["paid"] is True
        assert entry.options["automatic_advances_from"] == "2026-11"
        before = dict(entry.options)
        form = await choose(hass, entry, "monthly_advances")
        bad = await manager.async_configure(
            form["flow_id"],
            {
                "same_amount": True,
                "common_amount": 90,
                "automatic_advances": True,
            },
        )
        assert bad["errors"] == {"month_7_paid_amount": "invalid_advances"}
        assert (
            entry.options == before
        )  # No earlier month can be saved before the error.


async def test_edc_income_is_suggested_without_enabling_or_overwriting(hass):
    hass.states.async_set(
        "sensor.site_edc_data_available_since",
        "2026-07-01",
        {
            "energy_revenue_statistic_id": "edc_sharing:site_revenue",
        },
    )
    hass.states.async_set("sensor.shared_kwh", 12, {"unit_of_measurement": "kWh"})
    hass.states.async_set(
        "sensor.site_recipient",
        "meter",
        {
            "role": "target",
            "energy_revenue_statistic_id": "edc_sharing:recipient_revenue",
        },
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=OPTIONS)
    entry.add_to_hass(hass)
    form = await choose(hass, entry, "accounting")
    fields = {str(k): k for k in form["data_schema"].schema}
    assert (
        fields["shared_income_entity"].description["suggested_value"]
        == "sensor.site_edc_data_available_since"
    )
    assert fields["deduct_shared_income"].default() is False
    assert not entry.options.get("shared_income_entity")
    hass.states.async_set(
        "sensor.other_site_edc_data_available_since",
        "2026-07-01",
        {
            "energy_revenue_statistic_id": "edc_sharing:other_site_revenue",
        },
    )
    form = await choose(hass, entry, "accounting")
    fields = {str(k): k for k in form["data_schema"].schema}
    assert not fields["shared_income_entity"].description


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
