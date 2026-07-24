"""Pair backpack OCR screenshots against a validated same-batch MuMu snapshot."""
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

from src.e7_enhance.ocr_backpack_pair import pair_manifest


DEFAULT_MANIFEST = ROOT / "manual_acceptance" / "ocr_stage1" / "batch_003" / "manifest.json"


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
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--player-data", type=Path, required=True)
    parser.add_argument("--reader-result", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output_path = args.output or args.manifest
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    player_bytes = args.player_data.read_bytes()
    reader_bytes = args.reader_result.read_bytes()
    output = pair_manifest(
        manifest,
        json.loads(player_bytes),
        json.loads(reader_bytes),
        player_data_path=str(args.player_data),
        reader_result_path=str(args.reader_result),
        player_data_bytes=player_bytes,
        reader_result_bytes=reader_bytes,
    )
    _atomic_json(output_path, output)
    print(json.dumps({
        "output": str(output_path),
        "matched": sum(record["match_status"] == "matched" for record in output["records"]),
        "records": len(output["records"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
