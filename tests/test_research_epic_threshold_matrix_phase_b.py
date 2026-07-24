from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from tools.research_epic_threshold_matrix_phase_b import (
    Candidate,
    CURRENT_KEY,
    HEROIC_SHARED_KEY,
    JOINT_SCHEMA_VERSION,
    _atomic_json,
    _joint_expected,
    _joint_path,
    _select_joint_jobs,
    _valid_joint_shard,
    action,
    selected_candidate_snapshot,
    FORMAL_CATEGORY_GROUPS,
    system_group,
)
from src.e7_enhance.rules import CATEGORY_RULES
from src.e7_enhance.models import Gear


class PhaseBFeatureConsistencyTest(unittest.TestCase):
    def test_system_group_mapping(self):
        self.assertEqual(system_group("\u8f93\u51fa"), "pure_output")
        # Regression: the formal label is "必爆", not the homophone "必暴".
        self.assertEqual(system_group("\u8f93\u51fa(\u5fc5\u7206)"), "pure_output")
        self.assertEqual(system_group("\u53cc\u6548"), "dual")

    def test_all_formal_category_names_have_an_explicit_group(self):
        formal_names = {row["category"] for row in CATEGORY_RULES}
        self.assertEqual(formal_names, set(FORMAL_CATEGORY_GROUPS))
        self.assertNotIn("unknown", {system_group(name) for name in formal_names})

    def test_unofficial_spelling_variants_do_not_silently_join_a_group(self):
        for variant in ("\u8f93\u51fa(\u5fc5\u66b4)", "\u8f93\u51fa\uff08\u5fc5\u7206\uff09", "\u8f38\u51fa(\u5fc5\u7206)"):
            self.assertEqual(system_group(variant), "unknown")

    def test_group_delta_only_applies_to_selected_candidate_system(self):
        candidate=Candidate(10,14,"pure_output",2)
        output={"system_group":"pure_output","effective_gs":12.0,"current_valid":2,"probability":0.0,"conversion_value":0.0}
        tank={**output,"system_group":"pure_tank"}
        self.assertEqual(action("continue",0,output,candidate),"stop")
        self.assertEqual(action("continue",0,tank,candidate),"continue")

    def test_mixed_candidate_fields_are_not_accepted(self):
        # The snapshot API deliberately exposes one selected candidate only;
        # callers cannot supply GS from one category and probability from another.
        self.assertEqual(set(selected_candidate_snapshot.__annotations__), {"gear", "return"})

    def test_joint_shard_requires_candidate_and_input_hashes(self):
        gear = Gear.from_dict({
            "rank": "Epic", "slot": "weapon", "set": "speed", "level": 85, "enhance": 0,
            "main_stat": {"key": "attack", "value": 500},
            "substats": [
                {"key": "attack_percent", "value": 5}, {"key": "crit_chance", "value": 3},
                {"key": "crit_damage", "value": 4}, {"key": "health_percent", "value": 4},
            ],
        })
        matrix = {Candidate(10, 14).key: {"candidate": {"t0": 10, "t3": 14, "system_group": "global", "delta": 0}}}
        expected, _ = _joint_expected(matrix, [gear], [gear], runs=1)
        item = next(value for value in expected.values() if value["candidate_key"] == Candidate(10, 14).key and value["seed"] == 20260712)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = _joint_path(root, item["candidate_key"], item["rank"], item["seed"], item["gear_index"])
            payload = {"status": "complete", "schema_version": JOINT_SCHEMA_VERSION, "candidate_hash": item["candidate_hash"], "input_hash": item["input_hash"], "seed": item["seed"], "rank": item["rank"], "gear_index": item["gear_index"], "flow": {}, "paths": 1}
            _atomic_json(path, payload)
            self.assertTrue(_valid_joint_shard(path, candidate_hash=item["candidate_hash"], input_hash=item["input_hash"], seed=item["seed"], rank=item["rank"], gear_index=item["gear_index"]))
            payload["candidate_hash"] = "wrong"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(_valid_joint_shard(path, candidate_hash=item["candidate_hash"], input_hash=item["input_hash"], seed=item["seed"], rank=item["rank"], gear_index=item["gear_index"]))

    def test_joint_job_filters_are_strict_and_do_not_schedule_shared_heroic_for_epic_slice(self):
        gear = Gear.from_dict({
            "rank": "Epic", "slot": "weapon", "set": "speed", "level": 85, "enhance": 0,
            "main_stat": {"key": "attack", "value": 500},
            "substats": [
                {"key": "attack_percent", "value": 5}, {"key": "crit_chance", "value": 3},
                {"key": "crit_damage", "value": 4}, {"key": "health_percent", "value": 4},
            ],
        })
        candidate = Candidate(10, 14)
        matrix = {candidate.key: {"candidate": {"t0": 10, "t3": 14, "system_group": "global", "delta": 0}}}
        expected, _ = _joint_expected(matrix, [gear], [gear], runs=1)
        with tempfile.TemporaryDirectory() as directory:
            jobs, skipped = _select_joint_jobs(expected, Path(directory), runs=1, selected_candidates={candidate.key}, selected_seeds={20260712}, selected_ranks={"Epic"}, gear_start=0, gear_end=0, shard_start=None, shard_end=None)
        self.assertEqual(skipped, 0)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["candidate_key"], candidate.key)
        self.assertEqual(jobs[0]["rank"], "Epic")
        self.assertNotEqual(jobs[0]["candidate_key"], CURRENT_KEY)
        self.assertNotEqual(jobs[0]["candidate_key"], HEROIC_SHARED_KEY)
