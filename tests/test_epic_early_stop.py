from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.epic_early_stop import (
    CANDIDATE_KEY,
    candidate_action,
    released_early_stop_decision,
    system_group,
    threshold_for,
)
from src.e7_enhance.models import Gear
from src.e7_enhance.gui_support import debug_view_model


ROOT = Path(__file__).resolve().parents[1]
HOLDOUT_RESULT = ROOT / "reports" / "epic_output_8_13_tank_10_17_holdout_validation_20260719.json"


def _gear(*, enhance: int = 0, rank: str = "Epic", slot: str = "Weapon", speed: float | None = None) -> Gear:
    substats = [
        {"type": "AttackPercent", "value": 4, "rolls": 1},
        {"type": "CriticalHitChancePercent", "value": 3, "rolls": 1},
        {"type": "HealthPercent", "value": 4, "rolls": 1},
        {"type": "EffectivenessPercent", "value": 4, "rolls": 1},
    ]
    if rank == "Heroic":
        substats.pop()
    if speed is not None:
        substats[-1] = {"type": "Speed", "value": speed, "rolls": 1}
    main_by_slot = {
        "Weapon": {"type": "Attack", "value": 525},
        "Boots": {"type": "HealthPercent", "value": 65},
    }
    return Gear.from_dict(
        {
            "set": "Critical",
            "slot": slot,
            "mainStat": main_by_slot[slot],
            "enhance": enhance,
            "level": 85,
            "rank": rank,
            "substats": substats,
        }
    )


def _features(group: str, *, gs: float, valid: int = 2, probability: float = 0.0, conversion: float = 0.0) -> dict:
    return {
        "category": "test",
        "system_group": group,
        "effective_gs": gs,
        "current_valid": valid,
        "probability": probability,
        "conversion_value": conversion,
    }


class EpicEarlyStopTest(unittest.TestCase):
    def test_exact_category_mapping_and_thresholds_are_frozen(self):
        self.assertEqual(system_group("输出"), "pure_output")
        self.assertEqual(system_group("输出(必爆)"), "pure_output")
        self.assertEqual(system_group("纯肉"), "pure_tank")
        self.assertEqual(system_group("双效"), "dual")
        self.assertEqual(system_group("未知拼写"), "unknown")
        self.assertEqual((threshold_for(0, "pure_output"), threshold_for(3, "pure_output")), (8.0, 13.0))
        self.assertEqual((threshold_for(0, "pure_tank"), threshold_for(3, "pure_tank")), (10.0, 17.0))
        self.assertEqual((threshold_for(0, "bruiser"), threshold_for(3, "bruiser")), (12.0, 17.0))

    def test_stop_requires_every_frozen_condition(self):
        boundary = _features("pure_output", gs=8, valid=2, probability=0.002, conversion=0)
        self.assertEqual(candidate_action("continue", 0, boundary), "stop")
        self.assertEqual(candidate_action("stop", 0, boundary), "stop")
        for changed in (
            {**boundary, "effective_gs": 8.1},
            {**boundary, "current_valid": 3},
            {**boundary, "probability": 0.0021},
            {**boundary, "conversion_value": 0.1},
        ):
            with self.subTest(changed=changed):
                self.assertEqual(candidate_action("continue", 0, changed), "continue")

    def test_scope_excludes_other_routes(self):
        eligible = released_early_stop_decision(_gear(), item_source="normal_85", baseline_action="continue", candidates=[])
        self.assertTrue(eligible["eligible"])
        for gear, source in (
            (_gear(slot="Boots"), "normal_85"),
            (_gear(speed=2), "normal_85"),
            (_gear(enhance=6), "normal_85"),
            (_gear(rank="Heroic"), "normal_85"),
            (_gear(), "rift_85"),
        ):
            with self.subTest(gear=gear, source=source):
                result = released_early_stop_decision(gear, item_source=source, baseline_action="continue", candidates=[])
                self.assertFalse(result["eligible"])
                self.assertEqual(result["final_action"], "continue")
                self.assertFalse(result["added_stop"])

    def test_holdout_actions_match_the_released_pure_rule(self):
        payload = json.loads(HOLDOUT_RESULT.read_text(encoding="utf-8"))
        compared = 0
        stops = 0
        for partition in ("development", "frozen_validation"):
            for item in payload["partitions"][partition]["items"]:
                states = [(0, item)] + [(3, branch) for branch in item["plus3_branches"]]
                for checkpoint, state in states:
                    observed = candidate_action(state["current_action"], checkpoint, state["features"])
                    self.assertEqual(observed, state["candidate_action"])
                    compared += 1
                    stops += observed == "stop" and state["current_action"] != "stop"
        self.assertGreater(compared, 128)
        self.assertGreater(stops, 0)
        self.assertEqual(payload["candidate"]["key"], CANDIDATE_KEY)

    def test_production_feature_selection_matches_every_holdout_state(self):
        payload = json.loads(HOLDOUT_RESULT.read_text(encoding="utf-8"))
        compared = 0
        for partition in ("development", "frozen_validation"):
            for item in payload["partitions"][partition]["items"]:
                states = [item] + list(item["plus3_branches"])
                for state in states:
                    result = released_early_stop_decision(
                        Gear.from_dict(state["gear"]),
                        item_source="normal_85",
                        baseline_action=state["current_action"],
                    )
                    self.assertEqual(result["final_action"], state["candidate_action"])
                    self.assertEqual(result["system_group"], state["features"]["system_group"])
                    self.assertEqual(result["category"], state["features"]["category"])
                    for key in ("effective_gs", "current_valid", "probability"):
                        self.assertAlmostEqual(float(result["features"][key]), float(state["features"][key]))
                    self.assertEqual(
                        float(result["features"]["conversion_gs_gain"]) > 0,
                        float(state["features"]["conversion_value"]) > 0,
                    )
                    compared += 1
        self.assertGreater(compared, 128)

    def test_policy_wiring_stops_and_uses_each_immediate_checkpoint(self):
        candidates = [
            {
                "qualified": False,
                "formal_terminal_formula_available": True,
                "category": "输出",
                "current_pre_reforge_gs": 8.0,
                "current_valid_substat_count": 2,
                "terminal_reach_probability": 0.0,
                "conversion_max_value": 0.0,
            }
        ]

        def prediction(checkpoint: int) -> dict:
            return {
                "action": "review",
                "terminal_value": 0.0,
                "expected_final_speed": 0.0,
                "expected_speed_rolls": 0.0,
                "speed_set_eligible": False,
                "speed_threshold_blocked_probability": 0.0,
                "speed_potential_value": 0.0,
                "target_category": "输出",
                "reason": "baseline review",
                "basis": {"candidate_evaluations": candidates, "checkpoint": checkpoint},
            }

        for checkpoint, next_check in ((0, 3), (3, 6)):
            with self.subTest(checkpoint=checkpoint), patch(
                "src.e7_enhance.enhance_policy.lightweight_prediction",
                return_value=prediction(checkpoint),
            ):
                result = advise_gear(_gear(enhance=checkpoint), item_source="normal_85")
                release = result["debug"]["dp_assist"]["epic_early_stop"]
                self.assertTrue(release["added_stop"])
                self.assertEqual(result["summary"]["recommendation"], "stop")
                self.assertEqual(result["summary"]["next_check_at"], next_check)
                self.assertTrue(result["debug"]["dp_assist"]["overrode_baseline"])
                view = debug_view_model(result)["epic_early_stop"]
                self.assertEqual(view["候选"], CANDIDATE_KEY)
                self.assertEqual(view["原正式二元动作"], "continue")
                self.assertEqual(view["最终二元动作"], "stop")
                self.assertTrue(view["是否新增止损"])


if __name__ == "__main__":
    unittest.main()
