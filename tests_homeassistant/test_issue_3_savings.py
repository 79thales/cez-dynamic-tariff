"""Regrese úspor při obnovách cen, výpadcích a znovunačtení integrace."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.pricing import PROFILE_DEFAULTS

HDO = "binary_sensor.issue3_hdo"
VALID = "binary_sensor.issue3_hdo_valid"
SCHEDULE = "sensor.issue3_hdo_schedule"
METER = "sensor.issue3_import"
PREFIX = f"sensor.{DOMAIN}_"
SAVINGS = ("dynamic_savings", "realized_savings", "daily_savings")


@pytest.fixture(autouse=True)
def no_external_holidays():
    """Výpočet použije místní kalendář a nevyžaduje vnější závislosti."""
    with patch(
        "custom_components.cez_dynamic_tariff.coordinator.holidays.country_holidays",
        return_value=set(),
    ):
        yield


async def setup_pricing(hass: HomeAssistant, freezer, tariff="NT", meter="17000"):
    """Nastaví lokální cenový profil, spojitý rozvrh HDO a počáteční stav kWh."""
    freezer.move_to("2026-10-09T01:00:00+00:00")
    await hass.config.async_set_time_zone("Europe/Prague")
    now = datetime.now(UTC)
    hass.states.async_set(HDO, "on" if tariff == "NT" else "off")
    hass.states.async_set(VALID, "on")
    hass.states.async_set(
        SCHEDULE,
        "ready",
        {
            "last_update": now.isoformat(),
            "schedule": [
                {
                    "start": (now - timedelta(hours=3)).isoformat(),
                    "end": (now + timedelta(days=3)).isoformat(),
                    "tariff": tariff,
                }
            ],
        },
    )
    hass.states.async_set(METER, meter, {"unit_of_measurement": "kWh"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Tariff",
        unique_id=DOMAIN,
        data={"name": "Tariff", "base_price_kwh": 4.5},
        options={
            **PROFILE_DEFAULTS,
            "pricing_enabled": True,
            "dynamic_pricing": True,
            # Vypnutí stálých plateb zjednoduší očekávaný rozdíl pouze na Kč/kWh.
            "include_standing_fees": False,
            "hdo_entity": HDO,
            "hdo_valid_entity": VALID,
            "hdo_schedule_entity": SCHEDULE,
            "import_energy_entity": METER,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def refresh(hass, entry):
    """Vynutí výpočet při zmrazeném času a propíše výsledky do entit."""
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


def assert_numeric_savings(hass, expected):
    """Ověří hodnoty všech veřejných úspor v Kč i úplnost jejich podkladů."""
    for name in SAVINGS:
        state = hass.states.get(PREFIX + name)
        assert state.state not in ("unknown", "unavailable"), (
            f"{name}: {state.state}; neoceněno "
            f"{state.attributes['unpriced_energy_kwh']!r} kWh"
        )
        assert float(state.state) == pytest.approx(expected, abs=1e-6)
        assert state.attributes["unit_of_measurement"] == "CZK"
        assert state.attributes["comparison_complete"] is True


@pytest.mark.parametrize(
    ("tariff", "price", "saving"), [("NT", 1.89894, 1.525), ("VT", 2.73624, 1.59)]
)
async def test_fragmented_price_refresh_meter_lifecycle(
    hass: HomeAssistant, freezer, tariff, price, saving
):
    """Minutové obnovy nesmí znehodnotit opakované pětiminutové odečty."""
    entry = await setup_pricing(hass, freezer, tariff)
    registry = er.async_get(hass)
    identities = {name: registry.async_get(PREFIX + name).unique_id for name in SAVINGS}
    assert entry.runtime_data.update_interval == timedelta(seconds=60)
    assert_numeric_savings(hass, 0)
    for cycle in range(3):
        # Úmyslně začínáme v t+1 s: hrany 0, 1, 61, 121, 181, 241, 300 s
        # vyvolávaly chybu zaokrouhlení v součtu zlomků před opravou.
        for index, seconds in enumerate((1, 60, 60, 60, 60)):
            freezer.tick(timedelta(seconds=seconds))
            if cycle == 0 and index == 1:
                # Jednu obnovu vyvolá skutečný časovač koordinátoru HA.
                async_fire_time_changed(hass, datetime.now(UTC))
                await hass.async_block_till_done()
                assert entry.runtime_data.billing.last_pricing_refresh == datetime.now(
                    UTC
                )
            else:
                await refresh(hass, entry)
            if cycle == 1 and index == 2:
                # Reload proběhne uprostřed rozpracovaného odečtu, jehož časové
                # hranice a počáteční stav se musí obnovit z uložených údajů.
                assert await hass.config_entries.async_reload(entry.entry_id)
                await hass.async_block_till_done()
            if cycle == 2 and index == 2:
                # Odpojení a nové sestavení integrace ověří obnovu ze Store;
                # proces Home Assistantu se v tomto testu nerestartuje.
                assert await hass.config_entries.async_unload(entry.entry_id)
                assert await hass.config_entries.async_setup(entry.entry_id)
                await hass.async_block_till_done()
        if cycle == 0:
            start, _, rows, _ = entry.runtime_data.billing.ledger.previous
            fragments = [
                row
                for row in rows
                if row["start"] >= start
                and row["start"] < start + timedelta(seconds=300)
            ]
            assert [
                int((row["start"] - start).total_seconds()) for row in fragments
            ] == [0, 1, 61, 121, 181, 241]
        freezer.tick(timedelta(seconds=59))
        hass.states.async_set(METER, str(17001 + cycle), {"unit_of_measurement": "kWh"})
        await hass.async_block_till_done()
        await refresh(hass, entry)
        assert_numeric_savings(hass, (cycle + 1) * saving)
        assert entry.runtime_data.billing.ledger.totals["unpriced_kwh"] == 0
        assert float(hass.states.get(PREFIX + "actual_cost").state) == pytest.approx(
            (cycle + 1) * price, abs=1e-6
        )
    for name in SAVINGS:
        assert registry.async_get(PREFIX + name).unique_id == identities[name]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_hdo_price_gap_remains_unknown_after_restore(hass, freezer):
    """Skutečný minutový výpadek cen HDO zůstane neoceněný i po obnově."""
    entry = await setup_pricing(hass, freezer)
    freezer.tick(timedelta(seconds=60))
    hass.states.async_set(VALID, "off")
    await hass.async_block_till_done()
    await refresh(hass, entry)
    assert hass.states.get(PREFIX + "total_price").state == "unknown"
    freezer.tick(timedelta(seconds=60))
    hass.states.async_set(VALID, "on")
    await hass.async_block_till_done()
    await refresh(hass, entry)
    freezer.tick(timedelta(seconds=180))
    hass.states.async_set(METER, "17001", {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()
    await refresh(hass, entry)
    assert entry.runtime_data.billing.ledger.totals["unpriced_kwh"] == pytest.approx(
        0.2
    )
    for name in SAVINGS:
        assert hass.states.get(PREFIX + name).state == "unknown"
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    for name in SAVINGS:
        assert hass.states.get(PREFIX + name).state == "unknown"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("invalid", "unit"),
    [
        ("unknown", "kWh"),
        ("unavailable", "kWh"),
        ("nan", "kWh"),
        ("invalid", "kWh"),
        ("-1", "kWh"),
        ("2", "W"),
    ],
)
async def test_invalid_meter_breaks_baseline_without_inventing_energy(
    hass, freezer, invalid, unit
):
    """Neplatný stav přeruší odečty; neznámou spotřebu nelze dopočítat jako nulu."""
    entry = await setup_pricing(hass, freezer)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set(METER, invalid, {"unit_of_measurement": unit})
    await hass.async_block_till_done()
    await refresh(hass, entry)
    assert entry.runtime_data.billing.ledger.previous is None
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set(METER, "17001", {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()
    await refresh(hass, entry)
    assert entry.runtime_data.billing.ledger.totals["energy_kwh"] == 0
    assert entry.runtime_data.billing.ledger.totals["actual_cost"] == 0
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set(METER, "17002", {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()
    await refresh(hass, entry)
    assert entry.runtime_data.billing.ledger.totals["energy_kwh"] == pytest.approx(1)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_zero_reading_is_valid_and_long_interval_stays_unpriced(hass, freezer):
    """Nula je platný odečet, interval nad 15 minut ale nemá spolehlivou cenu."""
    entry = await setup_pricing(hass, freezer, meter="0")
    assert_numeric_savings(hass, 0)
    # Změna textu stavu z 0 na 0.0 vyvolá událost, ale přírůstek je stále 0 kWh.
    # Cenu před tím fragmentujeme stejně jako u původního pětiminutového případu.
    for seconds in (1, 60, 60, 60, 60):
        freezer.tick(timedelta(seconds=seconds))
        await refresh(hass, entry)
    freezer.tick(timedelta(seconds=59))
    hass.states.async_set(METER, "0.0", {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()
    await refresh(hass, entry)
    ledger = entry.runtime_data.billing.ledger
    assert ledger.previous[0] == datetime.now(UTC)
    assert ledger.totals["energy_kwh"] == 0
    assert ledger.totals["unpriced_kwh"] == 0
    assert_numeric_savings(hass, 0)
    freezer.tick(timedelta(seconds=901))
    hass.states.async_set(METER, "1", {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()
    await refresh(hass, entry)
    assert entry.runtime_data.billing.ledger.totals["unpriced_kwh"] == 1
    for name in SAVINGS:
        assert hass.states.get(PREFIX + name).state == "unknown"
    assert await hass.config_entries.async_unload(entry.entry_id)
