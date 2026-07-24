from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "run_all_tests.py"
SPEC = importlib.util.spec_from_file_location("run_all_tests", TOOL_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class RunAllTestsTest(unittest.TestCase):
    def test_runner_includes_gui_tests_in_independent_processes(self):
        files = runner.discover_test_files(ROOT / "tests")
        self.assertIn(ROOT / "tests" / "test_gui_app.py", files)
        commands = runner.build_commands(files[:2], sys.executable)
        self.assertEqual(commands[0][0], sys.executable)
        gui_commands = runner.build_commands([ROOT / "tests" / "test_gui_app.py"], sys.executable)
        self.assertEqual(len(gui_commands), len(runner.GUI_APP_TEST_PATTERNS))
        self.assertIn("test_gui_app.py", " ".join(" ".join(command) for command in gui_commands))
        performance_commands = runner.build_commands([ROOT / "tests" / "test_manual_sample_performance.py"], sys.executable)
        self.assertEqual(len(performance_commands), len(runner.MANUAL_SAMPLE_PERFORMANCE_TEST_PATTERNS))

    def test_runner_uses_discovery_so_tests_can_import_sibling_modules(self):
        command = runner.build_commands([ROOT / "tests" / "test_gui_app.py"], sys.executable)[0]
        self.assertEqual(command[1:4], ["-m", "unittest", "discover"])
        self.assertIn("-s", command)
        self.assertIn("-p", command)
        self.assertEqual(command[command.index("-p") + 1], "test_gui_app.py")
        self.assertIn("-k", command)
