"""Regrese retence, souběhu, options a diskových chyb na skutečném HA."""

import asyncio
import copy
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.file import WriteError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff.accounting_archive import AccountingArchive
from custom_components.cez_dynamic_tariff.accounting_storage import AccountingStore
from custom_components.cez_dynamic_tariff.band_pricing import BandPricing, record_change
from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.pricing import PROFILE_DEFAULTS
from custom_components.cez_dynamic_tariff.schedule import DEFAULT_SCHEDULES
from tests_homeassistant.test_accounting_options import OPTIONS, choose
from tests_homeassistant.test_settlement import TZ, adapter, state

NOW = datetime(2026, 10, 2, 0, 0, tzinfo=TZ)
LEFT = NOW - timedelta(days=1)


def raw_data(*, schedule=True, rows=True):
    schedule_state = state(
        "sensor.schedule",
        "ready",
        LEFT,
        {
            "last_update": LEFT.isoformat(),
            "schedule": [
                {
                    "start": LEFT.isoformat(),
                    "end": (LEFT + timedelta(days=3)).isoformat(),
                    "tariff": "NT",
                }
            ],
        },
    )
    return {
        "hourly": {
            "sensor.import": [
                {"start": LEFT.timestamp() + i * 3600, "change": 1} for i in range(24)
            ]
            if rows
            else []
        },
        "history": {"sensor.schedule": [schedule_state]} if schedule else {},
        "cost_id": "sensor.cost",
        "revenue_id": "",
        "unpriced_id": "sensor.unpriced",
        "savings_id": "sensor.savings",
        "short_today": {},
        "midnight": NOW,
        "closed_hour": NOW,
    }


async def ready(hass):
    obj = adapter(hass, {"billing_start": "2026-10-01", "billing_end": "2026-10-31"})
    obj.coordinator.hass = hass
    obj.coordinator.async_update_listeners = lambda: None
    obj.coordinator.options_snapshot = {}
    obj.billing.timeline = [
        {"start": NOW, "end": NOW + timedelta(days=2), "price_kwh": 2}
    ]
    await obj.async_initialize()
    obj._today = lambda now, schedules: (
        {
            "energy_kwh": 0,
            "unpriced_kwh": 0,
            "actual_cost": 0,
            "without_cost": 0,
            "energy_complete": True,
            "through": now.isoformat(),
        },
        True,
        0,
    )
    return obj


async def test_purge_and_restart_preserve_closed_day_and_forecast(hass):
    obj = await ready(hass)
    obj._load_raw = AsyncMock(return_value=raw_data())
    await obj.async_refresh(NOW, force=True)
    before = copy.deepcopy(obj.result)
    assert before["accounting_status"] == "complete"
    assert before["forecast_gross_cost"] is not None
    saved = obj.archive.snapshot()
    restored = await ready(hass)
    restored.archive = AccountingArchive(saved)
    # Purge odstranil HDO i energie, takže vše musí vycházet z vlastního
    # ověřeného archivu. Kontrolní odečet zde není vůbec zadán.
    restored._load_raw = AsyncMock(return_value=raw_data(schedule=False, rows=False))
    await restored.async_refresh(NOW, force=True)
    assert restored.result["period_gross_cost"] == before["period_gross_cost"]
    assert restored.result["forecast_gross_cost"] == before["forecast_gross_cost"]
    assert restored.result["metadata"]["unpriced_period_kwh"] == 0
    assert (
        restored.result["metadata"]["cost_forecast_series"]
        == before["metadata"]["cost_forecast_series"]
    )


async def test_never_known_history_is_not_fabricated_and_zero_is_valid(hass):
    obj = await ready(hass)
    obj._load_raw = AsyncMock(return_value=raw_data(schedule=False))
    await obj.async_refresh(NOW, force=True)
    assert obj.result["period_gross_cost"] is None
    assert obj.result["metadata"]["unpriced_period_kwh"] == 24
    assert "historical_hdo_missing" in obj.result["metadata"]["reason_codes"]
    zero = raw_data(schedule=False)
    for row in zero["hourly"]["sensor.import"]:
        row["change"] = 0
    obj._load_raw = AsyncMock(return_value=zero)
    await obj.async_refresh(NOW, force=True)
    assert obj.result["accounting_status"] == "complete"
    assert obj.result["metadata"]["unpriced_period_kwh"] == 0


async def test_price_activation_keeps_verified_old_cost_after_hdo_purge(hass):
    """Změna aktuální ceny nezneplatní ověřené uzavřené hodiny před aktivací."""
    obj = await ready(hass)
    obj._load_raw = AsyncMock(return_value=raw_data())
    await obj.async_refresh(NOW, force=True)
    before = obj.result["period_gross_cost"]
    saved = obj.archive.snapshot()
    updated = record_change(obj.billing.values, {**obj.billing.values, "trade_nt": 4.0},
                            PROFILE_DEFAULTS, NOW, archive_revision=obj._cost_revision,
                            archive_identity=obj._archive_source_identity)
    restored = await ready(hass)
    restored.billing.values["trade_nt"] = 4.0
    restored.billing.strategy = BandPricing(updated, PROFILE_DEFAULTS, TZ, lambda day: False,
        {k: [(r.start_minute, r.modifier_percent) for r in rows] for k, rows in DEFAULT_SCHEDULES.items()})
    restored._identities()
    restored.archive = AccountingArchive(saved)
    restored.archive.data["schedules"] = {}
    restored._load_raw = AsyncMock(return_value=raw_data(schedule=False, rows=False))
    await restored.async_refresh(NOW, force=True)
    assert restored.result["period_gross_cost"] == before
    assert restored.result["metadata"]["unpriced_period_kwh"] == 0


async def test_changed_energy_and_price_revision_do_not_reuse_old_cost(hass):
    obj = await ready(hass)
    obj._load_raw = AsyncMock(return_value=raw_data())
    await obj.async_refresh(NOW, force=True)
    original = obj.result["period_gross_cost"]
    corrected = raw_data()
    corrected["hourly"]["sensor.import"][0]["change"] = 2
    obj._load_raw = AsyncMock(return_value=corrected)
    await obj.async_refresh(NOW, force=True)
    assert obj.result["period_import_energy"] == 25
    assert obj.result["period_gross_cost"] > original
    saved = obj.archive.snapshot()
    other = await ready(hass)
    other.billing.values["trade_nt"] += 1
    other._identities()
    other.archive = AccountingArchive(saved)
    other.archive.data["schedules"] = {}
    other._load_raw = AsyncMock(return_value=raw_data(schedule=False))
    await other.async_refresh(NOW, force=True)
    assert other.result["period_gross_cost"] is None


async def test_backfill_double_press_repeat_and_partial_source(hass):
    obj = await ready(hass)
    started, release = asyncio.Event(), asyncio.Event()

    async def read(*args, **kwargs):
        started.set()
        await release.wait()
        return raw_data()

    obj._load_raw = read
    with patch(
        "custom_components.cez_dynamic_tariff.accounting_recovery.dt_util.now",
        return_value=NOW,
    ):
        assert obj.async_start_history_backfill(start=LEFT.date(), end=LEFT.date())
        await started.wait()
        assert not obj.async_start_history_backfill(start=LEFT.date(), end=LEFT.date())
        release.set()
        await obj._backfill_task
        assert obj.backfill_state["status"] == "completed"
        saved_energy = copy.deepcopy(obj.archive.data["energy"])
        saved_cost = copy.deepcopy(obj.archive.data["costs"])
        obj.async_start_history_backfill(start=LEFT.date(), end=LEFT.date())
        await obj._backfill_task
        assert obj.archive.data["energy"] == saved_energy
        assert obj.archive.data["costs"] == saved_cost
        assert obj.backfill_state["processed_blocks"] == 1
    empty = await ready(hass)
    empty._load_raw = AsyncMock(return_value=raw_data(schedule=False, rows=False))
    with patch(
        "custom_components.cez_dynamic_tariff.accounting_recovery.dt_util.now",
        return_value=NOW,
    ):
        empty.async_start_history_backfill(start=LEFT.date(), end=LEFT.date())
        await empty._backfill_task
    assert empty.backfill_state["status"] == "incomplete"
    assert empty.backfill_state["gaps"]


async def test_unload_pauses_background_job_and_leaves_options_unchanged(hass):
    obj = await ready(hass)
    before = copy.deepcopy(obj.values)
    started = asyncio.Event()

    async def read(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    obj._load_raw = read
    with patch(
        "custom_components.cez_dynamic_tariff.accounting_recovery.dt_util.now",
        return_value=NOW,
    ):
        obj.async_start_history_backfill(start=LEFT.date(), end=LEFT.date())
        await started.wait()
        await obj.async_close()
    assert obj.backfill_state["status"] == "paused"
    assert obj.backfill_state["cursor"] == LEFT.date().isoformat()
    assert obj.values == before


async def test_store_write_failure_propagates_and_forecast_is_marked_stale(hass):
    store = AccountingStore(hass, 1, "cez_write_failure_test", atomic_writes=True)
    with (
        patch(
            "homeassistant.helpers.storage.Store._async_write_data",
            side_effect=WriteError("disk full"),
        ),
        pytest.raises(HomeAssistantError, match="accounting_archive_write_failed"),
    ):
        await store.async_save({"value": 1})
    obj = await ready(hass)
    obj._load_raw = AsyncMock(return_value=raw_data())
    await obj.async_refresh(NOW, force=True)
    obj._load_raw = AsyncMock(side_effect=HomeAssistantError("Recorder unavailable"))
    await obj.async_refresh(NOW + timedelta(minutes=5), force=True)
    assert obj.result["accounting_status"] == "history_unavailable"
    assert obj.result["metadata"]["forecast_stale"]
    assert (
        obj.result["metadata"]["last_complete_forecast"]["calculated_at"]
        == NOW.isoformat()
    )
    assert "recorder_unavailable" in obj.result["metadata"]["reason_codes"]
    assert obj.archive.data["energy"]
    await obj.async_refresh(NOW + timedelta(minutes=5, seconds=5))
    assert obj.result["accounting_status"] == "history_unavailable"
    assert obj.result.get("forecast_gross_cost") is None
    assert obj._load_raw.call_count == 1


async def test_auto_history_preserves_reference_unless_explicitly_disabled(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=OPTIONS)
    entry.add_to_hass(hass)
    form = await choose(hass, entry, "accounting_history")
    form = await hass.config_entries.options.async_configure(
        form["flow_id"], {"next_step_id": "history_auto"}
    )
    await hass.config_entries.options.async_configure(form["flow_id"], {})
    assert all(entry.options[k] == OPTIONS[k] for k in OPTIONS)
    form = await choose(hass, entry, "accounting_history")
    form = await hass.config_entries.options.async_configure(
        form["flow_id"], {"next_step_id": "history_auto"}
    )
    await hass.config_entries.options.async_configure(
        form["flow_id"], {"disable_reference": True}
    )
    assert entry.options["reference_date"] == ""
    assert entry.options["reference_energy"] == OPTIONS["reference_energy"]


async def test_registry_rename_preserves_identity_and_other_meter_is_separate(hass):
    obj = await ready(hass)
    entry = MockConfigEntry(domain="test", data={})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor", "test", "meter1", suggested_object_id="import", config_entry=entry
    )
    before = obj._source_identity(entity.entity_id)
    configured = entity.entity_id
    assert obj._resolve_source(configured) == configured
    renamed = registry.async_update_entity(
        entity.entity_id, new_entity_id="sensor.renamed_import"
    )
    assert obj._source_identity(renamed.entity_id) == before
    assert obj._resolve_source(configured) == renamed.entity_id
    restored = await ready(hass)
    restored.archive = AccountingArchive(obj.archive.snapshot())
    assert restored._resolve_source(configured) == renamed.entity_id
    second = registry.async_get_or_create(
        "sensor", "test", "meter2", suggested_object_id="import2", config_entry=entry
    )
    assert obj._source_identity(second.entity_id) != before


async def test_backfill_rejects_invalid_range_before_reading(hass):
    obj = await ready(hass)
    with pytest.raises(HomeAssistantError):
        obj.async_start_history_backfill(start=date(2027, 1, 1), end=date(2026, 1, 1))
    assert obj._backfill_task is None


async def test_config_change_during_read_discards_old_result(hass):
    obj = await ready(hass)
    entry = SimpleNamespace(entry_id="changed_during_read", options={})
    obj.coordinator.entry = entry
    obj.coordinator.options_snapshot = {}
    obj.coordinator.entry.async_create_background_task = lambda hass, coro, name: (
        hass.async_create_task(coro)
    )

    async def changed(*args, **kwargs):
        entry.options = {"trade_nt": 99}
        return raw_data()

    obj._load_raw = changed
    with patch(
        "custom_components.cez_dynamic_tariff.accounting_recovery.dt_util.now",
        return_value=NOW,
    ):
        obj.async_start_history_backfill(start=LEFT.date(), end=LEFT.date())
        await obj._backfill_task
    assert obj.backfill_state["status"] == "paused"
    assert obj.archive.data["energy"] == {}
    assert obj.backfill_state["processed_blocks"] == 0


async def test_corrupt_archive_is_read_only_and_backfill_is_rejected(hass):
    obj = adapter(hass, {})
    obj._store = SimpleNamespace(
        path="missing_archive_file", async_load=AsyncMock(return_value={"schema": 999})
    )
    await obj.async_initialize()
    assert not obj._store_writable
    assert "archive_invalid" in obj._reasons
    with pytest.raises(HomeAssistantError, match="archive is invalid"):
        obj.async_start_history_backfill()


async def test_backfill_resume_cursor_repeats_only_uncommitted_block(hass):
    obj = await ready(hass)
    obj.archive.data["backfill"] = {
        "status": "paused",
        "run_id": "old_run",
        "revision": obj._cost_revision,
        "start": "2026-09-24",
        "end": "2026-10-01",
        "cursor": "2026-10-01",
        "processed_blocks": 1,
        "total_blocks": 2,
        "gaps": [],
    }
    obj._load_raw = AsyncMock(return_value=raw_data())
    with patch(
        "custom_components.cez_dynamic_tariff.accounting_recovery.dt_util.now",
        return_value=NOW,
    ):
        assert obj.async_start_history_backfill()
        await obj._backfill_task
    assert obj.backfill_state["run_id"] == "old_run"
    assert obj.backfill_state["processed_blocks"] == 2
    assert obj._load_raw.call_args_list[0].args[1].date() == date(2026, 10, 1)


async def test_invalid_edc_does_not_invalidate_gross_energy_and_cost(hass):
    obj = await ready(hass)
    obj.values["deduct_shared_income"] = True
    raw = raw_data()
    raw["revenue_id"] = "edc:income"
    raw["hourly"]["edc:income"] = [{"start": LEFT.timestamp(), "change": float("nan")}]
    obj._load_raw = AsyncMock(return_value=raw)
    await obj.async_refresh(NOW, force=True)
    assert obj.result["period_import_energy"] == 24
    assert obj.result["period_gross_cost"] is not None
    assert obj.result["forecast_gross_cost"] is not None
    assert obj.result["forecast_net_cost"] is None
    assert "income_statistics_invalid" in obj.result["metadata"]["reason_codes"]
    assert "statistics_invalid" not in obj.result["metadata"]["reason_codes"]


async def test_cancelled_save_finishes_before_shutdown_snapshot(hass):
    obj = await ready(hass)
    started, release = asyncio.Event(), asyncio.Event()
    writes = []

    async def save(snapshot):
        started.set()
        await release.wait()
        writes.append(snapshot)

    obj._store = SimpleNamespace(async_save=save)
    task = hass.async_create_task(obj._persist())
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(writes) == 1
    assert writes[0]["schema"] == 1


async def test_transient_recorder_failure_retries_bounded_then_recovers(hass):
    obj = await ready(hass)
    executor = AsyncMock(side_effect=[OSError("busy"), TimeoutError(), raw_data()])
    with (
        patch(
            "custom_components.cez_dynamic_tariff.accounting_recovery.get_instance",
            return_value=SimpleNamespace(async_add_executor_job=executor),
        ),
        patch(
            "custom_components.cez_dynamic_tariff.accounting_recovery.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
    ):
        raw = await obj._load_raw(NOW, LEFT)
        assert raw["hourly"]["sensor.import"]
        assert executor.call_count == 3
        assert [c.args[0] for c in sleep.call_args_list] == [1, 2]
        executor.reset_mock(side_effect=True)
        executor.side_effect = OSError("still unavailable")
        with pytest.raises(OSError):
            await obj._load_raw(NOW, LEFT)
        assert executor.call_count == 3


async def test_cache_expiry_uses_elapsed_utc_across_repeated_hour(hass):
    obj = await ready(hass)
    first = datetime(2026, 10, 25, 2, 55, tzinfo=TZ, fold=0)
    second = datetime(2026, 10, 25, 2, 0, tzinfo=TZ, fold=1)
    obj._last_attempt = first
    # Od prvního 02:55 k druhému 02:00 uplynulo 5 skutečných minut,
    # nikoli -55. I při chybě zdroje se musí provést nové čtení.
    obj._load_raw = AsyncMock(side_effect=HomeAssistantError("not ready"))
    await obj.async_refresh(second)
    assert obj._load_raw.call_count == 1


async def test_seasonal_energy_does_not_require_prices_outside_billing_period(hass):
    obj = await ready(hass)
    raw = raw_data()
    old = LEFT.replace(year=2025)
    raw["hourly"]["sensor.import"] += [
        {"start": old.timestamp() + i * 3600, "change": 1} for i in range(24)
    ]
    obj._load_raw = AsyncMock(return_value=raw)
    await obj.async_refresh(NOW, force=True)
    assert obj.result["accounting_status"] == "complete"
    assert obj.result["forecast_gross_cost"] is not None
    assert "historical_price_missing" not in obj.result["metadata"]["reason_codes"]


@pytest.mark.parametrize("arguments", [({"value": 1},), ("/storage/test", {"value": 1})])
@pytest.mark.parametrize("write_fails", [False, True])
async def test_storage_hook_preserves_ha_call_shape(hass, arguments, write_fails):
    """HA 2025/2026 musí dostat původní argumenty; chyba se nesmí skrýt.

    Rozdílné interní rozhraní zůstává v nadřazeném Store. Adaptér pouze
    zachová volání a převede diskovou chybu na potvrzené selhání zápisu.
    """
    store = AccountingStore(hass, 1, "cez_storage_signature_test", atomic_writes=True)
    with patch(
        "homeassistant.helpers.storage.Store._async_write_data",
        new_callable=AsyncMock,
        side_effect=WriteError("disk full") if write_fails else None,
    ) as writer:
        if write_fails:
            with pytest.raises(HomeAssistantError, match="accounting_archive_write_failed"):
                await store._async_write_data(*arguments)
        else:
            await store._async_write_data(*arguments)
        writer.assert_awaited_once_with(*arguments)


async def test_actual_store_round_trip_preserves_verified_hour(hass):
    """Skutečný atomický Store uloží archiv a nová instance obnoví tutéž hodinu.

    Ověřujeme veřejné async_save/async_load celé podporované verze HA,
    takže nekompatibilní interní podpis nebo ztracené potvrzení zápisu
    zachytí také CI matice, nejen test adaptéru s náhradním zapisovačem.
    """
    archive = AccountingArchive()
    stamp = LEFT.timestamp()
    archive.merge_energy("meter", [{"start": stamp, "change": 2.5}])
    archive.save_cost("revision", stamp, 2.5, 9.25, "historical_hdo")
    store = AccountingStore(hass, 1, "cez_archive_roundtrip_test", private=True, atomic_writes=True)
    await store.async_save(archive.snapshot())
    restored_store = AccountingStore(hass, 1, "cez_archive_roundtrip_test", private=True, atomic_writes=True)
    restored = AccountingArchive(await restored_store.async_load())
    assert restored.energy_rows("meter", stamp, stamp + 3600) == [
        {"start": stamp, "end": stamp + 3600, "change": 2.5}
    ]
    assert restored.cost("revision", stamp, 2.5) == 9.25
