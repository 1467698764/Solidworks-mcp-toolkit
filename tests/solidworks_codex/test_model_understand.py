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


class ModelUnderstandTests(unittest.TestCase):
    def test_model_understand_builds_task_scoped_context_without_dumping_everything(self):
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "understanding.md"
            out_json = Path(d) / "understanding.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", "tools/solidworks_codex/sandbox/report_after.json",
                "--task", "判断轴承、编码器、电机安装和输出法兰厚度是否合理",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertIn("SolidWorks Model Understanding", text)
            self.assertIn("Task-scoped view", text)
            self.assertEqual(data["document"]["title"], "sample_machine.SLDASM")
            domains = {item["domain"] for item in data["task_model"]["domains"]}
            self.assertIn("rotating_support", domains)
            self.assertIn("drive_or_actuator_interface", domains)
            self.assertIn("sensor_or_reference_alignment", domains)
            self.assertIn("plate_shell_interface", domains)
            names = {item["name"] for item in data["task_model"]["relevant_objects"]}
            self.assertIn("support_bushing-1", names)
            self.assertIn("reference_sensor-1", names)
            self.assertIn("drive_unit-1", names)
            self.assertLessEqual(len(data["task_model"]["relevant_objects"]), 12)
            self.assertTrue(any(item["kind"] == "unknown" for item in data["unknowns_and_risks"]))
            self.assertTrue(any(cmd["tool"] == "report-search" for cmd in data["next_queries"]))
            self.assertNotIn("Do not blindly replay templates", text)

    def test_model_understand_keeps_broad_task_compact_and_marks_inferences(self):
        with tempfile.TemporaryDirectory() as d:
            out_json = Path(d) / "understanding.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", "tools/solidworks_codex/sandbox/report_after.json",
                "--task", "理解这个装配体现在的建模状态",
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["scope"]["mode"], "broad")
            self.assertLessEqual(len(data["baseline"]["anchors"]), 15)
            self.assertTrue(data["relationship_hypotheses"])
            self.assertTrue(all("confidence" in item for item in data["relationship_hypotheses"]))
            self.assertIn("component_count", data["baseline"]["inventory"])


if __name__ == "__main__":
    unittest.main()
