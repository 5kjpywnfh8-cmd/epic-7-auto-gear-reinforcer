"""Fail-closed archive intake for schema 1.2 MuMu player-data snapshots."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance import epic_balanced_holdout as holdout
from src.e7_enhance import epic_plus0_archive as archive
from src.e7_enhance.mumu_player_data import archive_payload

DEFAULT_ARCHIVE = ROOT / "samples" / "epic_plus0_real_archive_20260719.json"
DEFAULT_FREEZE = ROOT / "samples" / "epic_output_8_13_tank_10_17_holdout_freeze_20260718.json"

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--player-data", type=Path, required=True)
    parser.add_argument("--reader-result", type=Path, required=True)
    args = parser.parse_args(argv)
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    archive.create_dataset(args.archive, minimum_exported_at=str(freeze["frozen_at"]))
    source_bytes = args.player_data.read_bytes()
    incoming = archive_payload(source_bytes, json.loads(source_bytes), json.loads(args.reader_result.read_text(encoding="utf-8")))
    result = archive.ingest_export(args.archive, incoming, known=holdout.historical_identity_index(), minimum_exported_at=str(freeze["frozen_at"]))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
