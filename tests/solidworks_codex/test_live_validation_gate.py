import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_live_validation_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sw_live_validation_gate", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load live validation gate module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LiveValidationGateSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_gate_contract_requires_capability_suite_and_complete_shaper(self):
        contract = self.module.build_gate_contract()
        names = [check.name for check in contract.checks]
        self.assertEqual(names, ["live_capability_suite", "complete_shaper_v5"])
        self.assertIn("sw_live_capability_suite.py", contract.checks[0].command[1])
        self.assertIn("sw_create_complete_shaper_fixture.py", contract.checks[1].command[1])
        for check in contract.checks:
            self.assertIn("--force", check.command)
            self.assertTrue(check.report_json.endswith(".json"))

    def test_validate_gate_rejects_missing_or_failed_reports(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing.json"
            failed = root / "failed.json"
            failed.write_text(json.dumps({"ok": False, "validation": {"failed": ["mass_callback"]}}), encoding="utf-8")
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("missing_check", missing, ("ok",)),
                self.module.ReportExpectation("failed_check", failed, ("ok",)),
            ])
        self.assertFalse(result["ok"])
        self.assertIn("missing_report:missing_check", result["failed"])
        self.assertIn("report_not_ok:failed_check", result["failed"])


    def test_validate_gate_rejects_weak_shaper_evidence_even_when_report_says_ok(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            weak = root / "complete_shaper_build.json"
            weak.write_text(json.dumps({"ok": True, "validation": {"ok": True, "failed": []}}), encoding="utf-8")
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("complete_shaper_v5", weak, ("ok",), self.module.shaper_v5_strict_checks()),
            ])
        self.assertFalse(result["ok"])
        self.assertIn("strict:complete_shaper_v5:part_count", result["failed"])
        self.assertIn("strict:complete_shaper_v5:component_count", result["failed"])
        self.assertIn("strict:complete_shaper_v5:interference_clearance", result["failed"])
        self.assertIn("strict:complete_shaper_v5:post_cleanup_single_session", result["failed"])

    def test_validate_gate_rejects_weak_capability_suite_native_artifacts_and_callbacks(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            weak = root / "live_capability_suite.json"
            weak.write_text(json.dumps({
                "ok": True,
                "native_artifacts": {"primary": True},
                "validation": {"ok": True, "failed_capabilities": []},
            }), encoding="utf-8")
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("live_capability_suite", weak, ("ok", "native_artifacts.primary"), self.module.capability_suite_strict_checks()),
            ])
        self.assertFalse(result["ok"])
        self.assertIn("strict:live_capability_suite:native_solidworks_artifacts", result["failed"])
        self.assertIn("strict:live_capability_suite:interference_callback", result["failed"])
        self.assertIn("strict:live_capability_suite:assembly_mates_persisted", result["failed"])


    def test_default_report_expectations_use_strict_live_checks(self):
        contract = self.module.build_gate_contract()
        expectations = {item.name: item for item in self.module.report_expectations(contract)}
        self.assertIn("native_solidworks_artifacts", expectations["live_capability_suite"].strict_checks)
        self.assertIn("assembly_mates_persisted", expectations["live_capability_suite"].strict_checks)
        self.assertIn("part_count", expectations["complete_shaper_v5"].strict_checks)
        self.assertIn("component_count", expectations["complete_shaper_v5"].strict_checks)
        self.assertIn("mate_semantics", expectations["complete_shaper_v5"].strict_checks)

    def test_validate_gate_accepts_strict_live_evidence_and_native_artifacts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            suite = root / "live_capability_suite.json"
            shaper = root / "complete_shaper_build.json"
            suite.write_text(json.dumps({
                "ok": True,
                "native_artifacts": {"assembly_exists": True, "part_count": 4, "primary": True},
                "callbacks": {"interference": {"available": True, "count": 0}, "mass": {"available": True, "mass_kg": 0.2}},
                "post_cleanup": {"locked_files": []},
                "validation": {"ok": True, "failed_capabilities": []},
            }), encoding="utf-8")
            shaper.write_text(json.dumps({
                "ok": True,
                "part_count": 24,
                "component_count": 58,
                "callbacks": {"interference": {"available": True, "count": 0}, "mass": {"available": True, "mass_kg": 15.125546510666322}},
                "post_cleanup": {"locked_files": [], "lock_files": []},
                "validation": {"ok": True, "failed": []},
            }), encoding="utf-8")
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("live_capability_suite", suite, ("ok", "native_artifacts.primary")),
                self.module.ReportExpectation("complete_shaper_v5", shaper, ("ok",)),
            ])
        self.assertTrue(result["ok"], result)
        self.assertEqual([], result["failed"])


    def test_readme_documents_live_gate_native_outputs_and_stale_cleanup(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        usage = (ROOT / "docs" / "solidworks-codex-usage.md").read_text(encoding="utf-8")
        joined = readme + "\n" + usage
        self.assertIn("live-gate", joined)
        self.assertIn(".SLDASM/.SLDPRT", joined)
        self.assertIn("STEP", joined)
        self.assertIn("--cleanup-stale", joined)
        self.assertIn("shaper_machine_v5", joined)


    def test_gate_script_advertises_downstream_pywin32_requirement_to_swctl(self):
        head = SCRIPT.read_text(encoding="utf-8").splitlines()[:80]
        self.assertTrue(any("win32com" in line or "pythoncom" in line for line in head))

    def test_swctl_exposes_live_gate_command(self):
        swctl = (ROOT / "tools" / "solidworks_codex" / "swctl.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("'live-gate'", swctl)
        self.assertIn("sw_live_validation_gate.py", swctl)

    def test_cleanup_stale_records_permission_errors_without_crashing(self):
        calls = []
        original_dirs = self.module.default_stale_fixture_dirs
        original_rmtree = self.module.shutil.rmtree
        try:
            stale = ROOT / "tools" / "solidworks_codex" / "live_fixture" / "shaper_machine_v4"
            self.module.default_stale_fixture_dirs = lambda: (stale,)
            def fake_rmtree(path):
                calls.append(path)
                raise PermissionError("locked by SolidWorks")
            self.module.shutil.rmtree = fake_rmtree
            result = self.module.cleanup_stale_fixtures(True)
        finally:
            self.module.default_stale_fixture_dirs = original_dirs
            self.module.shutil.rmtree = original_rmtree
        self.assertEqual([stale], calls)
        self.assertFalse(result["entries"][0]["removed"])
        self.assertIn("PermissionError", result["entries"][0]["error"])

    def test_safe_cleanup_scope_only_allows_generated_live_fixture_children(self):
        allowed = ROOT / "tools" / "solidworks_codex" / "live_fixture" / "shaper_machine_v4"
        current = ROOT / "tools" / "solidworks_codex" / "live_fixture" / "shaper_machine_v5"
        unrelated = ROOT / "docs"
        self.assertTrue(self.module.is_safe_stale_fixture_dir(allowed))
        self.assertFalse(self.module.is_safe_stale_fixture_dir(current))
        self.assertFalse(self.module.is_safe_stale_fixture_dir(unrelated))


if __name__ == "__main__":
    unittest.main()


