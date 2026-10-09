"""Seasonality, unknown payments and calendar-fee contracts."""

import importlib.util
import json
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

spec = importlib.util.spec_from_file_location(
    "settlement",
    Path(__file__).parents[1] / "custom_components/cez_dynamic_tariff/settlement.py",
)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
TZ = ZoneInfo("Europe/Prague")


class SettlementTests(unittest.TestCase):
    def test_default_period_crosses_year(self):
        self.assertEqual(
            s.default_period(date(2026, 1, 2)), ("2025-04-01", "2026-03-31")
        )
        self.assertEqual(
            s.default_period(date(2026, 4, 1)), ("2026-04-01", "2027-03-31")
        )

    def test_full_day_fee_calendar_and_leap_year(self):
        self.assertAlmostEqual(
            s.standing_fees(date(2024, 2, 1), date(2024, 2, 29), lambda _: 290), 290
        )
        self.assertAlmostEqual(
            s.standing_fees(date(2026, 1, 1), date(2026, 12, 31), lambda _: 850), 10200
        )

    def test_missing_payment_is_not_zero_or_paid(self):
        values = {
            **s.SETTLEMENT_DEFAULTS,
            "advance_mode": "monthly",
            "monthly_advances": json.dumps(
                [
                    {"month": "2026-05", "amount": 100, "paid": True},
                    {"month": "2026-06", "amount": 0, "paid": False},
                ]
            ),
        }
        self.assertEqual(
            s.advances(values, date(2026, 4, 1), date(2026, 6, 30)),
            (100, 100, ["2026-04"]),
        )

    def test_invalid_duplicate_nonfinite_and_payment_flags(self):
        good = {"month": "2026-04", "amount": 100, "paid": True}
        for rows in (
            [good, good],
            [{**good, "amount": float("nan")}],
            [{**good, "paid": "yes"}],
        ):
            with self.assertRaises(ValueError):
                s.parse_advances(json.dumps(rows), date(2026, 4, 1), date(2026, 5, 31))

    def test_complete_days_only_and_zero_is_valid(self):
        midnight = datetime(2026, 9, 1, tzinfo=TZ)
        rows = [
            {"start": (midnight + timedelta(hours=i)).timestamp(), "change": 0}
            for i in range(24)
        ]
        rows += [
            {
                "start": (midnight + timedelta(days=1, hours=i)).timestamp(),
                "change": 100,
            }
            for i in range(23)
        ]
        profile = s.consumption_profile(rows, midnight + timedelta(days=4), TZ)
        self.assertEqual(profile[8]["sample_days"], 1)
        self.assertEqual(profile[8]["daily_kwh"], 0)
        self.assertIsNone(profile[11]["daily_kwh"])
        self.assertEqual(
            s.remaining_import(profile, date(2026, 9, 5), date(2026, 9, 6)), (0, [])
        )
        self.assertEqual(
            s.remaining_import(profile, date(2026, 12, 5), date(2026, 12, 6)),
            (None, [12]),
        )

    def test_repeated_hour_is_a_complete_25_hour_day(self):
        midnight = datetime(2026, 10, 25, tzinfo=TZ)
        rows = [
            {"start": midnight.timestamp() + 3600 * i, "change": 1} for i in range(25)
        ]
        profile = s.consumption_profile(rows, midnight + timedelta(days=2), TZ)
        self.assertEqual(profile[9]["daily_kwh"], 25)
