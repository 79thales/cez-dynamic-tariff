"""Resolve the latest stable HA and its matching test plugin from PyPI."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from urllib.request import Request, urlopen


def _fetch_metadata(package: str, version: str | None = None) -> dict:
    """Read public package metadata with a bounded network timeout."""
    suffix = f"/{version}" if version else ""
    request = Request(
        f"https://pypi.org/pypi/{package}{suffix}/json",
        headers={"Accept": "application/json", "User-Agent": "cez-dynamic-tariff-ci"},
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def _stable_version(version: str) -> tuple[int, ...] | None:
    """Exclude pre-releases rather than accidentally selecting beta HA."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        return None
    return tuple(int(part) for part in version.split("."))


def _python_version(requirement: str) -> tuple[int, int]:
    """Select the minimum supported Python minor; setup-python supplies its patch."""
    match = re.search(r">=\s*(\d+)\.(\d+)(?:\.\d+)?", requirement)
    if match is None:
        raise ValueError(f"Cannot resolve Python from requires_python: {requirement!r}")
    return int(match[1]), int(match[2])


def resolve_latest_environment(
    fetch: Callable[[str, str | None], dict] = _fetch_metadata,
) -> dict[str, str]:
    """Keep HA at latest stable, even when the newest test plugin targets a beta."""
    core = fetch("homeassistant", None)["info"]
    version = core["version"]
    if _stable_version(version) is None:
        raise ValueError(f"PyPI did not return a stable Home Assistant version: {version}")
    plugin_package = "pytest-homeassistant-custom-component"
    plugin = fetch(plugin_package, None)
    releases = sorted(
        (
            candidate for candidate, files in plugin["releases"].items()
            if _stable_version(candidate) is not None
            and any(not file.get("yanked", False) for file in files)
        ),
        key=lambda candidate: _stable_version(candidate),
        reverse=True,
    )
    for candidate in releases[:25]:
        info = (
            plugin["info"] if candidate == plugin["info"]["version"]
            else fetch(plugin_package, candidate)["info"]
        )
        dependencies = {
            dependency.partition(";")[0].replace(" ", "")
            for dependency in info.get("requires_dist") or []
        }
        if f"homeassistant=={version}" not in dependencies:
            continue
        python = max(
            _python_version(core["requires_python"]),
            _python_version(info["requires_python"]),
        )
        return {
            "homeassistant": version,
            "test_plugin": candidate,
            "python": f"{python[0]}.{python[1]}",
        }
    raise ValueError(
        f"No matching test plugin found for latest stable Home Assistant {version}. "
        "Refusing to test an older or beta HA version instead."
    )


if __name__ == "__main__":
    print(json.dumps(resolve_latest_environment()))
