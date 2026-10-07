"""Regression tests for HACS ZIP layout, commit selection and release notes."""

from __future__ import annotations

import json
import subprocess
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from scripts.build_release import build_release, extract_release_notes

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ReleasePackageTest(unittest.TestCase):
    def setUp(self) -> None:
        fixture_root = REPOSITORY_ROOT / "dist"
        fixture_root.mkdir(exist_ok=True)
        temporary = TemporaryDirectory(prefix="package-test-", dir=fixture_root)
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name)
        self.component = self.repository / "custom_components" / "cez_dynamic_tariff"
        self._git("init", "--quiet")
        self._git("config", "core.autocrlf", "false")
        self._write(
            "custom_components/cez_dynamic_tariff/__init__.py", "# committed integration\n"
        )
        self._write(
            "custom_components/cez_dynamic_tariff/manifest.json",
            json.dumps({"domain": "cez_dynamic_tariff", "version": "0.1.0"}),
        )
        for path in ("strings.json", "translations/en.json", "translations/cs.json"):
            self._write(f"custom_components/cez_dynamic_tariff/{path}", "{}")
        self._write("custom_components/cez_dynamic_tariff/brand/icon.png", "test icon")
        self._write("README.md", "Not part of the installer")
        self._write(".vs/local-metadata.json", "Not part of the installer")
        self._write(
            "CHANGELOG.md",
            "# Changelog\n\n## 0.1.0 – test release\n\n"
            "### Čeština\n\n- Testovací vydání.\n\n"
            "### English\n\n- Test release.\n",
        )
        self._commit()
        self._git("tag", "v0.1.0")

    def _git(self, *args: str) -> bytes:
        return subprocess.check_output(["git", *args], cwd=self.repository)

    def _write(self, path: str, content: str) -> None:
        target = self.repository / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")

    def _commit(self) -> None:
        self._git("add", ".")
        self._git(
            "-c",
            "user.name=Package test",
            "-c",
            "user.email=package@example.com",
            "commit",
            "--quiet",
            "-m",
            "Package fixture",
        )

    def test_zip_has_root_level_manifest_and_runtime_assets(self) -> None:
        archive, notes = build_release(self.repository, "v0.1.0", "v0.1.0")
        with ZipFile(BytesIO(archive)) as package:
            self.assertIsNone(package.testzip())
            files = {item.filename for item in package.infolist() if not item.is_dir()}
            self.assertEqual(
                files,
                {
                    "__init__.py",
                    "manifest.json",
                    "strings.json",
                    "translations/en.json",
                    "translations/cs.json",
                    "brand/icon.png",
                },
            )
            self.assertEqual(
                json.loads(package.read("manifest.json"))["version"], "0.1.0"
            )
        self.assertIn("### Čeština", notes)
        self.assertIn("### English", notes)

    def test_untracked_files_and_uncommitted_edits_are_not_packaged(self) -> None:
        for path in ("cookies.json", "credentials.json", "__pycache__/api.pyc", ".env"):
            self._write(f"custom_components/cez_dynamic_tariff/{path}", "local test data")
        self._write("custom_components/cez_dynamic_tariff/__init__.py", "# local edit\n")
        archive, _ = build_release(self.repository)
        with ZipFile(BytesIO(archive)) as package:
            self.assertEqual(package.read("__init__.py"), b"# committed integration\n")
            for path in (
                "cookies.json",
                "credentials.json",
                "__pycache__/api.pyc",
                ".env",
            ):
                self.assertNotIn(path, package.namelist())

    def test_selected_tag_is_used_instead_of_newer_working_tree(self) -> None:
        self._write(
            "custom_components/cez_dynamic_tariff/manifest.json",
            json.dumps({"domain": "cez_dynamic_tariff", "version": "0.1.1"}),
        )
        self._commit()
        archive, _ = build_release(self.repository, "v0.1.0", "v0.1.0")
        with ZipFile(BytesIO(archive)) as package:
            self.assertEqual(
                json.loads(package.read("manifest.json"))["version"], "0.1.0"
            )

    def test_repeated_builds_have_the_same_asset_digest(self) -> None:
        first, _ = build_release(self.repository, "v0.1.0", "v0.1.0")
        self._write("custom_components/cez_dynamic_tariff/local-only.json", "local test data")
        self._git("config", "core.autocrlf", "true")
        second, _ = build_release(self.repository, "v0.1.0", "v0.1.0")
        self.assertEqual(first, second)

    def test_mismatched_or_invalid_release_tags_are_rejected(self) -> None:
        for tag in ("v0.1.1", "main", "v0.1.0; unsafe"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                build_release(self.repository, "HEAD", tag)

    def test_wrong_integration_domain_is_rejected(self) -> None:
        self._write(
            "custom_components/cez_dynamic_tariff/manifest.json",
            json.dumps({"domain": "other_integration", "version": "0.1.0"}),
        )
        self._commit()
        with self.assertRaises(ValueError):
            build_release(self.repository)

    def test_missing_root_entry_point_is_rejected(self) -> None:
        self._git("rm", "custom_components/cez_dynamic_tariff/__init__.py")
        self._commit()
        with self.assertRaises(ValueError):
            build_release(self.repository)


class ReleaseNotesTest(unittest.TestCase):
    def test_extracts_only_requested_bilingual_release(self) -> None:
        changelog = (
            "# Changelog\n\n## Unreleased\n\nFuture work\n\n"
            "## 0.1.1 – next\n\n### Čeština\n\nNové vydání.\n\n"
            "### English\n\nNew release.\n\n"
            "## 0.1.0 – old\n\n### Čeština\n\nStaré vydání.\n\n"
            "### English\n\nOld release.\n"
        )
        notes = extract_release_notes(changelog, "0.1.1")
        self.assertIn("New release.", notes)
        self.assertIn("Nové vydání.", notes)
        self.assertNotIn("Old release", notes)
        self.assertNotIn("Future work", notes)
        self.assertEqual(
            notes, extract_release_notes(changelog.replace("\n", "\r\n"), "0.1.1")
        )

    def test_missing_release_or_language_is_rejected(self) -> None:
        for changelog in (
            "## 0.1.0\n\n### English\n\nEnglish only\n",
            "## 0.1.1\n\n### Čeština\n\nTest\n\n### English\n\nTest\n",
        ):
            with self.subTest(changelog=changelog), self.assertRaises(ValueError):
                extract_release_notes(changelog, "0.1.0")


class HacsInstallerMetadataTest(unittest.TestCase):
    def test_hacs_and_badges_use_the_same_installer(self) -> None:
        hacs = json.loads((REPOSITORY_ROOT / "hacs.json").read_text(encoding="utf-8"))
        self.assertTrue(hacs["zip_release"])
        self.assertEqual(hacs["filename"], "cez_dynamic_tariff.zip")
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        for asset_path in ("cez_dynamic_tariff.zip?", "latest/cez_dynamic_tariff.zip?"):
            self.assertIn(
                "https://img.shields.io/github/downloads/79thales/cez-dynamic-tariff/"
                + asset_path,
                readme,
            )


if __name__ == "__main__":
    unittest.main()
