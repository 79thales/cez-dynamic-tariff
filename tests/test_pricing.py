"""Price-list, HDO validity, DST and metering regressions without HA stubs."""

import importlib.util
import sys
import unittest
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parents[1] / "custom_components/cez_dynamic_tariff"


def load_module(name):
    spec = importlib.util.spec_from_file_location(
        f"_pricing_test_{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


p = load_module("pricing")
a = load_module("accounting")
TZ = ZoneInfo("Europe/Prague")


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.profile = p.PriceProfile(dict(p.PROFILE_DEFAULTS))

    def test_bill_components_and_modifier_scope(self):
        self.assertAlmostEqual(self.profile.price("VT", 0, False), 4.32624)
        self.assertAlmostEqual(self.profile.price("NT", 0, False), 3.42394)
        self.assertAlmostEqual(self.profile.price("NT", -50, True), 1.89894)
        self.assertAlmostEqual(self.profile.price("VT", 25, True), 5.12124)
        self.assertAlmostEqual(self.profile.monthly, 850.47)
        self.assertIsNone(self.profile.allocation)
        other = p.PriceProfile({**p.PROFILE_DEFAULTS, "annual_import_kwh": 10000})
        self.assertAlmostEqual(other.allocation, 1.020564)

    def test_hdo_midnight_validity_and_gaps(self):
        expires = datetime(2026, 10, 10, 6, tzinfo=TZ)
        rows = [
            {
                "start": "2026-10-09T00:00:00+02:00",
                "end": "2026-10-09T23:59:59+02:00",
                "tariff": "NT",
            },
            {
                "start": "2026-10-10T00:00:00+02:00",
                "end": "2026-10-10T23:59:59+02:00",
                "tariff": "VT",
            },
        ]
        intervals = p.parse_hdo_schedule(rows, TZ, expires)
        self.assertEqual(len(intervals), 2)
        self.assertEqual(
            p.tariff_at(intervals, datetime(2026, 10, 10, tzinfo=TZ)), "VT"
        )
        self.assertIsNone(p.tariff_at(intervals, expires))
        self.assertEqual(p.parse_hdo_schedule(rows + rows, TZ, expires), [])
        self.assertEqual(p.parse_hdo_schedule([{"start": "bad"}], TZ, expires), [])
        self.assertIsNone(p.tariff_at(intervals, datetime(2026, 10, 8, tzinfo=TZ)))

    def test_hdo_and_dynamic_edges_are_combined(self):
        start = datetime(2026, 10, 9, 3, tzinfo=TZ)
        end = start + timedelta(hours=3)
        intervals = [
            p.HdoInterval(
                start.astimezone(UTC),
                (start + timedelta(hours=1)).astimezone(UTC),
                "VT",
            ),
            p.HdoInterval(
                (start + timedelta(hours=1)).astimezone(UTC), end.astimezone(UTC), "NT"
            ),
        ]
        rows = p.price_timeline(
            start,
            end,
            intervals,
            self.profile,
            lambda dt: -50 if dt.astimezone(TZ).hour < 5 else 25,
            True,
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["tariff"] for r in rows], ["VT", "NT", "NT"])
        self.assertEqual([r["modifier_percent"] for r in rows], [-50, -50, 25])
        self.assertAlmostEqual(rows[0]["price_kwh"], 2.73624)

    def test_forecast_uses_real_dst_hours(self):
        for month, day, hours in ((3, 29, 23), (10, 25, 25)):
            start = datetime(2026, month, day, tzinfo=TZ)
            end = start + timedelta(days=1)
            intervals = [
                p.HdoInterval(start.astimezone(UTC), end.astimezone(UTC), "NT")
            ]
            rows = p.price_timeline(
                start,
                end,
                intervals,
                self.profile,
                lambda dt: -50 if dt.astimezone(TZ).hour == 2 else 0,
                True,
            )
            self.assertEqual(
                sum((r["end"] - r["start"]).total_seconds() for r in rows), hours * 3600
            )
            discounted = sum(
                (r["end"] - r["start"]).total_seconds()
                for r in rows
                if r["modifier_percent"] == -50
            )
            self.assertEqual(discounted, 0 if month == 3 else 7200)

    def test_nonfinite_and_missing_states_are_rejected(self):
        for value in ("nan", "inf", "unavailable", None):
            self.assertIsNone(p.finite_number(value))


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 9, tzinfo=UTC)
        self.rows = [
            {
                "start": self.start,
                "end": self.start + timedelta(minutes=5),
                "price_kwh": 2,
                "without_dynamic_kwh": 4,
                "with_dynamic_kwh": 2,
            },
            {
                "start": self.start + timedelta(minutes=5),
                "end": self.start + timedelta(minutes=10),
                "price_kwh": 5,
                "without_dynamic_kwh": 4,
                "with_dynamic_kwh": 5,
            },
        ]

    def test_issue_3_fragmented_full_coverage_has_no_false_gap(self):
        """Navazující časové úseky musí pokrýt celý pětiminutový odběr."""
        boundaries = (0, 1, 61, 121, 181, 241, 300)
        rows = [
            {
                **self.rows[0],
                "start": self.start + timedelta(seconds=left),
                "end": self.start + timedelta(seconds=right),
            }
            for left, right in pairwise(boundaries)
        ]
        ledger = a.CostLedger()
        ledger.sample(self.start, 17000, rows)
        ledger.sample(self.start + timedelta(seconds=300), 17001, rows)
        self.assertEqual(ledger.totals["unpriced_kwh"], 0)
        self.assertAlmostEqual(ledger.totals["actual_cost"], 2)
        self.assertAlmostEqual(ledger.totals["without_cost"], 4)
        self.assertAlmostEqual(ledger.totals["dynamic_cost"], 2)
        self.assertEqual(ledger.totals["comparison_unpriced_kwh"], 0)

    def test_issue_3_microsecond_gap_remains_unpriced(self):
        """Skutečná mezera trvající 1 µs zůstane neoceněna i po uložení."""
        split = self.start + timedelta(seconds=120)
        after = split + timedelta(microseconds=1)
        left = {**self.rows[0], "end": split}
        right = {**self.rows[0], "start": after}
        unknown = {**self.rows[0], "start": split, "end": after, "price_kwh": None}
        for rows in ([left, right], [left, unknown, right]):
            with self.subTest(explicit_unknown=len(rows) == 3):
                ledger = a.CostLedger()
                ledger.sample(self.start, 17000, rows)
                ledger.sample(self.start + timedelta(seconds=300), 17001, rows)
                # 1 kWh rovnoměrně za 300 s: za 1 µs jde o 1/300 000 000 kWh.
                expected = 1 / 300_000_000
                self.assertAlmostEqual(
                    ledger.totals["unpriced_kwh"], expected, places=20
                )
                restored = a.CostLedger(ledger.as_dict())
                self.assertEqual(
                    restored.totals["unpriced_kwh"], ledger.totals["unpriced_kwh"]
                )

    def test_issue_3_fragmented_coverage_across_local_midnight(self):
        """Dělení půlnocí zachová plné pokrytí a částku obou kalendářních dnů."""
        start = datetime(2026, 10, 9, 23, 57, 30, tzinfo=TZ).astimezone(UTC)
        boundaries = (0, 1, 61, 121, 181, 241, 300)
        rows = [
            {
                **self.rows[0],
                "start": start + timedelta(seconds=left),
                "end": start + timedelta(seconds=right),
            }
            for left, right in pairwise(boundaries)
        ]
        ledger = a.CostLedger()
        ledger.sample(start, 100, rows, tz=TZ)
        ledger.sample(start + timedelta(seconds=300), 101, rows, tz=TZ)
        self.assertEqual(ledger.totals["unpriced_kwh"], 0)
        self.assertAlmostEqual(ledger.days["2026-10-09"]["energy_kwh"], 0.5)
        self.assertAlmostEqual(ledger.days["2026-10-10"]["energy_kwh"], 0.5)
        self.assertAlmostEqual(ledger.totals["actual_cost"], 2)

    def test_issue_3_preexisting_unpriced_amount_is_preserved(self):
        """Ze starého součtu nelze bezpečně určit, zda jde o skutečnou mezeru."""
        artifact_or_gap = 1.1102230246251565e-16
        ledger = a.CostLedger({"unpriced_kwh": artifact_or_gap})
        ledger.sample(self.start, 100, self.rows)
        ledger.sample(self.start + timedelta(seconds=300), 101, self.rows)
        self.assertEqual(ledger.totals["unpriced_kwh"], artifact_or_gap)
        self.assertEqual(
            a.CostLedger(ledger.as_dict()).totals["unpriced_kwh"], artifact_or_gap
        )

    def test_lifetime_baseline_then_split_and_signed_savings(self):
        ledger = a.CostLedger()
        ledger.sample(self.start, 17000, self.rows, 2)
        self.assertEqual(ledger.totals["actual_cost"], 0)
        ledger.sample(self.start + timedelta(minutes=10), 17002, self.rows, 2)
        self.assertEqual(ledger.totals["actual_cost"], 7)
        self.assertEqual(ledger.totals["without_cost"], 8)
        self.assertEqual(ledger.totals["dynamic_cost"], 7)
        self.assertEqual(ledger.totals["potential_savings"], 3)
        ledger.sample(self.start + timedelta(minutes=11), 17003, [], None)
        self.assertEqual(ledger.totals["unpriced_kwh"], 1)

    def test_reset_restart_unavailable_and_long_gap(self):
        ledger = a.CostLedger({"actual_cost": 100})
        ledger.sample(self.start, 17000, self.rows)
        ledger.sample(self.start + timedelta(minutes=1), 0, self.rows)
        self.assertEqual(ledger.totals["actual_cost"], 100)
        ledger.sample(self.start + timedelta(minutes=20), 5, self.rows)
        self.assertEqual(ledger.totals["unpriced_kwh"], 5)
        ledger.sample(self.start + timedelta(minutes=21), None, self.rows)
        ledger.sample(self.start + timedelta(minutes=22), 10, self.rows)
        self.assertEqual(ledger.totals["actual_cost"], 100)

    def test_expensive_import_produces_negative_savings(self):
        ledger = a.CostLedger()
        begin = self.start + timedelta(minutes=5)
        ledger.sample(begin, 100, self.rows)
        ledger.sample(begin + timedelta(minutes=5), 102, self.rows)
        self.assertEqual(
            ledger.totals["without_cost"] - ledger.totals["dynamic_cost"], -2
        )

    def test_monthly_fee_calendar_and_dst(self):
        ledger = a.CostLedger()
        for month in (3, 10):
            start = datetime(2026, month, 1, tzinfo=TZ)
            end = datetime(2026, month + 1, 1, tzinfo=TZ)
            ledger.accrue_fixed(start, end, 850.47, TZ)
        self.assertAlmostEqual(ledger.totals["fixed_cost"], 1700.94)

    def test_daily_meter_cost_splits_at_local_midnight(self):
        ledger = a.CostLedger()
        start = datetime(2026, 10, 9, 23, 55, tzinfo=TZ).astimezone(UTC)
        end = start + timedelta(minutes=10)
        rows = [
            {
                "start": start,
                "end": end,
                "price_kwh": 3,
                "without_dynamic_kwh": 4,
                "with_dynamic_kwh": 3,
            }
        ]
        ledger.sample(start, 100, rows, tz=TZ)
        ledger.sample(end, 102, rows, tz=TZ)
        self.assertEqual(ledger.days["2026-10-09"]["actual_cost"], 3)
        self.assertEqual(ledger.days["2026-10-10"]["actual_cost"], 3)
        restored = a.CostLedger(ledger.as_dict())
        self.assertEqual(restored.days, ledger.days)
        self.assertIsNone(restored.previous)

    def test_dst_day_gets_one_calendar_day_fee(self):
        for month, day in ((3, 29), (10, 25)):
            ledger = a.CostLedger()
            start = datetime(2026, month, day, tzinfo=TZ)
            ledger.accrue_fixed(start, start + timedelta(days=1), 850.47, TZ)
            self.assertAlmostEqual(ledger.totals["fixed_cost"], 850.47 / 31)


if __name__ == "__main__":
    unittest.main()
