import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_part_geometry_validate.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class PartGeometryValidateTests(unittest.TestCase):
    def report(self):
        return {
            "active_document": {
                "title": "fixture_plate.SLDPRT",
                "type": "part",
                "body_count": 1,
                "bbox_m": [0, 0, 0, 0.12, 0.08, 0.01],
                "volume_m3": 0.000096,
                "features": [
                    {"name": "Base_Boss", "type": "Boss", "semantic": "boss"},
                    {"name": "Mounting_Holes", "type": "Cut", "semantic": "through_hole", "count": 4},
                ],
                "interfaces": [
                    {"stable_id": "fixture_plate:top_face", "type": "bbox_planar_face"},
                    {"stable_id": "fixture_plate:hole_axis", "type": "cylindrical_axis"},
                ],
            }
        }

    def contract(self):
        return {
            "minimum_body_count": 1,
            "minimum_volume_m3": 0.00005,
            "minimum_bbox_size_m": [0.10, 0.06, 0.008],
            "required_features": ["Base_Boss", "Mounting_Holes"],
            "required_semantics": {"through_hole": {"min_count": 4}},
            "minimum_interface_count": 2,
        }

    def test_accepts_feature_rich_part_geometry(self):
        from tools.solidworks_codex.scripts import sw_part_geometry_validate as mod

        data = mod.validate(self.report(), self.contract())

        self.assertTrue(data["ok"], data)
        self.assertGreaterEqual(data["summary"]["accepted"], 5)
        self.assertEqual(data["summary"]["failed"], 0)

    def test_blocks_plain_block_missing_semantics_and_interfaces(self):
        from tools.solidworks_codex.scripts import sw_part_geometry_validate as mod

        report = self.report()
        report["active_document"]["features"] = [{"name": "Boss-Extrude1", "type": "Boss"}]
        report["active_document"]["interfaces"] = []
        report["active_document"]["volume_m3"] = 0.00001

        data = mod.validate(report, self.contract())

        self.assertFalse(data["ok"])
        kinds = {item["kind"] for item in data["failed"]}
        self.assertIn("feature_missing", kinds)
        self.assertIn("semantic_count", kinds)
        self.assertIn("interface_count", kinds)
        self.assertIn("volume", kinds)

    def test_cli_and_swctl_route_part_geometry_validate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            contract = root / "geometry_contract.json"
            out = root / "geometry.json"
            report.write_text(json.dumps(self.report()), encoding="utf-8")
            contract.write_text(json.dumps(self.contract()), encoding="utf-8")

            proc = run_py("--report", str(report), "--contract", str(contract), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(json.loads(out.read_text(encoding="utf-8-sig"))["ok"])

            swctl_out = root / "geometry_swctl.json"
            swctl = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "part-geometry-validate",
                    "-Report", str(report),
                    "-Manifest", str(contract),
                    "-Out", str(swctl_out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(swctl.returncode, 0, swctl.stderr + swctl.stdout)
            self.assertTrue(json.loads(swctl_out.read_text(encoding="utf-8-sig"))["ok"])


if __name__ == "__main__":
    unittest.main()
