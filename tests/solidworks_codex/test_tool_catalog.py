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
            self.assertIn("SolidWorks MCP Tool Catalog", text)
            self.assertIn("solidworks_handoff_bundle", names)
            self.assertIn("solidworks_worklog", names)
            self.assertIn("solidworks_report_context", names)
            self.assertIn("solidworks_model_understand", names)
            self.assertIn("read_only", data["groups"])
            self.assertIn("handoff", data["groups"])
            self.assertGreaterEqual(data["count"], 28)
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

