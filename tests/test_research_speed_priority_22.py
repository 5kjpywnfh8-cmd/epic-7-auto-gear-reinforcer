import random
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.research_speed_priority_22 import (
    SPEED_CANDIDATES,
    _empty_row,
    _atomic_json,
    _shard,
    candidate_entries_for,
    conditional_rate_row,
    joint_candidate_plans,
    speed_action,
    summarize,
    simulate_speed_paths,
)
from tools.epic_non_speed_early_policy_pareto import generate_conditional_gear
from src.e7_enhance.models import RollHit, Stat


class ResearchSpeedPriorityTest(unittest.TestCase):
    def test_speed_current_exact_uses_released_rank_and_source_thresholds(self):
        epic = generate_conditional_gear("Speed", "Epic", 5, slot="weapon", main_stat="atkFlat")
        epic = replace(epic, substats=[Stat("Speed", 2, rolls=1), *epic.substats[1:]])
        heroic_three = generate_conditional_gear("Speed", "Heroic", 6, slot="weapon", main_stat="atkFlat")
        heroic_three = replace(heroic_three, substats=[Stat("Speed", 3, rolls=1), *heroic_three.substats[1:]])
        heroic_four = replace(heroic_three, substats=[Stat("Speed", 4, rolls=1), *heroic_three.substats[1:]])

        self.assertEqual(speed_action("speed_current_exact", epic, "normal_85", 2), "continue")
        self.assertEqual(speed_action("speed_current_exact", epic, "rift_85", 2), "continue")
        self.assertEqual(speed_action("speed_current_exact", heroic_three, "normal_85", 2), "stop")
        self.assertEqual(speed_action("speed_current_exact", heroic_four, "normal_85", 2), "continue")

    def test_speed_current_exact_uses_speed_hit_at_plus_three_then_formal_followup(self):
        gear = generate_conditional_gear("Speed", "Epic", 31, slot="weapon", main_stat="atkFlat")
        gear = replace(
            gear,
            enhance=3,
            substats=[Stat("Speed", 6, rolls=2), *gear.substats[1:]],
            roll_history=[RollHit(3, "Speed", 2)],
        )
        missed = replace(gear, roll_history=[RollHit(3, "AttackPercent", 4)])
        plus_six = replace(
            gear,
            enhance=6,
            substats=[
                Stat("Speed", 8, rolls=2),
                Stat("AttackPercent", 12, rolls=2),
                Stat("CriticalHitChancePercent", 8, rolls=1),
                Stat("CriticalHitDamagePercent", 11, rolls=1),
            ],
            roll_history=[RollHit(3, "Speed", 4), RollHit(6, "AttackPercent", 4)],
        )

        self.assertEqual(speed_action("speed_current_exact", gear, "normal_85", 2), "continue")
        self.assertEqual(speed_action("speed_current_exact", missed, "normal_85", 2), "stop")
        self.assertEqual(speed_action("speed_current_exact", plus_six, "normal_85", 2), "continue")

    def test_joint_candidate_plan_keeps_epic_and_heroic_thresholds_independent(self):
        plans = joint_candidate_plans()

        self.assertEqual(
            plans["reachable_epic2_heroic3"],
            {"normal_epic": "speed_reachable_22_epic2", "normal_heroic": "speed_reachable_22_heroic3"},
        )
        self.assertEqual(
            plans["speed_current_exact"],
            {"normal_epic": "speed_current_exact", "normal_heroic": "speed_current_exact"},
        )
        self.assertEqual(
            plans["current_epic2_reachable_heroic4"],
            {"normal_epic": "speed_current_exact", "normal_heroic": "speed_reachable_22_heroic4"},
        )
        self.assertNotIn("speed_reachable_22_start_4", plans)

    def test_epic_candidate_entries_keep_two_speed_route_while_heroic_can_vary(self):
        epic = generate_conditional_gear("Speed", "Epic", 14, slot="weapon", main_stat="atkFlat")
        heroic = generate_conditional_gear("Speed", "Heroic", 15, slot="weapon", main_stat="atkFlat")

        epic_names = {name for name, _candidate, _threshold in candidate_entries_for(epic, "normal_85")}
        heroic_names = {name for name, _candidate, _threshold in candidate_entries_for(heroic, "normal_85")}

        self.assertIn("speed_reachable_22_epic2", epic_names)
        self.assertNotIn("speed_reachable_22_epic3", epic_names)
        self.assertNotIn("speed_reachable_22_epic4", epic_names)
        self.assertTrue({"speed_reachable_22_heroic2", "speed_reachable_22_heroic3", "speed_reachable_22_heroic4"}.issubset(heroic_names))

    def test_conditional_speed_metrics_exclude_gear_acquisition_stamina(self):
        row = _empty_row()
        row["paths"] = 1
        row["speed_bins"]["22"] = 1

        metrics = conditional_rate_row(row)

        self.assertEqual(metrics["acquisition_stamina"], 0.0)
        self.assertEqual(metrics["incremental_total_stamina"], 0.0)
        self.assertEqual(metrics["22_per_100_speed_embryos"], 100.0)
        self.assertNotIn("22_per_100_stamina", metrics)

    def test_summary_keeps_joint_plans_conditional_and_marks_full_pool_unestimated(self):
        epic = generate_conditional_gear("Speed", "Epic", 22, slot="weapon", main_stat="atkFlat")
        epic = replace(epic, substats=[Stat("Speed", 4, rolls=1), *epic.substats[1:]])
        heroic = generate_conditional_gear("Speed", "Heroic", 23, slot="weapon", main_stat="atkFlat")
        heroic = replace(heroic, substats=[Stat("Speed", 4, rolls=1), *heroic.substats[1:]])

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for group, gear, source in (
                ("normal_epic", epic, "normal_85"),
                ("normal_heroic", heroic, "normal_85"),
                ("rift_epic", epic, "rift_85"),
            ):
                path = root / "official" / "shards" / group / "seed-1" / "gear-0000-chunk-000.json"
                payload = _shard(gear, source, 1, 5, False)
                payload["schema_version"] = 3
                _atomic_json(path, payload)

            summary = summarize(root, [1], False)

        self.assertEqual(summary["full_pool_efficiency"]["status"], "not_estimated")
        self.assertEqual(
            summary["joint_conditional_plans"]["reachable_epic2_heroic3"]["members"]["normal_heroic"],
            "speed_reachable_22_heroic3",
        )
        self.assertIn("speed_current_exact", summary["groups"]["normal_heroic"])

    def test_non_boot_speed_path_records_all_five_checkpoints(self):
        gear = generate_conditional_gear("Speed", "Epic", 7, slot="weapon", main_stat="atkFlat")
        gear = replace(gear, substats=[Stat("Speed", 2, rolls=1), *gear.substats[1:]])
        paths = simulate_speed_paths(gear, "normal_85", 2, random.Random(8))
        self.assertEqual(set(paths[0]), {0, 3, 6, 9, 12, 15})
        self.assertIn("spd", {stat.key for stat in paths[0][15].substats})

    def test_reachable_22_never_continues_a_boot_speed_substat(self):
        gear = generate_conditional_gear("Speed", "Epic", 9, slot="boot", main_stat="atkFlat")
        self.assertEqual(speed_action("speed_reachable_22", gear, "normal_85", 2), "stop")
