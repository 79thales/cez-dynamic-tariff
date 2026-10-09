"""Serve the bundled monthly card without an additional HACS installation."""

from pathlib import Path

from .const import DOMAIN


async def async_register_card(hass):
    if (
        DOMAIN + "_card_registered" in hass.data
        or "frontend" not in hass.config.components
    ):
        return
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    url = "/cez_dynamic_tariff/advances-card.js"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url, str(Path(__file__).parent / "frontend/advances-card.js"), False
            )
        ]
    )
    add_extra_js_url(hass, url + "?v=1.0.7")
    hass.data[DOMAIN + "_card_registered"] = True
