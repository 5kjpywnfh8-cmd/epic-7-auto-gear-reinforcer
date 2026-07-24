"""CLI wrapper for the offline single-item confirmation validator."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.single_item_confirmation import main


if __name__ == "__main__":
    raise SystemExit(main())
