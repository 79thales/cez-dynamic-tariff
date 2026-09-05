"""Tests for the public entity and translation contract."""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "cez_dynamic_tariff"


def _description_keys(filename: str, constructor: str) -> set[str]:
    """Extract static entity description keys without importing Home Assistant."""
    tree = ast.parse((COMPONENT / filename).read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != constructor:
            continue
        for keyword in node.keywords:
            if keyword.arg == "key" and isinstance(keyword.value, ast.Constant):
                keys.add(str(keyword.value.value))
    return keys


class PublicContractTests(unittest.TestCase):
    """Protect stable IDs and translated entity names."""

    def test_all_sensor_keys_are_stable_and_translated(self) -> None:
        """Every public sensor key exists in all translation files."""
        expected = {
            "current_modifier",
            "current_band",
            "cheap_threshold",
            "super_cheap_threshold",
            "expensive_threshold",
            "very_expensive_threshold",
            "season",
            "day_type",
            "effective_price",
            "current_cheap_end",
            "next_cheap_start",
            "next_cheap_end",
            "next_cheap_modifier",
            "next_change",
            "next_modifier",
            "today_tariff_map",
            "tomorrow_tariff_map",
        }
        actual = _description_keys(
            "sensor.py",
            "CezDynamicTariffSensorDescription",
        )

        self.assertEqual(actual, expected)
        for filename in ("strings.json", "translations/en.json", "translations/cs.json"):
            content = json.loads((COMPONENT / filename).read_text(encoding="utf-8"))
            self.assertEqual(set(content["entity"]["sensor"]), expected)

    def test_all_binary_sensor_keys_are_stable_and_translated(self) -> None:
        """Every public binary sensor key exists in all translation files."""
        expected = {
            "cheap_now",
            "super_cheap_now",
            "expensive_now",
            "very_expensive_now",
        }
        actual = _description_keys(
            "binary_sensor.py",
            "CezDynamicTariffBinarySensorDescription",
        )

        self.assertEqual(actual, expected)
        for filename in ("strings.json", "translations/en.json", "translations/cs.json"):
            content = json.loads((COMPONENT / filename).read_text(encoding="utf-8"))
            self.assertEqual(set(content["entity"]["binary_sensor"]), expected)

    def test_entity_id_prefix_remains_explicit(self) -> None:
        """Future edits must not reintroduce language-derived entity IDs."""
        sensor_source = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        binary_source = (COMPONENT / "binary_sensor.py").read_text(encoding="utf-8")

        self.assertIn('f"sensor.{DOMAIN}_{description.key}"', sensor_source)
        self.assertIn('f"binary_sensor.{DOMAIN}_{description.key}"', binary_source)

    def test_options_flow_keeps_separate_steps(self) -> None:
        """The options flow retains its general, threshold, schedule, and reset steps."""
        tree = ast.parse((COMPONENT / "config_flow.py").read_text(encoding="utf-8"))
        methods = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertTrue(
            {
                "async_step_init",
                "async_step_thresholds",
                "async_step_schedules",
                "async_step_reset_schedules",
            }.issubset(methods)
        )

    def test_reload_uses_config_entry_lifecycle(self) -> None:
        """Options updates must not bypass Home Assistant unload callbacks."""
        tree = ast.parse((COMPONENT / "__init__.py").read_text(encoding="utf-8"))
        reload_function = next(
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "async_reload_entry"
        )
        calls = {
            ast.unparse(node.func)
            for node in ast.walk(reload_function)
            if isinstance(node, ast.Call)
        }

        self.assertIn("hass.config_entries.async_reload", calls)
        self.assertNotIn("async_unload_entry", calls)
        self.assertNotIn("async_setup_entry", calls)

    def test_default_schedule_has_public_provenance(self) -> None:
        """The bundled table must expose a stable revision and official source."""
        source = (COMPONENT / "const.py").read_text(encoding="utf-8")

        self.assertIn('DEFAULT_SCHEDULE_REVISION = "cez-public-table-2024-09"', source)
        self.assertIn("https://www.cez.cz/", source)

    def test_blueprint_examples_are_present(self) -> None:
        """Ship the documented automation starting points with the repository."""
        blueprint_dir = (
            ROOT / "blueprints" / "automation" / "cez_dynamic_tariff"
        )
        expected = {
            "cheap_window_device.yaml",
            "super_cheap_charging.yaml",
            "expensive_window_actions.yaml",
        }

        self.assertEqual(
            {path.name for path in blueprint_dir.glob("*.yaml")},
            expected,
        )
        for filename in expected:
            content = (blueprint_dir / filename).read_text(encoding="utf-8")
            self.assertIn("domain: automation", content)
            self.assertIn("source_url:", content)


if __name__ == "__main__":
    unittest.main()
