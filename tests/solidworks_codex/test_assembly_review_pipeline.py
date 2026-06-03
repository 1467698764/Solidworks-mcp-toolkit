import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_assembly_review_pipeline.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class AssemblyReviewPipelineTests(unittest.TestCase):
    def sample_report(self):
        return {
            "active_document": {
                "type": "assembly",
                "title": "pipeline_fixture.SLDASM",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/m/base_plate.SLDPRT", "fixed": True, "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                    {"name2": "cover_plate-1", "path": "C:/m/cover_plate.SLDPRT", "fixed": False, "bbox_m": [0.0, 0.0, 0.012, 0.20, 0.10, 0.024]},
                    {"name2": "bolt_m6-1", "path": "C:/m/bolt_m6.SLDPRT", "fixed": False, "bbox_m": [0.05, 0.05, 0.024, 0.058, 0.058, 0.065]},
                ],
                "mate_like_features": [
                    {"name": "Base_Cover_Coincident", "type": "MateCoincident", "components": ["base_plate-1", "cover_plate-1"], "suppressed": False},
                    {"name": "Broken_Bolt_Mate", "type": "MateConcentric", "components": ["bolt_m6-1", "cover_plate-1"], "suppressed": True, "status": "unsolved", "mate_error": 4},
                ],
            }
        }

    def test_pipeline_writes_all_review_artifacts_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            out_dir = root / "review"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")

            proc = run_py("--report", str(report), "--out-dir", str(out_dir), "--standard-part-regex", "bolt|washer|nut|screw")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(manifest["mode"], "read_only_assembly_review_pipeline")
            self.assertEqual(manifest["document"]["title"], "pipeline_fixture.SLDASM")
            for key in ["diagnosis", "interface_index", "repair_plan", "mate_group_plan", "mate_group_plan_md", "mate_group_validation"]:
                self.assertTrue((out_dir / manifest["artifacts"][key]).exists(), key)
            mate_groups = json.loads((out_dir / manifest["artifacts"]["mate_group_plan"]).read_text(encoding="utf-8-sig"))
            validation = json.loads((out_dir / manifest["artifacts"]["mate_group_validation"]).read_text(encoding="utf-8-sig"))
            self.assertTrue(any(item["group_id"] == "standard_bolt_m6-1" for item in mate_groups["mate_groups"]))
            self.assertEqual(manifest["counts"]["mate_groups"], len(mate_groups["mate_groups"]))
            self.assertEqual(manifest["validation"]["mate_group_plan_ok"], validation["ok"])

    def test_swctl_routes_assembly_review_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            out_dir = root / "review"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "assembly-review-pipeline",
                    "-Report", str(report),
                    "-OutDir", str(out_dir),
                    "-Target", "bolt|washer|nut|screw",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue((out_dir / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
