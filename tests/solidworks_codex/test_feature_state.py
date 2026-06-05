import unittest

from tools.solidworks_codex.scripts import sw_feature_state as mod


class FakeFeature:
    _oleobj_ = True

    def __init__(self, name, type_name="Boss"):
        self.Name = name
        self.type_name = type_name
        self.next = None
        self.sub = None
        self.selected = []
        self.definition = FakeDefinition()
        self.modified_definition = None

    def GetNameForSelection(self):
        return self.Name

    def GetTypeName2(self):
        return self.type_name

    def GetNextFeature(self):
        return self.next

    def GetFirstSubFeature(self):
        return self.sub

    def IsSuppressed2(self, *_args):
        return False

    def Select2(self, append, mark):
        self.selected.append((append, mark))
        return True

    def GetDefinition(self):
        return self.definition

    def ModifyDefinition(self, definition, model, component):
        self.modified_definition = (definition, model, component)
        return True


class FakeDefinition:
    _oleobj_ = True

    def __init__(self):
        self.Depth = 0.008
        self.ReverseDirection = False
        self.access_calls = []
        self.released = False

    def AccessSelections(self, model, component):
        self.access_calls.append((model, component))
        return True

    def ReleaseSelectionAccess(self):
        self.released = True
        return True


class FakeFeatureManager:
    _oleobj_ = True

    def __init__(self, model):
        self.model = model
        self.calls = []

    def ReorderFeature(self, source_name, target_name, position):
        self.calls.append(("ReorderFeature", (source_name, target_name, position)))
        self.model.move_feature(source_name, target_name, position)
        return True


class FakeModel:
    def __init__(self, names):
        self.features = [FakeFeature(name) for name in names]
        self.FeatureManager = FakeFeatureManager(self)
        self.relink()

    def relink(self):
        for index, feature in enumerate(self.features):
            feature.next = self.features[index + 1] if index + 1 < len(self.features) else None

    def FirstFeature(self):
        return self.features[0] if self.features else None

    def move_feature(self, source_name, target_name, position):
        source = next(item for item in self.features if item.Name == source_name)
        target = next(item for item in self.features if item.Name == target_name)
        self.features.remove(source)
        target_index = self.features.index(target)
        insert_index = target_index if position == "before" else target_index + 1
        self.features.insert(insert_index, source)
        self.relink()


class FeatureStateTests(unittest.TestCase):
    def test_edits_feature_definition_properties_and_reports_reviewed_scope(self):
        model = FakeModel(["BaseBoss", "PocketCut"])
        feature = mod.find_feature(model, "PocketCut")
        spec = {
            "edits": [
                {"property": "Depth", "value": 0.012},
                {"property": "ReverseDirection", "value": True},
            ]
        }

        result = mod.apply_action(model, feature, "edit-definition", definition_spec=spec)
        evidence = mod.action_evidence(
            action="edit-definition",
            before=mod.snapshot(feature),
            after=mod.snapshot(feature),
            before_feature_count=2,
            after_feature_count=2,
            action_result=result,
        )

        self.assertTrue(result["definition"]["modify_definition"]["ok"])
        self.assertEqual(feature.definition.Depth, 0.012)
        self.assertTrue(feature.definition.ReverseDirection)
        self.assertTrue(feature.definition.released)
        self.assertEqual(evidence["operation_role"], "feature_definition_edit")
        self.assertEqual(evidence["change_scope"], "feature_definition")
        self.assertEqual(evidence["changed_definition_properties"], ["Depth", "ReverseDirection"])
        self.assertEqual(evidence["definition_before"]["Depth"], 0.008)
        self.assertEqual(evidence["definition_after"]["Depth"], 0.012)

    def test_reorders_feature_before_reviewed_target_and_reports_order_delta(self):
        model = FakeModel(["BaseBoss", "PocketCut", "MountFillet"])
        feature = mod.find_feature(model, "MountFillet")
        before_order = mod.feature_order(model)

        result = mod.apply_action(model, feature, "reorder", target_feature="BaseBoss", reorder_position="before")
        after_order = mod.feature_order(model)
        evidence = mod.action_evidence(
            action="reorder",
            before=mod.snapshot(feature),
            after=mod.snapshot(feature),
            before_feature_count=3,
            after_feature_count=3,
            action_result=result,
            before_order=before_order,
            after_order=after_order,
        )

        self.assertTrue(result["reorder"]["ok"])
        self.assertEqual(model.FeatureManager.calls[-1], ("ReorderFeature", ("MountFillet", "BaseBoss", "before")))
        self.assertEqual(after_order, ["MountFillet", "BaseBoss", "PocketCut"])
        self.assertEqual(evidence["operation_role"], "feature_reorder")
        self.assertEqual(evidence["change_scope"], "feature_tree_order")
        self.assertEqual(evidence["feature_order_before"], ["BaseBoss", "PocketCut", "MountFillet"])
        self.assertEqual(evidence["feature_order_after"], ["MountFillet", "BaseBoss", "PocketCut"])


if __name__ == "__main__":
    unittest.main()
