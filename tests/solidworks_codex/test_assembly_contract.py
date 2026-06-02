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
