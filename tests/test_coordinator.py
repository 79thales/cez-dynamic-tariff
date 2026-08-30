"""Standalone coordinator tests with minimal Home Assistant stubs."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    PRAGUE_TIMEZONE = ZoneInfo("Europe/Prague")
    UTC_TIMEZONE = ZoneInfo("UTC")
except ZoneInfoNotFoundError:
    PRAGUE_TIMEZONE = timezone(timedelta(hours=2), "Europe/Prague")
    UTC_TIMEZONE = timezone.utc


def _load_coordinator_module():
    """Load coordinator.py without installing Home Assistant."""
    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    sys.modules["homeassistant"] = homeassistant

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object
    sys.modules[config_entries.__name__] = config_entries

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    sys.modules[core.__name__] = core

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules[helpers.__name__] = helpers

    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    class DataUpdateCoordinator:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, hass, logger, name, update_interval):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval

    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    sys.modules[update_coordinator.__name__] = update_coordinator

    util = types.ModuleType("homeassistant.util")
    util.__path__ = []
    sys.modules[util.__name__] = util

    dt_util = types.ModuleType("homeassistant.util.dt")
    dt_util.DEFAULT_TIME_ZONE = UTC_TIMEZONE
    dt_util.get_time_zone = lambda zone: PRAGUE_TIMEZONE
    dt_util.now = lambda: datetime.now(UTC_TIMEZONE)
    sys.modules[dt_util.__name__] = dt_util
    util.dt = dt_util

    ha_const = types.ModuleType("homeassistant.const")

    class Platform(StrEnum):
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"

    ha_const.Platform = Platform
    sys.modules[ha_const.__name__] = ha_const

    holidays = types.ModuleType("holidays")
    holidays.country_holidays = lambda country: set()
    sys.modules["holidays"] = holidays

    package_name = "_cez_dynamic_tariff_coordinator_test"
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package

    component_path = (
        Path(__file__).parents[1] / "custom_components" / "cez_dynamic_tariff"
    )
    for module_basename in ("const", "schedule", "coordinator"):
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

    return sys.modules[f"{package_name}.coordinator"], dt_util


coordinator_module, dt_util = _load_coordinator_module()


class _FakeEntry:
    entry_id = "test-entry"

    def __init__(self, options=None):
        self.data = {"name": "ČEZ Dynamic Tariff"}
        self.options = options or {}


class _FakeHass:
    def __init__(self):
        self.config = types.SimpleNamespace(time_zone="Europe/Prague")

    async def async_add_executor_job(self, target, *args):
        return target(*args)


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    """Verify calculated tariff states and boundaries."""

    async def _snapshot(self, when: datetime, options=None, holidays=None):
        coordinator = coordinator_module.CezDynamicTariffCoordinator(
            _FakeHass(),
            _FakeEntry(options),
        )
        coordinator._holidays = holidays or set()
        dt_util.now = lambda: when
        return await coordinator._async_update_data()

    async def test_next_change_and_tomorrow_map(self) -> None:
        """The next change is independent from the next cheap window."""
        snapshot = await self._snapshot(
            datetime(2026, 8, 23, 11, 30, tzinfo=PRAGUE_TIMEZONE)
        )

        self.assertEqual(snapshot.current_modifier_percent, -50)
        self.assertEqual(
            snapshot.next_change,
            datetime(2026, 8, 23, 14, 0, tzinfo=PRAGUE_TIMEZONE),
        )
        self.assertEqual(snapshot.next_modifier_percent, 10)
        self.assertEqual(
            snapshot.next_cheap_start,
            datetime(2026, 8, 23, 16, 0, tzinfo=PRAGUE_TIMEZONE),
        )
        self.assertEqual(snapshot.tomorrow_map_code, "summer_workday")
        self.assertIn(
            25,
            {item["modifier_percent"] for item in snapshot.tomorrow_schedule},
        )
        self.assertEqual(
            snapshot.today_schedule_revision,
            "cez-public-table-2024-09",
        )
        self.assertTrue(snapshot.today_schedule_source_url.startswith("https://"))

    async def test_custom_schedule_has_honest_provenance(self) -> None:
        """A user-edited table must not claim to be the official built-in revision."""
        snapshot = await self._snapshot(
            datetime(2026, 8, 24, 12, 0, tzinfo=PRAGUE_TIMEZONE),
            options={
                "summer_workday_schedule": "00:00=-10, 12:00=+10",
            },
        )

        self.assertEqual(snapshot.today_schedule_revision, "custom")
        self.assertIsNone(snapshot.today_schedule_source_url)

    async def test_cheap_binary_states_include_super_cheap(self) -> None:
        """Super cheap is also cheap, mirroring expensive classification."""
        snapshot = await self._snapshot(
            datetime(2026, 8, 23, 3, 30, tzinfo=PRAGUE_TIMEZONE)
        )

        self.assertTrue(snapshot.cheap_now)
        self.assertTrue(snapshot.super_cheap_now)
        self.assertFalse(snapshot.expensive_now)
        self.assertFalse(snapshot.very_expensive_now)

    async def test_season_boundary_is_visible_in_tomorrow_map(self) -> None:
        """September 30 correctly previews the winter schedule for October 1."""
        snapshot = await self._snapshot(
            datetime(2026, 9, 30, 23, 30, tzinfo=PRAGUE_TIMEZONE)
        )

        self.assertEqual(snapshot.season, "Letní")
        self.assertEqual(snapshot.season_code, "summer")
        self.assertEqual(snapshot.tomorrow_season, "Zimní")
        self.assertEqual(snapshot.tomorrow_season_code, "winter")
        self.assertEqual(snapshot.tomorrow_map_code, "winter_workday")

    async def test_holiday_setting_changes_day_type(self) -> None:
        """A configured Czech holiday uses the off-day schedule."""
        holiday = date(2026, 8, 24)
        when = datetime(2026, 8, 24, 12, 0, tzinfo=PRAGUE_TIMEZONE)

        included = await self._snapshot(when, holidays={holiday})
        excluded = await self._snapshot(
            when,
            options={"include_holidays": False},
            holidays={holiday},
        )

        self.assertTrue(included.is_holiday)
        self.assertEqual(included.day_type_code, "weekend_or_holiday")
        self.assertFalse(excluded.is_holiday)
        self.assertEqual(excluded.day_type_code, "workday")

    async def test_midnight_keeps_next_real_modifier_change(self) -> None:
        """A same-price midnight boundary is skipped in favor of the real change."""
        snapshot = await self._snapshot(
            datetime(2026, 8, 23, 23, 30, tzinfo=PRAGUE_TIMEZONE)
        )

        self.assertEqual(
            snapshot.next_change,
            datetime(2026, 8, 24, 3, 0, tzinfo=PRAGUE_TIMEZONE),
        )
        self.assertEqual(snapshot.next_modifier_percent, -50)

    async def test_spring_dst_transition_uses_home_assistant_timezone(self) -> None:
        """The next boundary keeps the correct offset across the DST jump."""
        snapshot = await self._snapshot(
            datetime(2026, 3, 29, 1, 30, tzinfo=PRAGUE_TIMEZONE)
        )

        self.assertEqual(snapshot.next_change.hour, 3)
        if isinstance(PRAGUE_TIMEZONE, ZoneInfo):
            self.assertEqual(snapshot.next_change.utcoffset(), timedelta(hours=2))


if __name__ == "__main__":
    unittest.main()
