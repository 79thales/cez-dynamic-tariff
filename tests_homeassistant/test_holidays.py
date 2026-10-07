"""Regressions for the real Czech holiday calendar, without mocked dates."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch
from zoneinfo import ZoneInfo

import holidays

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class HolidayCalendarTests(unittest.TestCase):
    """Keep the public dates used for tariff selection stable across upgrades."""

    def test_complete_public_calendar(self) -> None:
        """Fixed and movable public holidays match the expected dates."""
        fixed_dates = (
            (1, 1), (5, 1), (5, 8), (7, 5), (7, 6), (9, 28),
            (10, 28), (11, 17), (12, 24), (12, 25), (12, 26),
        )
        easter_dates = {
            2025: ((4, 18), (4, 21)),
            2026: ((4, 3), (4, 6)),
            2027: ((3, 26), (3, 29)),
        }
        for year, movable_dates in easter_dates.items():
            expected = {date(year, month, day) for month, day in fixed_dates + movable_dates}
            with self.subTest(year=year):
                self.assertEqual(set(holidays.country_holidays("CZ", years=year)), expected)

    def test_lazy_calendar_expands_across_new_year(self) -> None:
        """The production API works without preloading specific years."""
        calendar = holidays.country_holidays("CZ")
        self.assertIn(date(2026, 12, 24), calendar)
        self.assertNotIn(date(2026, 12, 31), calendar)
        self.assertIn(date(2027, 1, 1), calendar)
        self.assertNotIn(date(2027, 1, 4), calendar)

    def test_weekend_holiday_is_not_shifted_to_a_workday(self) -> None:
        """A Saturday public holiday does not create a substitute Monday."""
        calendar = holidays.country_holidays("CZ")
        self.assertIn(date(2027, 5, 1), calendar)
        self.assertNotIn(date(2027, 5, 3), calendar)


async def test_coordinator_uses_real_czech_holidays(hass: HomeAssistant) -> None:
    """Real calendar dates select the same tariff, price and next-day map."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.cez_dynamic_tariff.const import DOMAIN
    from custom_components.cez_dynamic_tariff.coordinator import (
        CezDynamicTariffCoordinator,
    )

    hass.config.set_time_zone("Europe/Prague")
    timezone = ZoneInfo("Europe/Prague")
    cases = (
        (datetime(2026, 4, 3, 5, tzinfo=timezone), True, True, 10, "summer_offday"),
        (datetime(2026, 4, 6, 5, tzinfo=timezone), True, True, 10, "summer_workday"),
        (datetime(2026, 4, 6, 5, tzinfo=timezone), False, False, 25, "summer_workday"),
        (datetime(2026, 4, 7, 5, tzinfo=timezone), True, False, 25, "summer_workday"),
        (datetime(2026, 12, 31, 5, tzinfo=timezone), True, False, 25, "winter_offday"),
        (datetime(2027, 1, 1, 5, tzinfo=timezone), True, True, 10, "winter_offday"),
    )
    for when, include_holidays, is_holiday, modifier, tomorrow_map in cases:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"include_holidays": include_holidays, "base_price_kwh": 4.5},
        )
        coordinator = CezDynamicTariffCoordinator(hass, entry)
        with patch("custom_components.cez_dynamic_tariff.coordinator.dt_util.now", return_value=when):
            snapshot = await coordinator._async_update_data()
        assert snapshot.is_holiday is is_holiday
        assert snapshot.day_type_code == ("weekend_or_holiday" if is_holiday else "workday")
        assert snapshot.current_modifier_percent == modifier
        assert snapshot.effective_price_kwh == round(4.5 * (1 + modifier / 100), 4)
        assert snapshot.tomorrow_map_code == tomorrow_map
