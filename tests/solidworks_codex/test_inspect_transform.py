import unittest
from tools.solidworks_codex.scripts import sw_assembly_inspect as mod

class FakeTransform:
    ArrayData = [1,0,0,0,1,0,0,0,1,0.01,0.02,0.03,1,0,0,0]

class FakeComponent:
    Transform2 = FakeTransform()



class FakeFeature:
    def __init__(self, name, typ, next_feature=None):
        self.Name = name
        self._type = typ
        self._next = next_feature
    def GetTypeName2(self):
        return self._type
    def IsSuppressed(self):
        return False
    def GetNextFeature(self):
        return self._next
    def GetFirstDisplayDimension(self):
        return None

class FakeAssemblyModel:
    def __init__(self):
        self._features = FakeFeature("Mate_A", "MateCoincident")
    def GetType(self):
        return 2
    def GetTitle(self):
        return "fixture.SLDASM"
    def GetPathName(self):
        return "C:/tmp/fixture.SLDASM"
    def FirstFeature(self):
        return self._features
    def GetComponents(self, top_only):
        return [FakeComponent()]

class InspectTransformTests(unittest.TestCase):
    def test_inspect_model_object_reads_current_assembly_without_starting_solidworks(self):
        report = mod.inspect_model_object(FakeAssemblyModel(), started_by_probe=False, revision_number="test", visible=False)
        doc = report["active_document"]
        self.assertFalse(report["started_by_probe"])
        self.assertEqual(doc["type"], "assembly")
        self.assertEqual(doc["component_count_sampled"], 1)
        self.assertEqual(doc["mate_like_features"][0]["name"], "Mate_A")

    def test_component_transform_returns_structured_origin_and_axes(self):
        data = mod.component_transform(FakeComponent())
        self.assertEqual(data["array"], [1,0,0,0,1,0,0,0,1,0.01,0.02,0.03,1,0,0,0])
        self.assertEqual(data["origin_m"], [0.01,0.02,0.03])
        self.assertEqual(data["local_axes"]["x"], [1,0,0])
        self.assertEqual(data["local_axes"]["y"], [0,1,0])
        self.assertEqual(data["local_axes"]["z"], [0,0,1])

    def test_inspect_components_falls_back_to_top_level_components_when_all_components_empty(self):
        model = FallbackComponentModel()
        report = mod.inspect_model_object(model, started_by_probe=False)
        self.assertEqual([False, True], model.calls)
        self.assertEqual(1, report["active_document"]["component_count_sampled"])

    def test_inspect_model_object_samples_mates_nested_under_mate_group(self):
        report = mod.inspect_model_object(NestedMateModel(), started_by_probe=False)
        names = {item["name"] for item in report["active_document"]["mate_like_features"]}
        self.assertIn("MateGroup", names)
        self.assertIn("Bed_Column_Distance_Mate", names)


class FakeNestedFeature:
    def __init__(self, name, typ, next_feature=None, first_sub=None):
        self.Name = name
        self._type = typ
        self._next = next_feature
        self._first_sub = first_sub
    def GetTypeName2(self):
        return self._type
    def IsSuppressed(self):
        return False
    def GetNextFeature(self):
        return self._next
    def GetFirstSubFeature(self):
        return self._first_sub
    def GetNextSubFeature(self):
        return self._next
    def GetFirstDisplayDimension(self):
        return None

class FallbackComponentModel(FakeAssemblyModel):
    def __init__(self):
        super().__init__()
        self.calls = []
    def GetComponents(self, top_only):
        self.calls.append(top_only)
        return [] if top_only is False else [FakeComponent()]

class NestedMateModel(FakeAssemblyModel):
    def __init__(self):
        mate = FakeNestedFeature("Bed_Column_Distance_Mate", "MateDistanceDim")
        self._features = FakeNestedFeature("MateGroup", "MateGroup", first_sub=mate)

if __name__ == "__main__":
    unittest.main()
