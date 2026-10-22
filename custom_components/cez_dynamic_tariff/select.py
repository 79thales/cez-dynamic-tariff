"""Nadřazený výběr cenové strategie; potvrzený výběr uloží časovou revizi."""

from typing import ClassVar

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .band_pricing import MODES, record_change, settings_at, validate_bands
from .const import DOMAIN
from .pricing import PROFILE_DEFAULTS


async def async_setup_entry(hass, entry, async_add_entities):
    """Volič existuje i bez ocenění; chybějící pevný profil nelze aktivovat."""
    async_add_entities([TariffModeSelect(entry)])


class TariffModeSelect(CoordinatorEntity, SelectEntity):
    """Změna režimu ponechá původní procentní entity a řízení spotřebičů."""

    _attr_has_entity_name = True
    _attr_translation_key = "tariff_mode"
    _attr_options: ClassVar[list[str]] = list(MODES)
    _attr_icon = "mdi:swap-horizontal"

    def __init__(self, entry):
        super().__init__(entry.runtime_data)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tariff_mode"
        self.entity_id = f"select.{DOMAIN}_tariff_mode"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def current_option(self):
        return settings_at(
            {**self.entry.data, **self.entry.options},
            PROFILE_DEFAULTS,
            dt_util.utcnow(),
        )["tariff_mode"]

    async def async_select_option(self, option):
        """Uloží okamžitou aktivaci; reload uzavře původní účetní interval.

        Chybějící/neúčinný profil vrátí chybu služby, bez náhradní ceny.
        Výběr konkrétního produktu a plánování jsou v nastavení integrace.
        """
        if option not in MODES:
            raise HomeAssistantError("Neplatný způsob výpočtu dynamického tarifu.")
        old = {**self.entry.data, **self.entry.options}
        if option == "fixed_bands":
            profile = next(
                (
                    p
                    for p in old.get("fixed_price_profiles", [])
                    if p["id"] == old.get("fixed_profile_id")
                ),
                None,
            )
            if profile is None:
                raise HomeAssistantError(
                    "Nejprve nahrajte a vyberte pevný ceník v nastavení integrace."
                )
            try:
                validate_bands(profile["schedules"])
            except (ValueError, KeyError) as err:
                raise HomeAssistantError("Pevný ceník není úplný.") from err
            if dt_util.now().date().isoformat() < max(
                profile["trade_effective"], profile["distribution_effective"]
            ):
                raise HomeAssistantError("Vybraný ceník ještě není účinný.")
        updated = record_change(
            old,
            {**old, "tariff_mode": option},
            PROFILE_DEFAULTS,
            dt_util.utcnow(),
            archive_revision=getattr(
                getattr(self.coordinator.billing, "settlement", None),
                "_cost_revision",
                None,
            ),
            force=True,
            archive_identity=getattr(
                getattr(self.coordinator.billing, "settlement", None),
                "_archive_source_identity",
                None,
            ),
        )
        options = {**self.entry.options, "tariff_mode": option}
        if "pricing_events" in updated:
            options["pricing_events"] = updated["pricing_events"]
        self.hass.config_entries.async_update_entry(self.entry, options=options)
