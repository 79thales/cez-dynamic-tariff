"""Ověření verzovaných URL při startu HA a skutečného HTTP obsahu modulů."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.dashboard_api import (
    MODULE_PATH,
    async_setup_dashboard_generator,
)
from custom_components.cez_dynamic_tariff.frontend import async_register_card

COMPONENT = Path(__file__).parents[1] / "custom_components" / DOMAIN
MANIFEST_VERSION = json.loads(
    (COMPONENT / "manifest.json").read_text(encoding="utf-8")
)["version"]
CARD_URL = "/cez_dynamic_tariff/advances-card.js"


@pytest.mark.parametrize("version", [MANIFEST_VERSION, "1.0.11"])
async def test_startup_uses_manifest_version_and_registers_once(hass, hass_client, version):
    """Čerstvý HA načte verzi loaderu; další setup neduplikuje HTTP cestu ani URL.

    Druhý případ mění jen manifest loaderu, nikoli obsah JS, a ověřuje tak
    automatickou změnu URL pro budoucí vydání po startu nové instance HA.
    """
    assert await async_setup_component(hass, "frontend", {})
    integration = await async_get_integration(hass, DOMAIN)
    assert integration.manifest["version"] == MANIFEST_VERSION
    with patch.dict(integration.manifest, version=version):
        await async_register_card(hass)
        await async_register_card(hass)
    module_url = f"{CARD_URL}?v={version}"
    urls = hass.data[DATA_EXTRA_MODULE_URL].urls
    assert [url for url in urls if url.split("?", 1)[0] == CARD_URL] == [module_url]
    assert hass.data[DOMAIN + "_card_registered"]
    client = await hass_client(hass)
    response = await client.get(module_url)
    assert response.status == 200
    assert await response.read() == (COMPONENT / "frontend/advances-card.js").read_bytes()


@pytest.mark.parametrize("version", [MANIFEST_VERSION, "1.0.11"])
async def test_generator_also_uses_manifest_version(
    hass, hass_ws_client, hass_client, version
):
    """Druhý přibalený modul má stejný zdroj verze a zachová registraci panelu."""
    from custom_components.cez_dynamic_tariff.dashboard import PANEL_PATH

    assert await async_setup_component(hass, "frontend", {})
    integration = await async_get_integration(hass, DOMAIN)
    with patch.dict(integration.manifest, version=version):
        await async_setup_dashboard_generator(hass)
        await async_setup_dashboard_generator(hass)
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "get_panels"})
    panel = (await ws.receive_json())["result"][PANEL_PATH]
    module_url = panel["config"]["_panel_custom"]["module_url"]
    assert module_url == f"{MODULE_PATH}?v={version}"
    client = await hass_client(hass)
    response = await client.get(module_url)
    assert response.status == 200
    assert await response.read() == (
        COMPONENT / "frontend/dashboard-generator.js"
    ).read_bytes()


async def test_without_frontend_defers_registration(hass):
    """Bez UI nezůstane příznak, který by bránil pozdější registraci."""
    await async_register_card(hass)
    assert DOMAIN + "_card_registered" not in hass.data


async def test_loader_failure_allows_retry(hass):
    """Selhání loaderu nezaregistruje cestu; další setup může bezpečně uspět."""
    assert await async_setup_component(hass, "frontend", {})
    with (
        patch("homeassistant.loader.async_get_integration", side_effect=HomeAssistantError),
        pytest.raises(HomeAssistantError),
    ):
        await async_register_card(hass)
    assert DOMAIN + "_card_registered" not in hass.data
    await async_register_card(hass)
    assert f"{CARD_URL}?v={MANIFEST_VERSION}" in hass.data[DATA_EXTRA_MODULE_URL].urls
