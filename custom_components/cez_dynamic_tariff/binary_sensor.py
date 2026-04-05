from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CezDynamicTariffCoordinator, TariffSnapshot


@dataclass(frozen=True, kw_only=True)
class CezDynamicTariffBinarySensorDescription(BinarySensorEntityDescription):
    """Description for ČEZ Dynamic Tariff binary sensors."""

    value_fn: Callable[[TariffSnapshot], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[CezDynamicTariffBinarySensorDescription, ...] = (
    CezDynamicTariffBinarySensorDescription(
        key="expensive_now",
        name="Expensive now",
        value_fn=lambda data: data.expensive_now,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up binary sensors for a config entry."""
    coordinator: CezDynamicTariffCoordinator = hass.data[DOMAIN][entry.entry_id]

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
    _attr_should_poll = False

    def __init__(self, coordinator, entry, description) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = f"{entry.title} {description.name}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
