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
from .settlement import (
    SETTLEMENT_DEFAULTS,
    advance_paid_amount,
    automatic_from,
    default_period,
    month_starts,
    parse_advances,
)

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
            vol.Required("import_price_list", default=False): bool,
            vol.Required("configure_accounting", default=False): bool,
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
        self._price_list_info = None

    async def async_step_init(self, user_input=None):
        """Configure general tariff options."""
        if user_input is not None:
            if user_input.get("configure_accounting"):
                self._pending_options = {}
                return await self.async_step_accounting()
            if user_input.get("import_price_list"):
                # Import changes only new price-profile values. Original entity
                # settings and schedules must remain exactly as saved.
                self._pending_options = {}
                return await self.async_step_price_list()
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

    async def async_step_price_list(self, user_input=None):
        """Upload a ČEZ PDF or read its public HTTPS URL, then review rates."""
        from homeassistant.helpers import selector
        from homeassistant.util import dt as dt_util

        from .price_list import PriceListError
        from .price_list_import import async_import_price_list

        errors = {}
        if user_input is not None:
            has_file = bool(user_input.get("price_list_file"))
            has_url = bool(str(user_input.get("price_list_url", "")).strip())
            annual = finite_number(user_input["annual_import_kwh"])
            if annual is None or annual < 0:
                errors["annual_import_kwh"] = "invalid_price"
            elif has_file == has_url:
                errors["base"] = "choose_one_price_list_source"
            else:
                try:
                    imported, source = await async_import_price_list(
                        self.hass, user_input
                    )
                    if (
                        max(imported.trade_effective, imported.distribution_effective)
                        > dt_util.now().date().isoformat()
                    ):
                        raise PriceListError("future_price_list")
                except PriceListError as err:
                    errors["base"] = str(err)
                else:
                    self._price_list_info = {
                        "source": source,
                        "rate": user_input["distribution_rate"],
                        "breaker": f"{user_input['breaker_phases']}×{user_input['breaker_amperes']} A",
                        "trade_effective": imported.trade_effective,
                        "distribution_effective": imported.distribution_effective,
                        "poze_estimated": "yes" if imported.poze_estimated else "no",
                    }
                    self._pending_options.update(imported.rates)
                    self._pending_options.update(
                        {
                            k: user_input[k]
                            for k in (
                                "distribution_rate",
                                "breaker_amperes",
                                "breaker_phases",
                                "annual_import_kwh",
                            )
                        }
                    )
                    self._pending_options.update(
                        {
                            "price_list_source": source,
                            "price_list_sha256": imported.digest,
                            "price_list_trade_effective": imported.trade_effective,
                            "price_list_distribution_effective": imported.distribution_effective,
                            "price_list_imported_at": dt_util.utcnow().isoformat(),
                            "price_list_poze_estimated": imported.poze_estimated,
                        }
                    )
                    return await self.async_step_price_list_review()
        schema = {
            vol.Optional("price_list_file"): selector.FileSelector(
                selector.FileSelectorConfig(accept=".pdf,application/pdf")
            ),
            vol.Optional("price_list_url"): str,
            vol.Required(
                "distribution_rate",
                default=_option_default(
                    self._config_entry, user_input, "distribution_rate", "D57d"
                ),
            ): str,
            vol.Required(
                "breaker_amperes",
                default=_option_default(
                    self._config_entry, user_input, "breaker_amperes", 25
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000)),
            vol.Required(
                "breaker_phases",
                default=_option_default(
                    self._config_entry, user_input, "breaker_phases", 3
                ),
            ): vol.All(vol.Coerce(int), vol.In((1, 3))),
            vol.Required(
                "annual_import_kwh",
                default=_option_default(
                    self._config_entry, user_input, "annual_import_kwh", 0.0
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0)),
        }
        return self.async_show_form(
            step_id="price_list",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={"cez_website": "https://www.cez.cz"},
        )

    async def async_step_price_list_review(self, user_input=None):
        """Confirm/edit the parsed VAT-inclusive rates before saving."""
        return await self.async_step_price_rates(user_input)

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
                if self._price_list_info and not user_input.get("confirm_price_list"):
                    errors["base"] = "confirm_price_list"
                else:
                    self._pending_options.update(
                        {k: float(user_input[k]) for k in keys}
                    )
                    if self._price_list_info:
                        self._pending_options["price_list_rates_edited"] = any(
                            float(user_input[k])
                            != self._pending_imported_rates.get(k, float(user_input[k]))
                            for k in keys
                        )
                    elif self._config_entry.options.get("price_list_sha256"):
                        self._pending_options["price_list_rates_edited"] = bool(
                            self._config_entry.options.get("price_list_rates_edited")
                        ) or any(
                            float(user_input[k])
                            != self._config_entry.options.get(k, PROFILE_DEFAULTS[k])
                            for k in keys
                        )
                    return self._finish_options()
        if self._price_list_info and not hasattr(self, "_pending_imported_rates"):
            self._pending_imported_rates = {
                k: self._pending_options[k] for k in keys if k in self._pending_options
            }
        schema = vol.Schema(
            {
                vol.Required(
                    k,
                    default=(
                        user_input[k]
                        if user_input and k in user_input
                        else self._pending_options.get(
                            k,
                            _option_default(
                                self._config_entry, None, k, PROFILE_DEFAULTS[k]
                            ),
                        )
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0))
                for k in keys
            }
        )
        if self._price_list_info:
            schema = schema.extend(
                {vol.Required("confirm_price_list", default=False): bool}
            )
        return self.async_show_form(
            step_id="price_list_review" if self._price_list_info else "price_rates",
            data_schema=schema,
            errors=errors,
            description_placeholders=self._price_list_info or {},
        )

    async def async_step_accounting(self, user_input=None):
        """Independent accounting options preserve original schedules and IDs."""
        from datetime import date

        from homeassistant.helpers import selector
        from homeassistant.util import dt as dt_util

        keys = (
            "accounting_enabled",
            "billing_start",
            "billing_end",
            "dynamic_start",
            "dynamic_contract_mode",
            "current_price_start",
            "advance_mode",
            "automatic_advances",
            "accounting_energy_entity",
            "deduct_shared_income",
            "shared_income_entity",
            "historical_cost_entity",
        )
        defaults = dict(SETTLEMENT_DEFAULTS)
        defaults["billing_start"], defaults["billing_end"] = default_period(
            dt_util.now().date()
        )
        defaults["current_price_start"] = self._config_entry.options.get(
            "price_list_trade_effective", ""
        )
        errors = {}
        if user_input is not None:
            try:
                start, end = (
                    date.fromisoformat(user_input["billing_start"]),
                    date.fromisoformat(user_input["billing_end"]),
                )
                if not start < end or (end - start).days > 370:
                    raise ValueError
                for key in ("dynamic_start", "current_price_start"):
                    if user_input.get(key):
                        date.fromisoformat(user_input[key])
            except (KeyError, ValueError, TypeError):
                errors["base"] = "invalid_accounting_dates"
            if user_input.get(
                "accounting_enabled"
            ) and not self._config_entry.options.get("pricing_enabled"):
                errors["base"] = "pricing_required"
            for key in ("historical_cost_entity", "shared_income_entity"):
                entity = user_input.get(key)
                state = self.hass.states.get(entity) if entity else None
                if entity and (
                    state is None
                    or not (
                        state.attributes.get("energy_revenue_statistic_id")
                        or state.attributes.get("unit_of_measurement") == "CZK"
                    )
                ):
                    errors[key] = "invalid_monetary_entity"
            if user_input.get("deduct_shared_income") and not user_input.get(
                "shared_income_entity"
            ):
                errors["shared_income_entity"] = "missing_entity"
            energy = user_input.get("accounting_energy_entity")
            energy_state = self.hass.states.get(energy) if energy else None
            if energy and (
                energy_state is None
                or energy_state.attributes.get("unit_of_measurement")
                not in ("Wh", "kWh", "MWh")
            ):
                errors["accounting_energy_entity"] = "invalid_energy_entity"
            if not errors:
                self._pending_options.update(
                    {k: user_input.get(k, defaults[k]) for k in keys}
                )
                if user_input.get(
                    "automatic_advances"
                ) and not self._config_entry.options.get("automatic_advances"):
                    self._pending_options["automatic_advances_from"] = automatic_from(
                        dt_util.now().date()
                    )
                elif not user_input.get("automatic_advances"):
                    self._pending_options["automatic_advances_from"] = ""
                return await self.async_step_advances()
        schema = {}
        for key in keys:
            value = _option_default(self._config_entry, user_input, key, defaults[key])
            marker = (
                vol.Required(key, default=value)
                if key
                not in (
                    "dynamic_start",
                    "current_price_start",
                    "historical_cost_entity",
                    "shared_income_entity",
                    "accounting_energy_entity",
                )
                else vol.Optional(
                    key, description={"suggested_value": value} if value else {}
                )
            )
            if key.endswith("entity"):
                schema[marker] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                )
            elif key in (
                "billing_start",
                "billing_end",
                "dynamic_start",
                "current_price_start",
            ):
                schema[marker] = selector.DateSelector()
            elif key == "advance_mode":
                schema[marker] = selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["annual", "monthly"], translation_key="advance_mode"
                    )
                )
            elif key == "dynamic_contract_mode":
                schema[marker] = selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["unknown", "regular", "trial"],
                        translation_key="dynamic_contract_mode",
                    )
                )
            else:
                schema[marker] = bool
        return self.async_show_form(
            step_id="accounting", data_schema=vol.Schema(schema), errors=errors
        )

    async def async_step_monthly_advances(self, user_input=None):
        """Dispatch the monthly form through Home Assistant's flow manager."""
        return await self.async_step_advances(user_input)

    async def async_step_advances(self, user_input=None):
        """Annual aggregates or individually entered monthly paid/planned amounts."""
        import json
        from datetime import date

        start, end = (
            date.fromisoformat(self._pending_options[k])
            for k in ("billing_start", "billing_end")
        )
        months = list(month_starts(start, end))
        mode = self._pending_options["advance_mode"]
        errors = {}
        if user_input is not None:
            if mode == "annual":
                total, paid = (
                    finite_number(user_input.get(k))
                    for k in ("advance_total", "advance_paid")
                )
                if total is None or paid is None or not 0 <= paid <= total:
                    errors["base"] = "invalid_advances"
                else:
                    self._pending_options.update(advance_total=total, advance_paid=paid)
            else:
                rows = [
                    {
                        "month": m.strftime("%Y-%m"),
                        "amount": user_input[f"month_{i}_amount"],
                        "paid": user_input.get(f"month_{i}_paid", False),
                    }
                    for i, m in enumerate(months, 1)
                    if f"month_{i}_amount" in user_input
                ]
                saved_rows = {
                    r["month"]: r
                    for r in json.loads(
                        self._config_entry.options.get("monthly_advances", "[]")
                    )
                }
                for i, m in enumerate(months, 1):
                    row = next(
                        (r for r in rows if r["month"] == m.strftime("%Y-%m")), None
                    )
                    if row is None:
                        continue
                    key = f"month_{i}_paid_amount"
                    if key in user_input:
                        paid_amount = row["amount"] if row["paid"] else user_input[key]
                        row.update(
                            paid_amount=paid_amount, paid=paid_amount == row["amount"]
                        )
                    old_row = saved_rows.get(row["month"], {})
                    if advance_paid_amount(row) == advance_paid_amount(
                        old_row or {"amount": 0}
                    ):
                        row.update(
                            {
                                k: v
                                for k, v in old_row.items()
                                if k not in ("amount", "paid", "paid_amount", "month")
                            }
                        )
                try:
                    parse_advances(json.dumps(rows), start, end)
                    self._pending_options["monthly_advances"] = json.dumps(rows)
                except (ValueError, TypeError, KeyError):
                    errors["base"] = "invalid_advances"
            if not errors:
                return await self.async_step_accounting_history()
        schema = {}
        if mode == "annual":
            for key in ("advance_total", "advance_paid"):
                schema[
                    vol.Required(
                        key,
                        default=_option_default(
                            self._config_entry, user_input, key, 0.0
                        ),
                    )
                ] = vol.All(vol.Coerce(float), vol.Range(min=0))
        else:
            saved = {
                r["month"]: r
                for r in json.loads(
                    self._config_entry.options.get("monthly_advances", "[]")
                )
            }
            for i, month in enumerate(months, 1):
                row = saved.get(month.strftime("%Y-%m"), {})
                value = (user_input or {}).get(f"month_{i}_amount", row.get("amount"))
                schema[
                    vol.Optional(
                        f"month_{i}_amount",
                        description={"suggested_value": value}
                        if value is not None
                        else {},
                    )
                ] = vol.All(vol.Coerce(float), vol.Range(min=0))
                schema[
                    vol.Required(
                        f"month_{i}_paid",
                        default=(user_input or {}).get(
                            f"month_{i}_paid", row.get("paid", False)
                        ),
                    )
                ] = bool
                paid_value = (user_input or {}).get(
                    f"month_{i}_paid_amount", row.get("paid_amount")
                )
                schema[
                    vol.Optional(
                        f"month_{i}_paid_amount",
                        description={"suggested_value": paid_value}
                        if paid_value is not None
                        else {},
                    )
                ] = vol.All(vol.Coerce(float), vol.Range(min=0))
        return self.async_show_form(
            step_id="advances" if mode == "annual" else "monthly_advances",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "months": ", ".join(
                    f"{i}: {m.strftime('%Y-%m')}" for i, m in enumerate(months, 1)
                )
            },
        )

    async def async_step_accounting_history(self, user_input=None):
        """Optional provider checkpoint and verified settled bills; never fake old HDO."""
        import json
        from datetime import date

        from homeassistant.helpers import selector

        keys = (
            "reference_date",
            "reference_energy",
            "reference_cost",
            "settled_bills",
            "historical_profiles",
        )
        errors = {}
        if user_input is not None:
            try:
                reference = user_input.get("reference_date")
                if reference and not date.fromisoformat(
                    self._pending_options["billing_start"]
                ) <= date.fromisoformat(reference) <= date.fromisoformat(
                    self._pending_options["billing_end"]
                ):
                    raise ValueError
                bills = json.loads(user_input["settled_bills"])
                profiles = json.loads(user_input["historical_profiles"])
                if (
                    not isinstance(bills, list)
                    or not isinstance(profiles, list)
                    or len(bills) > 24
                    or len(profiles) > 24
                ):
                    raise ValueError
                for bill in bills:
                    if date.fromisoformat(bill["start"]) > date.fromisoformat(
                        bill["end"]
                    ):
                        raise ValueError
                    for key in ("energy_kwh", "cost", "paid"):
                        if finite_number(bill[key]) is None or bill[key] < 0:
                            raise ValueError
                    if "fixed_cost" in bill and (
                        finite_number(bill["fixed_cost"]) is None
                        or bill["fixed_cost"] < 0
                    ):
                        raise ValueError
                    seen = set()
                    for row in bill.get("months", []):
                        month = date.fromisoformat(row["month"] + "-01")
                        if row["month"] in seen or not date.fromisoformat(
                            bill["start"]
                        ).replace(day=1) <= month <= date.fromisoformat(bill["end"]):
                            raise ValueError
                        seen.add(row["month"])
                        if any(
                            finite_number(row[k]) is None or row[k] < 0
                            for k in ("nt_kwh", "vt_kwh")
                        ):
                            raise ValueError
                rate_keys = {
                    k
                    for k, v in PROFILE_DEFAULTS.items()
                    if isinstance(v, float) and k != "annual_import_kwh"
                }
                for row in profiles:
                    if (
                        date.fromisoformat(row["start"])
                        > date.fromisoformat(row["end"])
                        or set(row["rates"]) != rate_keys
                    ):
                        raise ValueError
                    if any(
                        finite_number(v) is None or v < 0 for v in row["rates"].values()
                    ):
                        raise ValueError
                for key in ("reference_energy", "reference_cost"):
                    if finite_number(user_input[key]) is None or user_input[key] < 0:
                        raise ValueError
            except (KeyError, ValueError, TypeError):
                errors["base"] = "invalid_accounting_history"
            if not errors:
                self._pending_options.update(
                    {k: user_input.get(k, SETTLEMENT_DEFAULTS[k]) for k in keys}
                )
                self._pending_options["reference_period_start"] = self._pending_options[
                    "billing_start"
                ]
                return self._finish_options()
        schema = {}
        for key in keys:
            value = _option_default(
                self._config_entry, user_input, key, SETTLEMENT_DEFAULTS[key]
            )
            if (
                user_input is None
                and key.startswith("reference_")
                and self._config_entry.options.get("reference_period_start")
                != self._pending_options["billing_start"]
            ):
                value = SETTLEMENT_DEFAULTS[key]
            if key == "reference_date":
                schema[
                    vol.Optional(
                        key, description={"suggested_value": value} if value else {}
                    )
                ] = selector.DateSelector()
            elif key in ("reference_energy", "reference_cost"):
                schema[vol.Required(key, default=value)] = vol.All(
                    vol.Coerce(float), vol.Range(min=0)
                )
            else:
                schema[vol.Required(key, default=value)] = selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                )
        return self.async_show_form(
            step_id="accounting_history", data_schema=vol.Schema(schema), errors=errors
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
