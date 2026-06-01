import unittest
from tools.solidworks_codex.scripts import sw_assembly_inspect as mod

class FakeTransform:
    ArrayData = [1,0,0,0,1,0,0,0,1,0.01,0.02,0.03,1,0,0,0]

class FakeComponent:
    Transform2 = FakeTransform()

class InspectTransformTests(unittest.TestCase):
    def test_component_transform_returns_structured_origin_and_axes(self):
        data = mod.component_transform(FakeComponent())
        self.assertEqual(data["array"], [1,0,0,0,1,0,0,0,1,0.01,0.02,0.03,1,0,0,0])
        self.assertEqual(data["origin_m"], [0.01,0.02,0.03])
        self.assertEqual(data["local_axes"]["x"], [1,0,0])
        self.assertEqual(data["local_axes"]["y"], [0,1,0])
        self.assertEqual(data["local_axes"]["z"], [0,0,1])

if __name__ == "__main__":
    unittest.main()
