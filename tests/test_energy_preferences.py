"""Energy preferences remain a single source of truth across HA formats."""

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "energy_preferences",
    Path(__file__).parents[1]
    / "custom_components/cez_dynamic_tariff/energy_preferences.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EnergyPreferenceTests(unittest.TestCase):
    def test_legacy_and_unified_grid_compensation_without_import_costs(self):
        prefs = {
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [{"stat_cost": "sensor.import_cost"}],
                    "flow_to": [{"stat_compensation": "edc_sharing:legacy_revenue"}],
                },
                {
                    "type": "grid",
                    "stat_cost": "sensor.other_import_cost",
                    "stat_compensation": "edc_sharing:unified_revenue",
                },
                {"type": "gas", "stat_compensation": "sensor.unrelated"},
            ]
        }
        self.assertEqual(
            module.compensation_statistics(prefs),
            {
                "edc_sharing:legacy_revenue",
                "edc_sharing:unified_revenue",
            },
        )

    def test_missing_and_duplicate_preferences(self):
        self.assertEqual(module.compensation_statistics(None), set())
        prefs = {
            "energy_sources": [
                {
                    "type": "grid",
                    "stat_compensation": "edc_sharing:revenue",
                    "flow_to": [
                        {"stat_compensation": "edc_sharing:revenue"},
                        {"stat_compensation": None},
                    ],
                }
            ]
        }
        self.assertEqual(module.compensation_statistics(prefs), {"edc_sharing:revenue"})
