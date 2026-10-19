"""Serve the bundled monthly card without an additional HACS installation."""

from pathlib import Path

from .const import DOMAIN


async def async_register_card(hass):
    """Zpřístupnit editor s verzí manifestu pro obnovení cache po aktualizaci.

    Loader HA načte manifest mimo hlavní smyčku a sdílí jej během běhu HA.
    Po aktualizaci a restartu tak parametr v odpovídá nově instalované verzi.
    Opakovaný setup cestu ani modul neduplikuje; bez frontendu se registrace
    odloží. Chyba loaderu se propaguje před registrací HTTP cesty a nastavením
    příznaku, takže neúspěšný pokus nebrání opakování setupu.
    """
    if (
        DOMAIN + "_card_registered" in hass.data
        or "frontend" not in hass.config.components
    ):
        return
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.loader import async_get_integration

    integration = await async_get_integration(hass, DOMAIN)
    url = "/cez_dynamic_tariff/advances-card.js"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url, str(Path(__file__).parent / "frontend/advances-card.js"), False
            )
        ]
    )
    add_extra_js_url(hass, f"{url}?v={integration.manifest['version']}")
    hass.data[DOMAIN + "_card_registered"] = True
