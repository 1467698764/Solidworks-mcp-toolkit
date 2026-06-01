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


if __name__ == "__main__":
    unittest.main()
