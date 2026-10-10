"""Regrese HDO v reálném testovacím HA; bez sítě a bez změny cenového API.

Testujeme nové načtení uložené konfigurace (stejná cesta jako po restartu),
pozdní vznik závislých entit, jejich nedostupnost a unload/setup při reloadu.
Plný restart produkčního procesu tento test nenahrazuje.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import template
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.dashboard import build_views
from custom_components.cez_dynamic_tariff.pricing import PROFILE_DEFAULTS

HDO = "binary_sensor.cez_hdo_lowtariffactive_test"
VALID = "binary_sensor.cez_hdo_data_valid_test"
SCHEDULE = "sensor.cez_hdo_schedule_test"
PRICE = f"sensor.{DOMAIN}_total_price"


def _hdo_sources(hass, now, state):
    """Vstupy HDO: on = NT, off = VT; platný rozvrh na následující dva dny.

    Časové značky mají UTC offset. Neznámý živý stav se nesmí ocenit ani při
    platném rozvrhu; proto jej test mění samostatně po obnově těchto vstupů.
    """
    hass.states.async_set(HDO, state)
    hass.states.async_set(VALID, "on")
    hass.states.async_set(
        SCHEDULE, "ready",
        {"last_update": now.isoformat(), "schedule": [{
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(days=2)).isoformat(),
            "tariff": "NT" if state == "on" else "VT",
        }]},
    )


@pytest.mark.parametrize("startup_state", [None, "unavailable"])
@pytest.mark.parametrize(
    ("dynamic", "nt_price", "vt_price"),
    [(True, 1.89894, 2.73624), (False, 3.42394, 4.32624)],
)
async def test_delayed_hdo_startup_reload_and_recovery(
    hass, freezer, startup_state, dynamic, nt_price, vt_price
):
    """Opožděné HDO se obnoví přes odběr událostí bez změny ID nebo cen.

    Senzor musí publikovat nakonfigurované ID i před vznikem HDO. Po reloadu
    zůstane jediný aktivní odběr zdrojů; starý koordinátor už nedostává události.
    Ruční refresh po událostech odstraní závislost testu na časovači debounceru.
    """
    freezer.move_to("2026-10-09T01:00:00+00:00")
    await hass.config.async_set_time_zone("Europe/Prague")
    now = datetime.now(UTC)
    if startup_state is not None:
        for entity_id in (HDO, VALID, SCHEDULE):
            hass.states.async_set(entity_id, startup_state)
    entry = MockConfigEntry(
        domain=DOMAIN, title="ČEZ", unique_id=DOMAIN,
        data={"name": "ČEZ", "base_price_kwh": 4.5},
        options={
            **PROFILE_DEFAULTS, "pricing_enabled": True, "dynamic_pricing": dynamic,
            "hdo_entity": HDO, "hdo_valid_entity": VALID,
            "hdo_schedule_entity": SCHEDULE,
        },
    )
    entry.add_to_hass(hass)
    content = build_views("ČEZ", "cez-test", {}, {})["config"]["views"][0][
        "sections"
    ][0]["cards"][1]["content"]
    card = template.Template(content, hass)
    assert "HDO: **neznámé**" in card.async_render(parse_result=False)
    with patch(
        "custom_components.cez_dynamic_tariff.coordinator.holidays.country_holidays",
        return_value=set(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get(PRICE)
        assert state.state == "unknown"
        assert state.attributes["hdo_entity"] == HDO
        assert state.attributes["pricing_status"] == "hdo_unavailable"
        assert "HDO: **neznámé**" in card.async_render(parse_result=False)
        registry = er.async_get(hass)
        identities = {
            item.entity_id: item.unique_id
            for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        assert identities[PRICE] == f"{entry.entry_id}_total_price"

        coordinator = entry.runtime_data
        with patch.object(
            coordinator, "async_request_refresh", wraps=coordinator.async_request_refresh
        ) as refresh:
            _hdo_sources(hass, now, "on")
            await hass.async_block_till_done()
            assert refresh.await_count >= 3
        await coordinator.async_refresh()
        assert float(hass.states.get(PRICE).state) == nt_price
        assert "HDO: **NT — nízký tarif**" in card.async_render(parse_result=False)

        with patch.object(coordinator, "async_request_refresh") as old_refresh:
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            assert entry.runtime_data is not coordinator
            assert hass.states.get(PRICE).attributes["hdo_entity"] == HDO
            _hdo_sources(hass, now, "off")
            await hass.async_block_till_done()
            old_refresh.assert_not_called()
        await entry.runtime_data.async_refresh()
        assert float(hass.states.get(PRICE).state) == vt_price
        assert "HDO: **VT — vysoký tarif**" in card.async_render(parse_result=False)
        assert identities == {
            item.entity_id: item.unique_id
            for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        }

        hass.states.async_set(HDO, "unavailable")
        await hass.async_block_till_done()
        await entry.runtime_data.async_refresh()
        assert hass.states.get(PRICE).state == "unknown"
        assert hass.states.get(PRICE).attributes["hdo_entity"] == HDO
        assert "HDO: **neznámé**" in card.async_render(parse_result=False)
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(PRICE).state == "unknown"
        _hdo_sources(hass, now, "on")
        await hass.async_block_till_done()
        await entry.runtime_data.async_refresh()
        assert float(hass.states.get(PRICE).state) == nt_price
        assert "HDO: **NT — nízký tarif**" in card.async_render(parse_result=False)
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
