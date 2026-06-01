"""Deep read-only SolidWorks assembly/document inspection for Codex.

Default behavior attaches only to an already-running SolidWorks instance and does not
modify or save documents. Pass --start to allow launching SolidWorks via COM.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SW_DOC_TYPES = {1: "part", 2: "assembly", 3: "drawing"}

def load_pywin32() -> tuple[Any, Any]:
    try:
        import pythoncom  # type: ignore[import-not-found]
        import win32com.client  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "SolidWorks live COM commands require pywin32. "
            "Install pywin32 or set SWCODEX_PYTHON to a Python that can import pythoncom and win32com.client."
        ) from exc
    return pythoncom, win32com.client



def safe_value(value: Any) -> Any:
    try:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if hasattr(value, "_oleobj_"):
            return value
        if isinstance(value, (list, tuple)):
            return [safe_value(v) for v in value]
        return str(value)
    except Exception as exc:  # pragma: no cover - defensive COM formatting
        return f"<unprintable {type(exc).__name__}: {exc}>"


def read_member(obj: Any, name: str, *args: Any) -> Any:
    try:
        member = getattr(obj, name)
        if args:
            if callable(member):
                return safe_value(member(*args))
            return {"error": f"member {name} is a property, arguments were provided"}
        if hasattr(member, "_oleobj_"):
            return member
        if callable(member):
            return safe_value(member())
        return safe_value(member)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def attach_solidworks(allow_start: bool) -> tuple[Any, bool]:
    _pythoncom, win32_client = load_pywin32()
    try:
        return win32_client.GetActiveObject("SldWorks.Application"), False
    except Exception as attach_error:
        if not allow_start:
            raise RuntimeError(
                "SolidWorks is not running. Start SolidWorks and rerun, or pass --start to launch it."
            ) from attach_error
        sw = win32_client.Dispatch("SldWorks.Application")
        try:
            sw.Visible = True
        except Exception:
            pass
        return sw, True


def iter_features(model: Any, limit: int) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    feat = read_member(model, "FirstFeature")
    while feat is not None and not isinstance(feat, dict) and len(features) < limit:
        item = {
            "name": read_member(feat, "Name"),
            "type": read_member(feat, "GetTypeName2"),
            "suppressed": read_member(feat, "IsSuppressed"),
        }
        # Some feature types expose custom info, but keep this generic and safe.
        features.append(item)
        feat = read_member(feat, "GetNextFeature")
    return features


def iter_display_dimensions(model: Any, limit: int) -> list[dict[str, Any]]:
    dims: list[dict[str, Any]] = []
    feat = read_member(model, "FirstFeature")
    while feat is not None and not isinstance(feat, dict) and len(dims) < limit:
        disp_dim = read_member(feat, "GetFirstDisplayDimension")
        while disp_dim is not None and not isinstance(disp_dim, dict) and len(dims) < limit:
            dim = read_member(disp_dim, "GetDimension")
            dim_item: dict[str, Any] = {
                "feature": read_member(feat, "Name"),
                "display_name": read_member(disp_dim, "GetNameForSelection"),
            }
            if dim is not None and not isinstance(dim, dict):
                dim_item.update(
                    {
                        "name": read_member(dim, "Name"),
                        "full_name": read_member(dim, "FullName"),
                        "system_value_m": read_member(dim, "SystemValue"),
                    }
                )
            else:
                dim_item["dimension_error"] = dim
            dims.append(dim_item)
            disp_dim = read_member(feat, "GetNextDisplayDimension", disp_dim)
        feat = read_member(feat, "GetNextFeature")
    return dims


def component_transform(comp: Any) -> Any:
    try:
        transform = getattr(comp, "Transform2")
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    if transform is None:
        return None
    data = read_member(transform, "ArrayData")
    if isinstance(data, list) and len(data) >= 12:
        arr = data[:16]
        return {
            "array": arr,
            "origin_m": [arr[9], arr[10], arr[11]],
            "local_axes": {
                "x": [arr[0], arr[1], arr[2]],
                "y": [arr[3], arr[4], arr[5]],
                "z": [arr[6], arr[7], arr[8]],
            },
            "scale": arr[12] if len(arr) > 12 else None,
        }
    return data


def component_bbox(comp: Any) -> Any:
    """Return an approximate component bounding box in meters when COM exposes it.

    SolidWorks Component2.GetBox returns six doubles for the component extents in
    assembly coordinates. This is rough but valuable for AI spatial reasoning;
    exact contact/interference must still be verified by dedicated tools.
    """
    box = read_member(comp, "GetBox", False, False)
    if isinstance(box, list) and len(box) == 6:
        return box
    return box


def inspect_components(model: Any, limit: int) -> list[dict[str, Any]]:
    comps = read_member(model, "GetComponents", False)
    items: list[dict[str, Any]] = []
    if isinstance(comps, dict) or not comps:
        return items
    for comp in list(comps)[:limit]:
        ref_cfg = read_member(comp, "ReferencedConfiguration")
        item = {
            "name2": read_member(comp, "Name2"),
            "path": read_member(comp, "GetPathName"),
            "referenced_configuration": ref_cfg,
            "suppressed": read_member(comp, "IsSuppressed"),
            "hidden": read_member(comp, "IsHidden", True),
            "fixed": read_member(comp, "IsFixed"),
            "lightweight": read_member(comp, "IsLightWeight"),
            "transform": component_transform(comp),
            "bbox_m": component_bbox(comp),
        }
        items.append(item)
    return items


def classify_mate_like_features(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mate_type_markers = ("mate", "Mate", "MateGroup", "MateReference")
    result = []
    for feat in features:
        text = f"{feat.get('name')} {feat.get('type')}"
        if any(marker in text for marker in mate_type_markers):
            result.append(feat)
    return result


def open_model_if_requested(sw: Any, path: str | None, pythoncom: Any, win32_client: Any) -> Any:
    if not path:
        return read_member(sw, "ActiveDoc")
    model_path = str(Path(path).resolve())
    suffix = Path(model_path).suffix.lower()
    doc_type = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}.get(suffix)
    if doc_type is None:
        raise ValueError(f"Unsupported SolidWorks file type: {model_path}")
    errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    model = sw.OpenDoc6(model_path, doc_type, 0, "", errors, warnings)
    if model is None:
        raise RuntimeError(f"OpenDoc6 failed: errors={errors.value}, warnings={warnings.value}, path={model_path}")
    return model


def inspect(allow_start: bool, feature_limit: int, component_limit: int, dimension_limit: int, model_path: str | None = None) -> dict[str, Any]:
    pythoncom, win32_client = load_pywin32()
    pythoncom.CoInitialize()
    sw, started_by_probe = attach_solidworks(allow_start)
    report: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started_by_probe,
        "revision_number": read_member(sw, "RevisionNumber"),
        "visible": read_member(sw, "Visible"),
    }

    model = open_model_if_requested(sw, model_path, pythoncom, win32_client)
    if isinstance(model, dict) or model is None:
        report["active_document"] = None
        report["note"] = "No active SolidWorks document detected."
        return report

    doc_type = read_member(model, "GetType")
    active: dict[str, Any] = {
        "title": read_member(model, "GetTitle"),
        "path": read_member(model, "GetPathName"),
        "type_code": doc_type,
        "type": SW_DOC_TYPES.get(doc_type, f"unknown:{doc_type}"),
        "configuration": None,
        "features": iter_features(model, feature_limit),
        "dimensions": iter_display_dimensions(model, dimension_limit),
    }

    cfg_mgr = read_member(model, "ConfigurationManager")
    if not isinstance(cfg_mgr, dict) and cfg_mgr is not None:
        active_cfg = read_member(cfg_mgr, "ActiveConfiguration")
        if not isinstance(active_cfg, dict) and active_cfg is not None:
            active["configuration"] = read_member(active_cfg, "Name")

    if doc_type == 2:
        components = inspect_components(model, component_limit)
        active["components"] = components
        active["component_count_sampled"] = len(components)
        active["mate_like_features"] = classify_mate_like_features(active["features"])

    report["active_document"] = active
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true", help="Allow launching SolidWorks if it is not running")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/assembly_inspect.json")
    parser.add_argument("--model", default=None, help="Optional SolidWorks file to open before inspection")
    parser.add_argument("--feature-limit", type=int, default=300)
    parser.add_argument("--component-limit", type=int, default=500)
    parser.add_argument("--dimension-limit", type=int, default=500)
    args = parser.parse_args()

    result = inspect(args.start, args.feature_limit, args.component_limit, args.dimension_limit, args.model)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
