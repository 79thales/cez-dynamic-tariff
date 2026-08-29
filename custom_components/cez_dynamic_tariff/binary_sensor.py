from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CezDynamicTariffCoordinator, TariffSnapshot


@dataclass(frozen=True, kw_only=True)
class CezDynamicTariffBinarySensorDescription(BinarySensorEntityDescription):
    """Description for ČEZ Dynamic Tariff binary sensors."""

    value_fn: Callable[[TariffSnapshot], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[CezDynamicTariffBinarySensorDescription, ...] = (
    CezDynamicTariffBinarySensorDescription(
        key="cheap_now",
        translation_key="cheap_now",
        value_fn=lambda data: data.cheap_now,
    ),
    CezDynamicTariffBinarySensorDescription(
        key="super_cheap_now",
        translation_key="super_cheap_now",
        value_fn=lambda data: data.super_cheap_now,
    ),
    CezDynamicTariffBinarySensorDescription(
        key="expensive_now",
        translation_key="expensive_now",
        value_fn=lambda data: data.expensive_now,
    ),
    CezDynamicTariffBinarySensorDescription(
        key="very_expensive_now",
        translation_key="very_expensive_now",
        value_fn=lambda data: data.very_expensive_now,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up binary sensors for a config entry."""
    coordinator: CezDynamicTariffCoordinator = entry.runtime_data

    async_add_entities(
        CezDynamicTariffBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class CezDynamicTariffBinarySensor(
    CoordinatorEntity[CezDynamicTariffCoordinator],
    BinarySensorEntity,
):
    """Representation of a ČEZ Dynamic Tariff binary sensor."""

    entity_description: CezDynamicTariffBinarySensorDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator, entry, description) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self.entity_id = f"binary_sensor.{DOMAIN}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="79thales",
            model="ČEZ Dynamic Tariff",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
