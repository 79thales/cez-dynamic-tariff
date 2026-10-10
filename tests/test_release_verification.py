"""Existing release assets must match code and binaries, without replacement."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from scripts.verify_release_package import verify_existing_installer


class ExistingInstallerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.files = {
            "manifest.json": json.dumps({"domain": "cez_dynamic_tariff", "version": "1.0.8"}).encode(),
            "__init__.py": b"# integration\nVALUE = 1\n",
            "brand/icon.png": b"\x89PNG\r\n\x00\xff",
        }
        self.built = self.write("built.zip", self.files)

    def write(self, name, files, duplicate=False):
        target = self.root / name
        with ZipFile(target, "w") as archive:
            for path, data in files.items():
                archive.writestr(path, data)
            if duplicate:
                archive.writestr("__init__.py", b"# duplicate")
        return target

    def test_legacy_windows_newlines_are_accepted_without_changing_asset(self):
        files = {**self.files, "__init__.py": self.files["__init__.py"].replace(b"\n", b"\r\n")}
        existing = self.write("existing.zip", files)
        before = existing.read_bytes()
        verify_existing_installer(self.built, existing, "v1.0.8")
        self.assertEqual(existing.read_bytes(), before)

    def test_changed_code_binary_paths_and_manifest_are_rejected(self):
        variants = [
            {**self.files, "__init__.py": b"# changed code\n"},
            {**self.files, "brand/icon.png": self.files["brand/icon.png"].replace(b"\r\n", b"\n")},
            {key: value for key, value in self.files.items() if key != "brand/icon.png"},
            {**self.files, "extra.py": b"# unexpected"},
            {**self.files, "manifest.json": b'{"domain":"cez_dynamic_tariff","version":"1.0.7"}'},
            {**self.files, "../unexpected.py": b"# unsafe"},
            {**self.files, "__init__.py": b"\xff"},
        ]
        for files in variants:
            with self.subTest(files=list(files)), self.assertRaises(ValueError):
                verify_existing_installer(self.built, self.write("changed.zip", files), "v1.0.8")

    def test_duplicate_archive_paths_are_rejected(self):
        with self.assertWarns(UserWarning):
            existing = self.write("duplicate.zip", self.files, duplicate=True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            verify_existing_installer(self.built, existing, "v1.0.8")
