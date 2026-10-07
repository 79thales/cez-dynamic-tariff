"""Tests for resolving actual latest stable HA without network access."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "resolve_latest_ha.py"
spec = importlib.util.spec_from_file_location("resolve_latest_ha", SCRIPT)
assert spec is not None and spec.loader is not None
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


def _metadata(*, version: str, homeassistant: str | None = None) -> dict:
    """Make only the public metadata fields needed by the resolver."""
    return {"info": {
        "version": version,
        "requires_python": ">=3.14.2",
        "requires_dist": [f"homeassistant=={homeassistant}"] if homeassistant else [],
    }}


class LatestHomeAssistantTests(unittest.TestCase):
    """Prevent silent beta selection, downgrade or skipped compatibility tests."""

    def _fetch(self, *, stable: str = "2026.9.4", yanked: bool = False) -> Mock:
        core = _metadata(version=stable)
        plugin = _metadata(version="0.13.369", homeassistant="2026.10.0b2")
        plugin["releases"] = {
            "0.13.369": [{"yanked": False}],
            "0.13.368": [{"yanked": False}],
            "0.13.367": [{"yanked": yanked}],
            "0.13.370b1": [{"yanked": False}],
            "0.13.366": [],
        }
        values = {
            ("homeassistant", None): core,
            ("pytest-homeassistant-custom-component", None): plugin,
            ("pytest-homeassistant-custom-component", "0.13.368"):
                _metadata(version="0.13.368", homeassistant="2026.10.0b0"),
            ("pytest-homeassistant-custom-component", "0.13.367"):
                _metadata(version="0.13.367", homeassistant="2026.9.4"),
        }
        return Mock(side_effect=lambda package, version: values[(package, version)])

    def test_skips_newest_plugin_when_it_targets_beta_ha(self) -> None:
        fetch = self._fetch()
        self.assertEqual(resolver.resolve_latest_environment(fetch), {
            "homeassistant": "2026.9.4", "test_plugin": "0.13.367", "python": "3.14",
        })
        self.assertEqual(fetch.call_count, 4)

    def test_latest_stable_changes_without_a_workflow_edit(self) -> None:
        core = _metadata(version="2026.10.1")
        plugin = _metadata(version="0.13.400", homeassistant="2026.10.1")
        plugin["releases"] = {"0.13.400": [{"yanked": False}]}
        fetch = Mock(side_effect=[core, plugin])
        self.assertEqual(resolver.resolve_latest_environment(fetch)["homeassistant"], "2026.10.1")
        self.assertEqual(fetch.call_count, 2)

    def test_beta_ha_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "stable Home Assistant"):
            resolver.resolve_latest_environment(self._fetch(stable="2026.10.0b2"))

    def test_missing_matching_plugin_fails_instead_of_downgrading(self) -> None:
        with self.assertRaisesRegex(ValueError, "Refusing to test an older or beta"):
            resolver.resolve_latest_environment(self._fetch(stable="2026.10.1"))

    def test_yanked_matching_plugin_is_not_used(self) -> None:
        with self.assertRaisesRegex(ValueError, "No matching test plugin"):
            resolver.resolve_latest_environment(self._fetch(yanked=True))

    def test_network_failure_is_not_silently_skipped(self) -> None:
        with self.assertRaises(TimeoutError):
            resolver.resolve_latest_environment(Mock(side_effect=TimeoutError))

    def test_unrecognized_python_requirement_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Cannot resolve Python"):
            resolver._python_version("unknown")
