"""Validate captured visual evidence for SolidWorks assembly acceptance."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
VALID_SEVERITIES = {"blocking", "warning", "not_applicable", "accepted"}


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def active_document(report: dict[str, Any]) -> dict[str, Any]:
    return report.get("active_document") or report.get("document") or report


def add(findings: dict[str, list[dict[str, Any]]], severity: str, kind: str, reason: str, detail: Any = None) -> None:
    item = {"kind": kind, "reason": reason}
    if detail is not None:
        item["detail"] = detail
    findings.setdefault(severity, []).append(item)


def screenshot_record(path: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    return {
        "path": str(path),
        "exists": exists,
        "bytes": path.stat().st_size if exists else 0,
        "suffix": path.suffix.lower(),
    }


def normalize_review_findings(review: dict[str, Any]) -> list[dict[str, Any]]:
    raw = review.get("findings", [])
    if isinstance(raw, dict):
        expanded = []
        for severity, items in raw.items():
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict):
                    expanded.append({"severity": severity, **item})
        raw = expanded
    return [item for item in raw if isinstance(item, dict)]


def validate(report: dict[str, Any], screenshots: list[Path], review: dict[str, Any]) -> dict[str, Any]:
    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "not_applicable": [], "accepted": []}
    doc = active_document(report)
    screenshot_records = [screenshot_record(path) for path in screenshots]
    if not screenshot_records:
        add(findings, "blocking", "screenshot_missing", "visual validation requires at least one captured SolidWorks window screenshot")
    for record in screenshot_records:
        if not record["exists"] or record["bytes"] <= 0:
            add(findings, "blocking", "screenshot_missing", "declared screenshot path is missing or empty", record)
        elif record["suffix"] not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            add(findings, "warning", "screenshot_extension_unusual", "screenshot extension is unusual for visual evidence", record)
        else:
            add(findings, "accepted", "screenshot_present", "captured visual evidence is present", record)

    for item in normalize_review_findings(review):
        severity = str(item.get("severity", "warning")).casefold()
        if severity not in VALID_SEVERITIES:
            severity = "warning"
        add(
            findings,
            severity,
            str(item.get("kind") or "visual_review_finding"),
            str(item.get("reason") or item.get("message") or "visual review finding"),
            {key: value for key, value in item.items() if key not in {"severity", "kind", "reason", "message"}},
        )

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not findings["blocking"],
        "document": {
            "title": doc.get("title") or doc.get("document_title"),
            "type": doc.get("type"),
            "component_count": len(doc.get("components", []) or []),
        },
        "screenshots": screenshot_records,
        "counts": {
            "screenshots": len(screenshot_records),
            "blocking_findings": len(findings["blocking"]),
            "warning_findings": len(findings["warning"]),
        },
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate visual screenshot evidence against reviewed findings")
    parser.add_argument("--report", required=True)
    parser.add_argument("--screenshot", action="append", default=[])
    parser.add_argument("--visual-review", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = load_json(resolve(args.report))
    review = load_json(resolve(args.visual_review)) if args.visual_review else {}
    result = validate(report, [resolve(path) for path in args.screenshot], review)
    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "out": str(out), "blocking_findings": result["counts"]["blocking_findings"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
