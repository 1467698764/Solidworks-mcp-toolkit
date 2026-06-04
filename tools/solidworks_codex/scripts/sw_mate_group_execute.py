"""Execute reviewed mate group selectors in a live SolidWorks assembly."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

MATE_TYPES = {
    "coincident": 0,
    "concentric": 1,
    "perpendicular": 2,
    "parallel": 3,
    "tangent": 4,
    "distance": 5,
    "limit_distance": 5,
    "angle": 6,
    "limit_angle": 6,
    "symmetry": 8,
    "width": 11,
}

FALLBACK_SELECT_TYPES = {
    "bbox_planar_face": "FACE",
    "cylindrical_axis": "AXIS",
    "slot_centerline": "EDGE",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def selector_origin(selector: dict[str, Any]) -> list[float]:
    fallback = selector.get("fallback") if isinstance(selector.get("fallback"), dict) else {}
    origin = fallback.get("origin_m")
    if not isinstance(origin, list):
        centerline = fallback.get("centerline_m") if isinstance(fallback.get("centerline_m"), dict) else {}
        start = centerline.get("start")
        end = centerline.get("end")
        if isinstance(start, list) and isinstance(end, list) and len(start) == 3 and len(end) == 3:
            origin = [(float(start[i]) + float(end[i])) / 2.0 for i in range(3)]
    if not isinstance(origin, list) or len(origin) != 3:
        return [0.0, 0.0, 0.0]
    return [float(value) for value in origin]


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    try:
        return list(value)
    except TypeError:
        return [value]


def vector(value: Any, default: list[float] | None = None) -> list[float]:
    if isinstance(value, list) and len(value) == 3:
        return [float(item) for item in value]
    if isinstance(value, tuple) and len(value) == 3:
        return [float(item) for item in value]
    return list(default or [0.0, 0.0, 0.0])


def dot(a: list[float], b: list[float]) -> float:
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def distance(a: list[float], b: list[float]) -> float:
    return sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)) ** 0.5


def center_from_box(box: Any, fallback: list[float]) -> list[float]:
    values = as_list(box)
    if len(values) != 6:
        return fallback
    try:
        nums = [float(item) for item in values]
    except (TypeError, ValueError):
        return fallback
    return [(nums[i] + nums[i + 3]) / 2.0 for i in range(3)]


def component_display_name(component: Any) -> str:
    for attr in ("Name2", "Name", "name"):
        value = getattr(component, attr, None)
        if value:
            return str(value)
    for method in ("GetName2", "GetName", "GetPathName"):
        func = getattr(component, method, None)
        if callable(func):
            try:
                value = func()
            except Exception:
                value = None
            if value:
                return str(value)
    return ""


def names_match(actual: str, expected: str) -> bool:
    left = str(actual or "").strip().casefold()
    right = str(expected or "").strip().casefold()
    return bool(left and right and (left == right or left.startswith(f"{right}/") or left.startswith(f"{right}@")))


def assembly_components(assembly: Any) -> list[Any]:
    for args in ((False,), (True,), tuple()):
        try:
            return as_list(assembly.GetComponents(*args))
        except Exception:
            continue
    return []


def find_component(assembly: Any, component_name: str) -> Any | None:
    for component in assembly_components(assembly):
        if names_match(component_display_name(component), component_name):
            return component
    return None


def component_bodies(component: Any) -> list[Any]:
    for method, args in (("GetBodies3", (0, None)), ("GetBodies3", (0, True)), ("GetBodies2", (0,)), ("GetBodies", tuple())):
        func = getattr(component, method, None)
        if not callable(func):
            continue
        try:
            bodies = as_list(func(*args))
        except Exception:
            continue
        if bodies:
            return bodies
    return []


def body_faces(body: Any) -> list[Any]:
    func = getattr(body, "GetFaces", None)
    if not callable(func):
        return []
    try:
        return as_list(func())
    except Exception:
        return []


def component_faces(component: Any) -> list[Any]:
    faces: list[Any] = []
    for body in component_bodies(component):
        faces.extend(body_faces(body))
    return faces


def surface_for_face(face: Any) -> Any | None:
    func = getattr(face, "GetSurface", None)
    if not callable(func):
        return None
    try:
        return func()
    except Exception:
        return None


def surface_bool(surface: Any, method: str) -> bool:
    func = getattr(surface, method, None)
    if not callable(func):
        return False
    try:
        return bool(func())
    except Exception:
        return False


def surface_params(surface: Any, method: str) -> list[float]:
    func = getattr(surface, method, None)
    if not callable(func):
        return []
    try:
        return [float(item) for item in as_list(func())]
    except Exception:
        return []


def select_data(assembly: Any) -> Any:
    manager = getattr(assembly, "SelectionManager", None)
    func = getattr(manager, "CreateSelectData", None)
    if callable(func):
        try:
            return func()
        except Exception:
            return None
    return None


def select_entity(entity: Any, assembly: Any, append: bool) -> bool:
    func = getattr(entity, "Select4", None)
    if not callable(func):
        return False
    try:
        ok = bool(func(bool(append), select_data(assembly)))
    except TypeError:
        ok = bool(func(bool(append), None))
    if ok and hasattr(assembly, "_native_selected_count"):
        try:
            assembly._native_selected_count += 1
        except Exception:
            pass
    return ok


def best_planar_face(component: Any, fallback: dict[str, Any]) -> Any | None:
    expected_normal = vector(fallback.get("normal"), [0.0, 0.0, 0.0])
    expected_origin = vector(fallback.get("origin_m"), [0.0, 0.0, 0.0])
    best: tuple[float, Any] | None = None
    for face in component_faces(component):
        surface = surface_for_face(face)
        if surface is None or not surface_bool(surface, "IsPlane"):
            continue
        params = surface_params(surface, "PlaneParams")
        normal = params[3:6] if len(params) >= 6 else expected_normal
        normal_score = abs(dot(normal, expected_normal)) if any(expected_normal) else 1.0
        if normal_score < 0.8:
            continue
        face_center = center_from_box(getattr(face, "GetBox", lambda: [])(), expected_origin)
        score = distance(face_center, expected_origin) - normal_score
        if best is None or score < best[0]:
            best = (score, face)
    return best[1] if best else None


def best_cylindrical_face(component: Any, fallback: dict[str, Any]) -> Any | None:
    expected_axis = vector(fallback.get("axis"), [0.0, 0.0, 0.0])
    expected_origin = vector(fallback.get("origin_m"), [0.0, 0.0, 0.0])
    expected_radius = fallback.get("radius_m")
    best: tuple[float, Any] | None = None
    for face in component_faces(component):
        surface = surface_for_face(face)
        if surface is None or not surface_bool(surface, "IsCylinder"):
            continue
        params = surface_params(surface, "CylinderParams")
        if len(params) < 7:
            continue
        origin = params[:3]
        axis = params[3:6]
        radius = params[6]
        axis_score = abs(dot(axis, expected_axis)) if any(expected_axis) else 1.0
        if axis_score < 0.8:
            continue
        radius_penalty = abs(radius - float(expected_radius)) if expected_radius not in (None, "") else 0.0
        score = distance(origin, expected_origin) + radius_penalty - axis_score
        if best is None or score < best[0]:
            best = (score, face)
    return best[1] if best else None


def native_select_with_action(assembly: Any, action: dict[str, Any]) -> dict[str, Any]:
    component = find_component(assembly, str(action.get("component") or ""))
    if component is None:
        return {"ok": False, "method": "native_component_face", "error": "component_not_found"}
    fallback = action.get("fallback") if isinstance(action.get("fallback"), dict) else {}
    if action.get("fallback_type") == "bbox_planar_face":
        entity = best_planar_face(component, fallback)
    elif action.get("fallback_type") == "cylindrical_axis":
        entity = best_cylindrical_face(component, fallback)
    else:
        entity = None
    if entity is None:
        return {"ok": False, "method": "native_component_face", "error": "entity_not_found"}
    ok = select_entity(entity, assembly, bool(action["append"]))
    return {"ok": ok, "method": "Face.Select4", "component": component_display_name(component), "entity": entity}


def selection_action(selector: dict[str, Any], append: bool) -> dict[str, Any]:
    fallback = selector.get("fallback") if isinstance(selector.get("fallback"), dict) else {}
    fallback_type = str(fallback.get("type") or "")
    origin = selector_origin(selector)
    return {
        "stable_id": selector.get("stable_id"),
        "component": selector.get("component"),
        "type": FALLBACK_SELECT_TYPES.get(fallback_type, "FACE"),
        "xyz_m": origin,
        "append": append,
        "strategy": selector.get("strategy"),
        "fallback_type": fallback_type,
        "fallback": fallback,
        "width_role": selector.get("width_role") or fallback.get("width_role"),
    }


def planned_mate(item: dict[str, Any]) -> dict[str, Any]:
    selectors = [selector for selector in item.get("selection_selectors", []) if isinstance(selector, dict)]
    return {
        "group_id": item.get("group_id"),
        "mate_type": str(item.get("mate_type", "")).casefold(),
        "expected_mate_name": item.get("expected_mate_name"),
        "components": item.get("components", []),
        "distance_m": float(item.get("distance_m", 0.0) or 0.0),
        "distance_min_m": optional_float(item.get("distance_min_m")),
        "distance_max_m": optional_float(item.get("distance_max_m")),
        "angle_rad": mate_angle_rad(item),
        "angle_min_rad": optional_angle_rad(item, "angle_min_rad", "angle_min_deg"),
        "angle_max_rad": optional_angle_rad(item, "angle_max_rad", "angle_max_deg"),
        "width_constraint_type": int(item.get("width_constraint_type", item.get("constraint_type", 0)) or 0),
        "width_distance_m": optional_float(item.get("width_distance_m")),
        "flip": bool(item.get("flip", False)),
        "selection_actions": [selection_action(selector, append=index > 0) for index, selector in enumerate(selectors)],
    }


def select_with_action(assembly: Any, action: dict[str, Any]) -> dict[str, Any]:
    native = native_select_with_action(assembly, action)
    if native.get("ok"):
        action["method"] = native.get("method")
        return native
    x, y, z = action["xyz_m"]
    callout = None
    try:
        ok = bool(assembly.Extension.SelectByID2("", action["type"], x, y, z, bool(action["append"]), 0, callout, 0))
    except TypeError:
        ok = bool(assembly.Extension.SelectByID2("", action["type"], x, y, z, bool(action["append"]), 0, None, 0))
    action["method"] = "SelectByID2"
    return {"ok": ok, "method": "SelectByID2", "native_attempt": native}


def selected_count(assembly: Any) -> int:
    try:
        return int(assembly.SelectionManager.GetSelectedObjectCount2(-1))
    except Exception:
        return 0


def required_selector_count(mate_type: str) -> int:
    if mate_type == "width":
        return 4
    if mate_type == "symmetry":
        return 3
    return 2


def public_select_report(report: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in report.items() if key != "entity"}


def call_member(obj: Any, name: str, *args: Any) -> Any:
    value = getattr(obj, name, None)
    if callable(value):
        return value(*args)
    return value


def feature_name(feature: Any) -> str:
    for attr in ("Name", "name"):
        value = getattr(feature, attr, None)
        if value:
            return str(value)
    for method in ("GetName", "GetNameForSelection"):
        func = getattr(feature, method, None)
        if callable(func):
            try:
                value = func()
            except Exception:
                value = None
            if value:
                return str(value)
    return ""


def iter_sibling_features(first: Any) -> list[Any]:
    result: list[Any] = []
    feature = first
    seen: set[int] = set()
    while feature is not None and id(feature) not in seen:
        seen.add(id(feature))
        result.append(feature)
        try:
            feature = call_member(feature, "GetNextFeature")
        except Exception:
            feature = None
    return result


def iter_sub_features(feature: Any) -> list[Any]:
    try:
        first = call_member(feature, "GetFirstSubFeature")
    except Exception:
        first = None
    return iter_sibling_features(first)


def iter_document_features(assembly: Any) -> list[Any]:
    try:
        first = call_member(assembly, "FirstFeature")
    except Exception:
        first = None
    result: list[Any] = []
    stack = list(reversed(iter_sibling_features(first)))
    seen: set[int] = set()
    while stack:
        feature = stack.pop()
        if id(feature) in seen:
            continue
        seen.add(id(feature))
        result.append(feature)
        stack.extend(reversed(iter_sub_features(feature)))
    return result


def find_feature_by_name(assembly: Any, name: str) -> Any | None:
    for method in ("FeatureByName", "GetFeatureByName"):
        func = getattr(assembly, method, None)
        if callable(func):
            try:
                feature = func(name)
            except Exception:
                feature = None
            if feature is not None:
                return feature
    for feature in iter_document_features(assembly):
        if feature_name(feature) == name:
            return feature
    return None


def select_feature(assembly: Any, feature: Any, name: str) -> bool:
    if hasattr(assembly, "ClearSelection2"):
        assembly.ClearSelection2(True)
    for args in ((False, 0), (False,)):
        func = getattr(feature, "Select2", None)
        if callable(func):
            try:
                if bool(func(*args)):
                    return True
            except Exception:
                pass
    try:
        return bool(assembly.Extension.SelectByID2(name, "MATE", 0, 0, 0, False, 0, None, 0))
    except Exception:
        return False


def suppress_selected_feature(assembly: Any, feature: Any) -> bool:
    for method, args in (
        ("SetSuppression2", (0, 2, None)),
        ("SetSuppression2", (0,)),
        ("SetSuppression", (0,)),
    ):
        func = getattr(feature, method, None)
        if callable(func):
            try:
                if bool(func(*args)) or getattr(feature, "suppressed", False):
                    return True
            except Exception:
                pass
    for method in ("EditSuppress2", "EditSuppress"):
        func = getattr(assembly, method, None)
        if callable(func):
            try:
                result = func()
                return True if result is None else bool(result)
            except Exception:
                pass
    return False


def delete_selected_feature(assembly: Any) -> bool:
    extension = getattr(assembly, "Extension", None)
    for method, args in (("DeleteSelection2", (0,)), ("DeleteSelection2", (1,))):
        func = getattr(extension, method, None)
        if callable(func):
            try:
                if bool(func(*args)):
                    return True
            except Exception:
                pass
    for method in ("EditDelete", "DeleteSelection"):
        func = getattr(assembly, method, None)
        if callable(func):
            try:
                result = func()
                return True if result is None else bool(result)
            except Exception:
                pass
    return False


def execute_repair_action(assembly: Any, action: dict[str, Any]) -> dict[str, Any]:
    action_type = str(action.get("action") or "").casefold()
    target = str(action.get("target_mate") or action.get("mate") or action.get("target") or "")
    if action_type not in {"suppress_mate", "delete_mate"}:
        return {"ok": False, "action": action_type, "target_mate": target, "error": "unsupported_execution_action"}
    if not target:
        return {"ok": False, "action": action_type, "target_mate": target, "error": "missing_target_mate"}
    feature = find_feature_by_name(assembly, target)
    if feature is None:
        return {"ok": False, "action": action_type, "target_mate": target, "error": "mate_feature_not_found"}
    selected = select_feature(assembly, feature, target)
    if not selected:
        return {"ok": False, "action": action_type, "target_mate": target, "error": "mate_feature_not_selected"}
    ok = delete_selected_feature(assembly) if action_type == "delete_mate" else suppress_selected_feature(assembly, feature)
    if ok and hasattr(assembly, "ForceRebuild3"):
        assembly.ForceRebuild3(False)
    return {
        "ok": ok,
        "action": action_type,
        "target_mate": target,
        "feature_name": feature_name(feature),
        "selected": selected,
        "api": "DeleteSelection2" if action_type == "delete_mate" else "EditSuppress2",
    }


def mate_angle_rad(item: dict[str, Any]) -> float:
    raw_rad = item.get("angle_rad")
    if raw_rad not in (None, ""):
        try:
            return float(raw_rad)
        except (TypeError, ValueError):
            return 0.0
    raw_deg = item.get("angle_deg")
    if raw_deg not in (None, ""):
        try:
            return math.radians(float(raw_deg))
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_angle_rad(item: dict[str, Any], rad_key: str, deg_key: str) -> float | None:
    raw_rad = item.get(rad_key)
    if raw_rad not in (None, ""):
        try:
            return float(raw_rad)
        except (TypeError, ValueError):
            return None
    raw_deg = item.get(deg_key)
    if raw_deg not in (None, ""):
        try:
            return math.radians(float(raw_deg))
        except (TypeError, ValueError):
            return None
    return None


def add_selected_mate(assembly: Any, item: dict[str, Any]) -> dict[str, Any]:
    mate_type = str(item.get("mate_type", "")).casefold()
    if mate_type not in MATE_TYPES:
        return {"ok": False, "error": "unsupported_mate_type", "mate_type": mate_type}
    distance = float(item.get("distance_m", 0.0) or 0.0)
    distance_upper = optional_float(item.get("distance_max_m"))
    distance_lower = optional_float(item.get("distance_min_m"))
    if distance_upper is None:
        distance_upper = distance
    if distance_lower is None:
        distance_lower = distance
    angle = mate_angle_rad(item)
    angle_upper = optional_angle_rad(item, "angle_max_rad", "angle_max_deg")
    angle_lower = optional_angle_rad(item, "angle_min_rad", "angle_min_deg")
    if angle_upper is None:
        angle_upper = angle
    if angle_lower is None:
        angle_lower = angle
    mate_error = 0
    feature = assembly.AddMate5(
        MATE_TYPES[mate_type],
        -1,
        bool(item.get("flip", False)),
        distance,
        distance_upper,
        distance_lower,
        0,
        0,
        angle,
        angle_upper,
        angle_lower,
        0,
        False,
        False,
        0,
        mate_error,
    )
    if feature is not None and item.get("expected_mate_name"):
        try:
            feature.Name = str(item["expected_mate_name"])
        except Exception:
            pass
    return {
        "ok": feature is not None,
        "api": "AddMate5",
        "mate_type": mate_type,
        "expected_mate_name": item.get("expected_mate_name"),
        "distance_m": distance,
        "distance_max_m": distance_upper,
        "distance_min_m": distance_lower,
        "angle_rad": angle,
        "angle_max_rad": angle_upper,
        "angle_min_rad": angle_lower,
        "mate_error": mate_error,
    }


def add_width_mate(assembly: Any, item: dict[str, Any], select_reports: list[dict[str, Any]]) -> dict[str, Any]:
    entities = [report.get("entity") for report in select_reports]
    if len(entities) != 4 or any(entity is None for entity in entities):
        return {"ok": False, "error": "width_mate_requires_four_native_face_entities", "mate_type": "width"}
    create_data = getattr(assembly, "CreateMateData", None)
    create_mate = getattr(assembly, "CreateMate", None)
    if not callable(create_data) or not callable(create_mate):
        return {"ok": False, "error": "width_mate_create_data_unavailable", "mate_type": "width"}
    data = create_data(MATE_TYPES["width"])
    data.WidthSelection = entities[:2]
    data.TabSelection = entities[2:]
    data.ConstraintType = int(item.get("width_constraint_type", item.get("constraint_type", 0)) or 0)
    if item.get("width_distance_m") not in (None, ""):
        try:
            data.Distance = float(item["width_distance_m"])
        except (TypeError, ValueError):
            pass
    feature = create_mate(data)
    if feature is not None and item.get("expected_mate_name"):
        try:
            feature.Name = str(item["expected_mate_name"])
        except Exception:
            pass
    return {
        "ok": feature is not None,
        "api": "CreateMateData/CreateMate",
        "mate_type": "width",
        "expected_mate_name": item.get("expected_mate_name"),
        "width_constraint_type": data.ConstraintType,
        "width_selection_count": len(data.WidthSelection),
        "tab_selection_count": len(data.TabSelection),
    }


def execute_manifest(manifest: dict[str, Any], assembly: Any) -> dict[str, Any]:
    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "accepted": []}
    executed_actions: list[dict[str, Any]] = []
    executed: list[dict[str, Any]] = []
    seen_actions: set[tuple[str, str]] = set()
    for action in [item for item in manifest.get("execution_actions", []) if isinstance(item, dict)]:
        key = (str(action.get("action")), str(action.get("target_mate") or action.get("target") or action.get("mate")))
        if key in seen_actions:
            continue
        seen_actions.add(key)
        result = execute_repair_action(assembly, action)
        executed_actions.append(result)
        if result.get("ok"):
            findings["accepted"].append({
                "kind": "repair_action_executed",
                "mate": result.get("target_mate"),
                "reason": f"{result.get('action')} completed before mate creation",
            })
        else:
            findings["blocking"].append({
                "kind": "repair_action_failed",
                "mate": result.get("target_mate"),
                "reason": result.get("error", "repair action failed"),
                "detail": result,
            })
    for item in [macro for macro in manifest.get("macros", []) if isinstance(macro, dict)]:
        for action in [a for a in item.get("execution_actions", []) if isinstance(a, dict)]:
            key = (str(action.get("action")), str(action.get("target_mate") or action.get("target") or action.get("mate")))
            if key in seen_actions:
                continue
            seen_actions.add(key)
            result = execute_repair_action(assembly, action)
            executed_actions.append(result)
            if result.get("ok"):
                findings["accepted"].append({
                    "kind": "repair_action_executed",
                    "mate": result.get("target_mate"),
                    "reason": f"{result.get('action')} completed before mate creation",
                })
            else:
                findings["blocking"].append({
                    "kind": "repair_action_failed",
                    "mate": result.get("target_mate"),
                    "reason": result.get("error", "repair action failed"),
                    "detail": result,
                })
        plan = planned_mate(item)
        required_count = required_selector_count(plan["mate_type"])
        if len(plan["selection_actions"]) != required_count:
            findings["blocking"].append({
                "kind": "selector_count",
                "mate": item.get("expected_mate_name"),
                "reason": f"live {plan['mate_type']} mate execution requires exactly {required_count} reviewed selection selectors",
                "detail": plan,
            })
            continue
        if hasattr(assembly, "ClearSelection2"):
            assembly.ClearSelection2(True)
        if hasattr(assembly, "_native_selected_count"):
            assembly._native_selected_count = 0
        select_reports = [select_with_action(assembly, action) for action in plan["selection_actions"]]
        count = selected_count(assembly)
        guard = {
            "cleared_selection_count": 0,
            "selection_count_before_mate": count,
            "component_pair": item.get("components", []),
            "select_by_id_calls": plan["selection_actions"],
            "select_results": [bool(report.get("ok")) for report in select_reports],
            "selection_reports": [public_select_report(report) for report in select_reports],
        }
        if count != required_count or not all(report.get("ok") for report in select_reports):
            findings["blocking"].append({
                "kind": "selection_failed",
                "mate": item.get("expected_mate_name"),
                "reason": f"selector execution did not produce exactly {required_count} selected entities",
                "detail": guard,
            })
            continue
        mate_result = add_width_mate(assembly, item, select_reports) if plan["mate_type"] == "width" else add_selected_mate(assembly, item)
        mate_result["selection_guard"] = guard
        mate_result["selected_entities"] = count
        if mate_result["ok"]:
            if hasattr(assembly, "ForceRebuild3"):
                assembly.ForceRebuild3(False)
            findings["accepted"].append({
                "kind": "mate_executed",
                "mate": item.get("expected_mate_name"),
                "reason": f"selected entities were mated with {mate_result.get('api')} and rebuild was requested",
            })
        else:
            findings["blocking"].append({
                "kind": "addmate_failed",
                "mate": item.get("expected_mate_name"),
                "reason": mate_result.get("error", "AddMate5 did not return a feature"),
                "detail": mate_result,
            })
        executed.append(mate_result)
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not findings["blocking"],
        "mode": "mate_group_live_execute",
        "document": manifest.get("document", {}),
        "counts": {
            "planned_mates": len([m for m in manifest.get("macros", []) if isinstance(m, dict)]),
            "executed_actions": len([action for action in executed_actions if action.get("ok")]),
            "executed_mates": len([m for m in executed if m.get("ok")]),
            "blocking_findings": len(findings["blocking"]),
        },
        "executed_actions": executed_actions,
        "executed_mates": executed,
        "findings": findings,
    }


def dry_run_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    planned = [planned_mate(item) for item in manifest.get("macros", []) if isinstance(item, dict)]
    planned_actions = [item for item in manifest.get("execution_actions", []) if isinstance(item, dict)]
    blockers = []
    for item in planned:
        required_count = required_selector_count(item["mate_type"])
        if len(item["selection_actions"]) != required_count:
            blockers.append({
                "kind": "selector_count",
                "mate": item.get("expected_mate_name"),
                "reason": f"dry-run found a {item['mate_type']} mate without exactly {required_count} executable selectors",
                "detail": item,
            })
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not blockers,
        "mode": "mate_group_live_execute",
        "dry_run": True,
        "document": manifest.get("document", {}),
        "counts": {
            "planned_actions": len(planned_actions),
            "planned_mates": len(planned),
            "executable_mates": len(planned) - len(blockers),
            "blocking_findings": len(blockers),
        },
        "planned_actions": planned_actions,
        "planned_mates": planned,
        "findings": {"blocking": blockers, "warning": [], "accepted": []},
    }


def attach_active_assembly() -> Any:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore

    pythoncom.CoInitialize()
    sw = win32com.client.Dispatch("SldWorks.Application")
    doc = sw.ActiveDoc
    if doc is None:
        raise RuntimeError("No active SolidWorks document")
    if int(doc.GetType()) != 2:
        raise RuntimeError("Active SolidWorks document is not an assembly")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute reviewed mate group selectors in a live SolidWorks assembly")
    parser.add_argument("--macro-manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = load_json(Path(args.macro_manifest))
    result = dry_run_manifest(manifest) if args.dry_run else execute_manifest(manifest, attach_active_assembly())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "execution_ok": result["ok"], "out": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
