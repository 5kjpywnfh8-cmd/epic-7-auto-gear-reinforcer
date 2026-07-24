from __future__ import annotations

import unittest
from pathlib import Path

from tools.research_epic_exact_plus3_joint_pool import _outcome_at, _report_resume_path


class ExactPlus3JointPoolTest(unittest.TestCase):
    def test_interval_outcome_preserves_start_and_stop(self):
        class Gear:
            slot = "weapon"
            rank = "Epic"
        outcome = _outcome_at(0, 3, Gear())
        self.assertEqual(outcome["start_checkpoint"], 0)
        self.assertEqual(outcome["stop_checkpoint"], 3)
        self.assertGreater(outcome["net_stamina"], 0)

    def test_relative_resume_path_can_be_reported(self):
        relative = Path("reports") / "epic-exact-resume"
        self.assertEqual(Path(_report_resume_path(relative)), relative)
