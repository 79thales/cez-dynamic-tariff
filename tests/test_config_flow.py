"""Standalone behavior tests for the multi-step options flow."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from enum import StrEnum
from pathlib import Path


def _load_config_flow_module():
    """Load config_flow.py with small framework stubs."""
    voluptuous = types.ModuleType("voluptuous")
    voluptuous.ALLOW_EXTRA = object()
    voluptuous.Required = lambda key, default=None: key
    voluptuous.Schema = lambda schema, extra=None: schema
    voluptuous.Coerce = lambda target: target
    voluptuous.Range = lambda **kwargs: lambda value: value
    voluptuous.All = lambda *validators: validators
    sys.modules["voluptuous"] = voluptuous

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    sys.modules["homeassistant"] = homeassistant

    class _FlowBase:
        def async_show_form(self, *, step_id, data_schema, errors=None):
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors or {},
            }

        def async_create_entry(self, *, title, data, options=None):
            return {
                "type": "create_entry",
                "title": title,
                "data": data,
                "options": options,
            }

    class ConfigFlow(_FlowBase):
        def __init_subclass__(cls, **kwargs):
            return super().__init_subclass__()

        async def async_set_unique_id(self, unique_id):
            self.unique_id = unique_id

        def _abort_if_unique_id_configured(self):
            return None

    class OptionsFlow(_FlowBase):
        pass

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow
    sys.modules[config_entries.__name__] = config_entries
    homeassistant.config_entries = config_entries

    core = types.ModuleType("homeassistant.core")
    core.callback = lambda target: target
    sys.modules[core.__name__] = core

    ha_const = types.ModuleType("homeassistant.const")

    class Platform(StrEnum):
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"

    ha_const.Platform = Platform
    sys.modules[ha_const.__name__] = ha_const

    package_name = "_cez_dynamic_tariff_config_flow_test"
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package

    component_path = (
        Path(__file__).parents[1] / "custom_components" / "cez_dynamic_tariff"
    )
    for module_basename in ("const", "schedule", "config_flow"):
        module_name = f"{package_name}.{module_basename}"
        spec = importlib.util.spec_from_file_location(
            module_name,
            component_path / f"{module_basename}.py",
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load {module_basename}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    return sys.modules[f"{package_name}.config_flow"]


config_flow = _load_config_flow_module()


class _FakeEntry:
    def __init__(self, options=None):
        self.data = {
            "name": "ČEZ Dynamic Tariff",
            "base_price_kwh": 2.5,
            "include_holidays": True,
        }
        self.options = options or {}


GENERAL = {
    "base_price_kwh": 3.25,
    "include_holidays": False,
    "reset_schedules": False,
}
THRESHOLDS = {
    "super_cheap_threshold": -50,
    "cheap_threshold": -10,
    "expensive_threshold": 10,
    "very_expensive_threshold": 25,
}
SCHEDULES = {
    option: config_flow.format_schedule(config_flow.DEFAULT_SCHEDULES[option])
    for option in config_flow.SCHEDULE_OPTIONS
}


class OptionsFlowTests(unittest.IsolatedAsyncioTestCase):
    """Verify the complete options flow and reset behavior."""

    async def test_custom_options_pass_through_all_three_steps(self) -> None:
        """General settings, thresholds and schedules are saved together."""
        flow = config_flow.CezDynamicTariffOptionsFlow(_FakeEntry())

        result = await flow.async_step_init(GENERAL)
        self.assertEqual(result["step_id"], "thresholds")

        result = await flow.async_step_thresholds(THRESHOLDS)
        self.assertEqual(result["step_id"], "schedules")

        custom_schedules = dict(SCHEDULES)
        custom_schedules["summer_offday_schedule"] = "00:00=-10, 12:30=+5"
        result = await flow.async_step_schedules(custom_schedules)

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["base_price_kwh"], 3.25)
        self.assertFalse(result["data"]["include_holidays"])
        self.assertEqual(
            result["data"]["summer_offday_schedule"],
            "00:00=-10, 12:30=+5",
        )
        self.assertNotIn("reset_schedules", result["data"])

    async def test_invalid_thresholds_stay_on_threshold_step(self) -> None:
        """Contradictory thresholds are rejected without losing the step."""
        flow = config_flow.CezDynamicTariffOptionsFlow(_FakeEntry())
        await flow.async_step_init(GENERAL)
        invalid = dict(THRESHOLDS, expensive_threshold=30)

        result = await flow.async_step_thresholds(invalid)

        self.assertEqual(result["step_id"], "thresholds")
        self.assertEqual(
            result["errors"],
            {"base": "expensive_not_below_very_expensive"},
        )

    async def test_invalid_schedule_stays_on_schedule_step(self) -> None:
        """Each malformed schedule is attached to its own form field."""
        flow = config_flow.CezDynamicTariffOptionsFlow(_FakeEntry())
        await flow.async_step_init(GENERAL)
        await flow.async_step_thresholds(THRESHOLDS)
        invalid = dict(SCHEDULES, winter_workday_schedule="01:00=-10")

        result = await flow.async_step_schedules(invalid)

        self.assertEqual(result["step_id"], "schedules")
        self.assertEqual(
            result["errors"],
            {"winter_workday_schedule": "invalid_schedule"},
        )

    async def test_reset_requires_confirmation_and_removes_only_schedules(self) -> None:
        """Reset removes saved schedules while preserving submitted thresholds."""
        saved = dict(SCHEDULES, unrelated_future_option="keep-me")
        flow = config_flow.CezDynamicTariffOptionsFlow(_FakeEntry(saved))
        reset_general = dict(GENERAL, reset_schedules=True)
        await flow.async_step_init(reset_general)

        result = await flow.async_step_thresholds(THRESHOLDS)
        self.assertEqual(result["step_id"], "reset_schedules")

        result = await flow.async_step_reset_schedules({"confirm_reset": False})
        self.assertEqual(result["errors"], {"base": "confirm_reset"})

        result = await flow.async_step_reset_schedules({"confirm_reset": True})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["unrelated_future_option"], "keep-me")
        self.assertEqual(result["data"]["cheap_threshold"], -10)
        for option in config_flow.SCHEDULE_OPTIONS:
            self.assertNotIn(option, result["data"])


if __name__ == "__main__":
    unittest.main()
