import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CurrentDocumentationTests(unittest.TestCase):
    def test_docs_describe_intent_scoped_validation_and_honest_fixture_status(self):
        docs = "\n".join(
            (ROOT / rel).read_text(encoding="utf-8-sig")
            for rel in [
                "docs/solidworks-codex-usage.md",
                "docs/architecture.md",
                "docs/troubleshooting.md",
                "docs/solidworks-codex-final-readiness.md",
                "tools/solidworks_codex/README.md",
                "docs/solidworks-codex-capability-gap-checklist.md",
            ]
        )
        for needle in [
            "validation profiles",
            "workflow-plan",
            "draft_part",
            "single_part",
            "assembly",
            "mechanism_assembly",
            "engineering_release",
            "runtime_budget",
            "extra_checks",
            "simple-mechanism regression",
            "not a showcase",
            "not proof",
            "assembly diagnosis",
            "interface indexing",
            "local repair",
            "mate groups",
            "visual validation",
            "native file readback",
            "semantic mate participation",
            "0 interference",
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
        for stale_claim in [
            "58 components",
            "19 MateLock layout stabilizers",
            "verified MateLock layout-stabilizer network",
            "stable fixture-level assembly with MateLock",
            "prove display-grade native bullhead shaper",
            "high-fidelity SolidWorks bullhead shaper",
        ]:
            self.assertNotIn(stale_claim, docs)

    def test_docs_do_not_present_named_fixture_as_project_boundary(self):
        usage = (ROOT / "docs/solidworks-codex-usage.md").read_text(encoding="utf-8-sig")
        self.assertIn("not by a single named fixture", usage)
        self.assertIn("not impressive enough to define the project", usage)
        self.assertIn("general SolidWorks MCP", usage)


if __name__ == "__main__":
    unittest.main()
