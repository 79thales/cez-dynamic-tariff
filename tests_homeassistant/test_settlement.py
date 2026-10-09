"""History reuse and options tested against real HA state objects."""

import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import State
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff.billing import ElectricityBilling
from custom_components.cez_dynamic_tariff.config_flow import CezDynamicTariffOptionsFlow
from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.pricing import PROFILE_DEFAULTS, PriceProfile
from custom_components.cez_dynamic_tariff.sensor import _invoice_price
from custom_components.cez_dynamic_tariff.settlement import SETTLEMENT_DEFAULTS
from custom_components.cez_dynamic_tariff.settlement_history import SettlementHistory

TZ = ZoneInfo("Europe/Prague")


def test_invoice_price_reuses_selected_existing_price_and_rejects_unknown_contract():
    billing = {
        "total_price": 5,
        "price_without_dynamic": 4,
        "metadata": {"dynamic_pricing": True},
        "settlement": {"metadata": {"dynamic_contract_mode": "unknown"}},
    }
    data = SimpleNamespace(billing=billing)
    assert _invoice_price(data) is None
    billing["settlement"]["metadata"]["dynamic_contract_mode"] = "trial"
    assert _invoice_price(data) == 4
    billing["settlement"]["metadata"]["dynamic_contract_mode"] = "regular"
    assert _invoice_price(data) == 5
    billing["metadata"]["dynamic_pricing"] = False
    assert _invoice_price(data) == 4


@pytest.fixture
def mock_recorder_before_hass(recorder_db_url):
    """Prepare the test database before HA's autouse integration fixture."""
    yield


async def test_enabled_accounting_lifecycle_reads_real_recorder_and_adds_only_new_entities(
    recorder_mock, hass, freezer
):
    freezer.move_to("2026-10-09T08:00:00+00:00")
    await hass.config.async_set_time_zone("Europe/Prague")
    now = datetime.now(ZoneInfo("UTC"))
    hass.states.async_set("binary_sensor.hdo_test", "on")
    hass.states.async_set("binary_sensor.valid_test", "on")
    hass.states.async_set(
        "sensor.schedule_test",
        "ready",
        {
            "last_update": now.isoformat(),
            "schedule": [
                {
                    "start": (now - timedelta(hours=12)).isoformat(),
                    "end": (now + timedelta(days=2)).isoformat(),
                    "tariff": "NT",
                }
            ],
        },
    )
    hass.states.async_set(
        "sensor.import_test",
        100,
        {
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="Tariff",
        data={"name": "Tariff"},
        options={
            **PROFILE_DEFAULTS,
            "pricing_enabled": True,
            "accounting_enabled": True,
            "hdo_entity": "binary_sensor.hdo_test",
            "hdo_valid_entity": "binary_sensor.valid_test",
            "hdo_schedule_entity": "sensor.schedule_test",
            "import_energy_entity": "sensor.import_test",
            "current_price_start": "2026-04-01",
            "dynamic_start": "2025-11-01",
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.cez_dynamic_tariff.coordinator.holidays.country_holidays",
        return_value=set(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    states = [
        s
        for s in hass.states.async_all()
        if s.entity_id.startswith((f"sensor.{DOMAIN}_", f"binary_sensor.{DOMAIN}_"))
    ]
    assert len(states) == 57
    assert hass.states.get(f"sensor.{DOMAIN}_accounting_status").state == "incomplete"
    assert hass.states.get(f"sensor.{DOMAIN}_actual_cost").state == "0.0"
    assert hass.states.get(f"sensor.{DOMAIN}_daily_cost_backfilled").state == "unknown"
    assert await hass.config_entries.async_unload(entry.entry_id)


def adapter(hass, options):
    config = {
        **SETTLEMENT_DEFAULTS,
        "accounting_enabled": True,
        "current_price_start": "2026-04-01",
        "dynamic_start": "2025-11-01",
        "dynamic_contract_mode": "regular",
        **options,
    }
    coordinator = SimpleNamespace(
        _option=lambda k, d: config.get(k, d),
        _local_tz=lambda: TZ,
        _current_window=lambda when: SimpleNamespace(modifier_percent=-10),
    )
    values = {
        **PROFILE_DEFAULTS,
        "dynamic_pricing": True,
        "import_energy_entity": "sensor.import",
        "hdo_schedule_entity": "sensor.schedule",
    }
    billing = SimpleNamespace(
        hass=hass,
        coordinator=coordinator,
        values=values,
        profile=PriceProfile(values),
        _meter_value=ElectricityBilling._meter_value,
        status="ok",
        timeline=[],
    )
    obj = SettlementHistory(billing)
    return obj


def state(entity, value, when, attributes=None):
    return State(
        entity, str(value), attributes or {}, last_updated=when, last_changed=when
    )


async def test_today_backfill_reuses_existing_cost_without_adding_twice(hass):
    now = datetime(2026, 10, 9, 0, 10, tzinfo=TZ)
    obj = adapter(hass, {})
    midnight = now.replace(minute=0)
    schedule = state(
        "sensor.schedule",
        "ready",
        midnight,
        {
            "last_update": midnight.isoformat(),
            "schedule": [
                {
                    "start": midnight.isoformat(),
                    "end": (midnight + timedelta(days=2)).isoformat(),
                    "tariff": "NT",
                }
            ],
        },
    )
    samples = [
        state(
            "sensor.import",
            n,
            midnight + timedelta(minutes=i * 5),
            {"unit_of_measurement": "kWh"},
        )
        for i, n in enumerate([100, 101, 103])
    ]
    costs = [
        state(f"sensor.{DOMAIN}_actual_cost", n, midnight + timedelta(minutes=i * 5))
        for i, n in enumerate([20, 22, 27])
    ]
    obj.raw = {
        "midnight": midnight,
        "cost_id": f"sensor.{DOMAIN}_actual_cost",
        "history": {
            "sensor.import": samples,
            "sensor.schedule": [schedule],
            f"sensor.{DOMAIN}_actual_cost": costs,
        },
    }
    totals, complete, reused = obj._today(now, obj._intervals(now))
    assert complete
    assert totals["energy_kwh"] == 3
    assert (
        totals["actual_cost"] == 7
    )  # Already computed source, not 7 + reconstructed cost.
    assert reused == 2


async def test_missing_history_gap_and_reset_are_not_free_energy(hass):
    now = datetime(2026, 10, 9, 0, 30, tzinfo=TZ)
    obj = adapter(hass, {})
    midnight = now.replace(minute=0)
    samples = [
        state("sensor.import", 100, midnight, {"unit_of_measurement": "kWh"}),
        state("sensor.import", 105, now, {"unit_of_measurement": "kWh"}),
    ]
    obj.raw = {
        "midnight": midnight,
        "cost_id": "sensor.cost",
        "history": {"sensor.import": samples},
    }
    totals, complete, _ = obj._today(now, [])
    assert not complete
    assert totals["unpriced_kwh"] == 5


async def test_trial_reuses_baseline_cost_and_leaves_refund_separate(hass):
    now = datetime(2026, 10, 9, 0, 5, tzinfo=TZ)
    midnight = now.replace(minute=0)
    obj = adapter(hass, {"dynamic_contract_mode": "trial"})
    cost_id, savings_id = (
        f"sensor.{DOMAIN}_actual_cost",
        f"sensor.{DOMAIN}_realized_savings",
    )
    obj.raw = {
        "midnight": midnight,
        "cost_id": cost_id,
        "savings_id": savings_id,
        "history": {
            "sensor.import": [
                state("sensor.import", n, when, {"unit_of_measurement": "kWh"})
                for n, when in [(100, midnight), (101, now)]
            ],
            cost_id: [
                state(cost_id, n, when) for n, when in [(20, midnight), (22, now)]
            ],
            savings_id: [
                state(savings_id, n, when) for n, when in [(2, midnight), (3, now)]
            ],
        },
    }
    totals, complete, reused = obj._today(now, [])
    assert complete  # The monetary source already knows the price; no repricing.
    assert reused == 1
    assert totals["actual_cost"] == 3
    assert totals["without_cost"] == 3
    with patch(
        "custom_components.cez_dynamic_tariff.settlement_history.price_timeline",
        return_value=[],
    ) as timeline:
        obj._timeline(now.date(), [], now)
        assert timeline.call_args.args[5] is False


async def test_five_minute_statistics_preserve_zero_import_and_reuse_cost(hass):
    midnight = datetime(2026, 10, 9, tzinfo=TZ)
    now = midnight + timedelta(minutes=11)
    obj = adapter(hass, {})
    cost_id, savings_id, unpriced_id = (
        f"sensor.{DOMAIN}_{key}"
        for key in ("actual_cost", "realized_savings", "unpriced_energy")
    )
    energy = [
        {"start": midnight.timestamp() + i * 300, "change": value, "state": 100 + value}
        for i, value in enumerate([1, 2])
    ]
    obj.raw = {
        "midnight": midnight,
        "history": {},
        "cost_id": cost_id,
        "savings_id": savings_id,
        "unpriced_id": unpriced_id,
        "short_today": {
            "sensor.import": energy,
            cost_id: [{**r, "change": 5} for r in energy],
            savings_id: [{**r, "change": 1} for r in energy],
            unpriced_id: [{**r, "change": 0} for r in energy],
        },
    }
    timeline = [
        {
            "start": midnight.astimezone(ZoneInfo("UTC")),
            "end": now.astimezone(ZoneInfo("UTC")),
            "price_kwh": 3,
            "without_dynamic_kwh": 4,
            "with_dynamic_kwh": 3,
        }
    ]
    with patch.object(obj, "_timeline", return_value=timeline):
        totals, complete, reused = obj._today(now, [])
    assert complete
    assert totals["energy_kwh"] == 3
    assert (
        totals["actual_cost"] == 8
    )  # First partial source bin reconstructed, second reused.
    assert reused == 1
    obj.raw["short_today"]["sensor.import"] = [{**r, "change": 0} for r in energy]
    obj.raw["short_today"][cost_id] = []
    with patch.object(obj, "_timeline", return_value=timeline):
        totals, complete, _ = obj._today(now, [])
    assert complete
    assert totals["energy_kwh"] == 0
    assert totals["actual_cost"] == 0


async def test_edc_financial_statistic_is_selected_directly(hass):
    obj = adapter(hass, {"shared_income_entity": "sensor.edc_source"})
    hass.states.async_set(
        "sensor.edc_source",
        "2026-07-01",
        {"energy_revenue_statistic_id": "edc_sharing:test_revenue"},
    )
    assert obj._revenue_id() == "edc_sharing:test_revenue"
    with (
        patch(
            "custom_components.cez_dynamic_tariff.settlement_history.get_metadata",
            return_value={
                "sensor.import": (1, {"has_sum": True, "unit_of_measurement": "kWh"}),
                "edc_sharing:test_revenue": (
                    2,
                    {"has_sum": True, "unit_of_measurement": "CZK"},
                ),
            },
        ),
        patch(
            "custom_components.cez_dynamic_tariff.settlement_history.statistics_during_period",
            return_value={},
        ) as stats,
        patch(
            "custom_components.cez_dynamic_tariff.settlement_history.get_significant_states",
            return_value={},
        ),
    ):
        obj._read(
            datetime(2026, 10, 9, tzinfo=TZ),
            datetime(2026, 4, 1, tzinfo=TZ),
            obj._revenue_id(),
        )
        assert stats.call_args.args[3] == {"sensor.import", "edc_sharing:test_revenue"}
        assert stats.call_args_list[0].args[6] == {"change"}
        assert stats.call_args_list[1].args[6] == {"change", "state"}


async def test_historical_dynamic_date_and_price_validity(hass):
    obj = adapter(hass, {})
    assert obj._profile_at(date(2026, 3, 31)) is None
    assert obj._profile_at(date(2026, 4, 1)) is obj.billing.profile
    now = datetime(2026, 10, 9, tzinfo=TZ)
    with (
        patch.object(obj, "_profile_at", return_value=obj.billing.profile),
        patch(
            "custom_components.cez_dynamic_tariff.settlement_history.price_timeline",
            return_value=[],
        ) as timeline,
    ):
        obj._timeline(date(2025, 10, 31), [], now)
        assert timeline.call_args.args[5] is False
        obj._timeline(date(2025, 11, 1), [], now)
        assert timeline.call_args.args[5] is True


async def test_accounting_options_preserve_original_values_and_unpaid_months(hass):
    old = {
        "pricing_enabled": True,
        "base_price_kwh": 99,
        "winter_workday_schedule": "00:00=-50",
    }
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=old)
    flow = CezDynamicTariffOptionsFlow(entry)
    flow.hass = hass
    first = await flow.async_step_init({"configure_accounting": True})
    assert first["step_id"] == "accounting"
    result = await flow.async_step_accounting(
        {
            "accounting_enabled": True,
            "billing_start": "2026-04-01",
            "billing_end": "2027-03-31",
            "advance_mode": "monthly",
            "deduct_shared_income": False,
        }
    )
    assert result["step_id"] == "monthly_advances"
    result = await flow.async_step_advances(
        {
            "month_2_amount": 100,
            "month_2_paid": True,
            "month_3_amount": 80,
            "month_3_paid": False,
        }
    )
    assert result["step_id"] == "accounting_history"
    result = await flow.async_step_accounting_history(
        {
            "reference_energy": 0,
            "reference_cost": 0,
            "settled_bills": "[]",
            "historical_profiles": "[]",
        }
    )
    assert result["type"] == "create_entry"
    assert all(result["data"][k] == v for k, v in old.items())
    rows = json.loads(result["data"]["monthly_advances"])
    assert rows == [
        {"month": "2026-05", "amount": 100, "paid": True},
        {"month": "2026-06", "amount": 80, "paid": False},
    ]


async def test_provider_checkpoint_fees_and_edc_revenue_are_counted_once(hass):
    now = datetime(2026, 10, 2, 12, tzinfo=TZ)
    obj = adapter(
        hass,
        {
            "reference_date": "2026-09-30",
            "reference_period_start": "2026-09-01",
            "reference_energy": 100,
            "reference_cost": 2000,
            "historical_cost_entity": "sensor.verified_import_cost",
            "advance_total": 5000,
            "advance_paid": 1000,
            "deduct_shared_income": True,
        },
    )
    left = datetime(2026, 10, 1, tzinfo=TZ)
    energy = [{"start": left.timestamp() + i * 3600, "change": 1} for i in range(24)]
    obj.raw = {
        "hourly": {
            "sensor.import": energy,
            "sensor.verified_import_cost": [{**r, "change": 2} for r in energy],
            "edc:test_income": [{"start": left.timestamp(), "change": 10}],
        },
        "history": {},
        "cost_id": "sensor.verified_import_cost",
        "revenue_id": "edc:test_income",
        "unpriced_id": "sensor.unpriced",
    }
    obj.last_read = now
    obj.billing.timeline = [
        {"start": left, "end": left + timedelta(days=2), "price_kwh": 2}
    ]
    with patch.object(
        obj,
        "_today",
        return_value=(
            {"energy_kwh": 1, "unpriced_kwh": 0, "actual_cost": 3, "without_cost": 4},
            True,
            1,
        ),
    ):
        result = obj._calculate(now, date(2026, 9, 1), date(2026, 10, 3))
    fee = obj.billing.profile.monthly / 31
    assert result["period_import_energy"] == 125
    assert result["period_gross_cost"] == pytest.approx(2000 + 48 + 3 + 2 * fee)
    assert result["metadata"]["reused_cost_hours"] == 24
    assert result["forecast_net_cost"] == pytest.approx(
        2000 + 48 + 3 + 3 * fee + 48 + 24 - 10
    )
    assert result["forecast_balance"] == pytest.approx(
        5000 - result["forecast_net_cost"]
    )
    assert result["advance_payments_paid"] == 1000
    assert result["daily_shared_income"] is None  # Yesterday is not today's revenue.
    assert result["daily_net_cost"] is None


async def test_settled_bill_replaces_missing_history_and_supplies_seasonality(hass):
    now = datetime(2026, 10, 9, tzinfo=TZ)
    archive = [
        {
            "start": "2024-04-01",
            "end": "2025-03-31",
            "energy_kwh": 1200,
            "cost": 5000,
            "paid": 6000,
            "fixed_cost": 1000,
            "months": [
                {"month": f"2024-{month:02}", "nt_kwh": 90, "vt_kwh": 10}
                for month in range(4, 13)
            ]
            + [
                {"month": f"2025-{month:02}", "nt_kwh": 90, "vt_kwh": 10}
                for month in range(1, 4)
            ],
        }
    ]
    obj = adapter(hass, {"settled_bills": json.dumps(archive)})
    obj.raw = {
        "hourly": {},
        "history": {},
        "cost_id": "sensor.cost",
        "revenue_id": "",
        "unpriced_id": "sensor.unpriced",
    }
    obj.last_read = now
    with patch.object(
        obj,
        "_today",
        return_value=(
            {"energy_kwh": 0, "unpriced_kwh": 0, "actual_cost": 0, "without_cost": 0},
            False,
            0,
        ),
    ):
        result = obj._calculate(now, date(2024, 4, 1), date(2025, 3, 31))
    assert result["period_gross_cost"] == 5000
    assert result["period_import_energy"] == 1200
    assert all(
        r["source"] == "settled_bill" for r in result["metadata"]["consumption_profile"]
    )
