"""Reuse one monetary EDC source without guessing a different site's revenue."""

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "edc_source",
    Path(__file__).parents[1] / "custom_components/cez_dynamic_tariff/edc_source.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def state(entity_id, **attributes):
    return SimpleNamespace(entity_id=entity_id, attributes=attributes)


class EdcSourceTests(unittest.TestCase):
    def test_diagnostic_metadata_is_the_revenue_source_not_kwh(self):
        candidates = [
            state("sensor.shared_energy", unit_of_measurement="kWh"),
            state("sensor.sharing_unit_price", unit_of_measurement="CZK/kWh"),
            state(
                "sensor.site_edc_data_available_since",
                energy_revenue_statistic_id="edc_sharing:site_revenue",
            ),
        ]
        self.assertEqual(
            module.suggest_edc_income(candidates),
            "sensor.site_edc_data_available_since",
        )

    def test_duplicate_statistic_is_suggested_once(self):
        candidates = [
            state(
                "sensor.a_edc_latest",
                energy_revenue_statistic_id="edc_sharing:site_revenue",
            ),
            state(
                "sensor.site_edc_data_available_since",
                energy_revenue_statistic_id="edc_sharing:site_revenue",
            ),
        ]
        self.assertEqual(
            module.suggest_edc_income(candidates),
            "sensor.site_edc_data_available_since",
        )

    def test_aggregate_is_preferred_to_its_recipients(self):
        group = state(
            "sensor.site_edc_data_available_since",
            energy_revenue_statistic_id="edc_sharing:site_revenue",
        )
        target = state(
            "sensor.site_target",
            role="target",
            energy_revenue_statistic_id="edc_sharing:recipient_revenue",
        )
        self.assertEqual(module.suggest_edc_income([group, target]), group.entity_id)
        self.assertIsNone(module.suggest_edc_income([target]))

    def test_multiple_sites_or_no_monetary_source_are_not_guessed(self):
        self.assertIsNone(module.suggest_edc_income([]))
        self.assertIsNone(
            module.suggest_edc_income(
                [
                    state(
                        "sensor.a", energy_revenue_statistic_id="edc_sharing:a_revenue"
                    ),
                    state(
                        "sensor.b", energy_revenue_statistic_id="edc_sharing:b_revenue"
                    ),
                ]
            )
        )
