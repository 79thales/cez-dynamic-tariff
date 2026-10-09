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
    period_advances,
    update_advance_options,
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
        self._advance_month = None

    async def async_step_init(self, user_input=None):
        """Open the requested task without requiring unrelated financial forms."""
        if user_input is not None:
            return await self.async_step_general(user_input)
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "advance_month",
                "advances",
                "accounting",
                "accounting_history",
                "price_list",
                "general",
            ],
        )

    def _accounting_values(self):
        from homeassistant.util import dt as dt_util

        values = {
            **SETTLEMENT_DEFAULTS,
            **self._config_entry.options,
            **self._pending_options,
        }
        start, end = default_period(dt_util.now().date())
        values["billing_start"] = values["billing_start"] or start
        values["billing_end"] = values["billing_end"] or end
        return values

    async def async_step_general(self, user_input=None):
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
            step_id="general",
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
                return self._finish_options()
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

    async def async_step_advance_month(self, user_input=None):
        """Choose a real month before showing its saved amount and confirmation."""
        from datetime import date

        from homeassistant.helpers import selector
        from homeassistant.util import dt as dt_util

        values = self._accounting_values()
        months = [
            d.strftime("%Y-%m")
            for d in month_starts(
                date.fromisoformat(values["billing_start"]),
                date.fromisoformat(values["billing_end"]),
            )
        ]
        if user_input is not None and user_input.get("month") in months:
            self._advance_month = user_input["month"]
            return await self.async_step_monthly_advances()
        names = (
            "leden",
            "únor",
            "březen",
            "duben",
            "květen",
            "červen",
            "červenec",
            "srpen",
            "září",
            "říjen",
            "listopad",
            "prosinec",
        )
        options = [
            {"value": m, "label": f"{names[int(m[5:]) - 1]} {m[:4]}"} for m in months
        ]
        current = dt_util.now().strftime("%Y-%m")
        return self.async_show_form(
            step_id="advance_month",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "month", default=current if current in months else months[0]
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
            errors={"base": "invalid_advances"} if user_input is not None else {},
        )

    async def async_step_monthly_advances(self, user_input=None):
        """Edit a single month in native Home Assistant settings, without JSON."""
        from datetime import date

        from homeassistant.util import dt as dt_util

        if self._advance_month is None:
            return await self.async_step_advance_month()
        values = self._accounting_values()
        errors = {}
        if user_input is not None:
            try:
                data = {
                    "month": self._advance_month,
                    "amount": user_input["amount"],
                    "paid_amount": user_input.get("paid_amount", 0),
                    "use_monthly": True,
                }
                if user_input.get("confirm_paid"):
                    data["confirm"] = True
                changes = update_advance_options(values, data, dt_util.now().date())
                enabled = bool(user_input.get("automatic_advances", False))
                changes["automatic_advances"] = enabled
                if enabled != bool(values["automatic_advances"]):
                    changes["automatic_advances_from"] = (
                        automatic_from(dt_util.now().date()) if enabled else ""
                    )
            except (ValueError, KeyError, TypeError):
                errors["base"] = "invalid_advances"
            else:
                self._pending_options.update(changes)
                return self._finish_options()
        rows = period_advances(
            values["monthly_advances"],
            date.fromisoformat(values["billing_start"]),
            date.fromisoformat(values["billing_end"]),
        )
        row = next((r for r in rows if r["month"] == self._advance_month), None)
        submitted = user_input or {}
        amount = submitted.get("amount", row["amount"] if row else None)
        paid = submitted.get("paid_amount", advance_paid_amount(row) if row else 0)
        return self.async_show_form(
            step_id="monthly_advances",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "amount",
                        description={"suggested_value": amount}
                        if amount is not None
                        else {},
                    ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1e9)),
                    vol.Required("paid_amount", default=paid): vol.All(
                        vol.Coerce(float), vol.Range(min=0, max=1e9)
                    ),
                    vol.Required(
                        "confirm_paid",
                        default=bool(submitted.get("confirm_paid", False)),
                    ): bool,
                    vol.Required(
                        "automatic_advances",
                        default=bool(
                            submitted.get(
                                "automatic_advances", values["automatic_advances"]
                            )
                        ),
                    ): bool,
                }
            ),
            errors=errors,
            description_placeholders={"month": self._advance_month},
        )

    async def async_step_advances(self, user_input=None):
        """Optional annual aggregate is independent of monthly entries and history."""
        errors = {}
        if user_input is not None:
            total, paid = (
                finite_number(user_input.get(k))
                for k in ("advance_total", "advance_paid")
            )
            if total is None or paid is None or not 0 <= paid <= total:
                errors["base"] = "invalid_advances"
            else:
                self._pending_options.update(
                    advance_mode="annual", advance_total=total, advance_paid=paid
                )
                return self._finish_options()
        schema = {
            vol.Required(
                k, default=_option_default(self._config_entry, user_input, k, 0.0)
            ): vol.All(vol.Coerce(float), vol.Range(min=0))
            for k in ("advance_total", "advance_paid")
        }
        return self.async_show_form(
            step_id="advances", data_schema=vol.Schema(schema), errors=errors
        )

    async def async_step_accounting_history(self, user_input=None):
        """History already backfills automatically; a supplier total is optional."""
        return self.async_show_menu(
            step_id="accounting_history",
            menu_options=["history_auto", "history_reading"],
        )

    async def async_step_history_auto(self, user_input=None):
        """Explicitly use existing HA statistics instead of a manual checkpoint."""
        if user_input is not None:
            self._pending_options["reference_date"] = ""
            return self._finish_options()
        return self.async_show_form(step_id="history_auto", data_schema=vol.Schema({}))

    async def async_step_history_reading(self, user_input=None):
        """Reuse a verified cumulative invoice/app total exactly once."""
        from datetime import date

        from homeassistant.helpers import selector
        from homeassistant.util import dt as dt_util

        values = self._accounting_values()
        errors = {}
        if user_input is not None:
            try:
                day = date.fromisoformat(user_input["reference_date"])
                if (
                    not date.fromisoformat(values["billing_start"])
                    <= day
                    <= min(
                        date.fromisoformat(values["billing_end"]), dt_util.now().date()
                    )
                ):
                    raise ValueError
                energy, cost = (
                    finite_number(user_input.get(k))
                    for k in ("reference_energy", "reference_cost")
                )
                if energy is None or cost is None or energy < 0 or cost < 0:
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                errors["base"] = "invalid_accounting_history"
            else:
                self._pending_options.update(
                    reference_date=day.isoformat(),
                    reference_energy=energy,
                    reference_cost=cost,
                    reference_period_start=values["billing_start"],
                )
                return self._finish_options()
        valid_saved = bool(
            values["reference_date"]
            and values["reference_period_start"] == values["billing_start"]
        )
        schema = {}
        for key in ("reference_date", "reference_energy", "reference_cost"):
            value = (user_input or {}).get(key, values[key] if valid_saved else None)
            marker = vol.Required(
                key, description={"suggested_value": value} if value is not None else {}
            )
            schema[marker] = (
                selector.DateSelector()
                if key == "reference_date"
                else vol.All(vol.Coerce(float), vol.Range(min=0))
            )
        return self.async_show_form(
            step_id="history_reading",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "start": values["billing_start"],
                "end": values["billing_end"],
            },
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
