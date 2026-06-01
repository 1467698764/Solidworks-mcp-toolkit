import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_py(script: str, *args: str):
    return subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class ChangeVerifyTests(unittest.TestCase):
    def test_verify_allows_only_expected_dimension_change(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "verify.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_change_verify.py",
                "--delta", "tools/solidworks_codex/sandbox/compare_fixture.json",
                "--allow-dimension", "D1@Sketch1@plate.SLDPRT",
                "--allow-component", "support_bushing-1:suppressed",
                "--allow-component", "drive_unit-1:fixed",
                "--allow-component-added", "reference_sensor-1",
                "--allow-feature-type", "Fillet",
                "--out", str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["unexpected"], [])
            self.assertGreaterEqual(len(data["accepted"]), 4)

    def test_verify_rejects_unexpected_component_and_feature_changes(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "verify.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_change_verify.py",
                "--delta", "tools/solidworks_codex/sandbox/compare_fixture.json",
                "--allow-dimension", "D1@Sketch1@plate.SLDPRT",
                "--out", str(out),
            )
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["unexpected"]}
            self.assertFalse(data["ok"], data)
            self.assertIn("component_added", kinds)
            self.assertIn("component_changed", kinds)
            self.assertIn("feature_count_changed", kinds)


    def test_swctl_propagates_change_verify_failure_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "verify.json"
            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "change-verify",
                    "-Report", "tools/solidworks_codex/sandbox/compare_fixture.json",
                    "-AllowDimension", "D1@Sketch1@plate.SLDPRT",
                    "-Out", str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()
