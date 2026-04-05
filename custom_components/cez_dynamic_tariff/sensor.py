from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BASE_PRICE_KWH,
    ATTR_CURRENT_WINDOW_END,
    ATTR_CURRENT_WINDOW_START,
    ATTR_DAY_TYPE,
    ATTR_DISPLAY_MAP,
    ATTR_IS_HOLIDAY,
    ATTR_LEGEND,
    ATTR_NEXT_CHEAP_MODIFIER_PERCENT,
    ATTR_SCHEDULE,
    ATTR_SEASON,
    DOMAIN,
)
from .coordinator import CezDynamicTariffCoordinator, TariffSnapshot


@dataclass(frozen=True, kw_only=True)
class CezDynamicTariffSensorDescription(SensorEntityDescription):
    """Description for ČEZ Dynamic Tariff sensors."""

    value_fn: Callable[[TariffSnapshot], Any]


SENSOR_DESCRIPTIONS: tuple[CezDynamicTariffSensorDescription, ...] = (
    CezDynamicTariffSensorDescription(
        key="current_modifier",
        name="Current modifier",
        native_unit_of_measurement="%",
        value_fn=lambda data: data.current_modifier_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="current_band",
        name="Current band",
        value_fn=lambda data: data.current_band,
    ),
    CezDynamicTariffSensorDescription(
        key="cheap_threshold",
        name="Cheap threshold",
        native_unit_of_measurement="%",
        value_fn=lambda data: data.cheap_threshold_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="super_cheap_threshold",
        name="Super cheap threshold",
        native_unit_of_measurement="%",
        value_fn=lambda data: data.super_cheap_threshold_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="season",
        name="Season",
        value_fn=lambda data: data.season,
    ),
    CezDynamicTariffSensorDescription(
        key="day_type",
        name="Day type",
        value_fn=lambda data: data.day_type,
    ),
    CezDynamicTariffSensorDescription(
        key="effective_price",
        name="Effective price",
        native_unit_of_measurement="CZK/kWh",
        value_fn=lambda data: data.effective_price_kwh,
    ),
    CezDynamicTariffSensorDescription(
        key="next_cheap_start",
        name="Next cheap start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.next_cheap_start,
    ),
    CezDynamicTariffSensorDescription(
        key="next_cheap_end",
        name="Next cheap end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.next_cheap_end,
    ),
    CezDynamicTariffSensorDescription(
        key="next_cheap_modifier",
        name="Next cheap modifier",
        native_unit_of_measurement="%",
        value_fn=lambda data: data.next_cheap_modifier_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="today_tariff_map",
        name="Today tariff map",
        value_fn=lambda data: data.today_map_code,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up sensors for a config entry."""
    coordinator: CezDynamicTariffCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        CezDynamicTariffSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class CezDynamicTariffSensor(
    CoordinatorEntity[CezDynamicTariffCoordinator],
    SensorEntity,
):
    """Representation of a ČEZ Dynamic Tariff sensor."""

    entity_description: CezDynamicTariffSensorDescription
    _attr_should_poll = False

    def __init__(self, coordinator, entry, description) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = f"{entry.title} {description.name}"

    @property
    def native_value(self):
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        """Return extra attributes for the main modifier sensor."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.key != "current_modifier":
            if self.entity_description.key != "today_tariff_map":
                return None

            data = self.coordinator.data
            return {
                ATTR_DAY_TYPE: data.day_type,
                ATTR_DISPLAY_MAP: data.today_display_map,
                ATTR_LEGEND: data.legend,
                ATTR_SCHEDULE: data.today_schedule,
                ATTR_SEASON: data.season,
            }

        data = self.coordinator.data

        return {
            ATTR_BASE_PRICE_KWH: data.base_price_kwh,
            ATTR_CURRENT_WINDOW_START: data.current_window_start,
            ATTR_CURRENT_WINDOW_END: data.current_window_end,
            ATTR_DAY_TYPE: data.day_type,
            ATTR_IS_HOLIDAY: data.is_holiday,
            ATTR_NEXT_CHEAP_MODIFIER_PERCENT: data.next_cheap_modifier_percent,
            ATTR_SEASON: data.season,
        }
