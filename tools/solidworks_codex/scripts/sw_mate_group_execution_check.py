"""Check after-inspect evidence for mate group macro execution."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


OK_STATUSES = {"ok", "solved", "satisfied", "active", "0"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def active_document(report: dict[str, Any]) -> dict[str, Any]:
    doc = report.get("active_document") if isinstance(report, dict) else {}
    return doc if isinstance(doc, dict) else {}


def mate_is_bad(mate: dict[str, Any]) -> tuple[bool, str]:
    if mate.get("suppressed") is True:
        return True, "mate is suppressed"
    if mate.get("mate_error") not in (None, 1):
        return True, f"mate_error={mate.get('mate_error')}"
    status = mate.get("status", mate.get("solver_status"))
    if status is not None and str(status).strip().casefold() not in OK_STATUSES:
        return True, f"status={status}"
    return False, ""


def add(findings: dict[str, list[dict[str, Any]]], severity: str, kind: str, mate_name: str, detail: Any, reason: str) -> None:
    findings.setdefault(severity, []).append({
        "kind": kind,
        "mate": mate_name,
        "detail": detail,
        "reason": reason,
    })


def check(manifest: dict[str, Any], after_report: dict[str, Any]) -> dict[str, Any]:
    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "accepted": []}
    expected = [item for item in manifest.get("macros", []) if item.get("expected_mate_name")]
    mates = active_document(after_report).get("mate_like_features", [])
    mate_by_name = {str(item.get("name")): item for item in mates if isinstance(item, dict)}

    for item in expected:
        name = str(item.get("expected_mate_name"))
        mate = mate_by_name.get(name)
        if not mate:
            add(findings, "blocking", "mate_missing", name, item, "expected mate was not found in after-inspect report")
            continue
        bad, reason = mate_is_bad(mate)
        if bad:
            add(findings, "blocking", "mate_error", name, mate, reason)
            continue
        expected_components = {str(c) for c in item.get("components", []) if c}
        actual_components = {str(c) for c in mate.get("components", []) if c}
        if expected_components and actual_components and not expected_components.issubset(actual_components):
            add(findings, "warning", "mate_component_readback_mismatch", name, {"expected": sorted(expected_components), "actual": sorted(actual_components)}, "mate exists but component readback does not cover expected components")
            continue
        add(findings, "accepted", "mate_present", name, mate, "expected mate exists and reports no solver error")

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not findings["blocking"],
        "document": {
            "type": active_document(after_report).get("type"),
            "title": active_document(after_report).get("title") or active_document(after_report).get("name"),
        },
        "counts": {
            "expected_mates": len(expected),
            "accepted_mates": len(findings["accepted"]),
            "blocking_findings": len(findings["blocking"]),
            "warning_findings": len(findings["warning"]),
        },
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check after-inspect evidence for mate group macro execution")
    parser.add_argument("--macro-manifest", required=True)
    parser.add_argument("--after-report", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = check(load_json(Path(args.macro_manifest)), load_json(Path(args.after_report)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "execution_ok": result["ok"], "out": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
