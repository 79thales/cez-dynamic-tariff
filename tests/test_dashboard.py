"""Protect current layout, view navigation and registry-based entity binding."""

import importlib.util
import json
import unittest
from pathlib import Path

COMPONENT = Path(__file__).parents[1] / "custom_components/cez_dynamic_tariff"
spec = importlib.util.spec_from_file_location(
    "cez_dashboard_test", COMPONENT / "dashboard.py"
)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    def build(self, **kwargs):
        return dashboard.build_views(
            "ČEZ přehled", "cez-test", kwargs.get("entities", {}), kwargs.get("hdo", {})
        )

    def test_main_is_a_top_tab_and_details_are_linked_subviews(self):
        result = self.build()
        views = result["config"]["views"]
        self.assertEqual(
            [v["path"] for v in views],
            ["cez-test", "cez-test-detaily", "cez-test-zalohy"],
        )
        self.assertFalse(views[0]["subview"])
        self.assertTrue(all(v["subview"] for v in views[1:]))
        self.assertEqual(views[1]["back_path"], "/lovelace/cez-test")
        self.assertEqual(views[2]["back_path"], "/lovelace/cez-test-detaily")
        self.assertNotIn("/lovelace/cez-dynamic-tariff", json.dumps(result))

    def test_current_main_composition_and_single_forecast_are_preserved(self):
        main = self.build()["config"]["views"][0]
        self.assertEqual(
            [s["cards"][0]["heading"] for s in main["sections"]],
            [
                "Aktuální cena",
                "Dnes a úspory",
                "Zúčtovací období",
                "Skutečná spotřeba",
                "Nejlevnější odběr",
            ],
        )
        self.assertEqual([len(s["cards"]) for s in main["sections"]], [4, 4, 4, 4, 4])
        self.assertFalse(main["dense_section_placement"])
        self.assertNotIn("Srovnávací odhad", json.dumps(main, ensure_ascii=False))
        self.assertEqual(len(self.build()["config"]["views"][1]["sections"]), 6)

    def test_renamed_sensor_ids_apply_to_cards_templates_and_data_generators(self):
        result = self.build(
            entities={
                "accounting_status": "sensor.user_accounting",
                "price_with_dynamic": "sensor.user_price",
            }
        )
        text = json.dumps(result)
        self.assertIn("sensor.user_accounting", text)
        self.assertIn("sensor.user_price", text)
        self.assertNotIn("sensor.cez_dynamic_tariff_accounting_status", text)
        self.assertNotIn("accounting_status", result["missing_entities"])
        self.assertIn("daily_net_cost", result["missing_entities"])

    def test_selected_hdo_sources_are_resolved_without_site_ids(self):
        result = self.build(
            hdo={
                "HDO_ENTITY": "binary_sensor.my_hdo",
                "HDO_VALID": "binary_sensor.hdo_valid",
                "HDO_VALID_UNTIL": "sensor.hdo_expiry",
                "HDO_AGE": "sensor.hdo_age",
            }
        )
        text = json.dumps(result)
        for entity in ("binary_sensor.my_hdo", "sensor.hdo_expiry", "sensor.hdo_age"):
            self.assertIn(entity, text)
        self.assertEqual(result["missing_hdo_sources"], [])
        self.assertNotIn("__HDO", text)

    def test_unavailable_entities_are_reported_not_replaced_with_zero(self):
        result = self.build()
        self.assertIn("forecast_balance", result["missing_entities"])
        self.assertIn("HDO_ENTITY", result["missing_hdo_sources"])
        self.assertEqual(result["required_cards"], ["apexcharts-card"])

    def test_invalid_title_and_paths_are_rejected(self):
        for path in (
            "../home",
            "cez/home",
            "UPPER",
            "a" * 61,
            dashboard.PANEL_PATH,
            "quote'path",
        ):
            with self.assertRaises(ValueError):
                dashboard.build_views("ČEZ", path, {}, {})
        for title in ("", " ", "a" * 121):
            with self.assertRaises(ValueError):
                dashboard.build_views(title, "cez", {}, {})

    def test_template_has_no_customer_readings_or_external_network_calls(self):
        raw = dashboard.TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(raw, r"sensor\.[0-9]|hdo_evv[0-9]|C:/Users|\.pdf")
        self.assertNotIn("fetch(", raw)
        self.assertIn("a.settled_bills", raw)
        self.assertIn("state_attr(a,'settled_bills')", raw)
        before = dashboard.TEMPLATE_PATH.read_bytes()
        self.build()
        self.assertEqual(dashboard.TEMPLATE_PATH.read_bytes(), before)

    def test_button_and_menu_are_translated(self):
        for filename in (
            "strings.json",
            "translations/en.json",
            "translations/cs.json",
        ):
            data = json.loads((COMPONENT / filename).read_text(encoding="utf-8"))
            self.assertEqual(
                data["entity"]["button"]["generate_dashboard"]["name"],
                "Generate dashboard",
            )
            self.assertIn("dashboard", data["options"]["step"]["init"]["menu_options"])
            self.assertIn("{url}", data["options"]["step"]["dashboard"]["description"])
