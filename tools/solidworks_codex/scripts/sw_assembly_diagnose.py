"""Diagnose a SolidWorks assembly inspect report without mutating CAD files."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any


INSTANCE_SUFFIX = re.compile(r"-\d+$")


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def active_document(report: dict[str, Any]) -> dict[str, Any]:
    doc = report.get("active_document") if isinstance(report, dict) else {}
    return doc if isinstance(doc, dict) else {}


def instance_key(name: str) -> str:
    return INSTANCE_SUFFIX.sub("", str(name)).casefold()


def component_name(component: dict[str, Any]) -> str:
    return str(component.get("name2") or component.get("name") or "")


def normalized_components(doc: dict[str, Any]) -> list[dict[str, Any]]:
    raw = doc.get("components", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and component_name(item)]


def normalized_mates(doc: dict[str, Any]) -> list[dict[str, Any]]:
    raw = doc.get("mate_like_features", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and item.get("name")]


def mate_component_names(mate: dict[str, Any], known: set[str]) -> list[str]:
    names = mate.get("components")
    if not isinstance(names, list):
        return []
    result: list[str] = []
    by_key = {instance_key(name): name for name in known}
    for name in names:
        text = str(name)
        if text in known:
            result.append(text)
            continue
        matched = by_key.get(instance_key(text))
        if matched:
            result.append(matched)
    return result


def mate_is_bad(mate: dict[str, Any]) -> bool:
    if mate.get("suppressed") is True:
        return True
    if mate.get("mate_error") not in (None, 1):
        return True
    status = mate.get("status", mate.get("solver_status"))
    if status is not None and str(status).strip().casefold() not in {"ok", "solved", "satisfied", "active", "0"}:
        return True
    return False


def bbox(component: dict[str, Any]) -> list[float] | None:
    raw = component.get("bbox_m")
    if not isinstance(raw, list) or len(raw) != 6:
        return None
    try:
        values = [float(v) for v in raw]
    except (TypeError, ValueError):
        return None
    if any(math.isnan(v) or math.isinf(v) for v in values):
        return None
    return values


def bbox_gap(a: list[float], b: list[float]) -> float:
    gaps = [
        max(float(a[0]) - float(b[3]), float(b[0]) - float(a[3]), 0.0),
        max(float(a[1]) - float(b[4]), float(b[1]) - float(a[4]), 0.0),
        max(float(a[2]) - float(b[5]), float(b[2]) - float(a[5]), 0.0),
    ]
    return math.sqrt(sum(g * g for g in gaps))


def scan_locks(root: Path | None) -> list[str]:
    if root is None or not root.exists():
        return []
    return sorted(str(path.resolve()) for path in root.rglob("~$*"))


def standard_component_names(names: list[str], pattern: str) -> set[str]:
    regex = re.compile(pattern, re.I)
    return {name for name in names if regex.search(name)}


def connected_components(names: list[str], adjacency: dict[str, set[str]]) -> list[list[str]]:
    seen: set[str] = set()
    groups: list[list[str]] = []
    for name in names:
        if name in seen:
            continue
        group: list[str] = []
        queue: deque[str] = deque([name])
        seen.add(name)
        while queue:
            current = queue.popleft()
            group.append(current)
            for nxt in sorted(adjacency.get(current, set())):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        groups.append(sorted(group))
    return sorted(groups, key=lambda item: (-len(item), item))


def add_finding(findings: dict[str, list[dict[str, Any]]], severity: str, kind: str, detail: Any, reason: str) -> None:
    findings.setdefault(severity, []).append({"kind": kind, "detail": detail, "reason": reason})


def diagnose(report: dict[str, Any], *, lock_root: Path | None = None, near_tolerance_m: float = 0.002, standard_part_regex: str = r"bolt|washer|nut|screw|pin|bearing|key|retaining|oil") -> dict[str, Any]:
    doc = active_document(report)
    components = normalized_components(doc)
    names = [component_name(item) for item in components]
    known = set(names)
    mates = normalized_mates(doc)
    adjacency: dict[str, set[str]] = {name: set() for name in names}
    mate_edges: list[dict[str, Any]] = []
    bad_mates: list[str] = []
    no_participants: list[str] = []

    for mate in mates:
        participants = mate_component_names(mate, known)
        if len(participants) < 2:
            no_participants.append(str(mate.get("name")))
        else:
            left, right = participants[0], participants[1]
            bad = mate_is_bad(mate)
            if not bad:
                adjacency.setdefault(left, set()).add(right)
                adjacency.setdefault(right, set()).add(left)
            mate_edges.append({"mate": mate.get("name"), "type": mate.get("type"), "components": [left, right], "bad": bad})
        if mate_is_bad(mate):
            bad_mates.append(str(mate.get("name")))

    no_mate = sorted(name for name in names if not adjacency.get(name))
    groups = connected_components(names, adjacency)
    isolated = sorted(group[0] for group in groups if len(group) == 1)
    weak_groups = [group for group in groups if 1 < len(group) < max(2, len(names) // 2)]

    bboxes = {component_name(item): bbox(item) for item in components}
    near_pairs: list[dict[str, Any]] = []
    far_pairs: list[dict[str, Any]] = []
    for i, left in enumerate(names):
        left_box = bboxes.get(left)
        if left_box is None:
            continue
        for right in names[i + 1:]:
            right_box = bboxes.get(right)
            if right_box is None:
                continue
            gap = bbox_gap(left_box, right_box)
            item = {"a": left, "b": right, "gap_m": gap}
            if gap <= near_tolerance_m:
                near_pairs.append(item)
            else:
                far_pairs.append(item)
    far_pairs = sorted(far_pairs, key=lambda item: item["gap_m"], reverse=True)[:20]

    standard_names = standard_component_names(names, standard_part_regex)
    hostless_standard = sorted(name for name in standard_names if name in no_mate)
    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "not_applicable": []}
    if doc.get("type") != "assembly":
        add_finding(findings, "blocking", "document_not_assembly", {"actual": doc.get("type")}, "assembly diagnosis requires an assembly inspect report")
    for name in isolated:
        add_finding(findings, "warning", "isolated_component", name, "component is isolated in the mate graph; classify design intent before treating it as a blocking defect")
    for name in hostless_standard:
        add_finding(findings, "blocking", "hostless_standard_part", name, "standard/detail component has no mate host")
    for name in bad_mates:
        add_finding(findings, "blocking", "bad_mate", name, "mate is suppressed, unsolved, or reports an error")
    for name in no_participants:
        add_finding(findings, "warning", "mate_without_component_readback", name, "mate lacks two readable participating components")
    if len(groups) > 1:
        add_finding(findings, "warning", "disconnected_mate_graph", groups, "assembly has multiple mate graph components")

    fixed = sorted(name for name, item in ((component_name(c), c) for c in components) if item.get("fixed") is True)
    floating = sorted(name for name in names if name not in set(fixed))
    hidden = sorted(component_name(c) for c in components if c.get("hidden") is True)
    suppressed = sorted(component_name(c) for c in components if c.get("suppressed") is True)

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not findings["blocking"],
        "document": {"type": doc.get("type"), "title": doc.get("title") or doc.get("name")},
        "inventory": {
            "component_count": len(components),
            "reported_component_count": doc.get("component_count_sampled"),
            "fixed_components": fixed,
            "floating_components": floating,
            "hidden_components": hidden,
            "suppressed_components": suppressed,
        },
        "mates": {
            "mate_count": len(mates),
            "bad_mates": sorted(bad_mates),
            "without_component_readback": sorted(no_participants),
            "edges": mate_edges,
        },
        "mate_graph": {
            "mate_type_distribution": dict(sorted(Counter(str(m.get("type", "<unknown>")) for m in mates).items())),
            "no_mate_components": no_mate,
            "isolated_components": isolated,
            "connected_components": groups,
            "weakly_connected_components": weak_groups,
        },
        "standard_parts": {
            "pattern": standard_part_regex,
            "components": sorted(standard_names),
            "hostless": hostless_standard,
        },
        "spatial": {
            "near_tolerance_m": near_tolerance_m,
            "near_or_touching_pairs": sorted(near_pairs, key=lambda item: (item["gap_m"], item["a"], item["b"])),
            "largest_gap_pairs": far_pairs,
            "components_without_bbox": sorted(name for name, box in bboxes.items() if box is None),
        },
        "runtime": {"lock_root": str(lock_root.resolve()) if lock_root else None, "lock_files": scan_locks(lock_root)},
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", default="tools/solidworks_codex/reports/assembly_diagnosis.json")
    parser.add_argument("--lock-root", default="")
    parser.add_argument("--near-tolerance-m", type=float, default=0.002)
    parser.add_argument("--standard-part-regex", default=r"bolt|washer|nut|screw|pin|bearing|key|retaining|oil")
    args = parser.parse_args()

    lock_root = Path(args.lock_root) if args.lock_root else None
    result = diagnose(
        load_json(args.report),
        lock_root=lock_root,
        near_tolerance_m=args.near_tolerance_m,
        standard_part_regex=args.standard_part_regex,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "diagnosis_ok": result["ok"], "out": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
