"""Ověření načtení editoru přes skutečný HTTP server a registr zdrojů HA."""

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, add_extra_js_url
from homeassistant.components.lovelace.resources import ResourceYAMLCollection
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from custom_components.cez_dynamic_tariff.const import DOMAIN
from custom_components.cez_dynamic_tariff.frontend import (
    CARD_FILE,
    CARD_URL,
    _async_register_lovelace_resource,
    async_register_card,
)

MANIFEST_VERSION = json.loads(
    (Path(__file__).parents[1] / "custom_components/cez_dynamic_tariff/manifest.json")
    .read_text(encoding="utf-8")
)["version"]
MODULE_URL = f"{CARD_URL}?v={MANIFEST_VERSION}"


def lovelace_field(hass, key):
    """Číst pole slovníku HA 2025 i datového objektu novějších verzí."""
    data = hass.data["lovelace"]
    return data[key] if isinstance(data, Mapping) else getattr(data, key)


async def test_card_registers_once_with_http_and_keeps_dashboard(hass, hass_client):
    """Souběžný setup a reload nesmí duplikovat cestu, zdroj ani pohledy."""
    assert await async_setup_component(hass, "frontend", {})
    resources = lovelace_field(hass, "resources")
    overview = lovelace_field(hass, "dashboards")[None]
    original = {"title": "Dům", "views": [{"path": "home", "cards": []}]}
    await overview.async_save(original)
    await asyncio.gather(async_register_card(hass), async_register_card(hass))
    await async_register_card(hass)
    assert resources.async_items() == [
        {"id": resources.async_items()[0]["id"], "url": MODULE_URL, "type": "module"}
    ]
    assert MODULE_URL in hass.data[DATA_EXTRA_MODULE_URL].urls
    assert await overview.async_load(False) == original
    client = await hass_client(hass)
    response = await client.get(MODULE_URL)
    assert response.status == 200
    assert 'customElements.define("cez-advances-card"' in await response.text()


async def test_restart_loads_stored_resource_then_updates_same_id(hass, hass_storage):
    """Čtení uložených položek před změnou zachová ID i nesouvisející zdroje."""
    hass_storage["lovelace_resources"] = {
        "version": 1,
        "minor_version": 1,
        "key": "lovelace_resources",
        "data": {
            "items": [
                {"id": "cez", "url": CARD_URL + "?v=1.0.8", "type": "js"},
                {"id": "other", "url": "/local/user.js", "type": "module"},
            ]
        },
    }
    assert await async_setup_component(hass, "frontend", {})
    await async_register_card(hass)
    assert lovelace_field(hass, "resources").async_items() == [
        {"id": "cez", "url": MODULE_URL, "type": "module"},
        {"id": "other", "url": "/local/user.js", "type": "module"},
    ]
    # Reload napraví i zdroj, který byl odstraněn po první registraci HTTP cesty.
    resources = lovelace_field(hass, "resources")
    await resources.async_delete_item("cez")
    await async_register_card(hass)
    assert len(resources.async_items()) == 2
    assert sum(item["url"] == MODULE_URL for item in resources.async_items()) == 1


async def test_new_lovelace_data_object_uses_same_collection(hass):
    """Novější datový tvar HA má sdílet tutéž kolekci jako starší slovník."""
    assert await async_setup_component(hass, "frontend", {})
    await hass.async_block_till_done()
    original = hass.data["lovelace"]
    resources = lovelace_field(hass, "resources")
    hass.data["lovelace"] = SimpleNamespace(resources=resources)
    try:
        await _async_register_lovelace_resource(hass, MODULE_URL)
        assert len(resources.async_items()) == 1
        assert resources.async_items()[0]["url"] == MODULE_URL
    finally:
        hass.data["lovelace"] = original
    # Registr HA ukládá změny odloženě. Test dokončí skutečný zápis a ověří
    # zachování položek na disku, aby při ukončení nezůstal aktivní časovač.
    await resources.store.async_save({"items": resources.async_items()})
    assert (await resources.store.async_load())["items"] == resources.async_items()
    await hass.async_block_till_done()


async def test_yaml_resources_are_preserved_with_extra_module_fallback(hass, caplog):
    """Ruční YAML zůstává beze změny a log uvádí použitelnou adresu modulu."""
    assert await async_setup_component(hass, "frontend", {})
    yaml = [{"url": "/local/user.js", "type": "module"}]
    original = hass.data["lovelace"]
    hass.data["lovelace"] = SimpleNamespace(resources=ResourceYAMLCollection(yaml))
    await async_register_card(hass)
    hass.data["lovelace"] = original
    assert yaml == [{"url": "/local/user.js", "type": "module"}]
    assert MODULE_URL in hass.data[DATA_EXTRA_MODULE_URL].urls
    assert MODULE_URL in caplog.text


async def test_resource_failure_does_not_stop_setup_and_reload_retries(hass, caplog):
    """Chyba registru se přizná; zachovaný HTTP endpoint dovolí pozdější opravu."""
    assert await async_setup_component(hass, "frontend", {})
    resources = lovelace_field(hass, "resources")
    with patch.object(resources, "async_load", side_effect=HomeAssistantError("disk")):
        await async_register_card(hass)
    assert "registrace zdroje Lovelace selhala" in caplog.text
    assert hass.data[DOMAIN + "_card_registered"]
    assert not resources.loaded
    await async_register_card(hass)
    assert resources.async_items()[0]["url"] == MODULE_URL


async def test_no_frontend_defers_registration(hass):
    """Bez UI se nevytváří cesta ani příznak bránící pozdějšímu setupu."""
    await async_register_card(hass)
    assert DOMAIN + "_card_registered" not in hass.data


@pytest.mark.parametrize("version", [MANIFEST_VERSION, "99.8.7"])
async def test_changed_manifest_updates_cache_and_keeps_resource_id(
    hass, hass_client, version
):
    """Vydání změní URL, zachová ID zdroje a odstraní pouze staré vlastní URL.

    Skutečný loader HA poskytuje manifest; obě načítací cesty musejí
    použít stejnou verzi. Cizí zdroj a obsah přibaleného JS se zachovají.
    """
    assert await async_setup_component(hass, "frontend", {})
    add_extra_js_url(hass, CARD_URL + "?v=1.0.8")
    add_extra_js_url(hass, "/local/other.js")
    await async_register_card(hass)
    resources = lovelace_field(hass, "resources")
    original = dict(resources.async_items()[0])
    integration = await async_get_integration(hass, DOMAIN)
    with patch.dict(integration.manifest, {"version": version}):
        await async_register_card(hass)
    current = resources.async_items()[0]
    assert current["id"] == original["id"]
    assert current["url"] == f"{CARD_URL}?v={version}"
    assert len(resources.async_items()) == 1
    extra_urls = hass.data[DATA_EXTRA_MODULE_URL].urls
    assert current["url"] in extra_urls
    if version != MANIFEST_VERSION:
        assert original["url"] not in extra_urls
    assert CARD_URL + "?v=1.0.8" not in extra_urls
    assert "/local/other.js" in extra_urls
    client = await hass_client(hass)
    response = await client.get(current["url"])
    assert response.status == 200
    assert await response.read() == CARD_FILE.read_bytes()


@pytest.mark.parametrize("version", [MANIFEST_VERSION, "99.8.7"])
async def test_generator_uses_manifest_version(hass, hass_ws_client, hass_client, version):
    """Panel používá loader manifestu i při budoucím vydání a správně podává JS."""
    from custom_components.cez_dynamic_tariff import dashboard_api

    assert await async_setup_component(hass, "frontend", {})
    integration = await async_get_integration(hass, DOMAIN)
    with patch.dict(integration.manifest, {"version": version}):
        await dashboard_api.async_setup_dashboard_generator(hass)
        await dashboard_api.async_setup_dashboard_generator(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "get_panels"})
    panel = (await client.receive_json())["result"][dashboard_api.PANEL_PATH]
    module_url = panel["config"]["_panel_custom"]["module_url"]
    assert module_url == f"{dashboard_api.MODULE_PATH}?v={version}"
    assert panel["require_admin"] and panel["title"] is None
    http = await hass_client(hass)
    response = await http.get(module_url)
    assert response.status == 200
    assert await response.read() == dashboard_api.MODULE_FILE.read_bytes()
