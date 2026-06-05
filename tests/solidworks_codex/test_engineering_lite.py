import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_engineering_lite.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class EngineeringLiteTests(unittest.TestCase):
    def inspect_report(self):
        return {
            "active_document": {
                "title": "fixture.SLDASM",
                "type": "assembly",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/cad/base_plate.SLDPRT", "configuration": "Default", "material": "6061 Aluminum", "fixed": True},
                    {"name2": "bolt_m6-1", "path": "C:/cad/bolt_m6.SLDPRT", "configuration": "M6x20", "fixed": False},
                    {"name2": "bolt_m6-2", "path": "C:/cad/bolt_m6.SLDPRT", "configuration": "M6x20", "fixed": False},
                    {"name2": "floating_cover-1", "path": "C:/cad/floating_cover.SLDPRT", "configuration": "Default", "fixed": False},
                ],
                "mate_like_features": [
                    {"name": "Base_Bolt_1", "components": ["base_plate-1", "bolt_m6-1"], "suppressed": False, "mate_error": 1},
                ],
                "features": [
                    {"name": "Mounting_Hole_Close_To_Edge", "type": "Cut", "semantic": "through_hole", "diameter_m": 0.006, "edge_distance_m": 0.004},
                    {"name": "Pocket_Deep", "type": "Cut", "semantic": "pocket", "depth_m": 0.025, "width_m": 0.010},
                ],
            }
        }

    def test_engineering_report_builds_bom_and_blocks_material_and_attachment_gaps(self):
        result = subprocess.run(
            [sys.executable, "-c", "from tools.solidworks_codex.scripts import sw_engineering_lite as e; import json, sys; print(json.dumps(e.analyze(json.loads(sys.stdin.read())), ensure_ascii=False))"],
            input=json.dumps(self.inspect_report()),
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data["ok"])
        bom = {(row["part_key"], row["configuration"]): row for row in data["bom"]["rows"]}
        self.assertEqual(bom[("C:/cad/bolt_m6.SLDPRT", "M6x20")]["quantity"], 2)
        blocking = {item["kind"] for item in data["findings"]["blocking"]}
        warnings = {item["kind"] for item in data["findings"]["warning"]}
        self.assertIn("missing_material", blocking)
        self.assertIn("hostless_standard_part", blocking)
        self.assertIn("hole_edge_clearance_low", warnings)
        self.assertIn("deep_narrow_pocket", warnings)

    def test_cli_writes_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            out = root / "engineering.md"
            json_out = root / "engineering.json"
            report.write_text(json.dumps(self.inspect_report()), encoding="utf-8")

            proc = run_py("--report", str(report), "--out", str(out), "--json-out", str(json_out))

            self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
            self.assertIn("Engineering Lite Review", out.read_text(encoding="utf-8-sig"))
            self.assertEqual(json.loads(json_out.read_text(encoding="utf-8-sig"))["mode"], "engineering_lite")

    def test_swctl_routes_engineering_lite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            out = root / "engineering.md"
            json_out = root / "engineering.json"
            report.write_text(json.dumps(self.inspect_report()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "engineering-lite",
                    "-Report", str(report),
                    "-Out", str(out),
                    "-JsonOut", str(json_out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
            self.assertTrue(json_out.exists())


if __name__ == "__main__":
    unittest.main()
