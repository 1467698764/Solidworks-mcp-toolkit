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


class ModelUnderstandViewsTests(unittest.TestCase):
    def run_understand(self, view: str, task: str):
        d = tempfile.TemporaryDirectory()
        root = Path(d.name)
        out_json = root / f"{view}.json"
        out_md = root / f"{view}.md"
        proc = run_py(
            "tools/solidworks_codex/scripts/sw_model_understand.py",
            "--report", "tools/solidworks_codex/sandbox/report_after.json",
            "--task", task,
            "--view", view,
            "--out", str(out_md),
            "--json-out", str(out_json),
        )
        self.addCleanup(d.cleanup)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        return json.loads(out_json.read_text(encoding="utf-8-sig")), out_md.read_text(encoding="utf-8-sig")

    def test_dimension_edit_view_prioritizes_dimensions_and_guarded_edit_queries(self):
        data, text = self.run_understand("dimension-edit", "把输出法兰厚度尺寸改到12mm")
        self.assertEqual(data["scope"]["view"], "dimension-edit")
        self.assertEqual(data["view_model"]["primary_object_kind"], "dimension")
        kinds = [obj["kind"] for obj in data["task_model"]["relevant_objects"]]
        self.assertIn("dimension", kinds[:3])
        tools = [q["tool"] for q in data["next_queries"]]
        self.assertIn("safe-set-dimension", tools)
        self.assertIn("compare", tools)
        self.assertIn("View-specific context", text)

    def test_assembly_constraints_view_prioritizes_components_mates_and_selection(self):
        data, _text = self.run_understand("assembly-constraints", "理解电机 轴承 编码器 的装配约束和固定关系")
        self.assertEqual(data["scope"]["view"], "assembly-constraints")
        self.assertEqual(data["view_model"]["primary_object_kind"], "component")
        self.assertTrue(any("fixed" in item for item in data["view_model"]["focus_fields"]))
        names = [obj["name"] for obj in data["task_model"]["relevant_objects"]]
        self.assertIn("drive_unit-1", names)
        self.assertTrue(any(obj["kind"] == "feature" and "Mate" in obj.get("type", "") for obj in data["task_model"]["relevant_objects"]))
        self.assertIn("selection-report", [q["tool"] for q in data["next_queries"]])

    def test_auto_view_detects_interference_clearance_task(self):
        data, _text = self.run_understand("auto", "检查轴承和编码器附近有没有干涉或间隙风险")
        self.assertEqual(data["scope"]["view"], "interference-clearance")
        self.assertEqual(data["view_model"]["primary_object_kind"], "component")
        tools = [q["tool"] for q in data["next_queries"]]
        self.assertIn("interference", tools)
        self.assertIn("mass", tools)


if __name__ == "__main__":
    unittest.main()
