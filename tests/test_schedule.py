"""Tests for editable tariff schedules without requiring Home Assistant."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


def _load_schedule_module():
    """Load schedule.py with a minimal const module for standalone tests."""
    package_name = "_cez_dynamic_tariff_test"
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package

    const = types.ModuleType(f"{package_name}.const")
    const.CONF_SUMMER_OFFDAY_SCHEDULE = "summer_offday_schedule"
    const.CONF_SUMMER_WORKDAY_SCHEDULE = "summer_workday_schedule"
    const.CONF_WINTER_OFFDAY_SCHEDULE = "winter_offday_schedule"
    const.CONF_WINTER_WORKDAY_SCHEDULE = "winter_workday_schedule"
    sys.modules[const.__name__] = const

    module_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "cez_dynamic_tariff"
        / "schedule.py"
    )
    module_name = f"{package_name}.schedule"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load schedule module")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


schedule = _load_schedule_module()


class ScheduleTests(unittest.TestCase):
    """Verify parsing, formatting, validation, and backward compatibility."""

    def test_complete_schedule_supports_any_number_of_bands(self) -> None:
        """A complete schedule may add or remove bands and set modifiers."""
        result = schedule.parse_schedule(
            "00:00=-10, 03:30=-50; 12:15=+5\n22:00=25",
            schedule.WINTER_WORKDAY,
        )

        self.assertEqual(
            [(item.start_minute, item.end_minute, item.modifier_percent) for item in result],
            [
                (0, 210, -10),
                (210, 735, -50),
                (735, 1320, 5),
                (1320, 1440, 25),
            ],
        )

    def test_complete_schedule_round_trip(self) -> None:
        """Formatting and parsing a default schedule keeps every band."""
        formatted = schedule.format_schedule(schedule.SUMMER_WORKDAY)

        self.assertIn("00:00=-10", formatted)
        self.assertIn("05:00=+25", formatted)
        self.assertEqual(
            schedule.parse_schedule(formatted, schedule.SUMMER_WORKDAY),
            schedule.SUMMER_WORKDAY,
        )

    def test_legacy_starts_only_schedule_keeps_default_modifiers(self) -> None:
        """Schedules saved by version 0.1.7 remain valid."""
        legacy_value = ", ".join(
            f"{item.start_minute // 60:02d}:{item.start_minute % 60:02d}"
            for item in schedule.WINTER_OFFDAY
        )

        self.assertEqual(
            schedule.parse_schedule(legacy_value, schedule.WINTER_OFFDAY),
            schedule.WINTER_OFFDAY,
        )

    def test_invalid_schedules_are_rejected(self) -> None:
        """Invalid, ambiguous, and unordered schedules fail validation."""
        invalid_values = (
            "",
            "01:00=-10",
            "00:00=-10, 00:00=+10",
            "00:00=-10, 24:00=+10",
            "00:00=-10, 03:00",
            "00:00=cheap",
            "00:00=-10, 03:00=+5, 02:00=+10",
        )

        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                schedule.parse_schedule(value, schedule.WINTER_WORKDAY)

    def test_legacy_schedule_requires_original_number_of_bands(self) -> None:
        """A starts-only value cannot guess a modifier for a new band."""
        with self.assertRaises(ValueError):
            schedule.parse_schedule("00:00, 03:00", schedule.WINTER_WORKDAY)


if __name__ == "__main__":
    unittest.main()
