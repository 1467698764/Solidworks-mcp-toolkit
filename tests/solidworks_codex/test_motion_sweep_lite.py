import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.solidworks_codex.scripts import sw_motion_sweep_lite as motion

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_motion_sweep_lite.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class FakeDimension:
    def __init__(self):
        self.SystemValue = None


class FakeAssembly:
    def __init__(self):
        self.dimensions = {"crank_angle@Motion": FakeDimension(), "ram_travel@LimitMate": FakeDimension()}
        self.rebuilds = []

    def Parameter(self, name):
        return self.dimensions.get(name)

    def ForceRebuild3(self, top_only):
        self.rebuilds.append(bool(top_only))
        return True


class MotionSweepLiteTests(unittest.TestCase):
    def spec(self):
        return {
            "mechanism": "quick_return_fixture",
            "drivers": [
                {"id": "crank", "type": "dimension", "name": "crank_angle@Motion", "unit": "deg"},
                {"id": "ram", "type": "dimension", "name": "ram_travel@LimitMate", "unit": "mm"},
            ],
            "samples": [
                {"id": "home", "drivers": {"crank": 0, "ram": 0}, "interference": {"count": 0}},
                {"id": "mid", "drivers": {"crank": 90, "ram": 25}, "interference": {"count": 0}},
                {"id": "return", "drivers": {"crank": 180, "ram": 50}, "interference": {"count": 1, "pairs": [["ram-1", "column-1"]]}},
            ],
            "required_motion_pairs": [
                {"kind": "revolute", "components": ["bull_gear-1", "crank_pin-1"]},
                {"kind": "prismatic", "components": ["ram-1", "left_way-1"]},
            ],
        }

    def macro_manifest(self):
        return {
            "macros": [
                {"mate_type": "concentric", "expected_mate_name": "Bull_Gear_Crank_Revolute", "components": ["bull_gear-1", "crank_pin-1"]},
                {"mate_type": "limit_distance", "expected_mate_name": "Ram_Way_Limit", "components": ["ram-1", "left_way-1"], "distance_min_m": 0, "distance_max_m": 0.05},
            ]
        }

    def test_live_sweep_applies_sample_driver_positions_and_blocks_collisions(self):
        assembly = FakeAssembly()
        result = motion.execute_sweep(self.spec(), assembly=assembly, macro_manifest=self.macro_manifest())

        self.assertFalse(result["ok"])
        self.assertEqual(result["counts"]["sampled_positions"], 3)
        self.assertEqual(assembly.dimensions["crank_angle@Motion"].SystemValue, motion.deg_to_rad(180))
        self.assertEqual(assembly.dimensions["ram_travel@LimitMate"].SystemValue, 0.05)
        self.assertEqual(len(assembly.rebuilds), 3)
        kinds = {item["kind"] for item in result["findings"]["blocking"]}
        self.assertIn("sample_interference", kinds)
        self.assertIn("motion_pair_evidence_present", {item["kind"] for item in result["findings"]["accepted"]})

    def test_dry_run_blocks_missing_revolute_and_prismatic_evidence(self):
        spec = self.spec()
        result = motion.dry_run_sweep(spec, macro_manifest={"macros": []})

        self.assertFalse(result["ok"])
        kinds = {item["kind"] for item in result["findings"]["blocking"]}
        self.assertIn("required_motion_pair_missing", kinds)
        self.assertEqual(result["counts"]["required_motion_pairs"], 2)

    def test_cli_writes_report_and_routes_validate_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec = root / "motion.json"
            manifest = root / "manifest.json"
            out = root / "motion_report.json"
            spec.write_text(json.dumps(self.spec()), encoding="utf-8")
            manifest.write_text(json.dumps(self.macro_manifest()), encoding="utf-8")

            proc = run_py("--spec", str(spec), "--macro-manifest", str(manifest), "--dry-run", "--out", str(out))

            self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"])
            self.assertEqual(data["mode"], "motion_sweep_lite")

    def test_swctl_routes_motion_sweep_lite_validate_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec = root / "motion.json"
            manifest = root / "manifest.json"
            out = root / "motion_report.json"
            spec.write_text(json.dumps(self.spec()), encoding="utf-8")
            manifest.write_text(json.dumps(self.macro_manifest()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "motion-sweep-lite",
                    "-Report", str(spec),
                    "-Manifest", str(manifest),
                    "-ValidateOnly",
                    "-Out", str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
            self.assertEqual("motion_sweep_lite", json.loads(out.read_text(encoding="utf-8-sig"))["mode"])


if __name__ == "__main__":
    unittest.main()
