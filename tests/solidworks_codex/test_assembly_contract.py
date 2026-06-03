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


class AssemblyContractTests(unittest.TestCase):
    def sample_report(self):
        return {
            "part_feature_evidence": {
                "base_plate": {
                    "ok": True,
                    "features": [
                        {"name": "Base_Boss", "semantic": "boss"},
                        {"name": "Mounting_Holes", "semantic": "through_hole", "count": 4},
                    ],
                },
                "cover_plate": {
                    "ok": True,
                    "features": [{"name": "Cover_Window_Cut", "semantic": "window_cut"}],
                },
            },
            "active_document": {
                "type": "assembly",
                "component_count_sampled": 4,
                "components": [
                    {"name2": "base_plate-1", "suppressed": False, "transform": {"origin_m": [0.0, 0.0, 0.0]}},
                    {"name2": "cover_plate-1", "suppressed": False, "transform": {"origin_m": [0.0, 0.0, 0.05]}},
                    {"name2": "drive_shaft-1", "suppressed": False, "transform": {"origin_m": [0.10, 0.0, 0.02]}},
                    {"name2": "bearing_block-1", "suppressed": False, "transform": {"origin_m": [0.10, 0.0, 0.02]}},
                ],
                "mate_like_features": [
                    {"name": "Base_Cover_Distance", "type": "MateDistanceDim", "components": ["base_plate-1", "cover_plate-1"], "suppressed": False},
                    {"name": "Shaft_Bearing_Concentric", "type": "MateConcentric", "components": ["drive_shaft-1", "bearing_block-1"], "suppressed": False},
                ],
            }
        }

    def sample_contract(self):
        return {
            "document_type": "assembly",
            "minimum_component_count": 4,
            "components": {
                "base_plate": {"required": True, "origin_m": [0.0, 0.0, 0.0], "tolerance_m": 0.002},
                "cover_plate": {"required": True, "origin_m": [0.0, 0.0, 0.05], "tolerance_m": 0.002},
                "drive_shaft": {"required": True},
                "bearing_block": {"required": True},
            },
            "mates": {
                "Base_Cover_Distance": {"type": "MateDistanceDim", "semantic_pair": ["base_plate", "cover_plate"]},
                "Shaft_Bearing_Concentric": {"type": "MateConcentric", "semantic_pair": ["drive_shaft", "bearing_block"]},
            },
            "part_features": {
                "base_plate": {
                    "required": True,
                    "required_names": ["Base_Boss", "Mounting_Holes"],
                    "required_semantics": {"through_hole": {"min_count": 4}},
                },
                "cover_plate": {"required_names": ["Cover_Window_Cut"]},
            },
        }

    def test_contract_accepts_generic_mechanical_assembly_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            contract = root / "contract.json"
            out = root / "contract_result.json"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")
            contract.write_text(json.dumps(self.sample_contract()), encoding="utf-8")
            proc = run_py("tools/solidworks_codex/scripts/sw_assembly_contract.py", "--report", str(report), "--contract", str(contract), "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["summary"]["failed"], 0)
            self.assertGreaterEqual(data["summary"]["accepted"], 6)

    def test_contract_rejects_missing_mate_wrong_components_and_bad_origin(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report_data = self.sample_report()
            report_data["active_document"]["components"][1]["transform"]["origin_m"] = [9.0, 9.0, 9.0]
            report_data["active_document"]["mate_like_features"][1]["components"] = ["wrong-1", "bearing_block-1"]
            report = root / "inspect.json"
            contract = root / "contract.json"
            out = root / "contract_result.json"
            report.write_text(json.dumps(report_data), encoding="utf-8")
            contract.write_text(json.dumps(self.sample_contract()), encoding="utf-8")
            proc = run_py("tools/solidworks_codex/scripts/sw_assembly_contract.py", "--report", str(report), "--contract", str(contract), "--out", str(out))
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["failed"]}
            self.assertIn("component_origin", kinds)
            self.assertIn("mate_components", kinds)

    def test_contract_rejects_missing_part_shape_features_and_semantics(self):
        report = self.sample_report()
        report["part_feature_evidence"]["base_plate"]["features"] = [{"name": "Base_Boss", "semantic": "boss"}]
        result = __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_assembly_contract.py"))["validate"](report, self.sample_contract())

        self.assertFalse(result["ok"], result)
        failed = {(item["kind"], item["key"]) for item in result["failed"]}
        self.assertIn(("part_feature_name", "base_plate:Mounting_Holes"), failed)
        self.assertIn(("part_feature_semantic", "base_plate:through_hole"), failed)

    def test_contract_allows_warning_grade_shape_features(self):
        report = self.sample_report()
        contract = self.sample_contract()
        contract["part_features"]["optional_guard"] = {"required": True, "required_names": ["Guard_Rib"], "severity": "warning"}
        result = __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_assembly_contract.py"))["validate"](report, contract)

        self.assertTrue(result["ok"], result)
        self.assertIn("part_feature_missing", {item["kind"] for item in result["warnings"]})


    def test_contract_rejects_required_mate_between_fixed_components(self):
        report = self.sample_report()
        for component in report["active_document"]["components"][:2]:
            component["fixed"] = True
        contract = self.sample_contract()
        result = __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_assembly_contract.py"))["validate"](report, contract)

        self.assertFalse(result["ok"], result)
        self.assertIn("mate_between_fixed_components", {item["kind"] for item in result["failed"]})

    def test_contract_can_explicitly_allow_fixed_component_reference_mate(self):
        report = self.sample_report()
        for component in report["active_document"]["components"][:2]:
            component["fixed"] = True
        contract = self.sample_contract()
        contract["mates"]["Base_Cover_Distance"]["allow_fixed_fixed"] = True
        result = __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_assembly_contract.py"))["validate"](report, contract)

        self.assertTrue(result["ok"], result)

    def test_contract_rejects_suppressed_required_component(self):
        report = self.sample_report()
        report["active_document"]["components"][0]["suppressed"] = True
        result = __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_assembly_contract.py"))["validate"](report, self.sample_contract())

        self.assertFalse(result["ok"], result)
        self.assertIn("component_suppressed", {item["kind"] for item in result["failed"]})

    def test_contract_rejects_unsolved_mate_status_when_reported(self):
        report = self.sample_report()
        report["active_document"]["mate_like_features"][0]["mate_error"] = 4
        report["active_document"]["mate_like_features"][1]["status"] = "unsolved"
        result = __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_assembly_contract.py"))["validate"](report, self.sample_contract())

        kinds = {item["kind"] for item in result["failed"]}
        self.assertFalse(result["ok"], result)
        self.assertIn("mate_error", kinds)
        self.assertIn("mate_status", kinds)


    def test_contract_matches_solidworks_instance_suffix_without_breaking_hyphenated_names(self):
        report = self.sample_report()
        report["active_document"]["components"][2]["name2"] = "drive-shaft-1"
        report["active_document"]["mate_like_features"][1]["components"] = ["drive-shaft-1", "bearing_block-1"]
        contract = self.sample_contract()
        contract["components"].pop("drive_shaft")
        contract["components"]["drive-shaft"] = {"required": True}
        contract["mates"]["Shaft_Bearing_Concentric"]["semantic_pair"] = ["drive-shaft", "bearing_block"]
        result = __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_assembly_contract.py"))["validate"](report, contract)
        self.assertTrue(result["ok"], result)
        accepted = {(item["kind"], item["key"]) for item in result["accepted"]}
        self.assertIn(("component_present", "drive-shaft"), accepted)
        self.assertIn(("mate_components", "Shaft_Bearing_Concentric"), accepted)

    def test_contract_does_not_accept_substring_component_pair_matches(self):
        report = self.sample_report()
        report["active_document"]["components"].append({"name2": "pinion-1", "suppressed": False, "transform": {"origin_m": [0.2, 0.0, 0.0]}})
        report["active_document"]["mate_like_features"].append({"name": "Pin_Plate_Mate", "type": "MateConcentric", "components": ["pinion-1", "base_plate-1"], "suppressed": False})
        contract = {"document_type": "assembly", "components": {"pin": {"required": False}, "base_plate": {"required": True}}, "mates": {"Pin_Plate_Mate": {"type": "MateConcentric", "semantic_pair": ["pin", "base_plate"]}}}
        result = __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_assembly_contract.py"))["validate"](report, contract)
        self.assertFalse(result["ok"], result)
        self.assertIn("mate_components", {item["kind"] for item in result["failed"]})

    def test_contract_supports_warning_severity_without_blocking_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            contract = root / "contract.json"
            out = root / "contract_result.json"
            warning_contract = self.sample_contract()
            warning_contract["components"]["optional_guard"] = {"required": True, "severity": "warning", "reason": "nice-to-have guard component for release profile"}
            warning_contract["mates"]["Optional_Guard_Mate"] = {"type": "MateCoincident", "semantic_pair": ["optional_guard", "base_plate"], "severity": "warning"}
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")
            contract.write_text(json.dumps(warning_contract), encoding="utf-8")
            proc = run_py("tools/solidworks_codex/scripts/sw_assembly_contract.py", "--report", str(report), "--contract", str(contract), "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["summary"]["failed"], 0)
            self.assertGreaterEqual(data["summary"]["warnings"], 2)
            warning_kinds = {item["kind"] for item in data["warnings"]}
            self.assertIn("component_missing", warning_kinds)
            self.assertIn("mate_missing", warning_kinds)

    def test_contract_rejects_unknown_severity_to_keep_contracts_reviewable(self):
        contract = self.sample_contract()
        contract["components"]["base_plate"]["severity"] = "maybe"
        result = __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_assembly_contract.py"))["validate"](self.sample_report(), contract)
        self.assertFalse(result["ok"])
        self.assertIn("contract_severity", {item["kind"] for item in result["failed"]})

    def test_swctl_exposes_assembly_contract_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            contract = root / "contract.json"
            out = root / "contract_result.json"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")
            contract.write_text(json.dumps(self.sample_contract()), encoding="utf-8")
            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "assembly-contract",
                    "-Report", str(report),
                    "-Manifest", str(contract),
                    "-Out", str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(json.loads(out.read_text(encoding="utf-8-sig"))["ok"])



if __name__ == "__main__":
    unittest.main()
