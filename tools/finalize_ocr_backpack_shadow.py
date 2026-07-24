"""Finalize one backpack OCR sample as a read-only strategy shadow."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.ocr_backpack_shadow import finalize_shadow


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--player-data", type=Path, required=True)
    parser.add_argument("--reader-result", type=Path, required=True)
    parser.add_argument("--ocr", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest_path = args.batch / "manifest.json"
    shadow_path = args.batch / "ocr_shadow.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    player_bytes = args.player_data.read_bytes()
    reader_bytes = args.reader_result.read_bytes()
    ocr_bytes = args.ocr.read_bytes()
    ocr_payload = json.loads(ocr_bytes)
    ocr_payload["_raw_bytes"] = ocr_bytes
    paired, shadow = finalize_shadow(
        manifest,
        ocr_payload,
        json.loads(player_bytes),
        json.loads(reader_bytes),
        player_data_path=str(args.player_data),
        reader_result_path=str(args.reader_result),
        player_data_bytes=player_bytes,
        reader_result_bytes=reader_bytes,
    )
    _atomic_json(shadow_path, shadow)
    _atomic_json(manifest_path, paired)
    print(json.dumps({
        "manifest": str(manifest_path),
        "shadow": str(shadow_path),
        "status": paired["ocr_gate"]["status"],
        "accepted": shadow["ocr"]["accepted"],
        "advice_matched": shadow["advice_comparison"].get("matched", False),
        "click_performed": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
