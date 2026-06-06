import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CurrentDocumentationTests(unittest.TestCase):
    def test_docs_describe_current_toolchain_and_safety_model(self):
        docs = "\n".join(
            (ROOT / rel).read_text(encoding="utf-8-sig")
            for rel in [
                "README.md",
                "docs/mcp-tools.md",
                "docs/solidworks-automation-plan.md",
                "docs/solidworks-codex-capability-gap-checklist.md",
            ]
        )
        for needle in [
            "SolidWorks Codex MCP",
            "56 tools",
            "MCP Tool Manual",
            "Capability scope",
            "Limits and notes",
            "Required parameters",
            "Optional parameters",
            "workflow-plan",
            "runtime budget",
            "backup",
            "rebuild",
            "compare",
            "change-verify",
            "assembly diagnosis",
            "interface indexing",
            "mate group",
            "visual evidence",
            "present/guarded",
            ".SLDASM/.SLDPRT",
        ]:
            self.assertIn(needle, docs)
        for stale_claim in [
            "58 components",
            "19 MateLock layout stabilizers",
            "verified MateLock layout-stabilizer network",
            "stable fixture-level assembly with MateLock",
            "prove display-grade native bullhead shaper",
            "high-fidelity SolidWorks bullhead shaper",
        ]:
            self.assertNotIn(stale_claim, docs)

    def test_docs_use_github_readable_tool_lists(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        manual = (ROOT / "docs/mcp-tools.md").read_text(encoding="utf-8-sig")
        self.assertIn("| Path | Purpose |", readme)
        self.assertIn("| Tool | Purpose |", manual)
        self.assertIn("`solidworks_probe`", manual)
        self.assertNotIn("probestart-probeinspectstart-inspect", readme + manual)


if __name__ == "__main__":
    unittest.main()
