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
                "release_checklist",
                "security",
                "contributing",
                "offline_demo",
                "usage_docs",
                "tool_catalog_mention",
                "audit_gate",
            ]:
                self.assertTrue(required[key]["ok"], key)
            readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
            self.assertIn("45", readme)
            self.assertNotIn("30 conservative MCP tools", readme)
            self.assertNotIn("29", readme)
            self.assertIn("practical SolidWorks MCP", readme)
            self.assertIn("model-understand", readme)
            self.assertIn("report-context", readme)
            self.assertIn("handoff-bundle", readme)
            self.assertIn("tool-catalog", readme)
            license_text = (ROOT / "LICENSE").read_text(encoding="utf-8-sig")
            self.assertIn("Non-Commercial License", license_text)
            self.assertIn("non-commercial use only", license_text)
            self.assertIn("sell, rent, sublicense", license_text)
            self.assertNotIn("MIT License", license_text)
            usage = (ROOT / "docs/solidworks-codex-usage.md").read_text(encoding="utf-8-sig")
            self.assertIn("48 MCP tools", usage)
            self.assertNotRegex(usage, r"29 .{1,3} MCP tools")
            self.assertNotIn("35 MCP tools", usage)
            self.assertNotIn("36 MCP tools", usage)
            self.assertNotIn("37 MCP tools", usage)
            self.assertNotIn("38 MCP tools", usage)
            self.assertNotIn("39 MCP tools", usage)
            self.assertNotIn("40 MCP tools", usage)
            self.assertNotIn("41 MCP tools", usage)
            self.assertNotIn("42 MCP tools", usage)


if __name__ == "__main__":
    unittest.main()
