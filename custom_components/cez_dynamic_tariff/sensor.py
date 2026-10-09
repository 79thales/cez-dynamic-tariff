from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
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
    ATTR_SCHEDULE_REVISION,
    ATTR_SCHEDULE_SOURCE_URL,
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
        key="current_cheap_end",
        translation_key="current_cheap_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.current_cheap_end,
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


def _billing_value(key):
    return lambda data: (data.billing or {}).get(key)


PRICING_DESCRIPTIONS: tuple[CezDynamicTariffSensorDescription, ...] = (
    CezDynamicTariffSensorDescription(
        key="daily_cost",
        translation_key="daily_cost",
        native_unit_of_measurement="CZK",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=_billing_value("daily_cost"),
    ),
    CezDynamicTariffSensorDescription(
        key="daily_fixed_cost",
        translation_key="daily_fixed_cost",
        native_unit_of_measurement="CZK",
        value_fn=_billing_value("daily_fixed_cost"),
    ),
    CezDynamicTariffSensorDescription(
        key="daily_savings",
        translation_key="daily_savings",
        native_unit_of_measurement="CZK",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=_billing_value("daily_savings"),
    ),
    CezDynamicTariffSensorDescription(
        key="total_price",
        translation_key="total_price",
        native_unit_of_measurement="CZK/kWh",
        value_fn=_billing_value("total_price"),
    ),
    CezDynamicTariffSensorDescription(
        key="price_without_dynamic",
        translation_key="price_without_dynamic",
        native_unit_of_measurement="CZK/kWh",
        value_fn=_billing_value("price_without_dynamic"),
    ),
    CezDynamicTariffSensorDescription(
        key="price_with_dynamic",
        translation_key="price_with_dynamic",
        native_unit_of_measurement="CZK/kWh",
        value_fn=_billing_value("price_with_dynamic"),
    ),
    CezDynamicTariffSensorDescription(
        key="allocated_price",
        translation_key="allocated_price",
        native_unit_of_measurement="CZK/kWh",
        value_fn=_billing_value("allocated_price"),
    ),
    CezDynamicTariffSensorDescription(
        key="monthly_fixed_cost",
        translation_key="monthly_fixed_cost",
        native_unit_of_measurement="CZK",
        value_fn=_billing_value("monthly_fixed_cost"),
    ),
    CezDynamicTariffSensorDescription(
        key="minimum_price",
        translation_key="minimum_price",
        native_unit_of_measurement="CZK/kWh",
        value_fn=_billing_value("minimum_price"),
    ),
    CezDynamicTariffSensorDescription(
        key="best_price_start",
        translation_key="best_price_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_billing_value("best_price_start"),
    ),
    CezDynamicTariffSensorDescription(
        key="next_price_change",
        translation_key="next_price_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_billing_value("next_price_change"),
    ),
    CezDynamicTariffSensorDescription(
        key="price_forecast",
        translation_key="price_forecast",
        value_fn=_billing_value("price_forecast"),
    ),
    CezDynamicTariffSensorDescription(
        key="actual_cost",
        translation_key="actual_cost",
        native_unit_of_measurement="CZK",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=_billing_value("actual_cost"),
    ),
    CezDynamicTariffSensorDescription(
        key="total_cost",
        translation_key="total_cost",
        native_unit_of_measurement="CZK",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=_billing_value("total_cost"),
    ),
    CezDynamicTariffSensorDescription(
        key="dynamic_savings",
        translation_key="dynamic_savings",
        native_unit_of_measurement="CZK",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=_billing_value("dynamic_savings"),
    ),
    CezDynamicTariffSensorDescription(
        key="realized_savings",
        translation_key="realized_savings",
        native_unit_of_measurement="CZK",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=_billing_value("realized_savings"),
    ),
    CezDynamicTariffSensorDescription(
        key="potential_savings",
        translation_key="potential_savings",
        native_unit_of_measurement="CZK",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=_billing_value("potential_savings"),
    ),
    CezDynamicTariffSensorDescription(
        key="unpriced_energy",
        translation_key="unpriced_energy",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=_billing_value("unpriced_energy"),
    ),
)


ACCOUNTING_DESCRIPTIONS = tuple(
    CezDynamicTariffSensorDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=unit,
        device_class=SensorDeviceClass.MONETARY
        if unit == "CZK"
        else SensorDeviceClass.ENERGY
        if unit == "kWh"
        else SensorDeviceClass.ENUM,
        options=[
            "complete",
            "incomplete",
            "history_unavailable",
            "contract_unconfirmed",
        ]
        if unit is None
        else None,
        suggested_display_precision=2 if unit else None,
        value_fn=lambda data, key=key: (
            (data.billing or {}).get("settlement", {}).get(key)
        ),
    )
    for key, unit in (
        ("daily_import_energy", "kWh"),
        ("daily_import_cost_backfilled", "CZK"),
        ("daily_cost_backfilled", "CZK"),
        ("daily_savings_backfilled", "CZK"),
        ("daily_shared_income", "CZK"),
        ("daily_net_cost", "CZK"),
        ("period_import_energy", "kWh"),
        ("period_gross_cost", "CZK"),
        ("period_shared_income", "CZK"),
        ("advance_payments_total", "CZK"),
        ("advance_payments_paid", "CZK"),
        ("forecast_import_energy", "kWh"),
        ("forecast_gross_cost", "CZK"),
        ("forecast_net_cost", "CZK"),
        ("forecast_balance", "CZK"),
        ("consumption_profile", None),
        ("accounting_status", None),
    )
)


def _invoice_price(data):
    billing = data.billing or {}
    mode = billing.get("settlement", {}).get("metadata", {}).get("dynamic_contract_mode")
    if mode == "trial" or not billing.get("metadata", {}).get("dynamic_pricing"):
        return billing.get("price_without_dynamic")
    return billing.get("total_price") if mode == "regular" else None


ACCOUNTING_DESCRIPTIONS += (
    CezDynamicTariffSensorDescription(
        key="accounting_price",
        translation_key="accounting_price",
        native_unit_of_measurement="CZK/kWh",
        suggested_display_precision=3,
        value_fn=_invoice_price,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up sensors for a config entry."""
    coordinator: CezDynamicTariffCoordinator = entry.runtime_data

    descriptions = SENSOR_DESCRIPTIONS
    if coordinator.billing is not None:
        descriptions += PRICING_DESCRIPTIONS
        if coordinator.billing.settlement is not None:
            descriptions += ACCOUNTING_DESCRIPTIONS
    async_add_entities(
        CezDynamicTariffSensor(coordinator, entry, description)
        for description in descriptions
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
        value = self.entity_description.value_fn(self.coordinator.data)
        if self.entity_description in PRICING_DESCRIPTIONS and isinstance(value, float):
            return round(value, 6)
        if self.entity_description in ACCOUNTING_DESCRIPTIONS and isinstance(
            value, float
        ):
            return round(value, 6)
        return value

    @property
    def last_reset(self):
        """Daily monetary totals reset at the local calendar midnight."""
        if self.entity_description.key in ("daily_cost", "daily_savings"):
            data = self.coordinator.data
            day = (data.billing or {}).get("metadata", {}).get("day") if data else None
            if day:
                return datetime.combine(
                    datetime.fromisoformat(day).date(),
                    time.min,
                    tzinfo=self.coordinator._local_tz(),
                )
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes for the main modifier sensor."""
        if self.coordinator.data is None:
            return None

        data = self.coordinator.data
        key = self.entity_description.key

        if key in {description.key for description in ACCOUNTING_DESCRIPTIONS}:
            attributes = dict(
                (data.billing or {}).get("settlement", {}).get("metadata", {})
            )
            if key not in (
                "accounting_status",
                "consumption_profile",
                "forecast_balance",
            ):
                for large in (
                    "consumption_profile",
                    "settled_bills",
                    "months",
                    "history_months",
                    "cost_actual_series",
                    "cost_forecast_series",
                    "advance_paid_series",
                    "advance_planned_series",
                ):
                    attributes.pop(large, None)
            return attributes

        if key in {description.key for description in PRICING_DESCRIPTIONS}:
            billing = data.billing or {}
            attributes = dict(billing.get("metadata", {}))
            if key in ("total_price", "price_forecast"):
                attributes["forecast"] = billing.get("forecast", [])
            return attributes

        if key == "today_tariff_map":
            return {
                ATTR_DAY_TYPE: data.day_type,
                ATTR_DAY_TYPE_CODE: data.day_type_code,
                ATTR_DISPLAY_MAP: data.today_display_map,
                ATTR_LEGEND: data.today_legend,
                ATTR_SCHEDULE: data.today_schedule,
                ATTR_SCHEDULE_REVISION: data.today_schedule_revision,
                ATTR_SCHEDULE_SOURCE_URL: data.today_schedule_source_url,
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
                ATTR_SCHEDULE_REVISION: data.tomorrow_schedule_revision,
                ATTR_SCHEDULE_SOURCE_URL: data.tomorrow_schedule_source_url,
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
            ATTR_SCHEDULE_REVISION: data.today_schedule_revision,
            ATTR_SCHEDULE_SOURCE_URL: data.today_schedule_source_url,
            ATTR_SEASON: data.season,
            ATTR_SEASON_CODE: data.season_code,
        }
