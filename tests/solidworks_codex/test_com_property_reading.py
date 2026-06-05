import unittest
from tools.solidworks_codex.scripts import sw_assembly_inspect as inspect_mod
from tools.solidworks_codex.scripts import sw_com_probe as probe_mod
from tools.solidworks_codex.scripts import sw_component_state as component_state_mod
from tools.solidworks_codex.scripts import sw_export as export_mod
from tools.solidworks_codex.scripts import sw_feature_state as feature_state_mod
from tools.solidworks_codex.scripts import sw_interference as interference_mod
from tools.solidworks_codex.scripts import sw_mass_properties as mass_mod
from tools.solidworks_codex.scripts import sw_rebuild as rebuild_mod
from tools.solidworks_codex.scripts import sw_selection_report as selection_mod
from tools.solidworks_codex.scripts import sw_set_dimension as set_dimension_mod


class FakeComProperty:
    _oleobj_ = object()

    def __init__(self, value):
        self.value = value

    def __call__(self):
        raise RuntimeError("COM property wrapper is not callable")

    def __str__(self):
        return self.value


class ComPropertyReadingTests(unittest.TestCase):
    def test_inspect_read_member_returns_com_property_without_calling(self):
        class FakeObject:
            ActiveDoc = FakeComProperty("doc")

        prop = FakeObject.ActiveDoc
        self.assertIs(inspect_mod.read_member(FakeObject(), "ActiveDoc"), prop)


    def test_inspect_normalizes_doc_type_errors_without_unhashable_dict(self):
        self.assertEqual(inspect_mod.normalize_doc_type(2), (2, "assembly"))
        code, label = inspect_mod.normalize_doc_type({"error": "COM failed"})
        self.assertIsNone(code)
        self.assertEqual(label, "unknown")

    def test_probe_read_member_returns_com_property_without_calling(self):
        class FakeObject:
            ActiveDoc = FakeComProperty("doc")

        prop = FakeObject.ActiveDoc
        self.assertIs(probe_mod.read_member(FakeObject(), "ActiveDoc"), prop)

    def test_inspect_safe_value_preserves_com_dispatch_objects(self):
        prop = FakeComProperty("doc")
        self.assertIs(inspect_mod.safe_value(prop), prop)

    def test_probe_safe_value_preserves_com_dispatch_objects(self):
        prop = FakeComProperty("doc")
        self.assertIs(probe_mod.safe_value(prop), prop)

    def test_live_helpers_preserve_com_dispatch_properties(self):
        prop = FakeComProperty("doc")

        class FakeObject:
            ActiveDoc = prop

        self.assertIs(component_state_mod.read(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(export_mod.read_member(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(feature_state_mod.read(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(interference_mod.read(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(mass_mod.read_member(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(rebuild_mod.read_member(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(selection_mod.read(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(set_dimension_mod.read_member(FakeObject(), "ActiveDoc"), prop)

    def test_live_helpers_preserve_com_dispatch_inside_lists(self):
        prop = FakeComProperty("component")
        self.assertIs(component_state_mod.val([prop])[0], prop)
        self.assertIs(feature_state_mod.val([prop])[0], prop)
        self.assertIs(interference_mod.val([prop])[0], prop)
        self.assertIs(selection_mod.val([prop])[0], prop)
        self.assertIs(set_dimension_mod.safe_value([prop])[0], prop)

    def test_selection_report_native_identity_captures_persist_tracking_and_select_name(self):
        class FakeExtension:
            def GetPersistReference3(self, obj):
                self.last = obj
                return bytes([1, 2, 3, 255])

        class FakeModel:
            Extension = FakeExtension()

        class FakeObject:
            Name = "Face<1>"

            def GetTrackingID(self):
                return 42

            def GetNameForSelection(self):
                return "Face<1>@plate-1"

            def GetTypeName2(self):
                return "FACE"

        class FakeComponent:
            Name2 = "plate-1"

            def GetPathName(self):
                return "C:/m/plate.SLDPRT"

        identity = selection_mod.native_identity(FakeModel(), FakeObject(), FakeComponent())
        self.assertEqual(identity["persistent_reference"], [1, 2, 3, 255])
        self.assertEqual(identity["tracking_id"], 42)
        self.assertEqual(identity["select_name"], "Face<1>@plate-1")
        self.assertEqual(identity["component"], "plate-1")
        self.assertEqual(identity["component_path"], "C:/m/plate.SLDPRT")
        self.assertEqual(identity["object_type"], "FACE")
        self.assertIn("geometry_signature_fallback", identity["resolution_order"])

    def test_feature_state_finds_exact_subfeature_and_rejects_ambiguous_contains(self):
        class FakeFeature:
            _oleobj_ = object()

            def __init__(self, name, next_feature=None, subfeature=None):
                self.Name = name
                self._next = next_feature
                self._sub = subfeature

            def GetNameForSelection(self):
                return self.Name

            def GetTypeName2(self):
                return "Boss"

            def GetNextFeature(self):
                return self._next

            def GetFirstSubFeature(self):
                return self._sub

        child = FakeFeature("Cut-Exact")
        second = FakeFeature("Cut-Other")
        first = FakeFeature("Boss-Root", second, child)

        class FakeModel:
            def FirstFeature(self):
                return first

        self.assertIs(feature_state_mod.find_feature(FakeModel(), "Cut-Exact"), child)
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            feature_state_mod.find_feature(FakeModel(), "Cut-")

    def test_feature_state_suppress_unsuppress_and_delete_select_feature(self):
        calls = []

        class FakeExtension:
            _oleobj_ = object()

            def DeleteSelection2(self, options):
                calls.append(("DeleteSelection2", options))
                return True

        class FakeModel:
            Extension = FakeExtension()

        class FakeFeature:
            _oleobj_ = object()
            Name = "Cut-1"

            def Select2(self, append, mark):
                calls.append(("Select2", append, mark))
                return True

            def SetSuppression2(self, action, config_opt=None, configs=None):
                calls.append(("SetSuppression2", action, config_opt, configs))
                return True

        feature = FakeFeature()
        self.assertEqual(feature_state_mod.apply_action(FakeModel(), feature, "suppress")["state"], True)
        self.assertEqual(feature_state_mod.apply_action(FakeModel(), feature, "unsuppress")["state"], True)
        self.assertEqual(feature_state_mod.apply_action(FakeModel(), feature, "delete")["delete"], True)
        self.assertEqual(calls[0], ("Select2", False, 0))
        self.assertIn(("SetSuppression2", 0, 2, None), calls)
        self.assertIn(("SetSuppression2", 1, 2, None), calls)
        self.assertIn(("DeleteSelection2", 0), calls)

    def test_feature_state_sets_dimension_value_with_feature_scoped_resolution(self):
        calls = []

        class FakeDimension:
            _oleobj_ = object()

            def __init__(self, value):
                self.SystemValue = value

        class FakeModel:
            def __init__(self):
                self.dimension = FakeDimension(0.004)

            def Parameter(self, name):
                calls.append(("Parameter", name))
                if name == "D1@Cut-1":
                    return self.dimension
                return None

        class FakeFeature:
            _oleobj_ = object()
            Name = "Cut-1"

            def GetNameForSelection(self):
                return "Cut-1"

            def Select2(self, append, mark):
                calls.append(("Select2", append, mark))
                return True

        model = FakeModel()
        result = feature_state_mod.apply_action(model, FakeFeature(), "set-dimension", dimension="D1", value_m=0.012)

        self.assertEqual(result["dimension"]["name"], "D1@Cut-1")
        self.assertEqual(result["dimension"]["before_m"], 0.004)
        self.assertEqual(result["dimension"]["after_m"], 0.012)
        self.assertEqual(model.dimension.SystemValue, 0.012)
        self.assertEqual(calls[0], ("Select2", False, 0))
        self.assertIn(("Parameter", "D1@Cut-1"), calls)

    def test_feature_state_reports_action_roles_and_change_scope(self):
        before = {"name": "Cut-1", "suppressed": False}
        after = {"name": "Cut-1", "suppressed": True}
        action_result = {"select": True, "state": True}

        evidence = feature_state_mod.action_evidence(
            action="suppress",
            before=before,
            after=after,
            before_feature_count=8,
            after_feature_count=8,
            action_result=action_result,
        )

        self.assertEqual(evidence["operation_role"], "feature_deactivation")
        self.assertEqual(evidence["change_scope"], "feature_state")
        self.assertEqual(evidence["changed_feature"], "Cut-1")
        self.assertTrue(evidence["selection_evidence"]["selected"])
        self.assertEqual(evidence["feature_count_delta"], 0)

        dimension_evidence = feature_state_mod.action_evidence(
            action="set-dimension",
            before=before,
            after={"name": "Cut-1", "suppressed": False},
            before_feature_count=8,
            after_feature_count=8,
            action_result={"select": True, "dimension": {"name": "D1@Cut-1", "before_m": 0.004, "after_m": 0.012}},
        )

        self.assertEqual(dimension_evidence["operation_role"], "feature_parameter_adjustment")
        self.assertEqual(dimension_evidence["change_scope"], "feature_dimension")
        self.assertEqual(dimension_evidence["changed_parameter"], "D1@Cut-1")
        self.assertEqual(dimension_evidence["parameter_delta_m"], 0.008)

    def test_component_state_hide_show_uses_assembly_selection_commands(self):
        calls = []

        class FakeAssembly:
            def HideComponent(self):
                calls.append("HideComponent")
                return "hidden"

            def ShowComponent2(self):
                calls.append("ShowComponent2")
                return "shown"

        class FakeComponent:
            def Select4(self, append, callout, mark):
                calls.append(("Select4", append, mark, hasattr(callout, "value")))
                return True

        self.assertEqual(component_state_mod.apply_action(FakeAssembly(), FakeComponent(), "hide"), "hidden")
        self.assertEqual(component_state_mod.apply_action(FakeAssembly(), FakeComponent(), "show"), "shown")
        self.assertIn("HideComponent", calls)
        self.assertIn("ShowComponent2", calls)
        self.assertEqual(calls[0][0], "Select4")

    def test_component_state_fix_float_selects_with_dispatch_variant(self):
        calls = []

        class FakeAssembly:
            def FixComponent(self):
                calls.append("FixComponent")
                return "fixed"

            def UnfixComponent(self):
                calls.append("UnfixComponent")
                return "floating"

        class FakeComponent:
            def Select4(self, append, callout, mark):
                calls.append(("Select4", append, mark, hasattr(callout, "value")))
                return True

        self.assertEqual(component_state_mod.apply_action(FakeAssembly(), FakeComponent(), "fix"), "fixed")
        self.assertEqual(component_state_mod.apply_action(FakeAssembly(), FakeComponent(), "float"), "floating")
        self.assertEqual(calls[0], ("Select4", False, False, True))

    def test_set_dimension_attach_start_uses_required_win32_client(self):
        calls = []

        class FakeSw:
            Visible = False

        class FakeWin32Client:
            def GetActiveObject(self, prog_id):
                calls.append(("GetActiveObject", prog_id))
                raise RuntimeError("not running")

            def Dispatch(self, prog_id):
                calls.append(("Dispatch", prog_id))
                return FakeSw()

        original = set_dimension_mod.require_pywin32
        set_dimension_mod.require_pywin32 = lambda: (object(), FakeWin32Client())
        try:
            sw, started = set_dimension_mod.attach_solidworks(True)
        finally:
            set_dimension_mod.require_pywin32 = original

        self.assertIsInstance(sw, FakeSw)
        self.assertTrue(started)
        self.assertEqual(calls, [("GetActiveObject", "SldWorks.Application"), ("Dispatch", "SldWorks.Application")])


if __name__ == "__main__":
    unittest.main()
