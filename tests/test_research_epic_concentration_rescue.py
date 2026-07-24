import unittest

from src.e7_enhance.models import Gear, Stat
from tools.research_epic_concentration_rescue import (
    Candidate,
    _concentration_value,
    _compatible,
    _percentile,
    build_candidates,
)


class ConcentrationRescueStudyTests(unittest.TestCase):
    def test_percentile_interpolates(self):
        self.assertEqual(_percentile([0.0, 10.0, 20.0, 30.0], 0.5), 15.0)

    def test_flat_and_percent_attack_use_official_weights(self):
        gear = Gear(
            set="set_speed",
            slot="neck",
            main_stat=Stat("CriticalHitChancePercent", 0),
            substats=[Stat("AttackPercent", 20), Stat("Attack", 39), Stat("HealthPercent", 10)],
            level=90,
            rank="Epic",
            enhance=15,
        )
        self.assertAlmostEqual(_concentration_value(gear, "attack"), 23.46, places=2)

    def test_candidates_cover_attribute_quantile_and_mode(self):
        thresholds = {"quantiles": {"attack": {"0.9": 10, "0.95": 11, "0.975": 12}, "health": {"0.9": 20, "0.95": 21, "0.975": 22}}}
        rows = build_candidates(thresholds)
        self.assertEqual(len(rows), 18)
        self.assertEqual(len({row.key for row in rows}), 18)

    def test_compatibility_is_separate_from_threshold(self):
        output = Gear("set_speed", "neck", Stat("CriticalHitChancePercent", 0), level=85, rank="Epic", substats=[Stat("AttackPercent", 10), Stat("CriticalHitChancePercent", 5), Stat("CriticalHitDamagePercent", 5), Stat("HealthPercent", 5)])
        self.assertTrue(_compatible(output, "attack") or _compatible(output, "health"))


if __name__ == "__main__":
    unittest.main()
