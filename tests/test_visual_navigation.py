from __future__ import annotations

import unittest

from src.e7_enhance.visual_navigation import (
    NavigationEvidenceGate,
    NavigationPageEvidence,
    VisualNodeChain,
)
from src.e7_enhance.visual_runtime import MODE, VERIFICATION, VisualNodeRequest, VisualNodeResult


TARGET = {
    "slot": "Weapon",
    "rank": "Epic",
    "level": 85,
    "enhance": 3,
    "set": "HealthSet",
    "main": {"type": "Attack", "value": 100},
    "substats": (
        ("AttackPercent", 13),
        ("CriticalHitChancePercent", 3),
        ("Speed", 2),
        ("EffectResistancePercent", 8),
    ),
    "gear_score": 37,
}


def evidence(**overrides):
    value = {
        "operation_id": "operation-001",
        "captured_at": "2026-07-29T10:00:00+08:00",
        "page_type": "equipment_list",
        "page_signature": "a" * 64,
        "viewport": (1280, 720),
        "stability": {"sample_count": 3, "stable_count": 3, "frame_hashes": ["b" * 64] * 3},
        "anchors": [
            {"name": "list_header", "score": 0.99, "threshold": 0.98},
            {"name": "sort_button", "score": 0.99, "threshold": 0.98},
            {
                "name": "open_detail",
                "score": 0.99,
                "threshold": 0.98,
                "bounds": {"left": 0.30, "top": 0.40, "right": 0.50, "bottom": 0.60},
            },
        ],
        "candidates": [
            {
                "candidate_id": "candidate-001",
                "visual_fingerprint": "c" * 64,
                "visible_fields": TARGET,
                "field_confidence": {name: 0.99 for name in TARGET},
            }
        ],
        "target_visible": True,
    }
    value.update(overrides)
    return NavigationPageEvidence.from_mapping(value)


class NavigationEvidenceGateTest(unittest.TestCase):
    def test_unique_list_target_and_verified_button_anchor_produce_normalized_point(self):
        gate = NavigationEvidenceGate()
        located = gate.locate_unique_target(evidence(), TARGET)
        click = gate.derive_anchor_click(
            evidence(),
            required_page="equipment_list",
            anchor_name="open_detail",
            target_visible=True,
        )

        self.assertTrue(located.passed)
        self.assertEqual(located.candidate_id, "candidate-001")
        self.assertEqual(located.visual_fingerprint, "c" * 64)
        self.assertTrue(click.passed)
        self.assertEqual((click.click_target.x, click.click_target.y), (0.4, 0.5))

    def test_missing_target_low_confidence_or_nonunique_target_fails_closed_before_click(self):
        gate = NavigationEvidenceGate()
        cases = (
            evidence(candidates=[]),
            evidence(candidates=[{**evidence().candidates[0], "field_confidence": {**evidence().candidates[0]["field_confidence"], "set": 0.979}}]),
            evidence(candidates=[evidence().candidates[0], {**evidence().candidates[0], "candidate_id": "candidate-002", "visual_fingerprint": "d" * 64}]),
        )
        for item in cases:
            with self.subTest(candidates=len(item.candidates)):
                result = gate.locate_unique_target(item, TARGET)
                self.assertEqual(result.status, "fail_closed")
                self.assertIn("target_not_unique", result.stop_reasons)
                self.assertIsNone(result.click_target)

    def test_missing_anchor_or_invalid_stability_fails_closed(self):
        gate = NavigationEvidenceGate()
        missing_anchor = evidence(anchors=evidence().anchors[:2])
        bad_stability = evidence(stability={"sample_count": 3, "stable_count": 3, "frame_hashes": ["b" * 64, "d" * 64, "b" * 64]})

        self.assertIn(
            "button_anchor_not_confirmed",
            gate.derive_anchor_click(missing_anchor, required_page="equipment_list", anchor_name="open_detail", target_visible=True).stop_reasons,
        )
        self.assertIn("unstable_visual_state", gate.locate_unique_target(bad_stability, TARGET).stop_reasons)

        visual_stable = evidence(stability={
            "sample_count": 3,
            "stable_count": 3,
            "frame_hashes": ["b" * 64, "d" * 64, "b" * 64],
            "visual_fields_stable": True,
        })
        self.assertTrue(gate.locate_unique_target(visual_stable, TARGET).passed)

        detail_variation = evidence(
            page_type="equipment_detail",
            stability={
                "sample_count": 3,
                "stable_count": 3,
                "frame_hashes": ["b" * 64, "d" * 64, "b" * 64],
                "visual_fields_stable": True,
            },
        )
        self.assertIn("unstable_visual_state", gate.locate_unique_target(detail_variation, TARGET).stop_reasons)

    def test_transition_requires_new_stable_frames_page_change_and_target_continuity(self):
        gate = NavigationEvidenceGate()
        before = evidence()
        after = evidence(
            captured_at="2026-07-29T10:00:01+08:00",
            page_type="equipment_detail",
            page_signature="e" * 64,
            stability={"sample_count": 3, "stable_count": 3, "frame_hashes": ["f" * 64] * 3},
        )

        passed = gate.verify_transition(before, after, expected_after_page="equipment_detail", expected_fingerprint="c" * 64)
        reused = gate.verify_transition(before, evidence(page_type="equipment_detail", page_signature="e" * 64), expected_after_page="equipment_detail")

        self.assertTrue(passed.passed)
        self.assertEqual(reused.status, "fail_closed")
        self.assertIn("captured_at_not_increasing", reused.stop_reasons)
        self.assertIn("stale_visual_evidence_rejected", reused.stop_reasons)


class RecordingNodeRunner:
    def __init__(self):
        self.requests = []

    def run_node(self, request):
        self.requests.append(request)
        after = {name: amount - request.planned_cost[name] for name, amount in request.resource_before.items()}
        return VisualNodeResult(
            "completed_unverified",
            MODE,
            VERIFICATION,
            True,
            request.to_node,
            (),
            {"expected_after": after},
            None,
            object(),
        )


def node_request(from_node, to_node, resources):
    return VisualNodeRequest(
        operation_id="operation-001",
        from_node=from_node,
        to_node=to_node,
        visual_fingerprint="a" * 64,
        visible_fields={"slot": "Weapon"},
        resource_before=resources,
        planned_cost={name: 1 for name in resources},
        action_authorized=True,
    )


class VisualNodeChainTest(unittest.TestCase):
    def test_second_node_uses_first_posterior_ledger(self):
        runner = RecordingNodeRunner()
        chain = VisualNodeChain(runner)
        first = chain.run_node(node_request(0, 3, {"gold": 2, "stone": 2}))
        second = chain.run_node(node_request(3, 6, {"gold": 1, "stone": 1}))

        self.assertEqual(first.status, "completed_unverified")
        self.assertEqual(second.status, "completed_unverified")
        self.assertEqual(len(runner.requests), 2)

    def test_mismatched_second_ledger_stops_before_runner(self):
        runner = RecordingNodeRunner()
        chain = VisualNodeChain(runner)
        chain.run_node(node_request(0, 3, {"gold": 2, "stone": 2}))
        rejected = chain.run_node(node_request(3, 6, {"gold": 2, "stone": 1}))

        self.assertEqual(rejected.status, "fail_closed")
        self.assertIn("prior_posterior_ledger_mismatch", rejected.stop_reasons)
        self.assertEqual(len(runner.requests), 1)


if __name__ == "__main__":
    unittest.main()
