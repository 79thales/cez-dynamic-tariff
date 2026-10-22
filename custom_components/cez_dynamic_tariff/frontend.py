"""Zpřístupnění a registrace přibaleného editoru záloh bez instalace z HACS."""

import asyncio
import logging
from collections.abc import Mapping
from pathlib import Path

from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import async_get_integration

from .const import DOMAIN

CARD_URL = "/cez_dynamic_tariff/advances-card.js"
CARD_FILE = Path(__file__).parent / "frontend/advances-card.js"
_LOGGER = logging.getLogger(__name__)


async def async_module_url(hass, url: str) -> str:
    """Odlišit cache přibaleného JS podle verze integrace z manifestu.

    Vstup: místní HTTP cesta bez query. Výstup: cesta s parametrem v z
    manifest.json načteného loaderem HA. Po aktualizaci a restartu HA dostane
    nový release novou URL i při shodném obsahu JS. Loader zajišťuje načtení
    mimo hlavní smyčku a sdílí manifest v rámci běhu HA; další čtení souboru
    ani duplicitní konstanta nejsou potřeba. Chyba loaderu nebo chybějící
    povinná verze se propaguje do setupu, aby nevznikla URL s náhradní verzí.
    """
    integration = await async_get_integration(hass, DOMAIN)
    return f"{url}?v={integration.manifest['version']}"


async def _async_register_lovelace_resource(hass, module_url):
    """Zajistit modul v registru Lovelace, aniž se mění pohledy dashboardů.

    Vstupem je místní URL s verzí integrace; výstupem je nejvýše jedna nová
    položka resource. Starší HA používá slovník, novější LovelaceData.
    Storage načteme před hledáním, aby restart nevytvořil další kopii. U všech
    již existujících položek téže místní cesty zachováme ID a opravíme pouze
    URL/verzi a typ module. Cizí zdroje ani jejich pořadí se nemění.
    YAML zdroje mají ruční správu: nezapisujeme do souboru ani paměťové kopie;
    tam zůstává automatické načtení přes extra_js_url a případný pokyn v logu.
    Chyba čtení/zápisu se loguje, ale nesmí vyřadit účetnictví. Další reload
    registraci zopakuje. Zrušení úlohy při vypnutí HA se propaguje běžně.
    Volající drží zámek po celou dobu včetně asynchronního načtení a zápisu.
    """
    from homeassistant.components.lovelace.resources import ResourceStorageCollection

    data = hass.data.get("lovelace")
    resources = (
        data.get("resources")
        if isinstance(data, Mapping)
        else getattr(data, "resources", None)
    )
    if resources is None:
        return
    if not isinstance(resources, ResourceStorageCollection):
        if not any(
            item.get("url") == module_url and item.get("type") == "module"
            for item in resources.async_items()
        ):
            _LOGGER.warning(
                "Editor záloh: zdroje Lovelace jsou v YAML. Pro přímé načtení přidejte URL %s s typem module",
                module_url,
            )
        return
    try:
        if not resources.loaded:
            await resources.async_load()
            resources.loaded = True
        existing = [
            item
            for item in resources.async_items()
            if isinstance(item.get("url"), str)
            and item["url"].split("?", 1)[0] == CARD_URL
        ]
        if not existing:
            await resources.async_create_item({"url": module_url, "res_type": "module"})
        else:
            for item in existing:
                if item["url"] != module_url or item.get("type") != "module":
                    await resources.async_update_item(
                        item["id"], {"url": module_url, "res_type": "module"}
                    )
    except (HomeAssistantError, OSError):
        _LOGGER.exception(
            "Editor záloh: registrace zdroje Lovelace selhala. Zkuste reload integrace nebo přidejte URL %s s typem module",
            module_url,
        )


async def async_register_card(hass):
    """Při setupu/reloadu zpřístupnit soubor a zajistit obě cesty načtení.

    Bez frontend komponenty není co registrovat. Statická HTTP cesta se
    registruje jednou za běh HA; při restartu se vytvoří znovu. Registr zdrojů
    Lovelace kontrolujeme i při reloadu, který tak napraví chybějící položku.
    Zámek v hass.data brání duplicitám při souběhu dvou setupů. Verze manifestu
    nahrazuje pevné 1.0.8 a shodná URL v obou cestách umožní prohlížeči vykonat
    ES modul jen jednou. Úvodní stránka slouží jako fallback pro YAML; Lovelace
    načítá registrovaný modul i bez nového načtení úvodního HTML.
    Žádná část této funkce nespouští platbu ani neupravuje evidenci záloh.
    """
    if "frontend" not in hass.config.components:
        return
    from homeassistant.components.frontend import (
        DATA_EXTRA_MODULE_URL,
        add_extra_js_url,
        remove_extra_js_url,
    )
    from homeassistant.components.http import StaticPathConfig

    lock = hass.data.setdefault(DOMAIN + "_card_registration_lock", asyncio.Lock())
    async with lock:
        module_url = await async_module_url(hass, CARD_URL)
        if DOMAIN + "_card_registered" not in hass.data:
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        CARD_URL,
                        str(CARD_FILE),
                        False,
                    )
                ]
            )
            hass.data[DOMAIN + "_card_registered"] = True
        # Odstraníme jen starší adresy vlastního editoru z úvodního HTML.
        # Registry Lovelace se opravují níže pod stejným ID. Při reloadu se
        # tak nehromadí různé verze téhož modulu; jiné integrace se neovlivní.
        for previous in tuple(hass.data[DATA_EXTRA_MODULE_URL].urls):
            if previous.split("?", 1)[0] == CARD_URL and previous != module_url:
                remove_extra_js_url(hass, previous)
        add_extra_js_url(hass, module_url)
        await _async_register_lovelace_resource(hass, module_url)
