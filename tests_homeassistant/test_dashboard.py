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
