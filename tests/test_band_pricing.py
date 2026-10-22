"""Cenové revize, obě strategie, kalendář a selhání bez potřeby HA."""

import copy
import importlib.util
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from price_list_fixture import make_pdf

ROOT = Path(__file__).parents[1] / "custom_components/cez_dynamic_tariff"


def load(name):
    spec = importlib.util.spec_from_file_location(
        f"_band_test_{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


b, p, pdf, accounting = (
    load("band_pricing"),
    load("pricing"),
    load("price_list"),
    load("accounting"),
)
TZ = ZoneInfo("Europe/Prague")
# Kontrolní rozvrhy veřejného procentního produktu, oddělené od implementace.
STARTS = [
    (0, -10),
    (180, -50),
    (300, 25),
    (480, 10),
    (660, -10),
    (840, 10),
    (960, -10),
    (1080, 25),
    (1200, 10),
    (1380, -10),
]
DEFAULTS = {key: STARTS for key in b.SCHEDULE_KEYS}


def fixed(variant="2years"):
    result = pdf.parse_price_list(
        make_pdf(dynamic=variant, effective="1. 6. 2026"), "D57d", 25, 3
    )
    return {
        "id": variant,
        "product": result.product,
        "rates": result.rates,
        "schedules": result.schedules,
        "trade_effective": result.trade_effective,
        "distribution_effective": result.distribution_effective,
    }


def strategy(options):
    return b.BandPricing(
        options,
        p.PROFILE_DEFAULTS,
        TZ,
        lambda day: day.month == 10 and day.day == 28,
        DEFAULTS,
    )


class BandPricingTests(unittest.TestCase):
    def setUp(self):
        self.options = {
            **p.PROFILE_DEFAULTS,
            "dynamic_pricing": True,
            "fixed_price_profiles": [fixed(), fixed("indefinite")],
            "fixed_profile_id": "2years",
        }
        self.now = datetime(2026, 10, 22, 3, tzinfo=TZ)

    def test_manual_price_checks_and_no_double_percentage(self):
        for identity, trade, total in (
            ("2years", 1.85, 2.22394),
            ("indefinite", 1.95, 2.32394),
        ):
            engine = strategy(
                {
                    **self.options,
                    "tariff_mode": "fixed_bands",
                    "fixed_profile_id": identity,
                }
            )
            q = engine.quote(self.now, "NT", -50, True)
            self.assertAlmostEqual(q["price_kwh"], total)
            self.assertEqual(q["trade_price"], trade)
            self.assertIsNone(q["modifier_percent"])
            self.assertEqual(q["price_level"], "super_cheap")
            self.assertAlmostEqual(
                engine.quote(self.now, "VT", 25, True)["price_kwh"], trade + 1.14624
            )
        self.assertAlmostEqual(
            strategy(self.options).quote(self.now, "NT", -50, True)["price_kwh"],
            1.89894,
        )

    def test_activation_restart_and_percentage_profile_survives(self):
        activation = self.now + timedelta(hours=1, seconds=17)
        updated = b.record_change(
            self.options,
            {**self.options, "tariff_mode": "fixed_bands"},
            p.PROFILE_DEFAULTS,
            self.now,
            activation,
        )
        # Restart = vytvoření nové instance výhradně z uložené konfigurace.
        engine = strategy(copy.deepcopy(updated))
        self.assertEqual(
            engine.quote(activation - timedelta(microseconds=1), "NT", 0, True)[
                "tariff_mode"
            ],
            "percentage",
        )
        self.assertEqual(
            engine.quote(activation, "NT", 0, True)["tariff_mode"], "fixed_bands"
        )
        self.assertEqual(updated["trade_nt"], self.options["trade_nt"])
        back = b.record_change(
            updated,
            {**updated, "tariff_mode": "percentage"},
            p.PROFILE_DEFAULTS,
            activation + timedelta(hours=1),
        )
        self.assertEqual(len(back["pricing_events"]), 2)
        self.assertEqual(
            strategy(back).quote(activation, "NT", 0, True)["tariff_mode"],
            "fixed_bands",
        )

    def test_upload_unused_profile_does_not_change_history_or_mode(self):
        after = {
            **self.options,
            "fixed_price_profiles": self.options["fixed_price_profiles"] + [fixed()],
        }
        self.assertNotIn(
            "pricing_events",
            b.record_change(self.options, after, p.PROFILE_DEFAULTS, self.now),
        )

    def test_new_selection_replaces_future_plan_and_can_activate_same_mode_now(self):
        future = self.now + timedelta(days=2)
        planned = b.record_change(
            self.options,
            {**self.options, "tariff_mode": "fixed_bands"},
            p.PROFILE_DEFAULTS,
            self.now,
            future,
        )
        immediately = b.record_change(
            planned, planned, p.PROFILE_DEFAULTS, self.now, force=True
        )
        self.assertEqual(len(immediately["pricing_events"]), 1)
        self.assertEqual(
            strategy(immediately).quote(self.now, "NT", 0, True)["tariff_mode"],
            "fixed_bands",
        )
        later = b.record_change(
            planned,
            planned,
            p.PROFILE_DEFAULTS,
            self.now,
            future + timedelta(days=2),
            force=True,
        )
        self.assertEqual(len(later["pricing_events"]), 1)
        self.assertEqual(
            strategy(later).quote(future, "NT", 0, True)["tariff_mode"], "percentage"
        )

    def test_archive_alias_is_only_for_same_source_and_whole_old_hours(self):
        activation = self.now + timedelta(hours=1, minutes=30)
        identity = {"energy": "verified-meter", "hdo": "verified-hdo"}
        options = b.record_change(
            self.options,
            {**self.options, "tariff_mode": "fixed_bands"},
            p.PROFILE_DEFAULTS,
            self.now,
            activation,
            "verified-old",
            archive_identity=identity,
        )
        self.assertEqual(
            b.previous_archive_revision(
                options, self.now, self.now + timedelta(hours=1), identity
            ),
            "verified-old",
        )
        self.assertIsNone(
            b.previous_archive_revision(
                options,
                self.now,
                self.now + timedelta(hours=1),
                {**identity, "energy": "other-meter"},
            )
        )
        self.assertIsNone(
            b.previous_archive_revision(
                options, self.now + timedelta(hours=1), self.now + timedelta(hours=2)
            )
        )
        changed_meter = b.record_change(
            self.options,
            {**self.options, "import_energy_entity": "sensor.other"},
            p.PROFILE_DEFAULTS,
            self.now,
            archive_revision="verified-old",
            archive_identity=identity,
        )
        self.assertNotIn(
            "previous_archive_revision", changed_meter["pricing_events"][0]
        )

    def test_holidays_seasons_and_global_band_classification(self):
        engine = strategy({**self.options, "tariff_mode": "fixed_bands"})
        for when, expected in (
            (datetime(2026, 7, 1, 12, tzinfo=TZ), 1.85),
            (datetime(2026, 10, 22, 12, tzinfo=TZ), 3.33),
            (datetime(2026, 10, 28, 8, tzinfo=TZ), 4.07),
        ):
            self.assertEqual(engine.quote(when, "NT", 0, True)["trade_price"], expected)
        sunday = datetime(2026, 10, 25, 8, tzinfo=TZ)
        self.assertEqual(
            engine.quote(sunday, "NT", 0, True)["price_level"], "expensive"
        )
        # Starší preference vypnutí svátků nesmí změnit nový smluvní ceník.
        holiday = strategy(
            {**self.options, "tariff_mode": "fixed_bands", "include_holidays": False}
        )
        self.assertEqual(
            holiday.quote(datetime(2026, 10, 28, 8, tzinfo=TZ), "NT", 0, True)[
                "trade_price"
            ],
            4.07,
        )

    def test_missing_profile_hdo_and_future_effective_dates(self):
        engine = strategy(
            {
                **self.options,
                "tariff_mode": "fixed_bands",
                "fixed_profile_id": "missing",
            }
        )
        self.assertIsNone(engine.quote(self.now, "NT", 0, True)["price_kwh"])
        self.assertEqual(
            engine.quote(self.now, "NT", 0, True)["strategy_status"],
            "fixed_profile_missing",
        )
        self.assertIsNotNone(engine.quote(self.now, "NT", 0, False)["price_kwh"])
        engine = strategy({**self.options, "tariff_mode": "fixed_bands"})
        self.assertIsNone(engine.quote(self.now, None, 0, True)["price_kwh"])
        self.assertEqual(
            engine.quote(datetime(2026, 5, 1, tzinfo=TZ), "NT", 0, True)[
                "strategy_status"
            ],
            "price_list_not_effective",
        )
        for invalid in ("2026-10-25T02:30:00", "invalid"):
            with self.assertRaises(ValueError):
                b.instant(invalid)

    def test_timeline_dst_and_subminute_activation_edges(self):
        activation = self.now + timedelta(seconds=17)
        updated = b.record_change(
            self.options,
            {**self.options, "tariff_mode": "fixed_bands"},
            p.PROFILE_DEFAULTS,
            self.now,
            activation,
        )
        engine = strategy(updated)
        end = self.now + timedelta(minutes=1)
        rows = p.price_timeline(
            self.now,
            end,
            [p.HdoInterval(self.now.astimezone(UTC), end.astimezone(UTC), "NT")],
            p.PriceProfile(self.options),
            lambda when: -50,
            None,
            engine,
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["end"], activation.astimezone(UTC))
        self.assertAlmostEqual(rows[1]["price_kwh"], 2.22394)
        for day, hours in (
            (datetime(2026, 3, 29, tzinfo=TZ), 23),
            (datetime(2026, 10, 25, tzinfo=TZ), 25),
        ):
            right = day + timedelta(days=1)
            rows = p.price_timeline(
                day,
                right,
                [p.HdoInterval(day.astimezone(UTC), right.astimezone(UTC), "NT")],
                p.PriceProfile(self.options),
                lambda when: 0,
                None,
                strategy(self.options),
            )
            self.assertEqual(
                sum((r["end"] - r["start"]).total_seconds() for r in rows), hours * 3600
            )
            self.assertAlmostEqual(
                strategy(self.options).daily_fee(
                    day.astimezone(UTC), right.astimezone(UTC), True
                ),
                850.47 / 31,
            )

    def test_changed_fees_belong_to_selected_product_only(self):
        options = copy.deepcopy(self.options)
        options["tariff_mode"] = "fixed_bands"
        options["fixed_price_profiles"][0]["rates"]["supplier_monthly"] = 300.0
        engine = strategy(options)
        self.assertAlmostEqual(engine.monthly(self.now, True), 987.12)
        self.assertAlmostEqual(engine.monthly(self.now, False), 850.47)
        start = datetime(2026, 10, 25, tzinfo=TZ).astimezone(UTC)
        end = datetime(2026, 10, 26, tzinfo=TZ).astimezone(UTC)
        activation = start + (end - start) / 2
        revised = b.record_change(
            self.options, options, p.PROFILE_DEFAULTS, start, activation
        )
        self.assertAlmostEqual(
            strategy(revised).daily_fee(start, end, None), (850.47 + 987.12) / 2 / 31
        )

    def test_unknown_comparison_is_not_zero_and_does_not_break_actual_metering(self):
        engine = strategy(
            {
                **self.options,
                "tariff_mode": "fixed_bands",
                "fixed_profile_id": "missing",
                "dynamic_pricing": False,
            }
        )
        end = self.now + timedelta(minutes=1)
        rows = p.price_timeline(
            self.now,
            end,
            [p.HdoInterval(self.now.astimezone(UTC), end.astimezone(UTC), "NT")],
            p.PriceProfile(self.options),
            lambda when: -50,
            None,
            engine,
        )
        ledger = accounting.CostLedger()
        ledger.sample(self.now, 100, rows, tz=TZ)
        ledger.sample(end, 101, rows, tz=TZ)
        self.assertAlmostEqual(ledger.totals["actual_cost"], 3.42394)
        self.assertEqual(ledger.totals["comparison_unpriced_kwh"], 1)

    def test_bad_coverage_and_nonfinite_prices_are_rejected(self):
        for value in (float("nan"), float("inf"), -1, True):
            schedules = copy.deepcopy(fixed()["schedules"])
            schedules["summer_workday_schedule"][0]["price_kwh"] = value
            with self.assertRaises(ValueError):
                b.validate_bands(schedules)
        schedules = copy.deepcopy(fixed()["schedules"])
        schedules["winter_workday_schedule"][1]["start_minute"] += 1
        with self.assertRaises(ValueError):
            b.validate_bands(schedules)

    def test_invalid_legacy_percentage_schedule_keeps_coordinator_fallback(self):
        """Starý neplatný rozvrh nesmí v novém výpočtu získat jiný význam."""
        when = datetime(2026, 10, 22, 8, 30, tzinfo=TZ)
        for saved in ("00:00,08:00", "00:00,08:00=99", "00:00=", "00:00=0,00:00=25"):
            engine = strategy({**self.options, "winter_workday_schedule": saved})
            self.assertEqual(engine.quote(when, "NT", 0, True)["modifier_percent"], 10)
