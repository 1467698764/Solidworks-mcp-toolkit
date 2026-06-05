import unittest

from tools.solidworks_codex.scripts import sw_rebuild as rebuild


class FakeExtension:
    def __init__(self, rebuild_errors=0, rebuild_warnings=0):
        self.rebuild_errors = rebuild_errors
        self.rebuild_warnings = rebuild_warnings

    def GetErrorCount(self):
        return self.rebuild_errors

    def GetWarningCount(self):
        return self.rebuild_warnings


class FakeFeature:
    def __init__(self, name, feature_type, error_code=0, next_feature=None):
        self._name = name
        self._type = feature_type
        self._error_code = error_code
        self._next = next_feature

    def GetNameForSelection(self):
        return self._name

    def GetTypeName2(self):
        return self._type

    def GetErrorCode2(self):
        return self._error_code

    def GetNextFeature(self):
        return self._next


class FakeModel:
    def __init__(self, rebuild_result=True, extension=None, first_feature=None):
        self.rebuild_result = rebuild_result
        self.Extension = extension
        self.first_feature = first_feature

    def ForceRebuild3(self, top_only):
        return self.rebuild_result

    def FirstFeature(self):
        return self.first_feature

    def GetTitle(self):
        return "bad_fixture.SLDPRT"

    def GetPathName(self):
        return "C:/cad/bad_fixture.SLDPRT"


class RebuildHealthTests(unittest.TestCase):
    def test_rebuild_health_blocks_false_rebuild_and_feature_errors(self):
        broken = FakeFeature("DanglingCut", "Cut", 1024)
        model = FakeModel(False, FakeExtension(rebuild_errors=2, rebuild_warnings=1), broken)

        report = rebuild.rebuild_health(model)

        self.assertFalse(report["ok"])
        self.assertFalse(report["rebuild_ok"])
        self.assertEqual(report["error_count"], 2)
        self.assertEqual(report["warning_count"], 1)
        self.assertIn("feature_error", {item["kind"] for item in report["findings"]["blocking"]})
        self.assertEqual(report["feature_errors"][0]["name"], "DanglingCut")

    def test_rebuild_health_accepts_clean_rebuild(self):
        clean = FakeFeature("Boss", "Boss", 0)
        model = FakeModel(True, FakeExtension(), clean)

        report = rebuild.rebuild_health(model)

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["findings"]["blocking"], [])
        self.assertEqual(report["feature_errors"], [])


if __name__ == "__main__":
    unittest.main()
