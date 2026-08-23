from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_BASE_PRICE_KWH,
    CONF_CHEAP_THRESHOLD,
    CONF_EXPENSIVE_THRESHOLD,
    CONF_INCLUDE_HOLIDAYS,
    CONF_NAME,
    CONF_RESET_SCHEDULES,
    CONF_SUMMER_OFFDAY_SCHEDULE,
    CONF_SUMMER_WORKDAY_SCHEDULE,
    CONF_SUPER_CHEAP_THRESHOLD,
    CONF_WINTER_OFFDAY_SCHEDULE,
    CONF_WINTER_WORKDAY_SCHEDULE,
    DEFAULT_BASE_PRICE_KWH,
    DEFAULT_CHEAP_THRESHOLD,
    DEFAULT_EXPENSIVE_THRESHOLD,
    DEFAULT_INCLUDE_HOLIDAYS,
    DEFAULT_NAME,
    DEFAULT_SUPER_CHEAP_THRESHOLD,
    DOMAIN,
)
from .schedule import DEFAULT_SCHEDULES, format_schedule_starts, parse_schedule_starts

SCHEDULE_OPTIONS = (
    CONF_WINTER_WORKDAY_SCHEDULE,
    CONF_WINTER_OFFDAY_SCHEDULE,
    CONF_SUMMER_WORKDAY_SCHEDULE,
    CONF_SUMMER_OFFDAY_SCHEDULE,
)


def _validate_thresholds(user_input) -> dict[str, str]:
    """Validate threshold relationships."""
    cheap_threshold = int(user_input[CONF_CHEAP_THRESHOLD])
    super_cheap_threshold = int(user_input[CONF_SUPER_CHEAP_THRESHOLD])
    expensive_threshold = int(user_input[CONF_EXPENSIVE_THRESHOLD])

    if super_cheap_threshold > cheap_threshold:
        return {"base": "super_cheap_above_cheap"}

    if cheap_threshold >= expensive_threshold:
        return {"base": "cheap_not_below_expensive"}

    return {}


def _schedule_default(config_entry, option: str) -> str:
    """Return a saved schedule or the project default for the options form."""
    value = config_entry.options.get(option)
    if isinstance(value, str):
        return value
    return format_schedule_starts(DEFAULT_SCHEDULES[option])


def _validate_schedules(user_input) -> dict[str, str]:
    """Validate editable tariff window starts."""
    if user_input[CONF_RESET_SCHEDULES]:
        return {}

    errors: dict[str, str] = {}
    for option in SCHEDULE_OPTIONS:
        try:
            parse_schedule_starts(str(user_input[option]), DEFAULT_SCHEDULES[option])
        except ValueError:
            errors[option] = "invalid_schedule"

    return errors


def _options_schema(config_entry) -> vol.Schema:
    """Build options schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_BASE_PRICE_KWH,
                default=float(
                    config_entry.options.get(
                        CONF_BASE_PRICE_KWH,
                        config_entry.data.get(CONF_BASE_PRICE_KWH, DEFAULT_BASE_PRICE_KWH),
                    )
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required(
                CONF_INCLUDE_HOLIDAYS,
                default=bool(
                    config_entry.options.get(
                        CONF_INCLUDE_HOLIDAYS,
                        config_entry.data.get(CONF_INCLUDE_HOLIDAYS, DEFAULT_INCLUDE_HOLIDAYS),
                    )
                ),
            ): bool,
            vol.Required(
                CONF_CHEAP_THRESHOLD,
                default=int(
                    config_entry.options.get(
                        CONF_CHEAP_THRESHOLD,
                        DEFAULT_CHEAP_THRESHOLD,
                    )
                ),
            ): vol.Coerce(int),
            vol.Required(
                CONF_SUPER_CHEAP_THRESHOLD,
                default=int(
                    config_entry.options.get(
                        CONF_SUPER_CHEAP_THRESHOLD,
                        DEFAULT_SUPER_CHEAP_THRESHOLD,
                    )
                ),
            ): vol.Coerce(int),
            vol.Required(
                CONF_EXPENSIVE_THRESHOLD,
                default=int(
                    config_entry.options.get(
                        CONF_EXPENSIVE_THRESHOLD,
                        DEFAULT_EXPENSIVE_THRESHOLD,
                    )
                ),
            ): vol.Coerce(int),
            vol.Required(CONF_RESET_SCHEDULES, default=False): bool,
            vol.Required(
                CONF_WINTER_WORKDAY_SCHEDULE,
                default=_schedule_default(config_entry, CONF_WINTER_WORKDAY_SCHEDULE),
            ): str,
            vol.Required(
                CONF_WINTER_OFFDAY_SCHEDULE,
                default=_schedule_default(config_entry, CONF_WINTER_OFFDAY_SCHEDULE),
            ): str,
            vol.Required(
                CONF_SUMMER_WORKDAY_SCHEDULE,
                default=_schedule_default(config_entry, CONF_SUMMER_WORKDAY_SCHEDULE),
            ): str,
            vol.Required(
                CONF_SUMMER_OFFDAY_SCHEDULE,
                default=_schedule_default(config_entry, CONF_SUMMER_OFFDAY_SCHEDULE),
            ): str,
        }
    )


class CezDynamicTariffConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ČEZ Dynamic Tariff."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            data = {
                CONF_NAME: str(user_input[CONF_NAME]),
                CONF_BASE_PRICE_KWH: float(user_input[CONF_BASE_PRICE_KWH]),
                CONF_INCLUDE_HOLIDAYS: bool(user_input[CONF_INCLUDE_HOLIDAYS]),
            }

            options = {
                CONF_BASE_PRICE_KWH: float(user_input[CONF_BASE_PRICE_KWH]),
                CONF_INCLUDE_HOLIDAYS: bool(user_input[CONF_INCLUDE_HOLIDAYS]),
                CONF_CHEAP_THRESHOLD: DEFAULT_CHEAP_THRESHOLD,
                CONF_SUPER_CHEAP_THRESHOLD: DEFAULT_SUPER_CHEAP_THRESHOLD,
                CONF_EXPENSIVE_THRESHOLD: DEFAULT_EXPENSIVE_THRESHOLD,
            }

            return self.async_create_entry(
                title=str(user_input[CONF_NAME]),
                data=data,
                options=options,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(
                    CONF_BASE_PRICE_KWH,
                    default=DEFAULT_BASE_PRICE_KWH,
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                vol.Required(
                    CONF_INCLUDE_HOLIDAYS,
                    default=DEFAULT_INCLUDE_HOLIDAYS,
                ): bool,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return CezDynamicTariffOptionsFlow(config_entry)


class CezDynamicTariffOptionsFlow(config_entries.OptionsFlow):
    """Handle integration options."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            errors = _validate_thresholds(user_input)
            errors.update(_validate_schedules(user_input))
            if errors:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_options_schema(self._config_entry),
                    errors=errors,
                )

            options = {
                CONF_BASE_PRICE_KWH: float(user_input[CONF_BASE_PRICE_KWH]),
                CONF_INCLUDE_HOLIDAYS: bool(user_input[CONF_INCLUDE_HOLIDAYS]),
                CONF_CHEAP_THRESHOLD: int(user_input[CONF_CHEAP_THRESHOLD]),
                CONF_SUPER_CHEAP_THRESHOLD: int(user_input[CONF_SUPER_CHEAP_THRESHOLD]),
                CONF_EXPENSIVE_THRESHOLD: int(user_input[CONF_EXPENSIVE_THRESHOLD]),
            }

            if not user_input[CONF_RESET_SCHEDULES]:
                options.update(
                    {
                        option: format_schedule_starts(
                            parse_schedule_starts(
                                str(user_input[option]),
                                DEFAULT_SCHEDULES[option],
                            )
                        )
                        for option in SCHEDULE_OPTIONS
                    }
                )

            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._config_entry),
        )
