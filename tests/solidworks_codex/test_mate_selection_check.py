import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_mate_selection_check.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class MateSelectionCheckTests(unittest.TestCase):
    def manifest(self):
        return {
            "macros": [
                {
                    "group_id": "crank_shaft",
                    "mate_type": "concentric",
                    "expected_mate_name": "MG_crank_shaft_01_concentric",
                    "components": ["crank_disk-1", "crank_shaft-1"],
                }
            ]
        }

    def selection_report(self):
        return {
            "document_title": "shaper.SLDASM",
            "selection_count": 2,
            "selections": [
                {"index": 1, "type": "FACES", "component": {"Name2": "crank_disk-1"}},
                {"index": 2, "type": "DATUMAXES", "component": {"Name2": "crank_shaft-1"}},
            ],
        }

    def test_accepts_two_supported_selections_on_expected_components(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            selection = root / "selection.json"
            out = root / "check.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")
            selection.write_text(json.dumps(self.selection_report()), encoding="utf-8")

            proc = run_py("--macro-manifest", str(manifest), "--selection-report", str(selection), "--expected-mate-name", "MG_crank_shaft_01_concentric", "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["macro"]["expected_mate_name"], "MG_crank_shaft_01_concentric")
            self.assertEqual(data["counts"]["accepted_selections"], 2)

    def test_accepts_path_vertex_and_edge_selections(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "path"
        manifest["macros"][0]["expected_mate_name"] = "MG_follower_guide_01_path"
        manifest["macros"][0]["components"] = ["follower-1", "guide-1"]
        selection = {
            "document_title": "shaper.SLDASM",
            "selection_count": 2,
            "selections": [
                {"index": 1, "type": "VERTICES", "component": {"Name2": "follower-1"}},
                {"index": 2, "type": "EDGES", "component": {"Name2": "guide-1"}},
            ],
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest_path = root / "manifest.json"
            selection_path = root / "selection.json"
            out = root / "check.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            selection_path.write_text(json.dumps(selection), encoding="utf-8")

            proc = run_py("--macro-manifest", str(manifest_path), "--selection-report", str(selection_path), "--expected-mate-name", "MG_follower_guide_01_path", "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["counts"]["accepted_selections"], 2)

    def test_blocks_wrong_count_wrong_component_and_component_level_selection(self):
        selection = self.selection_report()
        selection["selection_count"] = 3
        selection["selections"][0]["type"] = "COMPONENTS"
        selection["selections"][1]["component"]["Name2"] = "wrong_part-1"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            selection_path = root / "selection.json"
            out = root / "check.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")
            selection_path.write_text(json.dumps(selection), encoding="utf-8")

            proc = run_py("--macro-manifest", str(manifest), "--selection-report", str(selection_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"], data)
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("selection_count", kinds)
            self.assertIn("unsupported_selection_type", kinds)
            self.assertIn("selection_component_mismatch", kinds)

    def test_swctl_routes_mate_selection_check(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            selection = root / "selection.json"
            out = root / "check.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")
            selection.write_text(json.dumps(self.selection_report()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-selection-check",
                    "-Report", str(manifest),
                    "-FromReport", str(selection),
                    "-Mate", "MG_crank_shaft_01_concentric",
                    "-Out", str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(json.loads(out.read_text(encoding="utf-8-sig"))["ok"])


if __name__ == "__main__":
    unittest.main()
