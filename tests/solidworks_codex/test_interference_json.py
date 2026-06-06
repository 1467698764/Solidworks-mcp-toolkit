import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_interference.py"


def load_interference_module():
    spec = importlib.util.spec_from_file_location("sw_interference", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load sw_interference")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class InterferenceJsonSafetyTests(unittest.TestCase):
    def test_json_safe_converts_com_dispatch_inside_interferences(self):
        module = load_interference_module()
        class FakeDispatch:
            _oleobj_ = object()
            def __str__(self):
                return "<COMObject FakeInterference>"
        payload = {"interference": {"interferences": [{"raw": FakeDispatch()}]}}
        safe = module.json_safe(payload)
        self.assertEqual(safe, {"interference": {"interferences": [{"raw": "<COMObject FakeInterference>"}]}})

    def test_open_or_active_records_explicit_assembly_handoff(self):
        module = load_interference_module()

        class FakeSw:
            def __init__(self):
                self.calls = []

            def OpenDoc6(self, path, doc_type, options, config, errors, warnings):
                self.calls.append((path, doc_type, options, config))
                errors.value = 0
                warnings.value = 4
                return {"assembly": path}

        class FakeVariant:
            def __init__(self, *_args):
                self.value = 0

        class FakePythonCom:
            VT_BYREF = 1
            VT_I4 = 2

        class FakeWin32:
            @staticmethod
            def VARIANT(*args):
                return FakeVariant(*args)

        module.pythoncom = FakePythonCom()
        module.win32com = type("Win32Com", (), {"client": FakeWin32})()
        sw = FakeSw()

        result = module.open_or_active(sw, "C:/models/gearbox.SLDASM")

        self.assertEqual(result["model"], {"assembly": str(Path("C:/models/gearbox.SLDASM").resolve())})
        self.assertEqual(result["handoff"]["source"], "specified_model")
        self.assertEqual(result["handoff"]["path"], str(Path("C:/models/gearbox.SLDASM").resolve()))
        self.assertEqual(result["handoff"]["open_errors"], 0)
        self.assertEqual(result["handoff"]["open_warnings"], 4)
        self.assertEqual(sw.calls[0][1], 2)

    def test_open_or_active_rejects_non_assembly_model_path(self):
        module = load_interference_module()
        with self.assertRaises(ValueError):
            module.open_or_active(object(), "C:/models/plate.SLDPRT")


if __name__ == "__main__":
    unittest.main()
