import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CurrentDocumentationTests(unittest.TestCase):
    def test_docs_describe_intent_scoped_validation_and_live_shaper_status(self):
        docs = "\n".join(
            (ROOT / rel).read_text(encoding="utf-8-sig")
            for rel in [
                "docs/solidworks-codex-usage.md",
                "docs/architecture.md",
                "docs/troubleshooting.md",
                "docs/solidworks-codex-final-readiness.md",
                "tools/solidworks_codex/README.md",
            ]
        )
        for needle in [
            "validation profiles",
            "draft_part",
            "single_part",
            "assembly",
            "mechanism_assembly",
            "engineering_release",
            "runtime_budget",
            "extra_checks",
            "24 parts",
            "58 components",
            "19 MateLock layout stabilizers",
            "structural-reference fixed evidence only",
            "attached detail-instance layout",
            "0 interference",
            "Transform2.ArrayData",
            "verified MateLock layout-stabilizer network",
            "assembly_component_placements",
            "part_geometry_readback",
            "mate_error: 1",
            "allow_fixed_fixed",
            "blocking",
            "warning",
            "not_applicable",
            ".SLDASM/.SLDPRT",
            "STEP optional smoke",
            "CleanupStale",
            "shaper_machine_v5",
        ]:
            self.assertIn(needle, docs)

    def test_docs_do_not_present_bullhead_shaper_as_project_boundary(self):
        usage = (ROOT / "docs/solidworks-codex-usage.md").read_text(encoding="utf-8-sig")
        self.assertIn("bullhead shaper is a stress test", usage)
        self.assertIn("not the project boundary", usage)
        self.assertIn("general SolidWorks MCP", usage)


if __name__ == "__main__":
    unittest.main()
