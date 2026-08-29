from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BASE_PRICE_KWH,
    ATTR_CURRENT_WINDOW_END,
    ATTR_CURRENT_WINDOW_START,
    ATTR_DAY_TYPE,
    ATTR_DAY_TYPE_CODE,
    ATTR_DISPLAY_MAP,
    ATTR_IS_HOLIDAY,
    ATTR_LEGEND,
    ATTR_NEXT_CHEAP_MODIFIER_PERCENT,
    ATTR_NEXT_MODIFIER_PERCENT,
    ATTR_SCHEDULE,
    ATTR_SEASON,
    ATTR_SEASON_CODE,
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
        translation_key="current_modifier",
        native_unit_of_measurement="%",
        value_fn=lambda data: data.current_modifier_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="current_band",
        translation_key="current_band",
        value_fn=lambda data: data.current_band,
    ),
    CezDynamicTariffSensorDescription(
        key="cheap_threshold",
        translation_key="cheap_threshold",
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.cheap_threshold_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="super_cheap_threshold",
        translation_key="super_cheap_threshold",
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.super_cheap_threshold_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="expensive_threshold",
        translation_key="expensive_threshold",
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.expensive_threshold_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="very_expensive_threshold",
        translation_key="very_expensive_threshold",
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.very_expensive_threshold_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="season",
        translation_key="season",
        value_fn=lambda data: data.season,
    ),
    CezDynamicTariffSensorDescription(
        key="day_type",
        translation_key="day_type",
        value_fn=lambda data: data.day_type,
    ),
    CezDynamicTariffSensorDescription(
        key="effective_price",
        translation_key="effective_price",
        native_unit_of_measurement="CZK/kWh",
        value_fn=lambda data: data.effective_price_kwh,
    ),
    CezDynamicTariffSensorDescription(
        key="next_cheap_start",
        translation_key="next_cheap_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.next_cheap_start,
    ),
    CezDynamicTariffSensorDescription(
        key="next_cheap_end",
        translation_key="next_cheap_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.next_cheap_end,
    ),
    CezDynamicTariffSensorDescription(
        key="next_cheap_modifier",
        translation_key="next_cheap_modifier",
        native_unit_of_measurement="%",
        value_fn=lambda data: data.next_cheap_modifier_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="next_change",
        translation_key="next_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.next_change,
    ),
    CezDynamicTariffSensorDescription(
        key="next_modifier",
        translation_key="next_modifier",
        native_unit_of_measurement="%",
        value_fn=lambda data: data.next_modifier_percent,
    ),
    CezDynamicTariffSensorDescription(
        key="today_tariff_map",
        translation_key="today_tariff_map",
        value_fn=lambda data: data.today_map_code,
    ),
    CezDynamicTariffSensorDescription(
        key="tomorrow_tariff_map",
        translation_key="tomorrow_tariff_map",
        value_fn=lambda data: data.tomorrow_map_code,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up sensors for a config entry."""
    coordinator: CezDynamicTariffCoordinator = entry.runtime_data

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
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator, entry, description) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self.entity_id = f"sensor.{DOMAIN}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="79thales",
            model="ČEZ Dynamic Tariff",
        )

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

        data = self.coordinator.data
        key = self.entity_description.key

        if key == "today_tariff_map":
            return {
                ATTR_DAY_TYPE: data.day_type,
                ATTR_DAY_TYPE_CODE: data.day_type_code,
                ATTR_DISPLAY_MAP: data.today_display_map,
                ATTR_LEGEND: data.today_legend,
                ATTR_SCHEDULE: data.today_schedule,
                ATTR_SEASON: data.season,
                ATTR_SEASON_CODE: data.season_code,
            }

        if key == "tomorrow_tariff_map":
            return {
                ATTR_DAY_TYPE: data.tomorrow_day_type,
                ATTR_DAY_TYPE_CODE: data.tomorrow_day_type_code,
                ATTR_DISPLAY_MAP: data.tomorrow_display_map,
                ATTR_LEGEND: data.tomorrow_legend,
                ATTR_SCHEDULE: data.tomorrow_schedule,
                ATTR_SEASON: data.tomorrow_season,
                ATTR_SEASON_CODE: data.tomorrow_season_code,
            }

        if key == "season":
            return {ATTR_SEASON_CODE: data.season_code}

        if key == "day_type":
            return {ATTR_DAY_TYPE_CODE: data.day_type_code}

        if key != "current_modifier":
            return None

        return {
            ATTR_BASE_PRICE_KWH: data.base_price_kwh,
            ATTR_CURRENT_WINDOW_START: data.current_window_start,
            ATTR_CURRENT_WINDOW_END: data.current_window_end,
            ATTR_DAY_TYPE: data.day_type,
            ATTR_DAY_TYPE_CODE: data.day_type_code,
            ATTR_IS_HOLIDAY: data.is_holiday,
            ATTR_NEXT_CHEAP_MODIFIER_PERCENT: data.next_cheap_modifier_percent,
            ATTR_NEXT_MODIFIER_PERCENT: data.next_modifier_percent,
            ATTR_SEASON: data.season,
            ATTR_SEASON_CODE: data.season_code,
        }
