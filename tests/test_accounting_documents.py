"""Ověření podkladů bez osobních dat: období, jednotky, poměry a změna času."""

import copy
import importlib.util
import sys
import types
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Čisté funkce testujeme bez importu HA a bez spouštění integračního __init__.
PACKAGE = "_cez_documents_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [
    str(Path(__file__).parents[1] / "custom_components/cez_dynamic_tariff")
]
sys.modules[PACKAGE] = package
for name in ("pricing", "accounting_documents"):
    spec = importlib.util.spec_from_file_location(
        PACKAGE + "." + name, Path(package.__path__[0]) / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    globals()[name] = module
d = sys.modules[PACKAGE + ".accounting_documents"]
pricing = sys.modules[PACKAGE + ".pricing"]
TODAY = date(2026, 10, 21)


def bill():
    return {
        "start": "2024-01-01",
        "end": "2024-12-31",
        "source": "Test",
        "energy_kwh": 100,
        "nt_kwh": 80,
        "vt_kwh": 20,
        "cost": 400,
    }


class DocumentTests(unittest.TestCase):
    def test_validation_keeps_unknown_fields_and_optional_unknown_amounts(self):
        row = {**bill(), "metadata": {"retained": True}}
        self.assertIs(d.validate_document(row, [], "bill", TODAY), row)
        self.assertNotIn("paid", row)
        self.assertTrue(row["metadata"]["retained"])

    def test_negative_nonfinite_and_boolean_values_are_rejected(self):
        for value in (-1, float("inf"), float("nan"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                d.validate_document({**bill(), "cost": value}, [], "bill", TODAY)

    def test_future_bill_overlap_and_mismatched_energy_are_rejected(self):
        for row, others in [
            ({**bill(), "end": "2026-12-31"}, []),
            (bill(), [bill()]),
            ({**bill(), "nt_kwh": 90}, []),
        ]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                d.validate_document(row, others, "bill", TODAY)

    def test_months_do_not_invent_zero_and_validate_partial_and_full_sums(self):
        row = {**bill(), "months": [{"month": "2024-03", "nt_kwh": 8, "vt_kwh": 2}]}
        d.validate_document(row, [], "bill", TODAY)
        for month in ("2023-12", "2025-01"):
            with self.assertRaises(ValueError):
                d.validate_document(
                    {**row, "months": [{"month": month, "nt_kwh": 8, "vt_kwh": 2}]},
                    [],
                    "bill",
                    TODAY,
                )
        with self.assertRaises(ValueError):
            d.validate_document({**row, "months": row["months"] * 2}, [], "bill", TODAY)
        with self.assertRaises(ValueError):
            d.validate_document(
                {
                    **bill(),
                    "months": [
                        {"month": f"2024-{i:02}", "nt_kwh": 1, "vt_kwh": 1}
                        for i in range(1, 13)
                    ],
                },
                [],
                "bill",
                TODAY,
            )

    def test_profile_requires_all_rates_and_cannot_overlap_current(self):
        row = {
            "start": "2025-01-01",
            "end": "2025-12-31",
            "source": "Test",
            "rates": {k: 0.0 for k in d.RATE_KEYS},
        }
        d.validate_document(row, [], "profile", TODAY, "2026-01-01")
        for modified in ({**row, "rates": {}}, {**row, "end": "2026-01-01"}):
            with self.assertRaises(ValueError):
                d.validate_document(modified, [], "profile", TODAY, "2026-01-01")

    def test_ratio_is_explicit_and_must_be_from_an_older_nonzero_bill(self):
        row = bill()
        self.assertEqual(d.selected_ratio([row], "", TODAY), (None, None))
        self.assertEqual(d.selected_ratio([row], d.bill_key(row), TODAY)[0], 0.8)
        self.assertEqual(
            d.selected_ratio([row], d.bill_key(row), date(2024, 6, 1)), (None, None)
        )
        zero = {**row, "nt_kwh": 0, "vt_kwh": 0}
        self.assertIsNone(d.selected_ratio([zero], d.bill_key(zero), TODAY)[0])

    def test_ratio_estimate_prices_only_unpriced_energy_and_never_mutates_input(self):
        rates = {
            **pricing.PROFILE_DEFAULTS,
            "trade_nt": 2,
            "trade_vt": 4,
            "distribution_nt": 0,
            "distribution_vt": 0,
            "electricity_tax": 0,
            "system_services": 0,
        }
        profile = pricing.PriceProfile(rates)
        when = datetime(2026, 10, 20, tzinfo=ZoneInfo("Europe/Prague"))
        gaps = [{"start": when, "end": when + timedelta(hours=1), "kwh": 3}]
        original = copy.deepcopy(gaps)
        result = d.estimate_gaps(
            gaps, 0.75, lambda _: profile, lambda _: -50, lambda _: True
        )
        self.assertAlmostEqual(result, 3 * (2 * 0.75 + 4 * 0.25) * 0.5)
        self.assertEqual(gaps, original)
        self.assertIsNone(
            d.estimate_gaps(gaps, 0.75, lambda _: None, lambda _: 0, lambda _: False)
        )

    def test_local_date_and_repeated_hour_are_respected(self):
        tz = ZoneInfo("Europe/Prague")
        seen = []
        profile = pricing.PriceProfile(pricing.PROFILE_DEFAULTS)
        left = datetime(2026, 10, 25, 0, tzinfo=UTC).astimezone(tz)
        right = (left.astimezone(UTC) + timedelta(hours=2)).astimezone(tz)
        gaps = [{"start": left, "end": right, "kwh": 2}]
        d.estimate_gaps(
            gaps,
            0.8,
            lambda day: seen.append(day) or profile,
            lambda _: 0,
            lambda _: False,
        )
        self.assertEqual(seen, [date(2026, 10, 25)])
        midnight = datetime(2026, 10, 21, 0, tzinfo=tz)
        d.estimate_gaps(
            [{"start": midnight, "end": midnight + timedelta(hours=1), "kwh": 1}],
            0.8,
            lambda day: seen.append(day) or profile,
            lambda _: 0,
            lambda _: False,
        )
        self.assertEqual(seen[-1], date(2026, 10, 21))


if __name__ == "__main__":
    unittest.main()
