from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_BASE_PRICE_KWH,
    CONF_CHEAP_THRESHOLD,
    CONF_CONFIRM_RESET,
    CONF_EXPENSIVE_THRESHOLD,
    CONF_INCLUDE_HOLIDAYS,
    CONF_NAME,
    CONF_RESET_SCHEDULES,
    CONF_SUMMER_OFFDAY_SCHEDULE,
    CONF_SUMMER_WORKDAY_SCHEDULE,
    CONF_SUPER_CHEAP_THRESHOLD,
    CONF_VERY_EXPENSIVE_THRESHOLD,
    CONF_WINTER_OFFDAY_SCHEDULE,
    CONF_WINTER_WORKDAY_SCHEDULE,
    DEFAULT_BASE_PRICE_KWH,
    DEFAULT_CHEAP_THRESHOLD,
    DEFAULT_EXPENSIVE_THRESHOLD,
    DEFAULT_INCLUDE_HOLIDAYS,
    DEFAULT_NAME,
    DEFAULT_SUPER_CHEAP_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DOMAIN,
)
from .pricing import PROFILE_DEFAULTS, finite_number
from .schedule import DEFAULT_SCHEDULES, format_schedule, parse_schedule

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
    very_expensive_threshold = int(user_input[CONF_VERY_EXPENSIVE_THRESHOLD])

    if super_cheap_threshold > cheap_threshold:
        return {"base": "super_cheap_above_cheap"}

    if cheap_threshold >= expensive_threshold:
        return {"base": "cheap_not_below_expensive"}

    if expensive_threshold >= very_expensive_threshold:
        return {"base": "expensive_not_below_very_expensive"}

    return {}


def _schedule_default(config_entry, option: str, user_input=None) -> str:
    """Return a saved schedule or the project default for the options form."""
    if user_input is not None and option in user_input:
        return str(user_input[option])

    value = config_entry.options.get(option)
    if isinstance(value, str):
        try:
            return format_schedule(parse_schedule(value, DEFAULT_SCHEDULES[option]))
        except ValueError:
            pass
    return format_schedule(DEFAULT_SCHEDULES[option])


def _validate_schedules(user_input) -> dict[str, str]:
    """Validate editable tariff schedules."""
    errors: dict[str, str] = {}
    for option in SCHEDULE_OPTIONS:
        try:
            parse_schedule(str(user_input[option]), DEFAULT_SCHEDULES[option])
        except ValueError:
            errors[option] = "invalid_schedule"

    return errors


def _option_default(config_entry, user_input, option: str, default):
    """Return a submitted, saved, configured, or default option value."""
    if user_input is not None and option in user_input:
        return user_input[option]
    if option in config_entry.options:
        return config_entry.options[option]
    if option in config_entry.data:
        return config_entry.data[option]
    return default


def _general_schema(config_entry, user_input=None) -> vol.Schema:
    """Build the general options schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_BASE_PRICE_KWH,
                default=float(
                    _option_default(
                        config_entry,
                        user_input,
                        CONF_BASE_PRICE_KWH,
                        DEFAULT_BASE_PRICE_KWH,
                    )
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required(
                CONF_INCLUDE_HOLIDAYS,
                default=bool(
                    _option_default(
                        config_entry,
                        user_input,
                        CONF_INCLUDE_HOLIDAYS,
                        DEFAULT_INCLUDE_HOLIDAYS,
                    )
                ),
            ): bool,
            vol.Required(
                CONF_RESET_SCHEDULES,
                default=bool(
                    user_input.get(CONF_RESET_SCHEDULES, False)
                    if user_input is not None
                    else False
                ),
            ): bool,
            vol.Required("configure_pricing", default=False): bool,
        }
    )


def _thresholds_schema(config_entry, user_input=None) -> vol.Schema:
    """Build the tariff classification thresholds schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SUPER_CHEAP_THRESHOLD,
                default=int(
                    _option_default(
                        config_entry,
                        user_input,
                        CONF_SUPER_CHEAP_THRESHOLD,
                        DEFAULT_SUPER_CHEAP_THRESHOLD,
                    )
                ),
            ): vol.Coerce(int),
            vol.Required(
                CONF_CHEAP_THRESHOLD,
                default=int(
                    _option_default(
                        config_entry,
                        user_input,
                        CONF_CHEAP_THRESHOLD,
                        DEFAULT_CHEAP_THRESHOLD,
                    )
                ),
            ): vol.Coerce(int),
            vol.Required(
                CONF_EXPENSIVE_THRESHOLD,
                default=int(
                    _option_default(
                        config_entry,
                        user_input,
                        CONF_EXPENSIVE_THRESHOLD,
                        DEFAULT_EXPENSIVE_THRESHOLD,
                    )
                ),
            ): vol.Coerce(int),
            vol.Required(
                CONF_VERY_EXPENSIVE_THRESHOLD,
                default=int(
                    _option_default(
                        config_entry,
                        user_input,
                        CONF_VERY_EXPENSIVE_THRESHOLD,
                        DEFAULT_VERY_EXPENSIVE_THRESHOLD,
                    )
                ),
            ): vol.Coerce(int),
        }
    )


def _schedules_schema(config_entry, user_input=None) -> vol.Schema:
    """Build the editable schedules schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_WINTER_WORKDAY_SCHEDULE,
                default=_schedule_default(
                    config_entry,
                    CONF_WINTER_WORKDAY_SCHEDULE,
                    user_input,
                ),
            ): str,
            vol.Required(
                CONF_WINTER_OFFDAY_SCHEDULE,
                default=_schedule_default(
                    config_entry,
                    CONF_WINTER_OFFDAY_SCHEDULE,
                    user_input,
                ),
            ): str,
            vol.Required(
                CONF_SUMMER_WORKDAY_SCHEDULE,
                default=_schedule_default(
                    config_entry,
                    CONF_SUMMER_WORKDAY_SCHEDULE,
                    user_input,
                ),
            ): str,
            vol.Required(
                CONF_SUMMER_OFFDAY_SCHEDULE,
                default=_schedule_default(
                    config_entry,
                    CONF_SUMMER_OFFDAY_SCHEDULE,
                    user_input,
                ),
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
                CONF_VERY_EXPENSIVE_THRESHOLD: DEFAULT_VERY_EXPENSIVE_THRESHOLD,
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
        self._pending_options = {}
        self._restore_schedules = False

    async def async_step_init(self, user_input=None):
        """Configure general tariff options."""
        if user_input is not None:
            self._pending_options = {
                CONF_BASE_PRICE_KWH: float(user_input[CONF_BASE_PRICE_KWH]),
                CONF_INCLUDE_HOLIDAYS: bool(user_input[CONF_INCLUDE_HOLIDAYS]),
                CONF_RESET_SCHEDULES: bool(user_input[CONF_RESET_SCHEDULES]),
                "configure_pricing": bool(user_input.get("configure_pricing", False)),
            }
            return await self.async_step_thresholds()

        return self.async_show_form(
            step_id="init",
            data_schema=_general_schema(self._config_entry),
        )

    async def async_step_thresholds(self, user_input=None):
        """Configure tariff classification thresholds."""
        if user_input is not None:
            errors = _validate_thresholds(user_input)
            if errors:
                return self.async_show_form(
                    step_id="thresholds",
                    data_schema=_thresholds_schema(self._config_entry, user_input),
                    errors=errors,
                )

            self._pending_options.update(
                {
                    CONF_CHEAP_THRESHOLD: int(user_input[CONF_CHEAP_THRESHOLD]),
                    CONF_SUPER_CHEAP_THRESHOLD: int(
                        user_input[CONF_SUPER_CHEAP_THRESHOLD]
                    ),
                    CONF_EXPENSIVE_THRESHOLD: int(user_input[CONF_EXPENSIVE_THRESHOLD]),
                    CONF_VERY_EXPENSIVE_THRESHOLD: int(
                        user_input[CONF_VERY_EXPENSIVE_THRESHOLD]
                    ),
                }
            )

            if self._pending_options[CONF_RESET_SCHEDULES]:
                return await self.async_step_reset_schedules()
            return await self.async_step_schedules()

        return self.async_show_form(
            step_id="thresholds",
            data_schema=_thresholds_schema(self._config_entry),
        )

    async def async_step_schedules(self, user_input=None):
        """Configure all four editable tariff schedules."""
        if user_input is not None:
            errors = _validate_schedules(user_input)
            if errors:
                return self.async_show_form(
                    step_id="schedules",
                    data_schema=_schedules_schema(self._config_entry, user_input),
                    errors=errors,
                )

            self._pending_options.update(
                {
                    option: format_schedule(
                        parse_schedule(
                            str(user_input[option]),
                            DEFAULT_SCHEDULES[option],
                        )
                    )
                    for option in SCHEDULE_OPTIONS
                }
            )
            return await self._pricing_or_finish()

        return self.async_show_form(
            step_id="schedules",
            data_schema=_schedules_schema(self._config_entry),
        )

    async def async_step_reset_schedules(self, user_input=None):
        """Confirm restoring all project default schedules."""
        if user_input is not None:
            if not user_input[CONF_CONFIRM_RESET]:
                return self.async_show_form(
                    step_id="reset_schedules",
                    data_schema=vol.Schema(
                        {vol.Required(CONF_CONFIRM_RESET, default=False): bool}
                    ),
                    errors={"base": "confirm_reset"},
                )

            options = dict(self._config_entry.options)
            options.update(self._pending_options)
            options.pop(CONF_RESET_SCHEDULES, None)
            for option in SCHEDULE_OPTIONS:
                options.pop(option, None)
            self._pending_options = options
            self._restore_schedules = True
            return await self._pricing_or_finish()

        return self.async_show_form(
            step_id="reset_schedules",
            data_schema=vol.Schema(
                {vol.Required(CONF_CONFIRM_RESET, default=False): bool}
            ),
        )

    async def _pricing_or_finish(self):
        if self._pending_options.get("configure_pricing"):
            return await self.async_step_pricing()
        return self._finish_options()

    async def async_step_pricing(self, user_input=None):
        """Select existing HDO entities; retain all original entities unchanged."""
        from homeassistant.helpers import selector

        keys = (
            "pricing_enabled",
            "dynamic_pricing",
            "include_standing_fees",
            "distribution_rate",
            "breaker_amperes",
            "breaker_phases",
            "hdo_entity",
            "hdo_schedule_entity",
            "hdo_valid_entity",
            "import_energy_entity",
            "annual_import_kwh",
        )
        errors = {}
        if user_input is not None:
            for key in ("breaker_amperes", "annual_import_kwh"):
                value = finite_number(user_input.get(key))
                if (
                    value is None
                    or value < 0
                    or (key == "breaker_amperes" and value == 0)
                ):
                    errors[key] = "invalid_price"
            if user_input["pricing_enabled"]:
                for key in ("hdo_entity", "hdo_schedule_entity", "hdo_valid_entity"):
                    if not user_input.get(key) or not self.hass.states.get(
                        user_input[key]
                    ):
                        errors[key] = "missing_entity"
                meter = user_input.get("import_energy_entity")
                if meter:
                    state = self.hass.states.get(meter)
                    if state is None or state.attributes.get(
                        "unit_of_measurement"
                    ) not in ("Wh", "kWh", "MWh"):
                        errors["import_energy_entity"] = "invalid_energy_entity"
            if not errors:
                self._pending_options.update(
                    {key: user_input.get(key, PROFILE_DEFAULTS[key]) for key in keys}
                )
                return await self.async_step_price_rates()
        schema = {}
        for key in keys:
            default = _option_default(
                self._config_entry, user_input, key, PROFILE_DEFAULTS[key]
            )
            if key.endswith("entity"):
                if not default:
                    prefixes = {
                        "hdo_entity": "binary_sensor.cez_hdo_lowtariffactive_",
                        "hdo_schedule_entity": "sensor.cez_hdo_schedule_",
                        "hdo_valid_entity": "binary_sensor.cez_hdo_data_valid_",
                    }
                    candidates = [
                        state.entity_id
                        for state in self.hass.states.async_all()
                        if (
                            key in prefixes
                            and state.entity_id.startswith(prefixes[key])
                        )
                        or (
                            key == "import_energy_entity"
                            and "total_energy_import" in state.entity_id
                            and state.attributes.get("device_class") == "energy"
                        )
                    ]
                    if len(candidates) == 1:
                        default = candidates[0]
                domain = (
                    "binary_sensor"
                    if key in ("hdo_entity", "hdo_valid_entity")
                    else "sensor"
                )
                schema[
                    vol.Optional(
                        key, description={"suggested_value": default} if default else {}
                    )
                ] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=domain)
                )
            elif isinstance(PROFILE_DEFAULTS[key], bool):
                schema[vol.Required(key, default=default)] = bool
            elif key == "distribution_rate":
                schema[vol.Required(key, default=default)] = str
            elif key == "breaker_phases":
                schema[vol.Required(key, default=default)] = vol.All(
                    vol.Coerce(int), vol.In((1, 3))
                )
            else:
                schema[vol.Required(key, default=default)] = vol.All(
                    vol.Coerce(float), vol.Range(min=0)
                )
        return self.async_show_form(
            step_id="pricing", data_schema=vol.Schema(schema), errors=errors
        )

    async def async_step_price_rates(self, user_input=None):
        """All component prices include VAT and are freely editable."""
        keys = [
            k
            for k, v in PROFILE_DEFAULTS.items()
            if isinstance(v, float) and k != "annual_import_kwh"
        ]
        errors = {}
        if user_input is not None:
            errors = {
                k: "invalid_price"
                for k in keys
                if finite_number(user_input.get(k)) is None or float(user_input[k]) < 0
            }
            if not errors:
                self._pending_options.update({k: float(user_input[k]) for k in keys})
                return self._finish_options()
        schema = vol.Schema(
            {
                vol.Required(
                    k,
                    default=_option_default(
                        self._config_entry, user_input, k, PROFILE_DEFAULTS[k]
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0))
                for k in keys
            }
        )
        return self.async_show_form(
            step_id="price_rates", data_schema=schema, errors=errors
        )

    def _finish_options(self):
        """Merge submitted values with existing options and finish the flow."""
        options = dict(self._config_entry.options)
        options.update(self._pending_options)
        options.pop(CONF_RESET_SCHEDULES, None)
        options.pop("configure_pricing", None)
        if self._restore_schedules:
            for option in SCHEDULE_OPTIONS:
                options.pop(option, None)
        return self.async_create_entry(title="", data=options)
