import unittest

from tools.solidworks_codex.scripts import sw_assembly_inspect as mod


class FakeTransform:
    ArrayData = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0.01, 0.02, 0.03, 1, 0, 0, 0]


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


class FakePartModel:
    def __init__(self, path):
        self._path = path

    def GetType(self):
        return 1

    def GetTitle(self):
        return "bracket.SLDPRT"

    def GetPathName(self):
        return self._path

    def FirstFeature(self):
        return None


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
        self.assertEqual(data["array"], [1, 0, 0, 0, 1, 0, 0, 0, 1, 0.01, 0.02, 0.03, 1, 0, 0, 0])
        self.assertEqual(data["origin_m"], [0.01, 0.02, 0.03])
        self.assertEqual(data["local_axes"]["x"], [1, 0, 0])
        self.assertEqual(data["local_axes"]["y"], [0, 1, 0])
        self.assertEqual(data["local_axes"]["z"], [0, 0, 1])

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

    def test_inspect_model_object_reads_mate_reference_components(self):
        report = mod.inspect_model_object(NestedMateModel(), started_by_probe=False)
        mates = {item["name"]: item for item in report["active_document"]["mate_like_features"]}
        self.assertEqual(
            ["cast_bed_with_t_slots-1", "column_frame_with_window-1"],
            mates["Bed_Column_Distance_Mate"]["components"],
        )

    def test_inspect_model_object_reads_indexed_mate_entities(self):
        report = mod.inspect_model_object(IndexedMateModel(), started_by_probe=False)
        mates = {item["name"]: item for item in report["active_document"]["mate_like_features"]}
        self.assertEqual(["left_part-1", "right_part-1"], mates["Indexed_Distance_Mate"]["components"])

    def test_inspect_reports_requested_model_open_handoff_evidence(self):
        class FakeVariantFactory:
            VT_BYREF = 0
            VT_I4 = 0

            def CoInitialize(self):
                pass

            def VARIANT(self, _flags, value):
                return type("Variant", (), {"value": value})()

        class FakeWin32Client(FakeVariantFactory):
            def GetActiveObject(self, _prog_id):
                return fake_sw

        class FakeSw:
            RevisionNumber = "rev"
            Visible = False

            def __init__(self):
                self.open_calls = []

            def OpenDoc6(self, path, doc_type, options, config, errors, warnings):
                self.open_calls.append((path, doc_type, options, config))
                return FakePartModel(path)

        fake_sw = FakeSw()
        original = mod.load_pywin32
        try:
            mod.load_pywin32 = lambda: (FakeVariantFactory(), FakeWin32Client())
            report = mod.inspect(False, 10, 10, 10, "C:/models/bracket.SLDPRT")
        finally:
            mod.load_pywin32 = original

        self.assertEqual(report["document_handoff"]["source"], "specified_model")
        self.assertEqual(report["document_handoff"]["requested_path"], "C:\\models\\bracket.SLDPRT")
        self.assertEqual(report["document_handoff"]["doc_type"], "part")
        self.assertEqual(report["document_handoff"]["open_options"], 0)
        self.assertEqual(report["document_handoff"]["open_errors"], 0)
        self.assertEqual(report["document_handoff"]["open_warnings"], 0)
        self.assertEqual(report["active_document"]["source"], "specified_model")
        self.assertEqual(report["active_document"]["handoff_path"], "C:\\models\\bracket.SLDPRT")


class FakeMateEntity:
    def __init__(self, component_name):
        self.ReferenceComponent = type("RefComponent", (), {"Name2": component_name})()


class FakeMateSpecificByIndex:
    def __init__(self, component_names):
        self._entities = [FakeMateEntity(name) for name in component_names]

    def GetMateEntityCount(self):
        return len(self._entities)

    def MateEntity(self, index):
        return self._entities[index]


class FakeNestedFeature:
    def __init__(self, name, typ, next_feature=None, first_sub=None, entities=None, specific=None):
        self.Name = name
        self._type = typ
        self._next = next_feature
        self._first_sub = first_sub
        self._entities = entities or []
        self._specific = specific or self

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

    def GetSpecificFeature2(self):
        return self._specific

    def GetEntities(self):
        return self._entities


class FallbackComponentModel(FakeAssemblyModel):
    def __init__(self):
        super().__init__()
        self.calls = []

    def GetComponents(self, top_only):
        self.calls.append(top_only)
        return [] if top_only is False else [FakeComponent()]


class NestedMateModel(FakeAssemblyModel):
    def __init__(self):
        mate = FakeNestedFeature(
            "Bed_Column_Distance_Mate",
            "MateDistanceDim",
            entities=[
                FakeMateEntity("cast_bed_with_t_slots-1"),
                FakeMateEntity("column_frame_with_window-1"),
            ],
        )
        self._features = FakeNestedFeature("MateGroup", "MateGroup", first_sub=mate)


class IndexedMateModel(FakeAssemblyModel):
    def __init__(self):
        mate = FakeNestedFeature(
            "Indexed_Distance_Mate",
            "MateDistanceDim",
            specific=FakeMateSpecificByIndex(["left_part-1", "right_part-1"]),
        )
        self._features = FakeNestedFeature("MateGroup", "MateGroup", first_sub=mate)


if __name__ == "__main__":
    unittest.main()
