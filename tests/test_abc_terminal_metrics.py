from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.abc_terminal_metrics import terminal_indicators_for_outcome, update_report
from tools.epic_non_speed_early_policy_pareto import generate_conditional_gear, simulate_paths


class AbcTerminalMetricsTest(unittest.TestCase):
    def test_terminal_production_is_zero_when_the_path_stops_before_plus15(self):
        gear = generate_conditional_gear("set_speed", "Epic", 17, slot="weapon")
        path = simulate_paths(gear, "normal_85", runs=1, seed=18)[0]

        values = terminal_indicators_for_outcome(path, {"stop_checkpoint": 9})

        self.assertEqual(
            values,
            {"native_heirloom": 0.0, "converted_heirloom": 0.0, "speed22": 0.0, "output60": 0.0},
        )

    def test_report_update_creates_an_independent_smoke_report(self):
        with TemporaryDirectory() as directory:
            report = Path(directory) / "new-report.md"
            update_report(report, "## 终局产量补全")
            self.assertIn("<!-- terminal-production:start -->", report.read_text(encoding="utf-8"))
