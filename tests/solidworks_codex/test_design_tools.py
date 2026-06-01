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
    )


class DesignToolTests(unittest.TestCase):
    def test_design_review_fixture_generates_evidence_first_recommendations(self):
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "design_review.md"
            out_json = Path(d) / "design_review.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_design_review.py",
                "--report", "tools/solidworks_codex/sandbox/report_after.json",
                "--out", str(out_md),
                "--json-out", str(out_json),
                "--intent", "bearing stack and encoder alignment",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertIn("Mechanical CAD Evidence Review", text)
            self.assertIn("support_bushing-1", text)
            self.assertIn("reference_sensor-1", text)
            self.assertIn("Open questions", text)
            self.assertIn("candidate_actions", data)
            self.assertTrue(any(item["category"] == "rotating_support" for item in data["findings"]))
            self.assertTrue(any(item["category"] == "sensor_or_reference_alignment" for item in data["findings"]))

    def test_change_plan_fixture_outputs_ordered_safe_workflow(self):
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "change_plan.md"
            out_json = Path(d) / "change_plan.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_change_plan.py",
                "--report", "tools/solidworks_codex/sandbox/report_after.json",
                "--goal", "把输出法兰加厚到12mm并检查轴承/编码器干涉",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertIn("Mechanical CAD Change Plan", text)
            self.assertIn("backup", text.lower())
            self.assertIn("session-snapshot", text)
            self.assertIn("D1@Sketch1@plate.SLDPRT", text)
            self.assertTrue(data["goal"].startswith("把输出法兰"))
            self.assertGreaterEqual(len(data["steps"]), 5)
            self.assertTrue(data["requires_backup"])
            self.assertIn("decision_points", data)
            self.assertIn("optional_branches", data)


if __name__ == "__main__":
    unittest.main()
