"""Resolve a reviewed local standard-part catalog item into a component-insert spec."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def as_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def normalize_path(value: str, base: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def catalog_items(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    items = catalog.get("items", [])
    if isinstance(items, dict):
        return [dict(value, id=key) if isinstance(value, dict) and "id" not in value else value for key, value in items.items()]
    if not isinstance(items, list):
        raise ValueError("catalog.items must be an array or object")
    if not all(isinstance(item, dict) for item in items):
        raise ValueError("catalog.items entries must be JSON objects")
    return items


def match_item(catalog: dict[str, Any], request: dict[str, Any]) -> dict[str, Any] | None:
    requested_id = str(request.get("id") or request.get("part_id") or "").strip().lower()
    requested_standard = str(request.get("standard") or "").strip().lower()
    requested_size = str(request.get("size") or "").strip().lower()
    for item in catalog_items(catalog):
        item_id = str(item.get("id") or "").strip().lower()
        if requested_id and item_id == requested_id:
            return item
        if requested_standard and requested_standard != str(item.get("standard") or "").strip().lower():
            continue
        if requested_size and requested_size != str(item.get("size") or item.get("configuration") or "").strip().lower():
            continue
        if requested_standard or requested_size:
            return item
    return None


def source_policy(catalog: dict[str, Any], item: dict[str, Any], catalog_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    catalog_base = catalog_path.parent
    approved_roots = [normalize_path(str(root), catalog_base) for root in as_list(catalog.get("approved_roots"))]
    part_path = normalize_path(str(item.get("path") or item.get("part_path") or ""), catalog_base)
    suffix = part_path.suffix.lower()
    if suffix not in {".sldprt", ".sldasm"}:
        blockers.append({"kind": "unsupported_standard_part_suffix", "path": str(part_path), "allowed": [".SLDPRT", ".SLDASM"]})
    if not part_path.exists():
        blockers.append({"kind": "missing_standard_part_file", "path": str(part_path)})
    if approved_roots and not any(is_under(part_path, root) for root in approved_roots):
        blockers.append({"kind": "unapproved_source_root", "path": str(part_path), "approved_roots": [str(root) for root in approved_roots]})
    supplier = str(item.get("supplier") or "").strip()
    license_name = str(item.get("license") or item.get("license_policy") or "").strip()
    if not supplier:
        blockers.append({"kind": "missing_supplier_evidence", "item_id": str(item.get("id") or "")})
    if not license_name:
        blockers.append({"kind": "missing_license_policy", "item_id": str(item.get("id") or "")})
    return {
        "status": "approved_local_source" if not blockers else "blocked",
        "part_path": str(part_path),
        "approved_roots": [str(root) for root in approved_roots],
        "supplier": supplier,
        "license": license_name,
        "standard": str(item.get("standard") or "").strip(),
    }, blockers


def build_component_spec(item: dict[str, Any], request: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    attachment_request = request.get("attachment") if isinstance(request.get("attachment"), dict) else {}
    required_mates = as_list(request.get("required_mates") or attachment_request.get("required_mates") or item.get("required_mates"))
    attachment = {
        "role": str(attachment_request.get("role") or request.get("role") or item.get("role") or "standard_part").strip(),
        "host_component": str(attachment_request.get("host_component") or request.get("host_component") or "").strip(),
        "host_interface_id": str(attachment_request.get("host_interface_id") or request.get("host_interface_id") or "").strip(),
        "mate_group_id": str(attachment_request.get("mate_group_id") or request.get("mate_group_id") or "").strip(),
        "required_mates": [str(mate).strip() for mate in required_mates if str(mate).strip()],
    }
    host_selector = attachment_request.get("host_selector") or request.get("host_selector")
    inserted_selector = attachment_request.get("inserted_selector") or request.get("inserted_selector") or item.get("inserted_selector") or item.get("component_selector")
    if host_selector is not None:
        attachment["host_selector"] = host_selector
    if inserted_selector is not None:
        attachment["inserted_selector"] = inserted_selector
    return {
        "part_path": policy["part_path"],
        "component_name": str(request.get("component_name") or item.get("component_name") or "").strip(),
        "configuration": str(request.get("configuration") or item.get("configuration") or "").strip(),
        "origin_m": [float(value) for value in as_list(request.get("origin_m") or [0.0, 0.0, 0.0])],
        "fixed": bool(request.get("fixed", False)),
        "standard_part": True,
        "source_policy": policy,
        "attachment": attachment,
    }


def resolve(catalog_path: str, request_path: str) -> dict[str, Any]:
    catalog_file = Path(catalog_path).resolve()
    request_file = Path(request_path).resolve()
    catalog = load_json(str(catalog_file))
    request = load_json(str(request_file))
    blockers: list[dict[str, Any]] = []
    item = match_item(catalog, request)
    if item is None:
        blockers.append({"kind": "standard_part_not_found", "request": request})
        policy = {"status": "blocked"}
        component_spec = None
        resolved_item = None
    else:
        policy, policy_blockers = source_policy(catalog, item, catalog_file)
        blockers.extend(policy_blockers)
        component_spec = build_component_spec(item, request, policy)
        resolved_item = {key: value for key, value in item.items() if key != "inserted_selector"}
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not blockers,
        "catalog": str(catalog_file),
        "request": str(request_file),
        "source_policy": policy,
        "resolved_item": resolved_item,
        "component_insert_spec": component_spec,
        "blockers": blockers,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, help="Reviewed local standard-part catalog JSON")
    parser.add_argument("--request", required=True, help="Standard-part request JSON")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/standard_part_resolve.json")
    parser.add_argument("--component-spec-out", default="")
    args = parser.parse_args()

    report = resolve(args.catalog, args.request)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.component_spec_out and report.get("component_insert_spec") is not None:
        spec_out = Path(args.component_spec_out)
        spec_out.parent.mkdir(parents=True, exist_ok=True)
        spec_out.write_text(json.dumps(report["component_insert_spec"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
