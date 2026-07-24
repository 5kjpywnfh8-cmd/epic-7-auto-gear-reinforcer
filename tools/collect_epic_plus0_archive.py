"""CLI for the broad real Epic +0 archive used by future research."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance import epic_balanced_holdout as holdout
from src.e7_enhance import epic_plus0_archive as archive
from tools.collect_epic_balanced_holdout import _prepare_payload


DEFAULT_ARCHIVE = ROOT / "samples" / "epic_plus0_real_archive_20260719.json"
DEFAULT_FREEZE = ROOT / "samples" / "epic_output_8_13_tank_10_17_holdout_freeze_20260718.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive new trusted normal_85 Epic +0 items for later research")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--import-json", type=Path)
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args(argv)

    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    minimum_exported_at = str(freeze["frozen_at"])
    archive.create_dataset(args.archive, minimum_exported_at=minimum_exported_at)
    if args.import_json:
        incoming = _prepare_payload(args.import_json.read_bytes())
        result = archive.ingest_export(
            args.archive,
            incoming,
            known=holdout.historical_identity_index(),
            minimum_exported_at=minimum_exported_at,
        )
    else:
        result = archive.progress(args.archive)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
