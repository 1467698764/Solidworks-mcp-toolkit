import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_mate_group_execution_check.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class MateGroupExecutionCheckTests(unittest.TestCase):
    def manifest(self):
        return {
            "mode": "reviewable_mate_group_macros",
            "macros": [
                {
                    "group_id": "standard_bolt_m6-1",
                    "mate_type": "concentric",
                    "expected_mate_name": "MG_standard_bolt_m6_1_01_concentric",
                    "components": ["bolt_m6-1", "cover_plate-1"],
                },
                {
                    "group_id": "standard_bolt_m6-1",
                    "mate_type": "coincident",
                    "expected_mate_name": "MG_standard_bolt_m6_1_02_coincident",
                    "components": ["bolt_m6-1", "cover_plate-1"],
                },
            ],
        }

    def inspect_report(self):
        return {
            "active_document": {
                "type": "assembly",
                "title": "after_macro.SLDASM",
                "mate_like_features": [
                    {"name": "MG_standard_bolt_m6_1_01_concentric", "type": "MateConcentric", "components": ["bolt_m6-1", "cover_plate-1"], "suppressed": False, "mate_error": 1, "status": "ok"},
                    {"name": "MG_standard_bolt_m6_1_02_coincident", "type": "MateCoincident", "components": ["bolt_m6-1", "cover_plate-1"], "suppressed": False, "mate_error": 1, "status": "ok"},
                ],
            }
        }

    def test_execution_check_accepts_named_mates_without_errors(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            report = root / "after.json"
            out = root / "execution_check.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")
            report.write_text(json.dumps(self.inspect_report()), encoding="utf-8")

            proc = run_py("--macro-manifest", str(manifest), "--after-report", str(report), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["counts"]["expected_mates"], 2)
            self.assertEqual(data["counts"]["accepted_mates"], 2)

    def test_execution_check_reports_missing_and_bad_mates(self):
        report = self.inspect_report()
        report["active_document"]["mate_like_features"][0]["mate_error"] = 4
        report["active_document"]["mate_like_features"].pop()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            after = root / "after.json"
            out = root / "execution_check.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")
            after.write_text(json.dumps(report), encoding="utf-8")

            proc = run_py("--macro-manifest", str(manifest), "--after-report", str(after), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"], data)
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("mate_error", kinds)
            self.assertIn("mate_missing", kinds)

    def test_swctl_routes_mate_group_execution_check(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            report = root / "after.json"
            out = root / "execution_check.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")
            report.write_text(json.dumps(self.inspect_report()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-group-execution-check",
                    "-Report", str(manifest),
                    "-After", str(report),
                    "-Out", str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()
