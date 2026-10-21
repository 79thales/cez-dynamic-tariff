"""Configuration button opening the same generator workflow as EDC Share."""

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .dashboard import PANEL_PATH


async def async_setup_entry(hass, entry, async_add_entities):
    entities = [CezDashboardButton(entry)]
    billing = entry.runtime_data.billing
    if billing is not None and billing.settlement is not None:
        entities.append(CezAccountingBackfillButton(entry))
    async_add_entities(entities)


class CezAccountingBackfillButton(ButtonEntity):
    """Ruční scan na pozadí; stable unique_id brání duplicitě při reloadu.

    Tlačítko pouze zahájí/připojí scan. Úspěch dotažení oznamuje stavový
    senzor až po dokončení. Opakovaný stisk za běhu nezaloží druhý úkol.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "accounting_backfill"
    _attr_icon = "mdi:database-sync"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry):
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_accounting_backfill"
        self.entity_id = f"button.{DOMAIN}_accounting_backfill"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def available(self):
        billing = self._entry.runtime_data.billing
        return billing is not None and billing.settlement is not None and not billing.settlement._closing and billing.settlement._store_writable

    @property
    def extra_state_attributes(self):
        obj = self._entry.runtime_data.billing.settlement
        return {"unavailable_reason": "archive_invalid" if not obj._store_writable else "runtime_closing" if obj._closing else None}

    async def async_press(self):
        self._entry.runtime_data.billing.settlement.async_start_history_backfill()


class CezDashboardButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "generate_dashboard"
    _attr_icon = "mdi:view-dashboard-plus-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry):
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_generate_dashboard"
        self.entity_id = f"button.{DOMAIN}_generate_dashboard"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="79thales",
            model="ČEZ Dynamic Tariff",
        )

    async def async_press(self):
        """A server-side entity cannot navigate the user's browser."""
        url = f"/{PANEL_PATH}?entry_id={self._entry.entry_id}"
        cs = self.hass.config.language.startswith("cs")
        persistent_notification.async_create(
            self.hass,
            (
                f"[Otevřít generátor dashboardu]({url})\n\n"
                "Současné složení přehledu a detailů. Vygenerovaný přehled se přidá do horní lišty Overview."
            )
            if cs
            else (
                f"[Open the dashboard generator]({url})\n\n"
                "The current overview and details layout. Adds a view to the top tab bar of Overview."
            ),
            title="ČEZ – Generate dashboard",
            notification_id=f"{DOMAIN}_dashboard_{self._entry.entry_id}",
        )
