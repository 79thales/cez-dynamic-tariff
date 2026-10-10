"""Verify existing installers without replacing published release assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

TEXT_SUFFIXES = {".py", ".js", ".json", ".yaml", ".yml"}


def _contents(path: Path, tag: str) -> dict[str, bytes]:
    """Read a valid root-level package; never extract archive paths."""
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Installer contains duplicate paths")
        for name in names:
            member = PurePosixPath(name)
            if member.is_absolute() or ".." in member.parts or "\\" in name:
                raise ValueError("Installer contains unsafe paths")
        if archive.testzip() is not None:
            raise ValueError("Installer failed integrity verification")
        content = {name: archive.read(name) for name in names if not name.endswith("/")}
    if not {"manifest.json", "__init__.py"}.issubset(content):
        raise ValueError("Installer is missing root-level integration files")
    manifest = json.loads(content["manifest.json"])
    if (
        manifest.get("domain") != "cez_dynamic_tariff"
        or f"v{manifest.get('version')}" != tag
    ):
        raise ValueError("Installer manifest does not match the release tag")
    return content


def verify_existing_installer(built: Path, existing: Path, tag: str) -> None:
    """Allow legacy CRLF and ZIP metadata differences, never code differences."""
    expected = _contents(built, tag)
    actual = _contents(existing, tag)
    if expected.keys() != actual.keys():
        raise ValueError("Existing installer has different files")
    for name, data in expected.items():
        other = actual[name]
        if PurePosixPath(name).suffix in TEXT_SUFFIXES:
            # Verify text encoding before allowing only Windows newline changes.
            data.decode("utf-8")
            other.decode("utf-8")
            data, other = data.replace(b"\r\n", b"\n"), other.replace(b"\r\n", b"\n")
        if data != other:
            raise ValueError(f"Existing installer content differs: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--built", type=Path, required=True)
    parser.add_argument("--existing", type=Path, required=True)
    parser.add_argument("--expected-tag", required=True)
    args = parser.parse_args()
    verify_existing_installer(args.built, args.existing, args.expected_tag)
    print("Existing installer verified; all integration files match the tagged build.")


if __name__ == "__main__":
    main()
