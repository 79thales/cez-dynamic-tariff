"""Admin-only read-only preview; view creation uses HA's native Lovelace API."""

from __future__ import annotations

from pathlib import Path

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.helpers import entity_registry as er
from homeassistant.util.yaml import dump

from .const import DOMAIN
from .dashboard import PANEL_PATH, build_views

MODULE_PATH = "/cez_dynamic_tariff/dashboard-generator.js"
PANEL_ELEMENT = "cez-dynamic-tariff-dashboard-generator"


def _panel_exists(hass):
    """HA 2025 uses the panel mapping; newer HA exposes a helper."""
    from homeassistant.components import frontend

    if hasattr(frontend, "async_panel_exists"):
        return frontend.async_panel_exists(hass, PANEL_PATH)
    return PANEL_PATH in hass.data.get(frontend.DATA_PANELS, {})


async def async_setup_dashboard_generator(hass):
    """Register a hidden helper without replacing the native options flow."""
    if (
        "frontend" not in hass.config.components
        or DOMAIN + "_generator_registered" in hass.data
    ):
        return
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.components.panel_custom import async_register_panel
    from homeassistant.loader import async_get_integration

    async_register_dashboard_commands(hass)
    if _panel_exists(hass):
        return
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                MODULE_PATH,
                str(Path(__file__).parent / "frontend/dashboard-generator.js"),
                False,
            )
        ]
    )
    await async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        module_url=f"{MODULE_PATH}?v={integration.manifest['version']}",
        require_admin=True,
    )
    hass.data[DOMAIN + "_generator_registered"] = True


def async_register_dashboard_commands(hass):
    websocket_api.async_register_command(hass, websocket_dashboard_entries)
    websocket_api.async_register_command(hass, websocket_dashboard_preview)


def _sources(hass, entry):
    """Resolve renamed integration entities and the selected HDO device."""
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    entities = {
        item.unique_id.removeprefix(prefix): item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.platform == DOMAIN
        and item.unique_id.startswith(prefix)
        and item.disabled_by is None
    }
    values = {**entry.data, **entry.options}
    hdo = {
        "HDO_ENTITY": values.get("hdo_entity", ""),
        "HDO_VALID": values.get("hdo_valid_entity", ""),
    }
    selected = registry.async_get(hdo["HDO_ENTITY"])
    if selected and selected.device_id:
        for item in er.async_entries_for_device(registry, selected.device_id):
            if item.platform != selected.platform or item.disabled_by is not None:
                continue
            if "data_valid_until" in item.unique_id.lower():
                hdo["HDO_VALID_UNTIL"] = item.entity_id
            if "data_age_days" in item.unique_id.lower():
                hdo["HDO_AGE"] = item.entity_id
    return entities, hdo


@websocket_api.require_admin
@websocket_api.websocket_command({"type": "cez_dynamic_tariff/dashboard/entries"})
@websocket_api.async_response
async def websocket_dashboard_entries(hass, connection, msg):
    connection.send_result(
        msg["id"],
        [
            {"entry_id": entry.entry_id, "name": entry.title}
            for entry in hass.config_entries.async_entries(DOMAIN)
        ],
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "cez_dynamic_tariff/dashboard/preview",
        vol.Required("entry_id"): str,
        vol.Required("title"): vol.All(str, vol.Length(min=1, max=120)),
        vol.Required("view_path"): vol.All(str, vol.Length(min=1, max=60)),
    }
)
@websocket_api.async_response
async def websocket_dashboard_preview(hass, connection, msg):
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(
            msg["id"], "entry_not_found", "ČEZ config entry not found"
        )
        return
    entities, hdo = _sources(hass, entry)
    try:
        result = await hass.async_add_executor_job(
            build_views, msg["title"], msg["view_path"], entities, hdo
        )
    except ValueError as err:
        connection.send_error(msg["id"], str(err), "Invalid view name or path")
        return
    result["yaml"] = await hass.async_add_executor_job(dump, result["config"])
    connection.send_result(msg["id"], result)
