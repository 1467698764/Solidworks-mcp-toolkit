import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_mate_group_validate.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class MateGroupValidateTests(unittest.TestCase):
    def good_plan(self):
        return {
            "mode": "read_only_mate_group_plan",
            "document": {"title": "validate_fixture.SLDASM"},
            "mate_groups": [
                {
                    "group_id": "standard_bolt_m6-1",
                    "components": ["bolt_m6-1", "cover_plate-1"],
                    "suggested_mates": [{"type": "concentric"}, {"type": "coincident"}],
                    "dof_expectation": {
                        "intent": "fully_located_attachment",
                        "remaining_dof": [],
                        "rotation_about_axis": "locked",
                    },
                    "verification": ["rebuild", "mate_errors", "minimum_clearance"],
                },
                {
                    "group_id": "classify_handle-1",
                    "components": ["handle-1"],
                    "suggested_mates": [],
                    "verification": ["design_intent_confirmed_before_mating"],
                },
            ],
        }

    def test_valid_plan_passes_with_group_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan.write_text(json.dumps(self.good_plan()), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["counts"]["groups"], 2)
            self.assertFalse(data["findings"]["blocking"])

    def test_invalid_plan_reports_blockers(self):
        bad = self.good_plan()
        bad["mate_groups"][0]["components"] = ["bolt_m6-1"]
        bad["mate_groups"][0]["suggested_mates"] = [{"type": "gear"}]
        bad["mate_groups"][0].pop("dof_expectation")
        bad["mate_groups"][0]["verification"] = ["visual_only"]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan.write_text(json.dumps(bad), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"], data)
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("mate_group_component_count", kinds)
            self.assertIn("unsupported_mate_type", kinds)
            self.assertIn("missing_dof_expectation", kinds)
            self.assertIn("missing_group_verification", kinds)

    def test_blocks_decorative_concentric_without_axial_locator_or_intended_rotation(self):
        bad = self.good_plan()
        bad["mate_groups"][0]["suggested_mates"] = [{"type": "concentric"}]
        bad["mate_groups"][0]["dof_expectation"] = {
            "intent": "fully_located_attachment",
            "remaining_dof": [],
            "rotation_about_axis": "locked",
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan.write_text(json.dumps(bad), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"], data)
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("concentric_without_axial_locator", kinds)

    def test_accepts_tangent_roller_contact_group(self):
        plan = self.good_plan()
        plan["mate_groups"][0]["suggested_mates"] = [{"type": "tangent"}]
        plan["mate_groups"][0]["dof_expectation"] = {
            "intent": "roller_surface_contact",
            "remaining_dof": ["rotation_about_roller_axis"],
            "rotation_about_axis": "free",
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)

    def test_accepts_limit_distance_and_limit_angle_groups(self):
        plan = self.good_plan()
        plan["mate_groups"][0]["suggested_mates"] = [
            {"type": "limit_distance", "distance_min_m": 0.005, "distance_max_m": 0.04},
            {"type": "limit_angle", "angle_min_deg": 10.0, "angle_max_deg": 70.0},
        ]
        plan["mate_groups"][0]["dof_expectation"] = {
            "intent": "bounded_slider_or_hinge",
            "remaining_dof": ["bounded_translation_or_rotation"],
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)

    def test_swctl_routes_mate_group_validate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan.write_text(json.dumps(self.good_plan()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-group-validate",
                    "-Report", str(plan),
                    "-Out", str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()
