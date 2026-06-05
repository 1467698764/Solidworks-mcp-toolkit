import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tools.solidworks_codex.scripts import sw_tool_catalog

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


class ToolCatalogTests(unittest.TestCase):
    def test_catalog_extracts_mcp_tools_and_groups_workflows(self):
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "catalog.md"
            out_json = Path(d) / "catalog.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_tool_catalog.py",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            names = {tool["name"] for tool in data["tools"]}
            by_name = {tool["name"]: tool for tool in data["tools"]}
            self.assertIn("SolidWorks MCP Tool Catalog", text)
            self.assertIn("solidworks_handoff_bundle", names)
            self.assertIn("solidworks_worklog", names)
            self.assertIn("solidworks_report_context", names)
            self.assertIn("solidworks_model_understand", names)
            self.assertIn("solidworks_assembly_diagnose", names)
            self.assertIn("solidworks_assembly_repair_plan", names)
            self.assertIn("solidworks_interface_index", names)
            self.assertIn("solidworks_mate_group_plan", names)
            self.assertIn("solidworks_assembly_review_pipeline", names)
            self.assertIn("solidworks_mate_group_macro", names)
            self.assertIn("solidworks_mate_group_execute", names)
            self.assertIn("solidworks_feature_state", names)
            self.assertIn("solidworks_mate_group_validate", names)
            self.assertIn("solidworks_mate_selection_check", names)
            self.assertIn("solidworks_mate_group_execution_check", names)
            self.assertIn("solidworks_mate_group_live_protocol", names)
            self.assertIn("solidworks_motion_sweep_lite", names)
            self.assertIn("mate", by_name["solidworks_mate_macro"]["properties"])
            schemas = {tool["name"]: tool for tool in sw_tool_catalog.list_tools_via_node()}
            mate_schema = schemas["solidworks_mate_macro"]["inputSchema"]["properties"]
            mate_enum = mate_schema["mate"]["enum"]
            self.assertIn("tangent", mate_enum)
            self.assertIn("limit_distance", mate_enum)
            self.assertIn("limit_angle", mate_enum)
            self.assertIn("distance_min_mm", mate_schema)
            self.assertIn("angle_max_deg", mate_schema)
            self.assertIn("read_only", data["groups"])
            self.assertIn("handoff", data["groups"])
            self.assertGreaterEqual(data["count"], 51)
            self.assertTrue(any("Do not blindly replay templates" in item for item in data["operator_notes"]))


    def test_capability_matrix_maps_cli_mcp_safety_and_workflows(self):
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "capability_matrix.md"
            out_json = Path(d) / "capability_matrix.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_capability_matrix.py",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            by_cli = {item["cli"]: item for item in data["capabilities"]}
            self.assertIn("SolidWorks Codex Capability Matrix", text)
            self.assertEqual(data["count"], len(data["capabilities"]))
            self.assertGreaterEqual(data["count"], 31)
            self.assertEqual(by_cli["live-gate"]["workflow"], "release_gate")
            self.assertEqual(by_cli["live-gate"]["safety"], "offline_gate")
            self.assertTrue(by_cli["live-gate"]["solidworks_required"])
            self.assertEqual(by_cli["backup"]["safety"], "guarded_write")
            self.assertEqual(by_cli["backup-status"]["mcp"], "solidworks_backup_status")

            self.assertFalse(by_cli["backup"]["solidworks_required"])
            self.assertFalse(by_cli["backup-status"]["solidworks_required"])
            self.assertFalse(by_cli["restore-backup"]["solidworks_required"])
            self.assertFalse(by_cli["change-verify"]["solidworks_required"])
            self.assertEqual(by_cli["restore-backup"]["safety"], "guarded_write")
            self.assertEqual(by_cli["restore-backup"]["mcp"], "solidworks_restore_backup")
            self.assertEqual(by_cli["set-dimension"]["safety"], "guarded_write")
            self.assertEqual(by_cli["safe-set-dimension"]["mcp"], "solidworks_safe_set_dimension")
            self.assertEqual(by_cli["safe-set-dimension"]["safety"], "guarded_write")
            self.assertEqual(by_cli["inspect"]["safety"], "read_only")
            self.assertEqual(by_cli["change-verify"]["mcp"], "solidworks_change_verify")
            self.assertEqual(by_cli["assembly-contract"]["workflow"], "verify_export")
            self.assertEqual(by_cli["assembly-contract"]["safety"], "verification_or_export")
            self.assertFalse(by_cli["assembly-contract"]["solidworks_required"])
            self.assertEqual(by_cli["assembly-diagnose"]["workflow"], "analysis")
            self.assertEqual(by_cli["assembly-diagnose"]["safety"], "read_only")
            self.assertEqual(by_cli["assembly-diagnose"]["mcp"], "solidworks_assembly_diagnose")
            self.assertFalse(by_cli["assembly-diagnose"]["solidworks_required"])
            self.assertEqual(by_cli["assembly-repair-plan"]["workflow"], "analysis")
            self.assertEqual(by_cli["assembly-repair-plan"]["safety"], "read_only")
            self.assertEqual(by_cli["assembly-repair-plan"]["mcp"], "solidworks_assembly_repair_plan")
            self.assertFalse(by_cli["assembly-repair-plan"]["solidworks_required"])
            self.assertEqual(by_cli["interface-index"]["workflow"], "analysis")
            self.assertEqual(by_cli["interface-index"]["safety"], "read_only")
            self.assertEqual(by_cli["interface-index"]["mcp"], "solidworks_interface_index")
            self.assertFalse(by_cli["interface-index"]["solidworks_required"])
            self.assertEqual(by_cli["mate-group-plan"]["workflow"], "analysis")
            self.assertEqual(by_cli["mate-group-plan"]["safety"], "read_only")
            self.assertEqual(by_cli["mate-group-plan"]["mcp"], "solidworks_mate_group_plan")
            self.assertFalse(by_cli["mate-group-plan"]["solidworks_required"])
            self.assertEqual(by_cli["assembly-review-pipeline"]["workflow"], "analysis")
            self.assertEqual(by_cli["assembly-review-pipeline"]["safety"], "read_only")
            self.assertEqual(by_cli["assembly-review-pipeline"]["mcp"], "solidworks_assembly_review_pipeline")
            self.assertFalse(by_cli["assembly-review-pipeline"]["solidworks_required"])
            self.assertEqual(by_cli["mate-group-macro"]["workflow"], "macro_generation")
            self.assertEqual(by_cli["mate-group-macro"]["safety"], "generated_reviewable_artifact")
            self.assertEqual(by_cli["mate-group-macro"]["mcp"], "solidworks_mate_group_macro")
            self.assertFalse(by_cli["mate-group-macro"]["solidworks_required"])
            self.assertEqual(by_cli["mate-group-execute"]["workflow"], "guarded_edit")
            self.assertEqual(by_cli["mate-group-execute"]["safety"], "guarded_write")
            self.assertEqual(by_cli["mate-group-execute"]["mcp"], "solidworks_mate_group_execute")
            self.assertTrue(by_cli["mate-group-execute"]["solidworks_required"])
            self.assertEqual(by_cli["feature-state"]["workflow"], "guarded_edit")
            self.assertEqual(by_cli["feature-state"]["safety"], "guarded_write")
            self.assertEqual(by_cli["feature-state"]["mcp"], "solidworks_feature_state")
            self.assertTrue(by_cli["feature-state"]["solidworks_required"])
            self.assertEqual(by_cli["start-feature-state"]["workflow"], "guarded_edit")
            self.assertEqual(by_cli["start-feature-state"]["safety"], "guarded_write")
            self.assertTrue(by_cli["start-feature-state"]["solidworks_required"])
            self.assertEqual(by_cli["mate-group-validate"]["workflow"], "analysis")
            self.assertEqual(by_cli["mate-group-validate"]["safety"], "read_only")
            self.assertEqual(by_cli["mate-group-validate"]["mcp"], "solidworks_mate_group_validate")
            self.assertFalse(by_cli["mate-group-validate"]["solidworks_required"])
            self.assertEqual(by_cli["mate-selection-check"]["workflow"], "analysis")
            self.assertEqual(by_cli["mate-selection-check"]["safety"], "read_only")
            self.assertEqual(by_cli["mate-selection-check"]["mcp"], "solidworks_mate_selection_check")
            self.assertFalse(by_cli["mate-selection-check"]["solidworks_required"])
            self.assertEqual(by_cli["mate-group-execution-check"]["workflow"], "verify_export")
            self.assertEqual(by_cli["mate-group-execution-check"]["safety"], "verification_or_export")
            self.assertEqual(by_cli["mate-group-execution-check"]["mcp"], "solidworks_mate_group_execution_check")
            self.assertFalse(by_cli["mate-group-execution-check"]["solidworks_required"])
            self.assertEqual(by_cli["motion-sweep-lite"]["workflow"], "guarded_edit")
            self.assertEqual(by_cli["motion-sweep-lite"]["safety"], "guarded_write")
            self.assertEqual(by_cli["motion-sweep-lite"]["mcp"], "solidworks_motion_sweep_lite")
            self.assertTrue(by_cli["motion-sweep-lite"]["solidworks_required"])
            self.assertEqual(by_cli["mate-group-live-protocol"]["workflow"], "analysis")
            self.assertEqual(by_cli["mate-group-live-protocol"]["safety"], "read_only")
            self.assertEqual(by_cli["mate-group-live-protocol"]["mcp"], "solidworks_mate_group_live_protocol")
            self.assertFalse(by_cli["mate-group-live-protocol"]["solidworks_required"])
            self.assertEqual(by_cli["handoff-bundle"]["workflow"], "handoff")
            self.assertEqual(by_cli["report-context"]["mcp"], "solidworks_report_context")
            self.assertEqual(by_cli["model-understand"]["mcp"], "solidworks_model_understand")
            self.assertEqual(by_cli["model-understand"]["safety"], "read_only")
            self.assertEqual(by_cli["workflow-plan"]["workflow"], "analysis")
            self.assertEqual(by_cli["workflow-plan"]["safety"], "read_only")
            self.assertFalse(by_cli["workflow-plan"]["solidworks_required"])
            self.assertEqual(by_cli["workflow-plan"]["required"], ["Target"])
            self.assertEqual(by_cli["offline-demo"]["solidworks_required"], False)
            self.assertTrue(data["coverage"]["has_cli_for_every_local_mcp"])
            self.assertTrue(data["coverage"]["has_safety_for_every_capability"])
            self.assertTrue(data["coverage"]["has_workflow_for_every_capability"])


    def test_swctl_default_reports_are_workspace_relative_without_rewriting_user_relative_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            external = Path(d) / "external.SLDPRT"
            external.write_text("dummy", encoding="utf-8")
            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "backup",
                    "-Files",
                    ".\\external.SLDPRT",
                ],
                cwd=d,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        data = json.loads(proc.stdout)
        self.assertEqual(str(external.resolve()), data["files"][0]["source"])
        report = ROOT / "tools/solidworks_codex/reports/backup.json"
        self.assertTrue(report.exists())

    def test_operator_notes_are_readable_public_copy(self):
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "catalog.md"
            out_json = Path(d) / "catalog.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_tool_catalog.py",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            joined = "\n".join(data["operator_notes"]) + "\n" + text
            for bad in ["?", "?", "?", "?", "?", "?"]:
                self.assertNotIn(bad, joined)
            self.assertTrue(any("Do not blindly replay templates" in item for item in data["operator_notes"]))


if __name__ == "__main__":
    unittest.main()

