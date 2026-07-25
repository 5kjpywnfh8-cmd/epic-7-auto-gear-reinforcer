"""Run the frozen policy V1 regression matrix and write hashed evidence."""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.policy_manifest import (  # noqa: E402
    REGRESSION_EVIDENCE_PATH,
    REGRESSION_TEST_INPUTS,
    write_regression_evidence,
)


RAN_PATTERN = re.compile(r"Ran (\d+) tests?")
SELECTED_PATTERNS = {
    "tests/test_epic_early_stop.py": (
        "exact_category_mapping_and_thresholds_are_frozen",
        "stop_requires_every_frozen_condition",
        "scope_excludes_other_routes",
        "policy_wiring_stops_and_uses_each_immediate_checkpoint",
    ),
}


def run_test_file(root: Path, relative_path: str) -> dict[str, object]:
    filename = Path(relative_path).name
    base_command = ["python", "-B", "-m", "unittest", "discover", "-s", "tests", "-p", filename]
    patterns = SELECTED_PATTERNS.get(relative_path, (None,))
    recorded_commands = [base_command if pattern is None else [*base_command, "-k", pattern] for pattern in patterns]
    started = time.perf_counter()
    results = [
        subprocess.run(
            [sys.executable, *recorded_command[1:]],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for recorded_command in recorded_commands
    ]
    duration = time.perf_counter() - started
    output = "\n".join(f"{result.stdout}\n{result.stderr}" for result in results)
    tests_run = sum(int(match.group(1)) for match in RAN_PATTERN.finditer(output))
    exit_code = 0 if all(result.returncode == 0 for result in results) else 1
    print(f"{'PASSED' if exit_code == 0 else 'FAILED'}: {relative_path} ({tests_run} tests)", flush=True)
    if exit_code:
        print(output[-4000:], file=sys.stderr, flush=True)
    return {
        "path": relative_path,
        "commands": recorded_commands,
        "exit_code": exit_code,
        "tests_run": tests_run,
        "duration_seconds": duration,
        "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成策略 V1 完整回归矩阵机器证据")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--generated-on", default=date.today().isoformat())
    args = parser.parse_args(argv)

    root = args.root.resolve()
    output_path = args.json or root / REGRESSION_EVIDENCE_PATH
    test_runs = [run_test_file(root, relative_path) for relative_path in REGRESSION_TEST_INPUTS]
    evidence = write_regression_evidence(
        root,
        test_runs=test_runs,
        json_path=output_path,
        generated_on=args.generated_on,
    )
    print(output_path)
    print(f"status={evidence['status']}")
    print(f"evidence_sha256={evidence['evidence_sha256']}")
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
