"""Regrese zjišťování HA a nezávislého spuštění podporovaných verzí v CI."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/quality.yaml"


def job(workflow: str, name: str) -> str:
    """Vrátí jeden job podle odsazení; jiné joby nesmějí ovlivnit kontrolu."""
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\s*\n(.*?)(?=^  [\w-]+:\s*$|\Z)",
        workflow,
    )
    if match is None:
        raise AssertionError(f"Chybí job {name}")
    return match.group(1)


def resolver_run(workflow: str) -> str:
    """Vybere skutečný shellový příkaz resolveru, jednořádkový i blokový."""
    lines = job(workflow, "latest-home-assistant").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "id: resolve")
    index = next(
        i for i in range(start + 1, len(lines)) if lines[i].startswith("        run:")
    )
    value = lines[index].split("run:", 1)[1].strip()
    if value != "|":
        return value
    result = []
    for line in lines[index + 1 :]:
        if line and not line.startswith("          "):
            break
        result.append(line[10:] if line else "")
    return "\n".join(result)


class QualityWorkflowTests(unittest.TestCase):
    """Testuje shell bez sítě a strukturu obou větví matice HA."""

    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.bash = (
            Path("C:/Program Files/Git/bin/bash.exe")
            if os.name == "nt"
            else Path(shutil.which("bash") or "/nonexistent/bash")
        )
        if not cls.bash.is_file():
            raise AssertionError("Test CI potřebuje bash (ve Windows Git Bash).")

    def shell(self, python_function: str):
        """Spustí příkaz stejným `-e -o pipefail` jako Actions, bez skutečné sítě."""
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "github_output"
            env = {**os.environ, "GITHUB_OUTPUT": output.as_posix()}
            script = python_function + "\n" + resolver_run(self.workflow) + "\n"
            result = subprocess.run(
                [
                    str(self.bash),
                    "--noprofile",
                    "--norc",
                    "-e",
                    "-o",
                    "pipefail",
                    "-c",
                    script,
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode, output.read_text(
                encoding="utf-8"
            ) if output.exists() else ""

    def test_resolver_failure_reaches_ci_without_empty_output(self):
        """Selhání Pythonu nesmí úspěšné `echo` skrýt ani zapsat prázdný výstup."""
        status, output = self.shell("python() { return 23; }")
        self.assertEqual(status, 23)
        self.assertEqual(output, "")

    def test_resolver_success_writes_complete_output(self):
        """Úspěšný JSON zůstane jediným úplným výstupem pro následující job."""
        payload = (
            '{"homeassistant":"2026.10.4","python":"3.14","test_plugin":"0.13.375"}'
        )
        status, output = self.shell(f"python() {{ printf '%s\\n' '{payload}'; }}")
        self.assertEqual(status, 0)
        self.assertEqual(output, f"environment={payload}\n")

    def test_supported_versions_run_independently_of_latest_resolver(self):
        """Pevné verze nemají závislost na selhání výběru nejnovějšího HA."""
        supported = job(self.workflow, "home-assistant")
        latest = job(self.workflow, "home-assistant-latest")
        self.assertNotRegex(supported, r"(?m)^    needs:")
        self.assertRegex(latest, r"(?m)^    needs: latest-home-assistant$")
        for version in ('"2025.1.4"', '"0.13.205"', '"2026.8.3"', '"0.13.357"'):
            self.assertIn(version, supported)
        self.assertNotIn("needs.latest-home-assistant", supported)
        for field in ("homeassistant", "test_plugin", "python"):
            self.assertIn(
                f"fromJSON(needs.latest-home-assistant.outputs.environment).{field}",
                latest,
            )
        # Obě větve musí instalovat a spouštět přesně stejné kroky testů.
        self.assertEqual(
            supported.split("    steps:\n", 1)[1].strip(),
            latest.split("    steps:\n", 1)[1].strip(),
        )
