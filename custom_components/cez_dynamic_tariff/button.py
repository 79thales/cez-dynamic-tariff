"""Configuration button opening the same generator workflow as EDC Share."""

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .dashboard import PANEL_PATH


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([CezDashboardButton(entry)])


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
