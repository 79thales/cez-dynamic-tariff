from homeassistant.const import Platform

DOMAIN = "cez_dynamic_tariff"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_NAME = "name"
CONF_BASE_PRICE_KWH = "base_price_kwh"
CONF_INCLUDE_HOLIDAYS = "include_holidays"
CONF_CHEAP_THRESHOLD = "cheap_threshold"
CONF_SUPER_CHEAP_THRESHOLD = "super_cheap_threshold"
CONF_EXPENSIVE_THRESHOLD = "expensive_threshold"
CONF_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"
CONF_RESET_SCHEDULES = "reset_schedules"
CONF_SUMMER_OFFDAY_SCHEDULE = "summer_offday_schedule"
CONF_SUMMER_WORKDAY_SCHEDULE = "summer_workday_schedule"
CONF_WINTER_OFFDAY_SCHEDULE = "winter_offday_schedule"
CONF_WINTER_WORKDAY_SCHEDULE = "winter_workday_schedule"

DEFAULT_NAME = "ČEZ Dynamic Tariff"
DEFAULT_BASE_PRICE_KWH = 0.0
DEFAULT_INCLUDE_HOLIDAYS = True
DEFAULT_CHEAP_THRESHOLD = -10
DEFAULT_SUPER_CHEAP_THRESHOLD = -50
DEFAULT_EXPENSIVE_THRESHOLD = 10
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 25
DEFAULT_UPDATE_INTERVAL_SECONDS = 60

ATTR_BASE_PRICE_KWH = "base_price_kwh"
ATTR_CURRENT_WINDOW_START = "current_window_start"
ATTR_CURRENT_WINDOW_END = "current_window_end"
ATTR_DAY_TYPE = "day_type"
ATTR_DISPLAY_MAP = "display_map"
ATTR_IS_HOLIDAY = "is_holiday"
ATTR_LEGEND = "legend"
ATTR_NEXT_CHEAP_MODIFIER_PERCENT = "next_cheap_modifier_percent"
ATTR_SCHEDULE = "schedule"
ATTR_SEASON = "season"
