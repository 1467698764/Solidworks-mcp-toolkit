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
        bad["mate_groups"][0]["suggested_mates"] = [{"type": "path"}]
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

    def test_accepts_width_group_with_four_face_selectors_and_blocks_short_selector_list(self):
        plan = self.good_plan()
        width_mate = {
            "type": "width",
            "selection_selectors": [
                {"stable_id": "guide_left:face", "fallback": {"type": "bbox_planar_face"}},
                {"stable_id": "guide_right:face", "fallback": {"type": "bbox_planar_face"}},
                {"stable_id": "slider_left:face", "fallback": {"type": "bbox_planar_face"}},
                {"stable_id": "slider_right:face", "fallback": {"type": "bbox_planar_face"}},
            ],
        }
        plan["mate_groups"][0]["suggested_mates"] = [width_mate]
        plan["mate_groups"][0]["dof_expectation"] = {
            "intent": "centered_slider_between_guides",
            "remaining_dof": ["translation_along_guide"],
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

        plan["mate_groups"][0]["suggested_mates"][0]["selection_selectors"] = width_mate["selection_selectors"][:3]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("width_selector_count", kinds)

    def test_accepts_slot_group_and_blocks_invalid_slot_constraints(self):
        plan = self.good_plan()
        slot_mate = {
            "type": "slot",
            "slot_constraint_type": 1,
            "selection_selectors": [
                {"stable_id": "slot:centerline", "fallback": {"type": "slot_centerline"}},
                {"stable_id": "pin:axis", "fallback": {"type": "cylindrical_axis"}},
            ],
        }
        plan["mate_groups"][0]["suggested_mates"] = [slot_mate]
        plan["mate_groups"][0]["dof_expectation"] = {
            "intent": "pin_follows_slot",
            "remaining_dof": ["translation_along_slot"],
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

        plan["mate_groups"][0]["suggested_mates"][0]["selection_selectors"] = slot_mate["selection_selectors"][:1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("slot_selector_count", kinds)

        plan["mate_groups"][0]["suggested_mates"][0]["selection_selectors"] = slot_mate["selection_selectors"]
        plan["mate_groups"][0]["suggested_mates"][0]["slot_constraint_type"] = 2
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("slot_distance_required", kinds)

        plan["mate_groups"][0]["suggested_mates"][0]["slot_constraint_type"] = 3
        plan["mate_groups"][0]["suggested_mates"][0]["slot_percent"] = 125.0
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("slot_percent_range", kinds)

    def test_accepts_symmetry_group_with_three_selectors_and_blocks_short_selector_list(self):
        plan = self.good_plan()
        symmetry_mate = {
            "type": "symmetry",
            "selection_selectors": [
                {"stable_id": "left_tab:face", "fallback": {"type": "bbox_planar_face"}},
                {"stable_id": "right_tab:face", "fallback": {"type": "bbox_planar_face"}},
                {"stable_id": "center_plane:face", "fallback": {"type": "bbox_planar_face"}},
            ],
        }
        plan["mate_groups"][0]["suggested_mates"] = [symmetry_mate]
        plan["mate_groups"][0]["dof_expectation"] = {
            "intent": "symmetric_attachment",
            "remaining_dof": [],
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

        plan["mate_groups"][0]["suggested_mates"][0]["selection_selectors"] = symmetry_mate["selection_selectors"][:2]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("symmetry_selector_count", kinds)

    def test_accepts_gear_group_with_two_selectors_and_blocks_missing_ratio(self):
        plan = self.good_plan()
        gear_mate = {
            "type": "gear",
            "gear_ratio_numerator": 18,
            "gear_ratio_denominator": 54,
            "selection_selectors": [
                {"stable_id": "pinion:axis", "fallback": {"type": "cylindrical_axis"}},
                {"stable_id": "spur_gear:axis", "fallback": {"type": "cylindrical_axis"}},
            ],
        }
        plan["mate_groups"][0]["suggested_mates"] = [gear_mate]
        plan["mate_groups"][0]["dof_expectation"] = {
            "intent": "gear_rotation_coupling",
            "remaining_dof": ["coupled_rotation"],
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

        plan["mate_groups"][0]["suggested_mates"][0].pop("gear_ratio_denominator")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("gear_ratio_required", kinds)

        plan["mate_groups"][0]["suggested_mates"][0]["gear_ratio_denominator"] = 54
        plan["mate_groups"][0]["suggested_mates"][0]["selection_selectors"] = gear_mate["selection_selectors"][:1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("gear_selector_count", kinds)

    def test_accepts_cam_group_with_two_selectors_and_blocks_short_selector_list(self):
        plan = self.good_plan()
        cam_mate = {
            "type": "cam",
            "selection_selectors": [
                {"stable_id": "cam:surface", "fallback": {"type": "cylindrical_axis"}},
                {"stable_id": "follower:roller", "fallback": {"type": "cylindrical_axis"}},
            ],
        }
        plan["mate_groups"][0]["suggested_mates"] = [cam_mate]
        plan["mate_groups"][0]["dof_expectation"] = {
            "intent": "cam_follower_contact",
            "remaining_dof": ["follower_motion_along_cam_profile"],
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

        plan["mate_groups"][0]["suggested_mates"][0]["selection_selectors"] = cam_mate["selection_selectors"][:1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = root / "mate_group_plan.json"
            out = root / "validation.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("cam_selector_count", kinds)

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
