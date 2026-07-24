"""Run each unittest file in its own process and preserve the real exit code."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
GUI_APP_TEST_PATTERNS = (
    "fribbels_import_shows_filter_report_and_keeps_layout_stable",
    "invalid_import_shows_error_without_changing_layout",
    "left_substats_and_suggest_button_remain_accessible_without_horizontal_scroll",
    "long_debug_keeps_window_and_splitter_stable_with_internal_scroll",
    "main_window_can_be_created_offscreen",
    "real_sample_import_selects_its_acceptance_batch",
    "real_sample_manager_records_review_without_resizing_main_window",
    "sample_switch_and_debug_toggle_do_not_resize_window",
)
MANUAL_SAMPLE_PERFORMANCE_TEST_PATTERNS = (
    "425_item_import_keeps_qt_heartbeat_running",
    "individual_enhance_filters_are_strict",
    "acceptance_batch_filter_keeps_existing_filters",
    "heroic_batch_filter_shows_16_without_hiding_original_batch",
    "425_item_review_save_keeps_qt_heartbeat_and_updates_one_row",
)
ISOLATED_QT_TEST_PATTERNS = {
    "test_gui_app.py": GUI_APP_TEST_PATTERNS,
    "test_manual_sample_performance.py": MANUAL_SAMPLE_PERFORMANCE_TEST_PATTERNS,
}


def discover_test_files(tests_dir: Path) -> list[Path]:
    files = sorted(Path(tests_dir).glob("test_*.py"))
    # Run the offscreen Qt smoke file in a fresh process before long-running
    # research tests. The runner still executes every test file independently.
    return sorted(files, key=lambda path: (path.name != "test_gui_app.py", path.name))


def build_commands(files: list[Path], python: str) -> list[list[str]]:
    # Discovery adds the tests directory to sys.path, so GUI smoke tests can
    # import their sibling support modules while remaining process-isolated.
    commands: list[list[str]] = []
    for path in files:
        base = [python, "-m", "unittest", "discover", "-s", str(path.parent), "-p", path.name]
        patterns = ISOLATED_QT_TEST_PATTERNS.get(path.name)
        if patterns:
            # PySide can retain native widget state between smoke methods even
            # after explicit cleanup. One method per process keeps coverage
            # intact while isolating that platform state.
            commands.extend([*base, "-k", pattern] for pattern in patterns)
        else:
            commands.append(base)
    return commands


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reliable Windows unittest runner with Qt process isolation")
    parser.add_argument("--tests-dir", type=Path, default=ROOT / "tests")
    args = parser.parse_args(argv)
    files = discover_test_files(args.tests_dir)
    failed: list[str] = []
    for command in build_commands(files, sys.executable):
        label = f"{command[command.index('-p') + 1]}"
        if "-k" in command:
            label += f"::{command[command.index('-k') + 1]}"
        print(f"RUNNING: {label}", flush=True)
        isolated_qt_case = "-k" in command and command[command.index("-p") + 1] in ISOLATED_QT_TEST_PATTERNS
        attempts = 3 if isolated_qt_case else 1
        result = None
        for attempt in range(1, attempts + 1):
            result = subprocess.run(command, cwd=ROOT)
            if not result.returncode:
                break
            if attempt < attempts:
                print(f"RETRY: {label} (exit={result.returncode}, attempt={attempt + 1}/{attempts})", flush=True)
        if result is None or result.returncode:
            failed.append(label)
            print(f"FAILED: {label} (exit={result.returncode if result else 'unknown'})", flush=True)
        else:
            print(f"PASSED: {label}", flush=True)
    if failed:
        print("FAILED: " + ", ".join(str(path) for path in failed), file=sys.stderr)
        return 1
    print("ALL TEST FILES PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
