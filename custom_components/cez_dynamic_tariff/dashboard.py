"""Build the current ČEZ view composition using existing registry entities."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

PANEL_PATH = "cez-dynamic-tariff-dashboard"
DEFAULT_VIEW_PATH = "cez-dynamic-tariff"
ENTITY_PATTERN = re.compile(
    r"\b(?:sensor|binary_sensor|button|select)\.cez_dynamic_tariff_([a-z0-9_]+)"
)
TEMPLATE_PATH = Path(__file__).with_name("dashboard_template.json")


def validate_view_name(title: str, view_path: str) -> None:
    """Keep generated view paths local and distinct from the helper panel."""
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
        raise ValueError("invalid_title")
    if (
        not isinstance(view_path, str)
        or len(view_path) > 60
        or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", view_path) is None
        or view_path == PANEL_PATH
    ):
        raise ValueError("invalid_path")


def build_views(
    title: str,
    view_path: str,
    entities: Mapping[str, str],
    hdo_sources: Mapping[str, str],
) -> dict[str, Any]:
    """Return three views, never a replacement for the user's whole dashboard.

    Volá se v executor threadu. Šablona obsahuje jen prezentaci, nikoli osobní
    odečty. Při změně dashboardu se udržuje společně s generátorem. EVAL tooltipy
    účetních grafů včetně českých komentářů se předají beze změny: null znamená
    chybějící údaj, číselná nula zůstává platnou hodnotou v kWh nebo Kč. Párování
    tooltipu podle X nemění účetní data ani zúčtovací období; přejmenují se pouze
    registrované entity a interní navigace. Neplatný název/adresa vyvolá ValueError.
    """
    validate_view_name(title, view_path)
    raw = TEMPLATE_PATH.read_text(encoding="utf-8")
    keys = sorted({match[1] for match in ENTITY_PATTERN.finditer(raw)})

    def entity(match: re.Match) -> str:
        return entities.get(match[1], match[0])

    raw = ENTITY_PATTERN.sub(entity, raw)
    for token, fallback in (
        ("HDO_ENTITY", "binary_sensor.cez_dynamic_tariff_hdo_not_configured"),
        ("HDO_VALID", "binary_sensor.cez_dynamic_tariff_hdo_valid_not_configured"),
        ("HDO_VALID_UNTIL", "sensor.cez_dynamic_tariff_hdo_valid_until_unavailable"),
        ("HDO_AGE", "sensor.cez_dynamic_tariff_hdo_age_unavailable"),
    ):
        raw = raw.replace(f"__{token}__", hdo_sources.get(token) or fallback)
    # Rewrite links as well as view paths. All views stay inside /lovelace.
    raw = raw.replace(DEFAULT_VIEW_PATH, view_path)
    result = json.loads(raw)
    result["views"][0]["title"] = title.strip()
    result["views"][0]["subview"] = False
    return {
        "config": result,
        "missing_entities": [key for key in keys if key not in entities],
        "missing_hdo_sources": [
            key
            for key in ("HDO_ENTITY", "HDO_VALID", "HDO_VALID_UNTIL", "HDO_AGE")
            if not hdo_sources.get(key)
        ],
        "required_cards": ["apexcharts-card"],
    }
