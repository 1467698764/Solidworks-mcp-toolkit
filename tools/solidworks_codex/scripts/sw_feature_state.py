"""Change SolidWorks feature state or feature-scoped dimensions and emit JSON evidence.

Supported actions: suppress, unsuppress, delete, set-dimension, reorder, edit-definition.
Works on the active part/assembly document, or opens a provided model path.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import pythoncom  # type: ignore[import-not-found]
    import win32com.client  # type: ignore[import-not-found]
except ModuleNotFoundError:  # offline tests can import helpers without pywin32
    pythoncom = None  # type: ignore[assignment]
    win32com = None  # type: ignore[assignment]


def require_pywin32() -> tuple[Any, Any]:
    if pythoncom is None or win32com is None:
        raise RuntimeError(
            "SolidWorks live COM commands require pywin32. "
            "Install pywin32 or set SWCODEX_PYTHON to a Python that can import pythoncom and win32com.client."
        )
    return pythoncom, win32com.client


def val(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "_oleobj_"):
        return value
    if isinstance(value, (list, tuple)):
        return [val(v) for v in value]
    return str(value)


def read(obj: Any, name: str, *args: Any) -> Any:
    try:
        member = getattr(obj, name)
        if args:
            if callable(member):
                return val(member(*args))
            return {"error": f"member {name} is a property, arguments were provided"}
        if hasattr(member, "_oleobj_"):
            return member
        if callable(member):
            return val(member())
        return val(member)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def attach(start: bool) -> tuple[Any, bool]:
    _pythoncom, win32_client = require_pywin32()
    try:
        return win32_client.GetActiveObject("SldWorks.Application"), False
    except Exception as exc:
        if not start:
            raise RuntimeError("SolidWorks is not running. Start it or pass --start.") from exc
        sw = win32_client.Dispatch("SldWorks.Application")
        sw.Visible = True
        return sw, True


def open_or_active(sw: Any, model_path: str | None) -> Any:
    if not model_path:
        model = read(sw, "ActiveDoc")
        if model is None or isinstance(model, dict):
            raise RuntimeError("No active SolidWorks document. Open a document or pass --model.")
        return model
    path = str(Path(model_path).resolve())
    doc_type = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}.get(Path(path).suffix.lower())
    if doc_type is None:
        raise ValueError(f"Unsupported SolidWorks file type: {path}")
    _pythoncom, win32_client = require_pywin32()
    errors = win32_client.VARIANT(_pythoncom.VT_BYREF | _pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(_pythoncom.VT_BYREF | _pythoncom.VT_I4, 0)
    model = sw.OpenDoc6(path, doc_type, 0, "", errors, warnings)
    if model is None:
        raise RuntimeError(f"OpenDoc6 failed: errors={errors.value}, warnings={warnings.value}, path={path}")
    return model


def feature_name(feature: Any) -> Any:
    name = read(feature, "Name")
    if isinstance(name, str):
        return name
    return read(feature, "GetNameForSelection")


def feature_type(feature: Any) -> Any:
    type_name = read(feature, "GetTypeName2")
    if isinstance(type_name, str):
        return type_name
    return read(feature, "GetTypeName")


def is_suppressed(feature: Any) -> Any:
    for args in ((2, None), (2, []), ()):
        result = read(feature, "IsSuppressed2", *args)
        if not isinstance(result, dict):
            return result
    return read(feature, "IsSuppressed")


def iter_feature_chain(first: Any) -> list[Any]:
    result: list[Any] = []
    seen: set[int] = set()
    current = first
    while current is not None and not isinstance(current, dict):
        ident = id(current)
        if ident in seen:
            break
        seen.add(ident)
        result.append(current)
        sub = read(current, "GetFirstSubFeature")
        result.extend(iter_feature_chain(sub))
        current = read(current, "GetNextFeature")
    return result


def list_features(model: Any) -> list[Any]:
    return iter_feature_chain(read(model, "FirstFeature"))


def feature_order(model: Any) -> list[str]:
    return [name for name in (feature_name(feature) for feature in list_features(model)) if isinstance(name, str)]


def snapshot(feature: Any | None) -> dict[str, Any] | None:
    if feature is None:
        return None
    return {
        "name": feature_name(feature),
        "type": feature_type(feature),
        "suppressed": is_suppressed(feature),
        "select_name": read(feature, "GetNameForSelection"),
    }


def find_feature(model: Any, query: str) -> Any:
    exact = []
    contains = []
    for feature in list_features(model):
        name = feature_name(feature)
        select_name = read(feature, "GetNameForSelection")
        candidates = [x for x in (name, select_name) if isinstance(x, str)]
        if any(x == query for x in candidates):
            exact.append(feature)
        elif any(query.lower() in x.lower() for x in candidates):
            contains.append(feature)
    matches = exact or contains
    if not matches:
        raise RuntimeError(f"Feature not found by name: {query}")
    if len(matches) > 1:
        names = [feature_name(f) for f in matches[:20]]
        raise RuntimeError(f"Feature name is ambiguous for {query}: {names}")
    return matches[0]


def select_feature(feature: Any) -> Any:
    result = read(feature, "Select2", False, 0)
    if not isinstance(result, dict):
        return result
    return read(feature, "Select", False)


def set_suppression(feature: Any, suppress: bool) -> Any:
    action = 0 if suppress else 1
    for args in ((action, 2, None), (action, 2, []), (action,)):
        result = read(feature, "SetSuppression2", *args)
        if not isinstance(result, dict):
            return result
    return read(feature, "SetSuppression", action)


def delete_selected(model: Any) -> Any:
    extension = read(model, "Extension")
    if extension is not None and not isinstance(extension, dict):
        result = read(extension, "DeleteSelection2", 0)
        if not isinstance(result, dict):
            return result
    result = read(model, "EditDelete")
    if not isinstance(result, dict):
        return result
    return read(model, "DeleteSelection", False)


def resolve_feature_dimension(model: Any, feature: Any, dimension_query: str) -> tuple[Any, str]:
    if not dimension_query:
        raise ValueError("set-dimension requires a dimension name or feature-local dimension token")
    feature_names = [item for item in (feature_name(feature), read(feature, "GetNameForSelection")) if isinstance(item, str)]
    candidates = [dimension_query]
    if "@" not in dimension_query:
        candidates.extend(f"{dimension_query}@{name}" for name in feature_names)
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        dim = read(model, "Parameter", candidate)
        if dim is not None and not isinstance(dim, dict):
            return dim, candidate
    raise RuntimeError(f"Dimension not found for feature {feature_names[:2]}: {dimension_query}")


def set_feature_dimension(model: Any, feature: Any, dimension_query: str, value_m: float) -> dict[str, Any]:
    dim, resolved = resolve_feature_dimension(model, feature, dimension_query)
    before = read(dim, "SystemValue")
    try:
        dim.SystemValue = float(value_m)
    except Exception as exc:
        raise RuntimeError(f"Could not set dimension {resolved} to {value_m}: {exc}") from exc
    after = read(dim, "SystemValue")
    return {"name": resolved, "before_m": before, "after_m": after, "target_m": float(value_m)}


def load_definition_spec(path: str) -> dict[str, Any]:
    if not path:
        raise ValueError("edit-definition requires --definition-spec")
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("definition spec must be a JSON object")
    edits = data.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ValueError("definition spec requires non-empty edits list")
    for edit in edits:
        if not isinstance(edit, dict) or not isinstance(edit.get("property"), str) or "value" not in edit:
            raise ValueError("each definition edit requires property and value")
        prop = edit["property"]
        if not prop.replace("_", "").isalnum() or prop.startswith("_"):
            raise ValueError(f"unsupported definition property name: {prop}")
        if not isinstance(edit["value"], (str, int, float, bool)) and edit["value"] is not None:
            raise ValueError(f"unsupported definition value for {prop}")
    return data


def definition_value(definition: Any, prop: str) -> Any:
    try:
        return val(getattr(definition, prop))
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def edit_feature_definition(model: Any, feature: Any, spec: dict[str, Any]) -> dict[str, Any]:
    definition = read(feature, "GetDefinition")
    if definition is None or isinstance(definition, dict):
        raise RuntimeError("Feature.GetDefinition is unavailable; cannot edit definition object")
    edits = [item for item in spec.get("edits", []) if isinstance(item, dict)]
    before = {str(edit["property"]): definition_value(definition, str(edit["property"])) for edit in edits}
    access = read(definition, "AccessSelections", model, None)
    for edit in edits:
        setattr(definition, str(edit["property"]), edit["value"])
    modify = read(feature, "ModifyDefinition", definition, model, None)
    release = read(definition, "ReleaseSelectionAccess")
    after = {str(edit["property"]): definition_value(definition, str(edit["property"])) for edit in edits}
    return {
        "ok": bool(modify) and not isinstance(modify, dict),
        "properties": [str(edit["property"]) for edit in edits],
        "before": before,
        "after": after,
        "access_selections": {"ok": bool(access) and not isinstance(access, dict), "raw": access},
        "modify_definition": {"ok": bool(modify) and not isinstance(modify, dict), "raw": modify},
        "release_selection_access": {"ok": bool(release) and not isinstance(release, dict), "raw": release},
    }


def operation_role(action: str) -> str:
    return {
        "suppress": "feature_deactivation",
        "unsuppress": "feature_reactivation",
        "delete": "feature_removal",
        "set-dimension": "feature_parameter_adjustment",
        "reorder": "feature_reorder",
        "edit-definition": "feature_definition_edit",
    }.get(action, "feature_state_change")


def action_evidence(
    *,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    before_feature_count: int,
    after_feature_count: int,
    action_result: dict[str, Any],
    before_order: list[str] | None = None,
    after_order: list[str] | None = None,
) -> dict[str, Any]:
    dimension = action_result.get("dimension") if isinstance(action_result, dict) else None
    before_value = dimension.get("before_m") if isinstance(dimension, dict) else None
    after_value = dimension.get("after_m") if isinstance(dimension, dict) else None
    parameter_delta = None
    if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
        parameter_delta = after_value - before_value
    changed_feature = None
    for candidate in (after, before):
        if isinstance(candidate, dict) and isinstance(candidate.get("name"), str):
            changed_feature = candidate["name"]
            break
    selected = action_result.get("select") if isinstance(action_result, dict) else None
    change_scope = {
        "suppress": "feature_state",
        "unsuppress": "feature_state",
        "delete": "feature_tree",
        "set-dimension": "feature_dimension",
        "reorder": "feature_tree_order",
        "edit-definition": "feature_definition",
    }.get(action, "feature")
    evidence = {
        "operation_role": operation_role(action),
        "change_scope": change_scope,
        "changed_feature": changed_feature,
        "feature_count_delta": after_feature_count - before_feature_count,
        "selection_evidence": {"selected": selected},
    }
    if isinstance(dimension, dict):
        evidence.update(
            {
                "changed_parameter": dimension.get("name"),
                "parameter_before_m": before_value,
                "parameter_after_m": after_value,
                "parameter_target_m": dimension.get("target_m"),
                "parameter_delta_m": parameter_delta,
            }
        )
    reorder = action_result.get("reorder") if isinstance(action_result, dict) else None
    if isinstance(reorder, dict):
        evidence.update(
            {
                "reorder_target_feature": reorder.get("target_feature"),
                "reorder_position": reorder.get("position"),
                "feature_order_before": before_order,
                "feature_order_after": after_order,
            }
        )
    definition = action_result.get("definition") if isinstance(action_result, dict) else None
    if isinstance(definition, dict):
        evidence.update(
            {
                "changed_definition_properties": definition.get("properties", []),
                "definition_before": definition.get("before", {}),
                "definition_after": definition.get("after", {}),
                "definition_access": definition.get("access_selections"),
                "definition_modify": definition.get("modify_definition"),
                "definition_release": definition.get("release_selection_access"),
            }
        )
    return evidence


def reorder_feature(model: Any, feature: Any, target_query: str, position: str) -> dict[str, Any]:
    if not target_query:
        raise ValueError("reorder requires target_feature")
    position = position.lower().strip()
    if position not in {"before", "after"}:
        raise ValueError("reorder_position must be before or after")
    target = find_feature(model, target_query)
    source_name = feature_name(feature)
    target_name = feature_name(target)
    if source_name == target_name:
        raise ValueError("reorder source and target feature must differ")
    feature_manager = read(model, "FeatureManager")
    if feature_manager is None or isinstance(feature_manager, dict):
        raise RuntimeError("Model.FeatureManager is unavailable; cannot reorder feature")
    for method, args in (
        ("ReorderFeature", (source_name, target_name, position)),
        ("ReorderFeature2", (source_name, target_name, position)),
        ("EditReorder", (source_name, target_name, position)),
    ):
        result = read(feature_manager, method, *args)
        if not isinstance(result, dict):
            return {"ok": bool(result), "method": method, "source_feature": source_name, "target_feature": target_name, "position": position, "raw": result}
    raise RuntimeError(f"Could not reorder feature {source_name} {position} {target_name}")


def apply_action(
    model: Any,
    feature: Any,
    action: str,
    dimension: str = "",
    value_m: float | None = None,
    target_feature: str = "",
    reorder_position: str = "after",
    definition_spec: dict[str, Any] | None = None,
) -> Any:
    selection_result = select_feature(feature)
    if action == "suppress":
        return {"select": selection_result, "state": set_suppression(feature, True)}
    if action == "unsuppress":
        return {"select": selection_result, "state": set_suppression(feature, False)}
    if action == "delete":
        return {"select": selection_result, "delete": delete_selected(model)}
    if action == "set-dimension":
        if value_m is None:
            raise ValueError("set-dimension requires value_m")
        return {"select": selection_result, "dimension": set_feature_dimension(model, feature, dimension, value_m)}
    if action == "reorder":
        return {"select": selection_result, "reorder": reorder_feature(model, feature, target_feature, reorder_position)}
    if action == "edit-definition":
        if definition_spec is None:
            raise ValueError("edit-definition requires definition_spec")
        return {"select": selection_result, "definition": edit_feature_definition(model, feature, definition_spec)}
    raise ValueError(f"Unsupported action: {action}")


def save_model(model: Any) -> dict[str, Any]:
    pythoncom_mod, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    ok = model.Save3(1, errors, warnings)
    return {"ok": bool(ok), "errors": getattr(errors, "value", errors), "warnings": getattr(warnings, "value", warnings)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature", required=True, help="Feature name exact or unique substring")
    parser.add_argument("--action", required=True, choices=["suppress", "unsuppress", "delete", "set-dimension", "reorder", "edit-definition"])
    parser.add_argument("--dimension", default="", help="Exact dimension full name or feature-local token such as D1")
    parser.add_argument("--value-m", type=float, default=None)
    parser.add_argument("--target-feature", default="", help="Feature name exact or unique substring used by reorder")
    parser.add_argument("--reorder-position", default="after", choices=["before", "after"])
    parser.add_argument("--definition-spec", default="", help="JSON spec with reviewed feature definition edits")
    parser.add_argument("--model", default=None)
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/feature_state.json")
    args = parser.parse_args()
    pythoncom_mod, _win32_client = require_pywin32()
    pythoncom_mod.CoInitialize()
    sw, started = attach(args.start)
    model = open_or_active(sw, args.model)
    before_features = len(list_features(model))
    before_order = feature_order(model)
    feature = find_feature(model, args.feature)
    before = snapshot(feature)
    definition_spec = load_definition_spec(args.definition_spec) if args.action == "edit-definition" else None
    action_result = apply_action(
        model,
        feature,
        args.action,
        dimension=args.dimension,
        value_m=args.value_m,
        target_feature=args.target_feature,
        reorder_position=args.reorder_position,
        definition_spec=definition_spec,
    )
    rebuild_result = read(model, "ForceRebuild3", False)
    after = None if args.action == "delete" else snapshot(find_feature(model, args.feature))
    after_features = len(list_features(model))
    after_order = feature_order(model)
    evidence = action_evidence(
        action=args.action,
        before=before,
        after=after,
        before_feature_count=before_features,
        after_feature_count=after_features,
        action_result=action_result,
        before_order=before_order,
        after_order=after_order,
    )
    save_result = save_model(model) if args.save else None
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started,
        "document_title": read(model, "GetTitle"),
        "document_path": read(model, "GetPathName"),
        "feature_query": args.feature,
        "action": args.action,
        "dimension_query": args.dimension,
        "value_m": args.value_m,
        "target_feature_query": args.target_feature,
        "reorder_position": args.reorder_position,
        "definition_spec": definition_spec,
        "before_feature_count": before_features,
        "after_feature_count": after_features,
        "feature_order_before": before_order,
        "feature_order_after": after_order,
        "before": before,
        "after": after,
        "action_result": action_result,
        "execution_evidence": evidence,
        "operation_role": evidence["operation_role"],
        "change_scope": evidence["change_scope"],
        "rebuild_result": rebuild_result,
        "saved": args.save,
        "save_result": save_result,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
