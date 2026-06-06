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


class RepoHealthTests(unittest.TestCase):
    def test_repo_health_checks_public_maintenance_assets(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "repo_health.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_repo_health.py",
                "--out", str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            for key in [
                "verify_script",
                "issue_template_bug",
                "issue_template_feature",
                "pull_request_template",
                "readme_quickstart",
                "readme_project_trackers",
                "release_tree_gate",
                "mcp_manual",
                "mcp_manual_tools",
                "automation_plan",
                "capability_checklist",
            ]:
                self.assertTrue(data["checks"][key]["ok"], key)


    def test_ci_workflow_runs_release_quality_gates(self):
        workflow = (ROOT / ".github/workflows/solidworks-codex-offline.yml").read_text(encoding="utf-8-sig")
        for needle in [
            "sw_repo_health.py",
            "sw_public_copy_guard.py",
            "sw_audit.py",
            "sw_release_tree.py",
            "sw_finalize.py",
            "ConvertFrom-Json",
        ]:
            self.assertIn(needle, workflow)


    def test_verify_all_checks_final_readiness_json_parse(self):
        script = (ROOT / "scripts/verify-all.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("release-tree", script)
        self.assertIn("finalize", script)
        self.assertIn("final_readiness", script)
        self.assertIn("ConvertFrom-Json", script)


if __name__ == "__main__":
    unittest.main()
