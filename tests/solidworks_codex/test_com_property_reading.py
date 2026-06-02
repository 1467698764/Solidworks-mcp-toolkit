import unittest
from tools.solidworks_codex.scripts import sw_assembly_inspect as inspect_mod
from tools.solidworks_codex.scripts import sw_com_probe as probe_mod
from tools.solidworks_codex.scripts import sw_component_state as component_state_mod
from tools.solidworks_codex.scripts import sw_export as export_mod
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
        self.assertIs(interference_mod.read(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(mass_mod.read_member(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(rebuild_mod.read_member(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(selection_mod.read(FakeObject(), "ActiveDoc"), prop)
        self.assertIs(set_dimension_mod.read_member(FakeObject(), "ActiveDoc"), prop)

    def test_live_helpers_preserve_com_dispatch_inside_lists(self):
        prop = FakeComProperty("component")
        self.assertIs(component_state_mod.val([prop])[0], prop)
        self.assertIs(interference_mod.val([prop])[0], prop)
        self.assertIs(selection_mod.val([prop])[0], prop)
        self.assertIs(set_dimension_mod.safe_value([prop])[0], prop)

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
