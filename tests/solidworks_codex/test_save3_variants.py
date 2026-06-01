import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SET_DIMENSION_SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_set_dimension.py"
REBUILD_SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_rebuild.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def load_set_dimension_module():
    return load_module("sw_set_dimension", SET_DIMENSION_SCRIPT)

def load_rebuild_module():
    return load_module("sw_rebuild", REBUILD_SCRIPT)


class SaveModelVariantTests(unittest.TestCase):
    def assert_save_model_uses_byref_error_and_warning_variants(self, module):
        calls = []
        class FakeVariant:
            def __init__(self, kind, value):
                self.kind = kind
                self.value = value
        class FakeClient:
            @staticmethod
            def VARIANT(kind, value):
                calls.append(("variant", kind, value))
                return FakeVariant(kind, value)
        class FakePythoncom:
            VT_BYREF = 0x4000
            VT_I4 = 3
        class FakeModel:
            def Save3(self, options, errors, warnings):
                calls.append(("save3", options, errors.kind, warnings.kind))
                errors.value = 0
                warnings.value = 0
                return True
        original = module.require_pywin32
        module.require_pywin32 = lambda: (FakePythoncom, FakeClient)
        try:
            result = module.save_model(FakeModel())
        finally:
            module.require_pywin32 = original
        self.assertEqual(result["ok"], True)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["warnings"], 0)
        self.assertEqual(calls[-1][0], "save3")

    def test_set_dimension_save_model_uses_byref_error_and_warning_variants(self):
        self.assert_save_model_uses_byref_error_and_warning_variants(load_set_dimension_module())

    def test_rebuild_save_model_uses_byref_error_and_warning_variants(self):
        self.assert_save_model_uses_byref_error_and_warning_variants(load_rebuild_module())


if __name__ == "__main__":
    unittest.main()
