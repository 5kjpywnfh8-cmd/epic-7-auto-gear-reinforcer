from __future__ import annotations

import unittest

from src.e7_enhance.visual_sampling import PureVisualSamplingExecutor


def valid_sample(**overrides):
    sample = {
        "sample_id": "visual-sample-001",
        "captured_at": "2026-07-26T10:00:00+08:00",
        "page": {"kind": "enhance_equipment", "is_unambiguous": True},
        "resource_caps": {
            "powder": 2,
            "lower_enhance_stone": 1,
            "upper_enhance_stone": 0,
            "gold": 17600,
        },
        "targets": [
            {
                "rank": "Epic",
                "level": 85,
                "slot": "Weapon",
                "set": "CriticalDamageSet",
                "enhance": 0,
                "main": {"type": "Attack", "value": 100},
                "substats": [
                    {"type": "HealthPercent", "value": 4},
                    {"type": "CriticalHitDamagePercent", "value": 4},
                    {"type": "CriticalHitChancePercent", "value": 5},
                    {"type": "Speed", "value": 2},
                ],
            }
        ],
    }
    sample.update(overrides)
    return sample


class RecordingClickExecutor:
    def __init__(self):
        self.calls = 0

    def click_enhance(self) -> None:
        self.calls += 1


class StaticSampler:
    def __init__(self, sample):
        self.sample = sample
        self.calls = 0

    def capture(self):
        self.calls += 1
        return self.sample


class PureVisualSamplingExecutorTest(unittest.TestCase):
    def test_matching_plus_zero_sample_proposes_dry_run_plus_three_and_ledger(self):
        clicker = RecordingClickExecutor()
        decision = PureVisualSamplingExecutor(click_executor=clicker).evaluate(valid_sample())

        self.assertEqual(decision.status, "ready")
        self.assertEqual(decision.next_action, "dry_run_propose_enhance_to_plus3")
        self.assertTrue(decision.dry_run)
        self.assertFalse(decision.click_sent)
        self.assertEqual(decision.mode, "visual_only")
        self.assertEqual(decision.verification, "unverified")
        self.assertEqual(clicker.calls, 0)
        self.assertEqual(decision.resource_ledger["planned"], {
            "powder": 2,
            "lower_enhance_stone": 1,
            "upper_enhance_stone": 0,
            "gold": 17600,
        })
        self.assertEqual(decision.resource_ledger["remaining"], {
            "powder": 0,
            "lower_enhance_stone": 0,
            "upper_enhance_stone": 0,
            "gold": 0,
        })
        self.assertEqual(decision.evidence_summary["candidate_count"], 1)
        self.assertEqual(decision.evidence_summary["current_node"], 0)

    def test_injected_sampler_is_used_but_click_executor_is_never_called(self):
        clicker = RecordingClickExecutor()
        sampler = StaticSampler(valid_sample())
        decision = PureVisualSamplingExecutor(sampler=sampler, click_executor=clicker).evaluate()

        self.assertEqual(decision.status, "ready")
        self.assertEqual(sampler.calls, 1)
        self.assertEqual(clicker.calls, 0)

    def test_target_aliases_are_normalized_before_exact_match(self):
        sample = valid_sample()
        target = sample["targets"][0]
        target.update({"rank": "红装", "slot": "武器", "set": "爆伤套"})
        target["main"]["type"] = "攻击"
        target["substats"][0]["type"] = "生命%"
        target["substats"][1]["type"] = "爆伤%"
        target["substats"][2]["type"] = "暴击%"
        target["substats"][3]["type"] = "速度"

        self.assertEqual(PureVisualSamplingExecutor().evaluate(sample).status, "ready")

    def test_ambiguous_page_multiple_targets_and_bad_target_fail_closed(self):
        cases = (
            (valid_sample(page={"kind": "inventory", "is_unambiguous": False}), "page_not_unambiguous_enhance_equipment"),
            (valid_sample(targets=valid_sample()["targets"] * 2), "target_not_unique"),
            (valid_sample(targets=[{**valid_sample()["targets"][0], "level": 88}]), "target_mismatch"),
        )
        for sample, reason in cases:
            with self.subTest(reason=reason):
                decision = PureVisualSamplingExecutor().evaluate(sample)
                self.assertEqual(decision.status, "fail_closed")
                self.assertIsNone(decision.next_action)
                self.assertIn(reason, decision.stop_reasons)
                self.assertFalse(decision.click_sent)

    def test_missing_fields_unknown_node_and_resource_shortfall_fail_closed(self):
        missing = valid_sample()
        missing.pop("captured_at")
        unknown_node = valid_sample(targets=[{**valid_sample()["targets"][0], "enhance": 1}])
        shortfall = valid_sample(resource_caps={"powder": 1, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600})

        cases = ((missing, "missing_captured_at"), (unknown_node, "unsupported_enhancement_node"), (shortfall, "resource_cap_exceeded"))
        for sample, reason in cases:
            with self.subTest(reason=reason):
                decision = PureVisualSamplingExecutor().evaluate(sample)
                self.assertEqual(decision.status, "fail_closed")
                self.assertIn(reason, decision.stop_reasons)

    def test_invalid_sampler_output_fails_closed(self):
        decision = PureVisualSamplingExecutor(sampler=StaticSampler([])).evaluate()

        self.assertEqual(decision.status, "fail_closed")
        self.assertEqual(decision.stop_reasons, ("invalid_sample_mapping",))


if __name__ == "__main__":
    unittest.main()
