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


class GenericDesignToolsTests(unittest.TestCase):
    def make_fixture_report(self, root: Path) -> Path:
        report = {
            "active_document": {
                "title": "gearbox_fixture.SLDASM",
                "path": "C:/machines/gearbox_fixture.SLDASM",
                "type": "assembly",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/machines/base_plate.SLDPRT", "suppressed": False, "hidden": False, "fixed": True, "bbox_m": [-0.12, -0.08, -0.01, 0.12, 0.08, 0.0]},
                    {"name2": "gearbox_housing-1", "path": "C:/machines/gearbox_housing.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.05, -0.04, 0.0, 0.05, 0.04, 0.06]},
                    {"name2": "cover_plate-1", "path": "C:/machines/cover_plate.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.052, -0.042, 0.058, 0.052, 0.042, 0.066]},
                    {"name2": "dowel_pin-1", "path": "C:/machines/dowel_pin.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.046, -0.036, -0.005, -0.041, -0.031, 0.064]},
                    {"name2": "bolt_m6-1", "path": "C:/machines/bolt_m6.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [0.04, 0.03, -0.006, 0.047, 0.037, 0.068]},
                ],
                "dimensions": [
                    {"full_name": "HoleDia@Sketch2@cover_plate.SLDPRT", "system_value_m": 0.0066, "feature": "Sketch2"}
                ],
                "features": [{"name": "HolePattern1", "type": "LPattern"}, {"name": "Cut-Extrude1", "type": "Cut"}]
            }
        }
        path = root / "fixture.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_design_review_outputs_generic_evidence_and_open_questions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_md = root / "review.md"
            out_json = root / "review.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_design_review.py",
                "--report", str(self.make_fixture_report(root)),
                "--intent", "评审齿轮箱夹具的定位销、螺栓孔、盖板装配和加工可行性",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertIn("Mechanical CAD Evidence Review", text)
            self.assertNotIn("Robot Joint", text)
            self.assertNotIn("修改队列", text)
            self.assertIn("open_questions", data)
            self.assertIn("candidate_actions", data)
            categories = {item["category"] for item in data["findings"]}
            self.assertIn("assembly_state", categories)
            self.assertIn("manufacturing_features", categories)
            self.assertTrue(any("dowel_pin-1" in e for f in data["findings"] for e in f.get("evidence", [])))

    def test_change_plan_is_flexible_generic_and_not_fixed_robot_workflow(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_md = root / "plan.md"
            out_json = root / "plan.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_change_plan.py",
                "--report", str(self.make_fixture_report(root)),
                "--goal", "调整盖板螺栓孔并检查定位销装配可行性",
                "--session-name", "fixture-hole-update",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertIn("Mechanical CAD Change Plan", text)
            self.assertNotIn("Robot Joint", text)
            self.assertIn("decision_points", data)
            self.assertIn("optional_branches", data)
            self.assertIn("candidate_actions", data)
            self.assertTrue(any(item["tool"] == "model-understand" for item in data["candidate_actions"]))
            self.assertTrue(any(item["tool"] == "backup" for item in data["candidate_actions"]))
            self.assertTrue(data["requires_backup"])
            self.assertLessEqual(len(data["steps"]), 8)

    def test_workflow_plan_supports_single_part_and_part_to_assembly_loops(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_md = root / "workflow.md"
            out_json = root / "workflow.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_workflow_plan.py",
                "--goal", "设计一个带沉头孔和加强筋的安装支架，先单独建模自检，再装到小型传动组件里检查配合和干涉",
                "--intent", "part_to_assembly",
                "--runtime-budget", "fast",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))

            self.assertIn("Mechanical CAD Workflow Plan", text)
            self.assertEqual("part_to_assembly", data["intent"])
            self.assertEqual("fast", data["runtime_budget"])
            self.assertIn("stage_graph", data)
            stage_names = [stage["name"] for stage in data["stage_graph"]]
            for expected in (
                "design_brief",
                "part_model",
                "part_self_check",
                "part_feedback_edit",
                "assembly_insert",
                "assembly_self_check",
                "handoff_or_iterate",
            ):
                self.assertIn(expected, stage_names)

            by_name = {stage["name"]: stage for stage in data["stage_graph"]}
            self.assertEqual("single_part", by_name["part_self_check"]["validation_profile"])
            self.assertEqual("assembly", by_name["assembly_self_check"]["validation_profile"])
            self.assertIn("part_geometry_readback", by_name["part_self_check"]["required_evidence"])
            self.assertIn("assembly_component_placements", by_name["assembly_self_check"]["required_evidence"])
            self.assertIn("static_interference", by_name["assembly_self_check"]["blocking_checks"])
            ledger = data["assumption_ledger"]
            self.assertEqual("assumption_ledger", ledger["artifact"])
            self.assertTrue(any(item["severity"] == "assumption" for item in ledger["items"]))
            self.assertTrue(any(item["severity"] == "warning" for item in ledger["items"]))
            self.assertTrue(any(item["severity"] == "blocker" for item in ledger["items"]))
            self.assertTrue(any(item["topic"] == "dimensions" for item in ledger["items"]))
            self.assertTrue(any(item["topic"] == "validation_scope" for item in ledger["items"]))
            self.assertIn("Assumption Ledger", text)
            self.assertIn("`blocker`", text)
            runtime = data["runtime_budget_plan"]
            self.assertEqual("runtime_budget_plan", runtime["artifact"])
            self.assertEqual("fast", runtime["budget"])
            self.assertGreaterEqual(runtime["expected_solidworks_sessions"], 1)
            self.assertIn("rebuild_scope", runtime)
            self.assertIn("memory_ceiling_mb", runtime)
            self.assertIn("timeout_seconds", runtime)
            self.assertIn("cleanup_policy", runtime)
            self.assertTrue(runtime["full_rebuild_requires_reason"])
            self.assertIn("Runtime Budget Plan", text)
            self.assertIn("memory ceiling", text)
            intent = data["design_intent"]
            self.assertEqual("design_intent", intent["artifact"])
            self.assertEqual(data["goal"], intent["goal"])
            self.assertEqual("part_to_assembly", intent["scope"])
            self.assertTrue(intent["parts"])
            self.assertTrue(intent["interfaces"])
            self.assertIn("validation_profile", intent)
            self.assertIn("editable_parameters", intent)
            self.assertIn("non_goals", intent)
            self.assertIn("Design Intent", text)
            self.assertIn("editable parameters", text)
            self.assertTrue(any(edge["from"] == "part_self_check" and edge["to"] == "part_feedback_edit" for edge in data["feedback_edges"]))
            self.assertTrue(any(edge["from"] == "assembly_self_check" and edge["to"] == "part_feedback_edit" for edge in data["feedback_edges"]))
            self.assertTrue(any(action["tool"] == "template-macro" for action in data["candidate_actions"]))
            self.assertTrue(any(action["tool"] == "assembly-contract" for action in data["candidate_actions"]))
            self.assertNotIn("bullhead", text.lower())

    def test_swctl_exposes_workflow_plan_as_generic_analysis_command(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_md = root / "workflow.md"
            out_json = root / "workflow.json"
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "workflow-plan",
                    "-Target",
                    "create a bearing bracket, check the part, then fit it into an assembly",
                    "-Action",
                    "part_to_assembly",
                    "-View",
                    "fast",
                    "-Out",
                    str(out_md),
                    "-JsonOut",
                    str(out_json),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertEqual("part_to_assembly", data["intent"])
            self.assertEqual("fast", data["runtime_budget"])
            self.assertIn("assembly_self_check", [stage["name"] for stage in data["stage_graph"]])


if __name__ == "__main__":
    unittest.main()
