"""Financially significant PDF import validations, using synthetic PDFs."""

import importlib.util
import sys
import unittest
from pathlib import Path

from price_list_fixture import make_pdf

spec = importlib.util.spec_from_file_location(
    "_cez_price_list_test",
    Path(__file__).parents[1] / "custom_components/cez_dynamic_tariff/price_list.py",
)
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)


class PriceListTests(unittest.TestCase):
    def test_vat_columns_mwh_conversion_and_breaker(self):
        result = p.parse_price_list(make_pdf(), "D57D", 25, 3)
        self.assertEqual(result.rates["trade_vt"], 3.18)
        self.assertEqual(result.rates["trade_nt"], 3.05)
        self.assertEqual(result.rates["distribution_vt"], 0.91327)
        self.assertEqual(result.rates["breaker_monthly"], 671.55)
        self.assertEqual(result.rates["poze_kwh"], 0)
        self.assertEqual(result.trade_effective, "2026-01-30")
        self.assertEqual(result.distribution_effective, "2026-01-01")
        self.assertEqual(len(result.digest), 64)
        self.assertFalse(result.poze_estimated)
        # A new list must change rates, not always return the bundled preset.
        updated = p.parse_price_list(make_pdf(trade_vt=4000), "D57d", 32, 3)
        self.assertEqual(updated.rates["trade_vt"], 4.0)
        self.assertEqual(updated.rates["breaker_monthly"], 859.10)

    def test_other_columns_and_single_phase_breakers(self):
        r = p.parse_price_list(make_pdf(), "D25d", 25, 3)
        self.assertEqual(r.rates["trade_vt"], 3.02)
        self.assertEqual(r.rates["breaker_monthly"], 325.49)
        self.assertEqual(
            p.parse_price_list(make_pdf(), "D57d", 25, 1).rates["breaker_monthly"],
            268.62,
        )
        self.assertEqual(
            p.parse_price_list(make_pdf(), "D57d", 32, 1).rates["breaker_monthly"],
            49.4 * 32,
        )
        self.assertEqual(
            p.parse_price_list(make_pdf(), "D57d", 80, 3).rates["breaker_monthly"],
            3742.53,
        )
        self.assertEqual(
            p.parse_price_list(make_pdf(), "D25d", 80, 3).rates["breaker_monthly"],
            13 * 80,
        )

    def test_unknown_missing_inconsistent_and_multiperiod_are_rejected(self):
        for kwargs, rate, error in (
            ({}, "D99d", "rate_not_in_price_list"),
            ({}, "D01d", "incomplete_price_list"),
            ({"missing": True}, "D57d", "incomplete_price_list"),
            ({"inconsistent": True}, "D57d", "inconsistent_price_list"),
            ({"duplicate": True}, "D57d", "ambiguous_price_list"),
            ({"territory": "PREdistribuce"}, "D57d", "unsupported_price_list"),
        ):
            with (
                self.subTest(error=error),
                self.assertRaisesRegex(p.PriceListError, error),
            ):
                p.parse_price_list(make_pdf(**kwargs), rate, 25, 3)

    def test_poze_is_lower_cap_estimate_and_requires_annual_energy(self):
        pdf = make_pdf(capacity=5)
        with self.assertRaisesRegex(p.PriceListError, "poze_requires_annual_import"):
            p.parse_price_list(pdf, "D57d", 25, 3)
        small = p.parse_price_list(pdf, "D57d", 25, 3, 10000)
        self.assertEqual(small.rates["poze_kwh"], 0.45)
        self.assertTrue(small.poze_estimated)
        large = p.parse_price_list(pdf, "D57d", 25, 3, 1000)
        self.assertAlmostEqual(large.rates["poze_kwh"], 0.59895)

    def test_size_corrupt_and_url_limits(self):
        for pdf, error in (
            (b"not a pdf", "invalid_price_list_pdf"),
            (b"%PDF-corrupt", "invalid_price_list_pdf"),
            (b"x" * (p.MAX_PDF_BYTES + 1), "price_list_too_large"),
        ):
            with self.assertRaisesRegex(p.PriceListError, error):
                p.parse_price_list(pdf, "D57d", 25, 3)
        good = "https://www.cez.cz/webpublic/file/edee/ceniky/test.pdf"
        self.assertEqual(p.validate_cez_url(good), good)
        for url in (
            "http://www.cez.cz/test.pdf",
            "https://localhost/test.pdf",
            "https://www.cez.cz.evil.test/t.pdf",
            "https://www.cez.cz@evil.test/t.pdf",
            "https://www.cez.cz:8123/t.pdf",
            "https://www.cez.cz/test.html",
            "https://www.cez.cz/test.pdf#x",
        ):
            with self.assertRaisesRegex(p.PriceListError, "invalid_price_list_url"):
                p.validate_cez_url(url)
