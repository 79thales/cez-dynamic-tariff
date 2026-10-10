"""Build the HACS installer from an immutable Git commit, not local account data."""

from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPONENT_PATH = "custom_components/cez_dynamic_tariff"
ASSET_NAME = "cez_dynamic_tariff.zip"


def _git(repository: Path, *args: str) -> bytes:
    """Read committed data without executing a shell."""
    return subprocess.check_output(
        ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", *args],
        cwd=repository,
    )


def extract_release_notes(changelog: str, version: str) -> str:
    """Extract only the requested version, preserving Czech and English notes."""
    changelog = changelog.replace("\r\n", "\n")
    match = re.search(
        rf"^## {re.escape(version)}(?:\s[^\n]*)?\n(.*?)(?=^## |\Z)",
        changelog,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise ValueError(f"CHANGELOG.md has no release notes for {version}")
    notes = match.group(1).strip() + "\n"
    if not all(
        re.search(rf"^### {language}$", notes, flags=re.MULTILINE)
        for language in ("Čeština", "English")
    ):
        raise ValueError("Release notes must contain Czech and English sections")
    return notes


def build_release(
    repository: Path, ref: str = "HEAD", expected_tag: str | None = None
) -> tuple[bytes, str]:
    """Return a validated root-level installer ZIP and matching release notes."""
    commit = (
        _git(
            repository, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"
        )
        .decode("ascii")
        .strip()
    )
    manifest = json.loads(
        _git(repository, "show", f"{commit}:{COMPONENT_PATH}/manifest.json")
    )
    version = manifest.get("version")
    if manifest.get("domain") != "cez_dynamic_tariff" or not isinstance(version, str):
        raise ValueError("Expected the versioned cez_dynamic_tariff integration manifest")
    if expected_tag is not None and (
        not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?", expected_tag)
        or expected_tag != f"v{version}"
    ):
        raise ValueError("Release tag must match the integration manifest version")

    # git archive uses local time for ZIP dates. Stamp the installer in UTC
    # explicitly so Windows and CI produce the same metadata.
    committed_at = int(_git(repository, "show", "-s", "--format=%ct", commit))
    stamp = datetime.fromtimestamp(committed_at, UTC)
    archive_date = (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second)
    source = _git(repository, "archive", "--format=zip", commit, COMPONENT_PATH)
    output = BytesIO()
    prefix = COMPONENT_PATH + "/"
    with ZipFile(BytesIO(source)) as package, ZipFile(output, "w") as installer:
        names = {
            name.removeprefix(prefix)
            for name in package.namelist()
            if name.startswith(prefix)
        }
        if not {"manifest.json", "__init__.py"}.issubset(names):
            raise ValueError(
                "Installer must contain manifest.json and __init__.py at its root"
            )
        for item in package.infolist():
            if item.is_dir():
                continue
            if not item.filename.startswith(prefix):
                raise ValueError("Installer contains files outside the integration")
            path = PurePosixPath(item.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in item.filename:
                raise ValueError("Unsafe path in installer")
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Installer must not contain symbolic links")
            target = ZipInfo(
                item.filename.removeprefix(prefix), date_time=archive_date
            )
            target.create_system = 3
            target.external_attr = 0o100644 << 16
            target.compress_type = ZIP_DEFLATED
            installer.writestr(target, package.read(item))
        if package.testzip() is not None:
            raise ValueError("Installer failed ZIP integrity verification")
        if json.loads(package.read(prefix + "manifest.json")) != manifest:
            raise ValueError("Packaged manifest differs from the selected commit")

    changelog = _git(repository, "show", f"{commit}:CHANGELOG.md").decode("utf-8")
    return output.getvalue(), extract_release_notes(changelog, version)


def main() -> None:
    """Write build artifacts; uploading or publishing is deliberately separate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--repository", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--expected-tag")
    parser.add_argument("--output", type=Path, default=Path("dist") / ASSET_NAME)
    args = parser.parse_args()
    if args.output.name != ASSET_NAME:
        parser.error(f"The HACS installer filename must be {ASSET_NAME}")
    archive, notes = build_release(args.repository.resolve(), args.ref, args.expected_tag)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(archive)
    args.output.with_name("release-notes.md").write_text(notes, encoding="utf-8")
    print(f"Built {args.output} ({len(archive)} bytes) from {args.ref}")


if __name__ == "__main__":
    main()
