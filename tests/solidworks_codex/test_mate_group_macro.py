import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_mate_group_macro.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class MateGroupMacroTests(unittest.TestCase):
    def sample_plan(self):
        return {
            "mode": "read_only_mate_group_plan",
            "document": {"title": "macro_fixture.SLDASM"},
            "mate_groups": [
                {
                    "group_id": "repair_Broken_Bolt_Mate",
                    "source_action": "resolve_bad_mate",
                    "priority": "P0",
                    "components": [],
                    "execution_actions": [
                        {
                            "action": "suppress_mate",
                            "target_mate": "Broken_Bolt_Mate",
                            "reason": "remove bad mate before recreation",
                        }
                    ],
                    "suggested_mates": [
                        {
                            "type": "recreate_from_current_interfaces",
                            "selection_intent": "recreate after suppressing stale mate",
                        }
                    ],
                    "verification": ["rebuild", "mate_errors"],
                },
                {
                    "group_id": "standard_bolt_m6-1",
                    "source_action": "attach_hostless_standard_part",
                    "priority": "P1",
                    "components": ["bolt_m6-1", "cover_plate-1"],
                    "suggested_mates": [
                        {
                            "type": "concentric",
                            "selection_intent": "bolt axis to cover hole axis",
                            "selection_selectors": [
                                {"stable_id": "bolt_m6-1:cylinder:shaft", "fallback": {"type": "cylindrical_axis", "origin_m": [0, 0, 0]}},
                                {"stable_id": "cover_plate-1:cylinder:hole", "fallback": {"type": "cylindrical_axis", "origin_m": [0, 0, 0]}},
                            ],
                            "lock_rotation": True,
                        },
                        {
                            "type": "coincident",
                            "selection_intent": "bolt head underside to cover top face",
                            "selection_selectors": [
                                {"stable_id": "bolt_m6-1:plane:z_min", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0, 0]}},
                                {"stable_id": "cover_plate-1:plane:z_max", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0, 0]}},
                            ],
                        },
                        {
                            "type": "distance",
                            "selection_intent": "keep cover offset from base",
                            "distance_m": 0.0125,
                            "selection_selectors": [
                                {"stable_id": "cover_plate-1:plane:z_min", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0, 0]}},
                                {"stable_id": "base_plate-1:plane:z_max", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0, 0]}},
                            ],
                        },
                        {
                            "type": "angle",
                            "selection_intent": "set bracket design angle",
                            "angle_deg": 30.0,
                            "flip": True,
                            "selection_selectors": [
                                {"stable_id": "bracket-1:plane:y_min", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0, 0]}},
                                {"stable_id": "base_plate-1:plane:y_max", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0, 0]}},
                            ],
                        },
                        {
                            "type": "tangent",
                            "selection_intent": "roller outer surface tangent to cam plate",
                            "selection_selectors": [
                                {"stable_id": "roller-1:cylinder:outer", "fallback": {"type": "cylindrical_axis", "origin_m": [0, 0, 0], "radius_m": 0.015}},
                                {"stable_id": "cam_plate-1:plane:x_max", "fallback": {"type": "bbox_planar_face", "origin_m": [0.015, 0, 0]}},
                            ],
                        },
                        {
                            "type": "limit_distance",
                            "selection_intent": "slider travel stop distance",
                            "distance_m": 0.02,
                            "distance_min_m": 0.005,
                            "distance_max_m": 0.04,
                            "selection_selectors": [
                                {"stable_id": "slider-1:plane:x_min", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0, 0]}},
                                {"stable_id": "stop-1:plane:x_max", "fallback": {"type": "bbox_planar_face", "origin_m": [0.02, 0, 0]}},
                            ],
                        },
                        {
                            "type": "limit_angle",
                            "selection_intent": "hinge travel stop angle",
                            "angle_deg": 45.0,
                            "angle_min_deg": 10.0,
                            "angle_max_deg": 70.0,
                            "selection_selectors": [
                                {"stable_id": "arm-1:plane:y_min", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0, 0]}},
                                {"stable_id": "base_plate-1:plane:y_max", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0, 0]}},
                            ],
                        },
                        {
                            "type": "width",
                            "selection_intent": "center slider tab between guide faces",
                            "width_constraint_type": 0,
                            "selection_selectors": [
                                {"stable_id": "guide_left-1:plane:y_min", "width_role": "width_face", "fallback": {"type": "bbox_planar_face", "origin_m": [0, -0.02, 0]}},
                                {"stable_id": "guide_right-1:plane:y_max", "width_role": "width_face", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0.02, 0]}},
                                {"stable_id": "slider-1:plane:y_min", "width_role": "tab_face", "fallback": {"type": "bbox_planar_face", "origin_m": [0, -0.01, 0]}},
                                {"stable_id": "slider-1:plane:y_max", "width_role": "tab_face", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0.01, 0]}},
                            ],
                        },
                        {
                            "type": "symmetry",
                            "selection_intent": "keep mirrored tabs symmetric around frame center plane",
                            "selection_selectors": [
                                {"stable_id": "left_tab-1:plane:y_max", "symmetry_role": "first_entity", "fallback": {"type": "bbox_planar_face", "origin_m": [0, -0.02, 0]}},
                                {"stable_id": "right_tab-1:plane:y_min", "symmetry_role": "second_entity", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0.02, 0]}},
                                {"stable_id": "frame-1:plane:center", "symmetry_role": "symmetry_plane", "fallback": {"type": "bbox_planar_face", "origin_m": [0, 0, 0]}},
                            ],
                        },
                        {
                            "type": "gear",
                            "selection_intent": "couple pinion and spur gear pitch axes",
                            "gear_ratio_numerator": 18,
                            "gear_ratio_denominator": 54,
                            "selection_selectors": [
                                {"stable_id": "pinion-1:cylinder:pitch_axis", "fallback": {"type": "cylindrical_axis", "origin_m": [0, 0, 0], "radius_m": 0.018}},
                                {"stable_id": "spur_gear-1:cylinder:pitch_axis", "fallback": {"type": "cylindrical_axis", "origin_m": [0.07, 0, 0], "radius_m": 0.054}},
                            ],
                        },
                    ],
                    "verification": ["rebuild", "mate_errors"],
                },
                {
                    "group_id": "classify_handle-1",
                    "source_action": "classify_isolated_component",
                    "priority": "P2",
                    "components": ["handle-1"],
                    "suggested_mates": [],
                    "verification": ["design_intent_confirmed_before_mating"],
                },
            ],
        }

    def test_generates_reviewable_preselect_macros_per_actionable_mate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "mate_group_plan.json"
            out_dir = root / "macros"
            manifest = root / "macro_manifest.json"
            plan.write_text(json.dumps(self.sample_plan()), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan), "--out-dir", str(out_dir), "--manifest", str(manifest))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["mode"], "reviewable_mate_group_macros")
            self.assertEqual(data["document"]["title"], "macro_fixture.SLDASM")
            self.assertEqual(data["execution_actions"][0]["action"], "suppress_mate")
            self.assertEqual(data["execution_actions"][0]["target_mate"], "Broken_Bolt_Mate")
            self.assertEqual(len(data["macros"]), 10)
            self.assertEqual(data["macros"][0]["expected_mate_name"], "MG_standard_bolt_m6_1_01_concentric")
            self.assertEqual(len(data["macros"][0]["selection_selectors"]), 2)
            distance_macro = next(item for item in data["macros"] if item["mate_type"] == "distance")
            angle_macro = next(item for item in data["macros"] if item["mate_type"] == "angle")
            tangent_macro = next(item for item in data["macros"] if item["mate_type"] == "tangent")
            limit_distance_macro = next(item for item in data["macros"] if item["mate_type"] == "limit_distance")
            limit_angle_macro = next(item for item in data["macros"] if item["mate_type"] == "limit_angle")
            width_macro = next(item for item in data["macros"] if item["mate_type"] == "width")
            symmetry_macro = next(item for item in data["macros"] if item["mate_type"] == "symmetry")
            gear_macro = next(item for item in data["macros"] if item["mate_type"] == "gear")
            self.assertEqual(distance_macro["distance_m"], 0.0125)
            self.assertEqual(angle_macro["angle_deg"], 30.0)
            self.assertTrue(angle_macro["flip"])
            self.assertEqual(tangent_macro["expected_mate_name"], "MG_standard_bolt_m6_1_05_tangent")
            self.assertEqual(limit_distance_macro["distance_min_m"], 0.005)
            self.assertEqual(limit_distance_macro["distance_max_m"], 0.04)
            self.assertEqual(limit_angle_macro["angle_min_deg"], 10.0)
            self.assertEqual(limit_angle_macro["angle_max_deg"], 70.0)
            self.assertEqual(len(width_macro["selection_selectors"]), 4)
            self.assertEqual(width_macro["width_constraint_type"], 0)
            width_text = Path(width_macro["macro"]).read_text(encoding="utf-8")
            self.assertIn("CreateMateData(11)", width_text)
            self.assertIn("WidthSelection", width_text)
            self.assertIn("TabSelection", width_text)
            self.assertEqual(len(symmetry_macro["selection_selectors"]), 3)
            symmetry_text = Path(symmetry_macro["macro"]).read_text(encoding="utf-8")
            self.assertIn("Preselect exactly three mate entities", symmetry_text)
            self.assertIn("Mate type: symmetry", symmetry_text)
            self.assertEqual(gear_macro["gear_ratio_numerator"], 18.0)
            self.assertEqual(gear_macro["gear_ratio_denominator"], 54.0)
            gear_text = Path(gear_macro["macro"]).read_text(encoding="utf-8")
            self.assertIn("Mate type: gear", gear_text)
            self.assertIn("18.000000000", gear_text)
            self.assertIn("54.000000000", gear_text)
            skipped_groups = {item["group_id"] for item in data["skipped"]}
            self.assertIn("classify_handle-1", skipped_groups)
            self.assertIn("repair_Broken_Bolt_Mate", skipped_groups)
            first_macro = Path(data["macros"][0]["macro"])
            self.assertTrue(first_macro.exists())
            text = first_macro.read_text(encoding="utf-8")
            self.assertIn("Preselect exactly two mate entities", text)
            self.assertIn("Group: standard_bolt_m6-1", text)
            self.assertIn("Mate type: concentric", text)
            self.assertIn('MateFeature.Name = "MG_standard_bolt_m6_1_01_concentric"', text)
            self.assertTrue(data["preselect_required"])

    def test_swctl_routes_mate_group_macro(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "mate_group_plan.json"
            out_dir = root / "macros"
            manifest = root / "macro_manifest.json"
            plan.write_text(json.dumps(self.sample_plan()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-group-macro",
                    "-Report", str(plan),
                    "-OutDir", str(out_dir),
                    "-Out", str(manifest),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            self.assertEqual(len(data["macros"]), 10)

    def test_swctl_routes_limit_mate_macro_parameters(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            macro_path = root / "limit_angle.swp.vba"
            manifest = root / "limit_angle_manifest.json"

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-macro",
                    "-Mate", "limit_angle",
                    "-AngleDeg", "45",
                    "-AngleMinDeg", "10",
                    "-AngleMaxDeg", "70",
                    "-Out", str(macro_path),
                    "-Manifest", str(manifest),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            text = macro_path.read_text(encoding="utf-8")
            self.assertEqual(data["mate"], "limit_angle")
            self.assertEqual(data["angle_min_deg"], 10.0)
            self.assertEqual(data["angle_max_deg"], 70.0)
            self.assertIn("0.785398163", text)
            self.assertIn("1.221730476", text)

    def test_swctl_routes_gear_mate_macro_parameters(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            macro_path = root / "gear.swp.vba"
            manifest = root / "gear_manifest.json"

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-macro",
                    "-Mate", "gear",
                    "-GearRatioNumerator", "18",
                    "-GearRatioDenominator", "54",
                    "-Out", str(macro_path),
                    "-Manifest", str(manifest),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            text = macro_path.read_text(encoding="utf-8")
            self.assertEqual(data["mate"], "gear")
            self.assertEqual(data["gear_ratio_numerator"], 18.0)
            self.assertEqual(data["gear_ratio_denominator"], 54.0)
            self.assertIn("18.000000000", text)
            self.assertIn("54.000000000", text)


if __name__ == "__main__":
    unittest.main()
