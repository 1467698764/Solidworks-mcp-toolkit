import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_create_shaper_fixture.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sw_create_shaper_fixture", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load shaper fixture module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ShaperFixtureSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_spec_describes_real_quick_return_shaper_not_two_plates(self):
        shaper = self.module.build_shaper_spec()

        self.assertEqual(shaper.name, "shaper_quick_return_validation")
        self.assertGreaterEqual(len(shaper.parts), 14)
        part_names = {part.name for part in shaper.parts}
        required = {
            "base_casting",
            "vertical_column",
            "ram_slide",
            "tool_head",
            "crank_disk",
            "eccentric_crank_pin",
            "slotted_rocker",
            "sliding_die_block",
            "rocker_pivot_bracket",
            "connecting_link",
            "stroke_adjuster",
            "left_ram_way",
            "right_ram_way",
            "front_limit_stop",
            "rear_limit_stop",
        }
        self.assertTrue(required.issubset(part_names), sorted(required - part_names))

        joint_types = {joint.kind for joint in shaper.joints}
        self.assertIn("revolute", joint_types)
        self.assertIn("sliding", joint_types)
        self.assertIn("slot", joint_types)
        self.assertIn("coincident", joint_types)
        self.assertGreaterEqual(len(shaper.joints), 10)

    def test_spec_has_adjustable_dimensions_and_expected_validation_targets(self):
        shaper = self.module.build_shaper_spec()
        dimensions = {dim.name: dim for dim in shaper.adjustable_dimensions}

        self.assertIn("D1@Sketch_Eccentric@crank_disk.Part", dimensions)
        self.assertAlmostEqual(dimensions["D1@Sketch_Eccentric@crank_disk.Part"].default_m, 0.018, places=6)
        self.assertAlmostEqual(dimensions["D1@Sketch_Eccentric@crank_disk.Part"].validation_value_m, 0.022, places=6)
        self.assertIn("D1@Sketch_StrokeWindow@ram_slide.Part", dimensions)
        self.assertGreaterEqual(len(dimensions), 4)

        targets = shaper.validation_targets
        self.assertEqual(targets.safe_set_dimension, "D1@Sketch_Eccentric@crank_disk.Part")
        self.assertEqual(targets.safe_set_value_m, 0.022)
        self.assertIn("tool_head-1", targets.hide_show_components)
        self.assertIn("connecting_link-1", targets.fix_float_components)
        self.assertTrue(targets.export_step.endswith("shaper_quick_return_validation.step"))

    def test_manifest_is_serializable_and_records_functional_intent(self):
        shaper = self.module.build_shaper_spec()
        manifest = self.module.spec_to_manifest(shaper)

        self.assertEqual(manifest["name"], "shaper_quick_return_validation")
        self.assertEqual(manifest["mechanism"], "bullhead shaper quick-return linkage")
        self.assertGreaterEqual(manifest["part_count"], 14)
        self.assertGreaterEqual(manifest["joint_count"], 10)
        self.assertIn("quick_return", manifest["functional_requirements"])
        self.assertIn("ram_guided_prismatic_motion", manifest["functional_requirements"])
        self.assertIn("eccentric_radius_change_observable", manifest["functional_requirements"])


class ShaperFixtureComCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_new_part_uses_default_part_template_when_newpart_dispatch_is_not_callable(self):
        class FakeSw:
            def __init__(self):
                self.calls = []
            def GetUserPreferenceStringValue(self, idx):
                self.calls.append(("pref", idx))
                return "C:/templates/gb_part.prtdot" if idx == 8 else ""
            def NewDocument(self, template, paper, width, height):
                self.calls.append(("newdoc", template, paper, width, height))
                return {"model": template}

        sw = FakeSw()
        model = self.module.new_part(sw)
        self.assertEqual(model, {"model": "C:/templates/gb_part.prtdot"})
        self.assertIn(("pref", 8), sw.calls)
        self.assertIn(("newdoc", "C:/templates/gb_part.prtdot", 0, 0, 0), sw.calls)

    def test_new_assembly_uses_default_assembly_template(self):
        class FakeSw:
            def __init__(self):
                self.calls = []
            def GetUserPreferenceStringValue(self, idx):
                self.calls.append(("pref", idx))
                return "C:/templates/gb_assembly.asmdot" if idx == 9 else ""
            def NewDocument(self, template, paper, width, height):
                self.calls.append(("newdoc", template, paper, width, height))
                return {"asm": template}

        sw = FakeSw()
        asm = self.module.new_assembly(sw)
        self.assertEqual(asm, {"asm": "C:/templates/gb_assembly.asmdot"})
        self.assertIn(("pref", 9), sw.calls)
        self.assertIn(("newdoc", "C:/templates/gb_assembly.asmdot", 0, 0, 0), sw.calls)


class ShaperFixtureSelectionVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_select_front_plane_passes_empty_dispatch_variant_to_selectbyid2(self):
        calls = []
        marker = object()

        class FakeWin32Client:
            @staticmethod
            def VARIANT(kind, value):
                calls.append(("variant", kind, value))
                return marker

        class FakePythoncom:
            VT_DISPATCH = 9

        original = self.module.require_pywin32
        self.module.require_pywin32 = lambda: (FakePythoncom, FakeWin32Client)
        try:
            class FakeExtension:
                def SelectByID2(self, *args):
                    calls.append(("select", args))
                    return True
            class FakeModel:
                Extension = FakeExtension()
            self.module.select_front_plane(FakeModel())
        finally:
            self.module.require_pywin32 = original

        self.assertEqual(calls[0], ("variant", 9, None))
        self.assertIs(calls[1][1][7], marker)

class ShaperFixtureComPropertyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_select_front_plane_fallback_reads_firstfeature_property_without_calling(self):
        calls = []
        marker = object()

        class FakeWin32Client:
            @staticmethod
            def VARIANT(kind, value):
                return marker

        class FakePythoncom:
            VT_DISPATCH = 9

        class FakeFeature:
            Name = "前视基准面"
            def GetTypeName2(self):
                return "RefPlane"
            def Select2(self, append, mark):
                calls.append(("select2", append, mark))
                return True

        class FakeExtension:
            def SelectByID2(self, *args):
                calls.append(("selectbyid", args))
                return False

        class FakeModel:
            Extension = FakeExtension()
            FirstFeature = FakeFeature()

        original = self.module.require_pywin32
        self.module.require_pywin32 = lambda: (FakePythoncom, FakeWin32Client)
        try:
            self.module.select_front_plane(FakeModel())
        finally:
            self.module.require_pywin32 = original

        self.assertEqual(calls[0][0], "selectbyid")
        self.assertEqual(calls[1], ("select2", False, 0))

class ShaperFixtureAddComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_add_component_opens_part_before_inserting(self):
        calls = []
        class FakeClient:
            @staticmethod
            def VARIANT(kind, value):
                return {"kind": kind, "value": value}
        class FakePythoncom:
            VT_BYREF = 0x4000
            VT_I4 = 3
        class FakeSw:
            def OpenDoc6(self, path, doc_type, options, config, errors, warnings):
                calls.append(("open", path, doc_type))
                return {"opened": path}
        class FakeComp:
            Name2 = "base_casting-1"
        class FakeAsm:
            def AddComponent5(self, *args):
                calls.append(("add", args[0]))
                return FakeComp()
        original = self.module.require_pywin32
        self.module.require_pywin32 = lambda: (FakePythoncom, FakeClient)
        try:
            comp = self.module.add_component(FakeSw(), FakeAsm(), Path("base_casting.SLDPRT"), (0, 0, 0))
        finally:
            self.module.require_pywin32 = original
        self.assertEqual(comp.Name2, "base_casting-1")
        self.assertEqual(calls[0][0], "open")
        self.assertEqual(calls[0][2], 1)
        self.assertEqual(calls[1][0], "add")

class ShaperFixtureCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_cleanup_output_dir_skips_locked_files_and_removes_unlocked_files(self):
        calls = []
        class FakePath:
            def __init__(self, name, locked=False):
                self.name = name
                self.locked = locked
            def is_file(self):
                return True
            def unlink(self):
                calls.append(self.name)
                if self.locked:
                    raise PermissionError("locked")
        class FakeDir:
            def exists(self):
                return True
            def glob(self, pattern):
                return [FakePath("locked.SLDPRT", True), FakePath("old.json", False)]
        skipped = self.module.cleanup_output_dir(FakeDir(), force=True)
        self.assertEqual(skipped, ["locked.SLDPRT"])
        self.assertEqual(calls, ["locked.SLDPRT", "old.json"])

class ShaperFixtureDocumentLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_close_document_after_save_uses_model_title(self):
        calls = []
        class FakeModel:
            def GetTitle(self):
                return "base_casting.SLDPRT"
        class FakeSw:
            def CloseDoc(self, title):
                calls.append(title)
                return True
        self.module.close_document(FakeSw(), FakeModel())
        self.assertEqual(calls, ["base_casting.SLDPRT"])

class ShaperFixtureInsertLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_add_component_closes_opened_part_after_insert(self):
        calls = []
        class FakeClient:
            @staticmethod
            def VARIANT(kind, value):
                return {"kind": kind, "value": value}
        class FakePythoncom:
            VT_BYREF = 0x4000
            VT_I4 = 3
        class FakeModel:
            def GetTitle(self):
                return "base_casting.SLDPRT"
        class FakeSw:
            def OpenDoc6(self, path, doc_type, options, config, errors, warnings):
                calls.append(("open", path))
                return FakeModel()
            def CloseDoc(self, title):
                calls.append(("close", title))
                return True
        class FakeComp:
            Name2 = "base_casting-1"
        class FakeAsm:
            def GetTitle(self):
                return "shaper_quick_return_validation.SLDASM"
            def AddComponent5(self, *args):
                calls.append(("add", args[0]))
                return FakeComp()
        original = self.module.require_pywin32
        self.module.require_pywin32 = lambda: (FakePythoncom, FakeClient)
        try:
            self.module.add_component(FakeSw(), FakeAsm(), Path("base_casting.SLDPRT"), (0, 0, 0))
        finally:
            self.module.require_pywin32 = original
        self.assertEqual([c[0] for c in calls], ["open", "add", "close"])
        self.assertEqual(calls[-1], ("close", "base_casting.SLDPRT"))

if __name__ == "__main__":
    unittest.main()
