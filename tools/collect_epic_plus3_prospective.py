"""CLI for the passive normal Epic +0/+3 prospective collector."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.epic_plus3_prospective import freeze_manifest, load_dataset, progress

DEFAULT_MANIFEST = ROOT / "samples" / "epic_plus3_prospective_runtime_manifest_20260714.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Passively collect real normal Epic +0/+3 prospective pairs.")
    parser.add_argument("--dataset", type=Path, default=ROOT / "samples" / "epic_plus3_prospective_runtime_20260714.json")
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--freeze-manifest", type=Path)
    args = parser.parse_args(argv)
    data = load_dataset(args.dataset)
    active_manifest = args.freeze_manifest or args.manifest
    output = {}
    if args.freeze_manifest:
        output["manifest"] = freeze_manifest(args.dataset, args.freeze_manifest)
    output["progress"] = progress(data, manifest_path=active_manifest)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
