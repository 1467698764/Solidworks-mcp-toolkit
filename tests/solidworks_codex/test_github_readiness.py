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


class GithubReadinessTests(unittest.TestCase):
    def test_github_readiness_gate_requires_public_release_assets(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "github_readiness.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_github_readiness.py",
                "--out", str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            required = data["checks"]
            for key in [
                "root_readme",
                "license",
                "install_script",
                "mcp_config_example",
                "ci_workflow",
                "mcp_manual",
                "capability_checklist",
                "automation_plan",
                "tool_catalog_mention",
                "audit_gate",
            ]:
                self.assertTrue(required[key]["ok"], key)
            readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
            self.assertIn("56 tools", readme)
            self.assertNotIn("30 conservative MCP tools", readme)
            self.assertNotIn("29", readme)
            self.assertNotIn("35 conservative MCP tools", readme)
            self.assertNotIn("45 conservative MCP tools", readme)
            self.assertIn("SolidWorks Codex MCP", readme)
            self.assertIn("model-understand", readme)
            self.assertIn("report-context", readme)
            self.assertIn("handoff-bundle", readme)
            self.assertIn("docs/mcp-tools.md", readme)
            license_text = (ROOT / "LICENSE").read_text(encoding="utf-8-sig")
            self.assertIn("Non-Commercial License", license_text)
            self.assertIn("non-commercial use only", license_text)
            self.assertIn("sell, rent, sublicense", license_text)
            self.assertNotIn("MIT License", license_text)
            manual = (ROOT / "docs/mcp-tools.md").read_text(encoding="utf-8-sig")
            self.assertIn("56 MCP tools", manual)
            self.assertIn("solidworks_part_feature_execute", manual)
            self.assertIn("Required parameters", manual)
            self.assertNotRegex(manual, r"29 .{1,3} MCP tools")


if __name__ == "__main__":
    unittest.main()
