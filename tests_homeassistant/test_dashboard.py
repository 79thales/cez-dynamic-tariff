"""Exercise the actual HA registry, permissions, panel and generated templates."""

import json
from unittest.mock import patch

import pytest
from homeassistant.helpers import template
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import parse_yaml
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cez_dynamic_tariff.dashboard import PANEL_PATH
from custom_components.cez_dynamic_tariff.dashboard_api import (
    async_register_dashboard_commands,
    async_setup_dashboard_generator,
)


def entry(hass):
    item = MockConfigEntry(
        domain="cez_dynamic_tariff",
        title="Example ČEZ",
        data={},
        options={
            "accounting_enabled": True,
            "hdo_entity": "binary_sensor.example_hdo",
            "hdo_valid_entity": "binary_sensor.example_valid",
            "monthly_advances": "[]",
        },
    )
    item.add_to_hass(hass)
    return item


def request(item, number=1):
    return {
        "id": number,
        "type": "cez_dynamic_tariff/dashboard/preview",
        "entry_id": item.entry_id,
        "title": "Example ČEZ",
        "view_path": "cez-test",
    }


async def test_preview_resolves_renames_and_hdo_device_without_writes(
    hass, hass_ws_client, entity_registry, device_registry
):
    item = entry(hass)
    entity_registry.async_get_or_create(
        "sensor",
        "cez_dynamic_tariff",
        f"{item.entry_id}_accounting_status",
        config_entry=item,
        suggested_object_id="original",
    )
    entity_registry.async_update_entity(
        "sensor.original", new_entity_id="sensor.renamed_accounting"
    )
    hdo = MockConfigEntry(domain="cez_distribuce", data={})
    hdo.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=hdo.entry_id, identifiers={("cez_distribuce", "example-hdo")}
    )
    for domain, key, object_id in (
        ("binary_sensor", "low_tariff", "example_hdo"),
        ("sensor", "data_valid_until", "renamed_hdo_expiry"),
        ("sensor", "data_age_days", "renamed_hdo_age"),
    ):
        entity_registry.async_get_or_create(
            domain,
            "cez_distribuce",
            f"{key}_example",
            config_entry=hdo,
            device_id=device.id,
            suggested_object_id=object_id,
        )
    before = dict(item.options)
    async_register_dashboard_commands(hass)
    client = await hass_ws_client(hass)
    await client.send_json(request(item))
    response = await client.receive_json()
    assert response["success"]
    data = response["result"]
    text = json.dumps(data)
    assert "sensor.renamed_accounting" in text
    assert "sensor.renamed_hdo_expiry" in text and "sensor.renamed_hdo_age" in text
    assert "sensor.cez_dynamic_tariff_accounting_status" not in text
    assert parse_yaml(data["yaml"]) == data["config"]
    assert dict(item.options) == before
    assert "lovelace" not in hass.data


async def test_non_admin_cannot_preview_or_list_entries(
    hass, hass_ws_client, hass_read_only_access_token
):
    item = entry(hass)
    async_register_dashboard_commands(hass)
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    for msg in (
        {"id": 1, "type": "cez_dynamic_tariff/dashboard/entries"},
        request(item, 2),
    ):
        await client.send_json(msg)
        response = await client.receive_json()
        assert not response["success"] and response["error"]["code"] == "unauthorized"


async def test_preview_rejects_unknown_entry_and_unsafe_path(hass, hass_ws_client):
    item = entry(hass)
    async_register_dashboard_commands(hass)
    client = await hass_ws_client(hass)
    for number, changes, code in (
        (1, {"entry_id": "missing"}, "entry_not_found"),
        (2, {"view_path": "../home"}, "invalid_path"),
    ):
        await client.send_json(request(item, number) | changes)
        response = await client.receive_json()
        assert not response["success"] and response["error"]["code"] == code


async def test_button_notification_and_stable_entity(hass):
    item = entry(hass)
    from custom_components.cez_dynamic_tariff.button import CezDashboardButton

    button = CezDashboardButton(item)
    button.hass = hass
    with patch(
        "homeassistant.components.persistent_notification.async_create"
    ) as notification:
        await button.async_press()
    assert button.unique_id == f"{item.entry_id}_generate_dashboard"
    assert button.entity_id == "button.cez_dynamic_tariff_generate_dashboard"
    assert PANEL_PATH in notification.call_args.args[1]
    assert item.entry_id in notification.call_args.args[1]


async def test_native_dashboard_menu_returns_without_changing_options(hass):
    item = entry(hass)
    before = dict(item.options)
    manager = hass.config_entries.options
    menu = await manager.async_init(item.entry_id)
    assert "dashboard" in menu["menu_options"]
    form = await manager.async_configure(menu["flow_id"], {"next_step_id": "dashboard"})
    assert (
        form["description_placeholders"]["url"]
        == f"/{PANEL_PATH}?entry_id={item.entry_id}"
    )
    menu = await manager.async_configure(form["flow_id"], {})
    assert menu["type"] == "menu" and dict(item.options) == before


async def test_hidden_generator_panel_is_registered_once_and_keeps_options_flow(
    hass, hass_ws_client, hass_client
):
    assert await async_setup_component(hass, "frontend", {})
    await async_setup_dashboard_generator(hass)
    await async_setup_dashboard_generator(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "get_panels"})
    panel = (await client.receive_json())["result"][PANEL_PATH]
    assert panel["require_admin"] and panel["title"] is None
    assert not panel.get("config_panel_domain")
    http = await hass_client(hass)
    response = await http.get(panel["config"]["_panel_custom"]["module_url"])
    assert response.status == 200
    assert "appendCezViews" in await response.text()


@pytest.mark.parametrize("has_bill", [False, True])
async def test_invoice_comparison_template_handles_missing_and_stored_months(
    hass, has_bill
):
    from custom_components.cez_dynamic_tariff.dashboard import build_views

    months = [
        {"month": f"2025-{m:02d}", "nt_kwh": 100, "vt_kwh": 10} for m in range(1, 13)
    ]
    attributes = {
        "settled_bills": [
            {
                "start": "2025-01-01",
                "end": "2025-12-31",
                "energy_kwh": 1320,
                "months": months,
            }
        ]
        if has_bill
        else [],
        "today_through": "2026-10-10T08:00:00+02:00",
        "billing_start": "2026-04-01",
        "billing_end": "2027-03-31",
        "period_energy_coverage": 1,
        "daily_energy_complete": True,
        "known_period_energy": 500,
    }
    hass.states.async_set(
        "sensor.cez_dynamic_tariff_accounting_status", "complete", attributes
    )
    views = build_views("ČEZ", "cez-test", {}, {})["config"]["views"]
    content = views[1]["sections"][-1]["cards"][-1]["content"]
    result = template.Template(content, hass).async_render()
    assert "1320" in result if has_bill else "není uložené vyúčtování" in result
    assert "Přibližně" in result if has_bill else "Přibližně" not in result


@pytest.mark.parametrize(
    ("source", "hdo_state", "expected"),
    [
        ("binary_sensor.test_hdo", "on", "NT — nízký tarif"),
        ("binary_sensor.test_hdo", "off", "VT — vysoký tarif"),
        ("binary_sensor.test_hdo", "unavailable", "neznámé"),
        ("binary_sensor.test_hdo", "unknown", "neznámé"),
        ("binary_sensor.test_hdo", None, "neznámé"),
        (None, "on", "neznámé"),
        ("", "on", "neznámé"),
        ("not_an_entity", "on", "neznámé"),
        ("binary_sensor.BAD", "on", "neznámé"),
        (" binary_sensor.test_hdo", "on", "neznámé"),
        ("binary_sensor.test_hdo\n", "on", "neznámé"),
        ("_binary_sensor.test_hdo", "on", "neznámé"),
        ("binary_sensor._test_hdo", "on", "neznámé"),
        ("binary_sensor.test_hdo_", "on", "neznámé"),
        ("binary__sensor.test_hdo", "on", "neznámé"),
        ("binary_sensor.test__hdo", "on", "neznámé"),
        (123, "on", "neznámé"),
        (False, "on", "neznámé"),
        ([], "on", "neznámé"),
        ({"entity_id": "binary_sensor.test_hdo"}, "on", "neznámé"),
    ],
)
async def test_hdo_card_renders_with_missing_or_invalid_source(
    hass, source, hdo_state, expected
):
    """Vykreslení skutečné karty: pouze on = NT, off = VT; jinak neznámé.

    Používáme skutečné Jinja prostředí HA, nikoli náhradu is_state. Neplatné
    ID se nesmí dostat ani do stavového registru, a to včetně koncového LF.
    Cena (Kč/kWh) a smluvní režim trial se při tomto čtení nesmějí měnit.
    """
    from custom_components.cez_dynamic_tariff.dashboard import build_views

    hass.states.async_set(
        "sensor.cez_dynamic_tariff_total_price", "1.89894", {"hdo_entity": source}
    )
    hass.states.async_set("sensor.cez_dynamic_tariff_accounting_price", "3.42394")
    hass.states.async_set("sensor.cez_dynamic_tariff_price_without_dynamic", "3.42394")
    hass.states.async_set(
        "sensor.cez_dynamic_tariff_accounting_status", "complete",
        {"dynamic_contract_mode": "trial"},
    )
    if hdo_state is not None:
        hass.states.async_set("binary_sensor.test_hdo", hdo_state)
    content = build_views("ČEZ", "cez-test", {}, {})["config"]["views"][0][
        "sections"
    ][0]["cards"][1]["content"]
    with patch.object(type(hass.states), "get", side_effect=hass.states.get) as read:
        rendered = template.Template(content, hass).async_render(parse_result=False)
    assert f"HDO: **{expected}**" in rendered
    assert "3,424 Kč/kWh" in rendered and "tarif na zkoušku" in rendered
    invalid = not isinstance(source, str) or source != "binary_sensor.test_hdo"
    if invalid:
        assert all(call.args[0] != source for call in read.call_args_list)


async def test_hdo_card_tracks_price_sensor_creation_removal_and_recovery(hass):
    """Start/reload šablony: stejný objekt přežije chybějící senzor i HDO.

    Před vznikem cenového senzoru a během jeho odebrání vrátí state_attr None.
    Po jeho opětovném vzniku šablona znovu čte HDO a nezůstane na starém tarifu.
    """
    from custom_components.cez_dynamic_tariff.dashboard import build_views

    price = "sensor.cez_dynamic_tariff_total_price"
    hdo = "binary_sensor.test_hdo"
    content = build_views("ČEZ", "cez-test", {}, {})["config"]["views"][0][
        "sections"
    ][0]["cards"][1]["content"]
    card = template.Template(content, hass)
    assert "HDO: **neznámé**" in card.async_render(parse_result=False)
    hass.states.async_set(price, "unknown", {"hdo_entity": hdo})
    assert "HDO: **neznámé**" in card.async_render(parse_result=False)
    hass.states.async_set(hdo, "on")
    assert "HDO: **NT — nízký tarif**" in card.async_render(parse_result=False)
    hass.states.async_remove(price)
    assert "HDO: **neznámé**" in card.async_render(parse_result=False)
    hass.states.async_set(hdo, "off")
    hass.states.async_set(price, "unknown", {"hdo_entity": hdo})
    assert "HDO: **VT — vysoký tarif**" in card.async_render(parse_result=False)


async def test_hdo_template_subscription_recovers_without_manual_render(hass):
    """Skutečný odběr Jinja se obnoví z None; nesmí zůstat na neznámém tarifu.

    Nejdříve sleduje cenový senzor, po objevení platného ID také HDO. Vznik,
    odebrání a změna HDO vyvolají nové výsledky přes stavové události HA.
    Odběr v finally ukončíme, takže po testu nezůstávají posluchače/časovače.
    """
    from homeassistant.helpers.event import TrackTemplate, async_track_template_result

    from custom_components.cez_dynamic_tariff.dashboard import build_views

    price = "sensor.cez_dynamic_tariff_total_price"
    hdo = "binary_sensor.test_hdo"
    content = build_views("ČEZ", "cez-test", {}, {})["config"]["views"][0][
        "sections"
    ][0]["cards"][1]["content"]
    results = []
    subscription = async_track_template_result(
        hass, [TrackTemplate(template.Template(content, hass), None)],
        lambda event, updates: results.extend(update.result for update in updates),
    )
    try:
        subscription.async_refresh()
        assert "HDO: **neznámé**" in results[-1]
        hass.states.async_set(price, "unknown", {"hdo_entity": hdo})
        await hass.async_block_till_done()
        hass.states.async_set(hdo, "on")
        await hass.async_block_till_done()
        assert "HDO: **NT — nízký tarif**" in results[-1]
        hass.states.async_set(hdo, "off")
        await hass.async_block_till_done()
        assert "HDO: **VT — vysoký tarif**" in results[-1]
        hass.states.async_remove(price)
        await hass.async_block_till_done()
        assert "HDO: **neznámé**" in results[-1]
        hass.states.async_set(price, "unknown", {"hdo_entity": hdo})
        await hass.async_block_till_done()
        assert "HDO: **VT — vysoký tarif**" in results[-1]
    finally:
        subscription.async_remove()


async def test_all_dashboard_markdown_renders_before_sources_exist(hass):
    """Startovní vykreslení všech markdown karet hlavního pohledu a detailů.

    Test běží se stavovým registrem HA bez cenových/účetních zdrojů. JavaScript
    grafů testuje samostatná sada; zde se ověřují skutečné serverové Jinja karty.
    """
    from custom_components.cez_dynamic_tariff.dashboard import build_views

    def cards(value):
        if isinstance(value, dict):
            if value.get("type") == "markdown":
                yield value["content"]
            for item in value.values():
                yield from cards(item)
        elif isinstance(value, list):
            for item in value:
                yield from cards(item)

    generated = build_views("ČEZ", "cez-test", {}, {})["config"]
    contents = list(cards(generated))
    assert len(contents) > 10
    for content in contents:
        assert isinstance(
            template.Template(content, hass).async_render(parse_result=False), str
        )


async def test_copied_legacy_card_renders_with_actual_frontend_migration(hass):
    """Skutečný JS generátor → skutečná Jinja HA, včetně escapování regexu.

    Proces Node běží v executor jobu s limitem 10 s, mimo asyncio smyčku.
    Vstupem je stará karta s on/off; výstupem je šablona generátoru, kterou HA
    vykreslí pro známé, chybějící i neplatné HDO. Test nepotřebuje síť ani prohlížeč.
    """
    import shutil
    import subprocess
    from functools import partial
    from pathlib import Path

    node = shutil.which("node")
    if node is None:
        pytest.skip("Pro test JS → Jinja je potřeba Node.js.")
    module = Path(__file__).parents[1] / (
        "custom_components/cez_dynamic_tariff/frontend/dashboard-generator.js"
    )
    legacy = (
        "{% set hdo = state_attr('sensor.cez_dynamic_tariff_total_price','hdo_entity') %}"
        "HDO: **{{ 'NT — nízký tarif' if is_state(hdo,'on') else "
        "'VT — vysoký tarif' if is_state(hdo,'off') else 'neznámé' }}**"
    )
    script = """
const fs = require('node:fs'), vm = require('node:vm');
const context = vm.createContext({HTMLElement: class {}, customElements: {get: () => false, define: () => {}}});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
process.stdout.write(context.cezGuardHdoTemplates(fs.readFileSync(0, 'utf8')));
"""
    output = await hass.async_add_executor_job(partial(
        subprocess.run, [node, "-e", script, str(module)], input=legacy,
        text=True, encoding="utf-8", capture_output=True, check=True, timeout=10,
    ))
    card = template.Template(output.stdout, hass)
    hdo = "binary_sensor.test_hdo"
    for source, state, expected in (
        (hdo, "on", "NT — nízký tarif"),
        (hdo, "off", "VT — vysoký tarif"),
        (hdo, "unavailable", "neznámé"),
        (None, "on", "neznámé"),
        (123, "on", "neznámé"),
        ([], "on", "neznámé"),
        (hdo + "\n", "on", "neznámé"),
    ):
        hass.states.async_set(hdo, state)
        hass.states.async_set(
            "sensor.cez_dynamic_tariff_total_price", "unknown", {"hdo_entity": source}
        )
        assert f"HDO: **{expected}**" in card.async_render(parse_result=False)
    hass.states.async_remove("sensor.cez_dynamic_tariff_total_price")
    assert "HDO: **neznámé**" in card.async_render(parse_result=False)


async def test_manual_hdo_yaml_matches_bundled_card_and_keeps_comments(hass):
    """Ruční oprava a export generátoru mají totožnou kartu včetně popisu.

    Ověříme parsování reálným HA YAML parserem i serializaci přes jeho dump,
    aby se Jinja komentáře a dvojité escapování regexu neztratily při exportu.
    """
    from pathlib import Path

    from homeassistant.util.yaml import dump

    from custom_components.cez_dynamic_tariff.dashboard import build_views

    card = build_views("ČEZ", "cez-test", {}, {})["config"]["views"][0][
        "sections"
    ][0]["cards"][1]
    manual = parse_yaml(
        (Path(__file__).parents[1] / "examples/hdo_status_card.yaml").read_text(
            encoding="utf-8"
        )
    )
    manual["content"] = manual["content"].rstrip()
    assert manual == card
    exported = parse_yaml(dump(card))
    assert exported == card
    assert "{# Cenový senzor" in exported["content"]
    assert "HDO: **neznámé**" in template.Template(
        exported["content"], hass
    ).async_render(parse_result=False)
