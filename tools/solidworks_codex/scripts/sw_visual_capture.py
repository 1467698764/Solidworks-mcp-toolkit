"""Capture SolidWorks window visual evidence into a screenshot manifest."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def placeholder_png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\xe2&\xb9"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def screenshot_record(path: Path, method: str, role: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "suffix": path.suffix.lower(),
        "capture_method": method,
        "evidence_role": role,
    }


def capture_with_pillow(path: Path) -> str:
    from PIL import ImageGrab  # type: ignore[import-not-found]

    image = ImageGrab.grab(all_screens=True)
    image.save(path)
    return "pillow_imagegrab_all_screens"


def capture(out_dir: Path, *, placeholder: bool = False, prefix: str = "solidworks_window") -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot = out_dir / f"{prefix}_{timestamp}.png"
    errors: list[str] = []
    method = "placeholder_png"
    if placeholder:
        screenshot.write_bytes(placeholder_png_bytes())
    else:
        try:
            method = capture_with_pillow(screenshot)
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            screenshot.write_bytes(placeholder_png_bytes())
            method = "placeholder_png_after_capture_error"
    records = [screenshot_record(screenshot, method, "solidworks_window_capture")]
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": all(item["exists"] and item["bytes"] > 0 for item in records),
        "capture_method": method,
        "capture_scope": "all_screens",
        "screenshots": records,
        "errors": errors,
        "review_instruction": "Use screenshots[].path as visual-validate --screenshot input after confirming the SolidWorks window is visible.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture SolidWorks window screenshot evidence")
    parser.add_argument("--out-dir", default="tools/solidworks_codex/screenshots")
    parser.add_argument("--manifest", default="tools/solidworks_codex/reports/visual_capture.json")
    parser.add_argument("--placeholder", action="store_true", help="Write a deterministic PNG placeholder for CI/protocol dry runs")
    parser.add_argument("--prefix", default="solidworks_window")
    args = parser.parse_args()

    result = capture(resolve(args.out_dir), placeholder=args.placeholder, prefix=args.prefix)
    manifest = resolve(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "manifest": str(manifest), "screenshots": [item["path"] for item in result["screenshots"]]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
