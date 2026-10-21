"""Nativní formuláře a odhad jsou ověřené proti skutečnému HA, bez zákaznických dat."""

import copy
import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff.accounting_documents import RATE_KEYS
from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.pricing import PriceProfile
from tests_homeassistant.test_accounting_options import OPTIONS, choose
from tests_homeassistant.test_settlement import TZ, adapter

BILL = {
    "start": "2024-01-01",
    "end": "2024-12-31",
    "source": "Testovací faktura",
    "energy_kwh": 100,
    "vt_kwh": 20,
    "nt_kwh": 80,
    "cost": 400,
}
RATIO_KEY = "2024-01-01/2024-12-31"


async def select(hass, entry, task, record="new", action="edit"):
    first = await choose(hass, entry, "accounting_documents")
    assert first["type"] == "menu"
    form = await hass.config_entries.options.async_configure(
        first["flow_id"], {"next_step_id": task}
    )
    return await hass.config_entries.options.async_configure(
        form["flow_id"], {"record": record, "action": action}
    )


async def test_bill_create_edit_delete_preserves_unrelated_settings(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=OPTIONS)
    entry.add_to_hass(hass)
    manager = hass.config_entries.options
    form = await select(hass, entry, "document_bills")
    result = await manager.async_configure(form["flow_id"], BILL)
    assert result["type"] == "create_entry"
    assert json.loads(entry.options["settled_bills"]) == [BILL]
    assert all(
        entry.options[k] == v for k, v in OPTIONS.items() if k != "settled_bills"
    )
    form = await select(hass, entry, "document_bills", "0")
    result = await manager.async_configure(form["flow_id"], {**BILL, "cost": 450})
    assert result["type"] == "create_entry"
    assert json.loads(entry.options["settled_bills"])[0]["cost"] == 450
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "estimate_bill": RATIO_KEY}
    )
    form = await select(hass, entry, "document_bills", "0", "delete")
    assert form["step_id"] == "document_delete"
    result = await manager.async_configure(form["flow_id"], {"confirm": True})
    assert result["type"] == "create_entry"
    assert entry.options["settled_bills"] == "[]"
    assert entry.options["estimate_bill"] == ""


async def test_invalid_bill_and_stale_editor_do_not_write(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=OPTIONS)
    entry.add_to_hass(hass)
    form = await select(hass, entry, "document_bills")
    bad = await hass.config_entries.options.async_configure(
        form["flow_id"], {**BILL, "nt_kwh": 90}
    )
    assert bad["errors"]["base"] == "bill_energy_mismatch"
    assert dict(entry.options) == OPTIONS
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "settled_bills": json.dumps([BILL])}
    )
    result = await hass.config_entries.options.async_configure(form["flow_id"], BILL)
    assert result["errors"]["base"] == "documents_changed"
    assert json.loads(entry.options["settled_bills"]) == [BILL]


async def test_monthly_profile_is_atomic_and_does_not_insert_unknown_zero(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=OPTIONS)
    entry.add_to_hass(hass)
    manager = hass.config_entries.options
    form = await select(hass, entry, "document_bills")
    form = await manager.async_configure(form["flow_id"], {**BILL, "edit_months": True})
    assert form["step_id"] == "document_months"
    assert entry.options["settled_bills"] == "[]"
    bad = await manager.async_configure(form["flow_id"], {"nt_1": 10})
    assert bad["errors"]["base"] == "invalid_bill_months"
    result = await manager.async_configure(form["flow_id"], {"nt_1": 10, "vt_1": 2})
    assert result["type"] == "create_entry"
    saved = json.loads(entry.options["settled_bills"])[0]
    assert saved["months"] == [{"month": "2024-01", "nt_kwh": 10, "vt_kwh": 2}]


async def test_historical_prices_validate_overlap_and_preserve_active_rates(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={**OPTIONS, "current_price_start": "2026-01-01", "trade_nt": 99},
    )
    entry.add_to_hass(hass)
    manager = hass.config_entries.options
    form = await select(hass, entry, "document_profiles")
    form = await manager.async_configure(
        form["flow_id"], {"next_step_id": "profile_manual"}
    )
    rates = {k: 0 for k in RATE_KEYS}
    data = {**rates, "source": "Test", "start": "2025-01-01", "end": "2026-01-01"}
    result = await manager.async_configure(form["flow_id"], data)
    assert result["errors"]["base"] == "current_price_overlap"
    result = await manager.async_configure(
        form["flow_id"], {**data, "end": "2025-12-31"}
    )
    assert result["type"] == "create_entry"
    assert entry.options["trade_nt"] == 99
    assert json.loads(entry.options["historical_profiles"])[0]["rates"] == rates
    assert entry.options["reference_cost"] == OPTIONS["reference_cost"]


async def test_historical_pdf_review_saves_only_historical_profile(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={**OPTIONS, "current_price_start": "2026-01-01", "trade_nt": 99},
    )
    entry.add_to_hass(hass)
    manager = hass.config_entries.options
    form = await select(hass, entry, "document_profiles")
    form = await manager.async_configure(
        form["flow_id"], {"next_step_id": "profile_import"}
    )
    imported = SimpleNamespace(
        rates={k: 1.0 for k in RATE_KEYS},
        trade_effective="2025-01-01",
        distribution_effective="2025-01-01",
        poze_estimated=False,
        digest="digest",
    )
    with patch(
        "custom_components.cez_dynamic_tariff.price_list_import.async_import_price_list",
        AsyncMock(return_value=(imported, "Testovací PDF")),
    ):
        form = await manager.async_configure(
            form["flow_id"],
            {
                "price_list_url": "https://www.cez.cz/test.pdf",
                "distribution_rate": "D57d",
                "breaker_amperes": 25,
                "breaker_phases": 3,
                "annual_import_kwh": 100,
            },
        )
    assert form["step_id"] == "document_profile"
    fields = {str(k): k for k in form["data_schema"].schema}
    assert fields["start"].description["suggested_value"] == "2025-01-01"
    assert fields["end"].description["suggested_value"] == "2025-12-31"
    result = await manager.async_configure(
        form["flow_id"],
        {
            **imported.rates,
            "source": "Testovací PDF",
            "start": "2025-01-01",
            "end": "2025-12-31",
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options["trade_nt"] == 99
    assert "price_list_sha256" not in entry.options
    assert (
        json.loads(entry.options["historical_profiles"])[0]["price_list_sha256"]
        == "digest"
    )


async def test_optional_ratio_selection_and_recalculate_use_existing_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={**OPTIONS, "settled_bills": json.dumps([BILL])}
    )
    entry.add_to_hass(hass)
    first = await choose(hass, entry, "accounting_documents")
    form = await hass.config_entries.options.async_configure(
        first["flow_id"], {"next_step_id": "estimate_settings"}
    )
    result = await hass.config_entries.options.async_configure(
        form["flow_id"], {"estimate_bill": RATIO_KEY}
    )
    assert result["type"] == "create_entry"
    assert entry.options["estimate_bill"] == RATIO_KEY
    calls = []

    async def recalculate(call):
        calls.append(dict(call.data))

    hass.services.async_register(DOMAIN, "backfill_accounting", recalculate)
    first = await choose(hass, entry, "accounting_documents")
    form = await hass.config_entries.options.async_configure(
        first["flow_id"], {"next_step_id": "accounting_check"}
    )
    result = await hass.config_entries.options.async_configure(
        form["flow_id"], {"recalculate": True}
    )
    assert result["type"] == "form"
    assert calls == [{"entry_id": entry.entry_id}]
    assert "neověřeno" in result["description_placeholders"]["report"]


def projection_fixture(hass, *, enabled=True):
    now = datetime(2026, 10, 21, 0, 5, tzinfo=TZ)
    start, end = date(2026, 10, 19), date(2026, 10, 22)
    obj = adapter(
        hass,
        {
            "billing_start": start.isoformat(),
            "billing_end": end.isoformat(),
            "reference_date": start.isoformat(),
            "reference_period_start": start.isoformat(),
            "reference_energy": 100,
            "reference_cost": 500,
            "estimate_bill": RATIO_KEY if enabled else "",
            "settled_bills": json.dumps([BILL]),
            "historical_cost_entity": "sensor.external_cost",
        },
    )
    # Jednoduché ceny pro ručně ověřitelný výsledek: NT=2, VT=4, bez stálých složek.
    rates = {k: 0.0 for k in RATE_KEYS}
    rates.update(trade_nt=2.0, trade_vt=4.0)
    obj.billing.values.update(rates, dynamic_pricing=False)
    obj.billing.profile = PriceProfile(obj.billing.values)
    yesterday = datetime(2026, 10, 20, tzinfo=TZ)
    energy = [
        {"start": yesterday.timestamp() + i * 3600, "change": 1} for i in range(24)
    ]
    # Jeden celý den z každého měsíce dodává skutečnému algoritmu sezónní profil.
    history = [
        {
            "start": datetime(2024, month, 2, tzinfo=TZ).timestamp() + i * 3600,
            "change": 1,
        }
        for month in range(1, 13)
        for i in range(24)
    ]
    obj.raw = {
        "hourly": {
            "sensor.import": history + energy,
            "sensor.external_cost": [{**energy[0], "change": 2}],
        },
        "history": {},
        "cost_id": "sensor.external_cost",
        "revenue_id": "",
        "unpriced_id": "sensor.unpriced",
    }
    obj.last_read = now
    obj.billing.timeline = [
        {
            "start": now,
            "end": now + timedelta(days=2),
            "price_kwh": 3,
            "without_dynamic_kwh": 3,
        }
    ]
    today = {
        "energy_kwh": 0,
        "unpriced_kwh": 0,
        "actual_cost": 0,
        "without_cost": 0,
        "energy_complete": True,
        "through": now.isoformat(),
    }
    return obj, now, start, end, today


async def test_estimate_keeps_exact_accounting_incomplete_and_checkpoint_once(hass):
    obj, now, start, end, today = projection_fixture(hass)
    archive = copy.deepcopy(obj.archive.data)
    with patch.object(obj, "_today", return_value=(today, True, 0)):
        result = obj._calculate(now, start, end)
    meta = result["metadata"]
    assert result["accounting_status"] == "incomplete"
    assert result["period_gross_cost"] is None
    assert result["period_import_energy"] == 124
    assert meta["known_period_cost"] == 502
    assert meta["unpriced_period_kwh"] == 23
    assert meta["estimated_history_cost"] == pytest.approx(23 * 2.4)
    assert meta["forecast_approximate"] is True
    assert meta["cost_forecast_series"][0][1] == pytest.approx(502 + 23 * 2.4)
    assert meta["cost_forecast_series"][-1][1] == pytest.approx(
        result["forecast_gross_cost"]
    )
    assert result["forecast_gross_cost"] > 502
    assert obj.archive.data["costs"] == archive["costs"]
    assert obj.values["reference_cost"] == 500


@pytest.mark.parametrize("failure", ["disabled", "price", "energy", "contract", "bill"])
async def test_estimate_never_hides_missing_essential_inputs(hass, failure):
    obj, now, start, end, today = projection_fixture(
        hass, enabled=failure != "disabled"
    )
    if failure == "price":
        obj.values["current_price_start"] = "2026-10-21"
    if failure == "energy":
        obj.raw["hourly"]["sensor.import"].pop()
    if failure == "contract":
        obj.billing.values["dynamic_pricing"] = True
        obj.values["dynamic_contract_mode"] = "unknown"
    if failure == "bill":
        obj.values["estimate_bill"] = "missing/bill"
    with patch.object(obj, "_today", return_value=(today, True, 0)):
        result = obj._calculate(now, start, end)
    assert result["forecast_gross_cost"] is None
    assert result["metadata"]["cost_forecast_series"] == []
    assert result["metadata"]["forecast_blockers"]


async def test_complete_costs_do_not_receive_extra_ratio_cost(hass):
    obj, now, start, end, today = projection_fixture(hass)
    obj.raw["hourly"]["sensor.external_cost"] = [
        {"start": datetime(2026, 10, 20, tzinfo=TZ).timestamp() + i * 3600, "change": 2}
        for i in range(24)
    ]
    with patch.object(obj, "_today", return_value=(today, True, 0)):
        result = obj._calculate(now, start, end)
    assert result["period_gross_cost"] == 548
    assert result["accounting_status"] == "complete"
    assert result["metadata"]["forecast_approximate"] is False
    assert result["metadata"]["estimated_history_cost"] is None


async def test_today_unpriced_tail_is_estimated_once_and_remains_incomplete(hass):
    obj, now, start, end, today = projection_fixture(hass)
    today.update(
        unpriced_kwh=1,
        unpriced_intervals=[
            {
                "start": now - timedelta(minutes=5),
                "end": now,
                "kwh": 1,
            }
        ],
    )
    with patch.object(obj, "_today", return_value=(today, False, 0)):
        result = obj._calculate(now, start, end)
    assert result["period_import_energy"] == 125
    assert result["period_gross_cost"] is None
    assert result["metadata"]["estimated_history_cost"] == pytest.approx(24 * 2.4)
    assert len(result["metadata"]["unpriced_intervals"]) == 24
    assert result["forecast_gross_cost"] is not None


async def test_legacy_bill_prefills_verified_monthly_totals(hass):
    old = {k: v for k, v in BILL.items() if k not in ("nt_kwh", "vt_kwh")}
    old["months"] = [{"month": "2024-01", "nt_kwh": 80, "vt_kwh": 20}]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            **OPTIONS,
            "settled_bills": json.dumps([old]),
        },
    )
    entry.add_to_hass(hass)
    form = await select(hass, entry, "document_bills", "0")
    keys = {str(k): k for k in form["data_schema"].schema}
    assert keys["nt_kwh"].description["suggested_value"] == 80
    assert keys["vt_kwh"].description["suggested_value"] == 20
    assert "months" not in keys


async def test_accounting_date_editor_cannot_create_price_overlap(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            **OPTIONS,
            "historical_profiles": json.dumps(
                [
                    {
                        "start": "2025-01-01",
                        "end": "2025-12-31",
                        "rates": {k: 0 for k in RATE_KEYS},
                        "source": "Test",
                    }
                ]
            ),
        },
    )
    entry.add_to_hass(hass)
    form = await choose(hass, entry, "accounting")
    before = dict(entry.options)
    result = await hass.config_entries.options.async_configure(
        form["flow_id"],
        {
            "accounting_enabled": False,
            "billing_start": "2026-04-01",
            "billing_end": "2027-03-31",
            "dynamic_contract_mode": "regular",
            "deduct_shared_income": False,
            "current_price_start": "2025-06-01",
        },
    )
    assert result["errors"]["current_price_start"] == "current_price_overlap"
    assert dict(entry.options) == before


async def test_midnight_hdo_trim_is_not_conflict_and_keeps_original_intervals(hass):
    from tests_homeassistant.test_settlement import state

    obj = adapter(hass, {})
    obj._hdo_identity = "hdo"
    updated = datetime(2026, 10, 19, 2, tzinfo=TZ)
    left = datetime(2026, 10, 19, tzinfo=TZ)
    right = datetime(2026, 10, 21, tzinfo=TZ)
    full = {
        "last_update": updated.isoformat(),
        "schedule": [
            {"start": left.isoformat(), "end": right.isoformat(), "tariff": "NT"}
        ],
    }
    trimmed = {
        **full,
        "schedule": [
            {**full["schedule"][0], "start": (left + timedelta(days=1)).isoformat()}
        ],
    }
    obj.raw = {
        "history": {
            "sensor.schedule": [
                state("sensor.schedule", "ready", updated, full),
                state("sensor.schedule", "ready", updated + timedelta(days=1), trimmed),
            ]
        }
    }
    intervals = obj._intervals(right)
    assert "hdo_schedule_conflict" not in obj._reasons
    assert intervals[0][1][0].start == left.astimezone(UTC)
    assert intervals[0][1][-1].end == right.astimezone(UTC)
