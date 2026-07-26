from __future__ import annotations

import unittest

from src.e7_enhance.visual_runtime import (
    ExpectedVisualState,
    VisualEvidence,
    VisualEvidenceGate,
    VisualNodeRequest,
    VisualOnlyEnhanceExecutor,
)


def valid_evidence(**overrides):
    evidence = {
        "schema_version": "e7_enhance.visual_evidence/1.0",
        "operation_id": "operation-001",
        "sample_id": "sample-001",
        "captured_at": "2026-07-26T10:00:00+08:00",
        "phase": "pre_action",
        "expected_node": 0,
        "page": {
            "page_type": "enhance_equipment",
            "is_unambiguous": True,
            "target_visible": True,
            "page_signature": "a" * 64,
        },
        "stability": {
            "sample_count": 3,
            "stable_count": 3,
            "poll_interval_ms": 250,
            "timeout_ms": 2000,
            "frame_hashes": ["b" * 64, "c" * 64, "d" * 64],
        },
        "anchors": [
            {"name": "back_arrow", "score": 0.99, "threshold": 0.98, "bright_ratio": 0.2},
            {"name": "help_icon", "score": 0.99, "threshold": 0.98, "bright_ratio": 0.2},
        ],
        "target": {
            "visible_fields": {"slot": "Weapon", "level": 85},
            "field_confidence": {"slot": 0.99, "level": 0.99},
            "candidate_count": 1,
            "visual_fingerprint": "e" * 64,
        },
        "resource_preview": {
            "visible": True,
            "materials": {"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0},
            "gold": 17600,
        },
        "sampler": {"adapter": "fake", "template_set": "fake", "version": "1"},
    }
    evidence.update(overrides)
    return evidence


class VisualEvidenceGateTest(unittest.TestCase):
    def test_stable_evidence_with_two_local_anchors_is_visual_only_unverified(self):
        result = VisualEvidenceGate().evaluate(
            VisualEvidence.from_mapping(valid_evidence()),
            ExpectedVisualState(node=0, phase="pre_action", visual_fingerprint="e" * 64),
        )

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.mode, "visual_only")
        self.assertEqual(result.verification, "unverified")
        self.assertEqual(result.stop_reasons, ())

    def test_unstable_frames_anchors_field_confidence_candidate_and_resources_fail_closed(self):
        expected = ExpectedVisualState(
            node=0,
            phase="pre_action",
            visual_fingerprint="e" * 64,
            resource_values={"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600},
        )
        cases = (
            (valid_evidence(stability={**valid_evidence()["stability"], "stable_count": 2}), "unstable_visual_state"),
            (valid_evidence(anchors=valid_evidence()["anchors"][:1]), "local_anchors_not_confirmed"),
            (valid_evidence(target={**valid_evidence()["target"], "field_confidence": {"slot": 0.979, "level": 0.99}}), "ocr_confidence_below_threshold"),
            (valid_evidence(target={**valid_evidence()["target"], "candidate_count": 2}), "target_not_unique"),
            (valid_evidence(target={**valid_evidence()["target"], "candidate_count": True}), "target_not_unique"),
            (valid_evidence(anchors=[
                {"name": "back_arrow", "score": 1.1, "threshold": 0.98, "bright_ratio": 0.2},
                {"name": "help_icon", "score": 0.99, "threshold": 0.98, "bright_ratio": 0.2},
            ]), "local_anchors_not_confirmed"),
            (valid_evidence(resource_preview={**valid_evidence()["resource_preview"], "gold": 17599}), "resource_reconciliation_failed"),
            (valid_evidence(resource_preview={
                **valid_evidence()["resource_preview"],
                "materials": {"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "unknown": 1},
            }), "resource_reconciliation_failed"),
        )

        for evidence, reason in cases:
            with self.subTest(reason=reason):
                result = VisualEvidenceGate().evaluate(VisualEvidence.from_mapping(evidence), expected)
                self.assertEqual(result.status, "fail_closed")
                self.assertEqual(result.mode, "visual_only")
                self.assertEqual(result.verification, "unverified")
                self.assertIn(reason, result.stop_reasons)


class ScriptedVisualSampler:
    def __init__(self, samples):
        self.samples = list(samples)
        self.requests = []

    def capture(self, request):
        self.requests.append(request)
        return VisualEvidence.from_mapping(self.samples.pop(0))


class RecordingVisualClicker:
    def __init__(self):
        self.calls = 0

    def click_enhance(self):
        self.calls += 1


class VisualOnlyEnhanceExecutorTest(unittest.TestCase):
    def test_one_node_runs_pre_click_post_then_exposes_next_node_as_unverified(self):
        post = valid_evidence(
            sample_id="sample-002",
            captured_at="2026-07-26T10:00:01+08:00",
            phase="post_action",
            expected_node=3,
            stability={**valid_evidence()["stability"], "frame_hashes": ["f" * 64, "1" * 64, "2" * 64]},
            resource_preview={
                "visible": True,
                "materials": {"powder": 0, "lower_enhance_stone": 0, "upper_enhance_stone": 0},
                "gold": 0,
            },
        )
        sampler = ScriptedVisualSampler((valid_evidence(), post))
        clicker = RecordingVisualClicker()

        result = VisualOnlyEnhanceExecutor(sampler, clicker).run_node(
            VisualNodeRequest(
                operation_id="operation-001",
                from_node=0,
                to_node=3,
                visual_fingerprint="e" * 64,
                visible_fields={"slot": "Weapon", "level": 85},
                resource_before={"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600},
                planned_cost={"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600},
                action_authorized=True,
            )
        )

        self.assertEqual(result.status, "completed_unverified")
        self.assertEqual(result.mode, "visual_only")
        self.assertEqual(result.verification, "unverified")
        self.assertEqual(result.next_node, 3)
        self.assertTrue(result.click_sent)
        self.assertEqual(clicker.calls, 1)
        self.assertEqual([request.phase for request in sampler.requests], ["pre_action", "post_action"])

    def test_node_jump_stops_before_click(self):
        sampler = ScriptedVisualSampler(())
        clicker = RecordingVisualClicker()

        result = VisualOnlyEnhanceExecutor(sampler, clicker).run_node(
            VisualNodeRequest(
                operation_id="operation-001",
                from_node=0,
                to_node=6,
                visual_fingerprint="e" * 64,
                visible_fields={"slot": "Weapon"},
                resource_before={"gold": 1},
                planned_cost={"gold": 1},
                action_authorized=True,
            )
        )

        self.assertEqual(result.status, "fail_closed")
        self.assertIn("node_sequence_jump", result.stop_reasons)
        self.assertFalse(result.click_sent)
        self.assertEqual(clicker.calls, 0)
        self.assertEqual(sampler.requests, [])

    def test_post_action_resource_conflict_is_unknown_and_same_node_is_never_retried(self):
        post_conflict = valid_evidence(
            sample_id="sample-002",
            captured_at="2026-07-26T10:00:01+08:00",
            phase="post_action",
            expected_node=3,
            stability={**valid_evidence()["stability"], "frame_hashes": ["f" * 64, "1" * 64, "2" * 64]},
        )
        sampler = ScriptedVisualSampler((valid_evidence(), post_conflict))
        clicker = RecordingVisualClicker()
        executor = VisualOnlyEnhanceExecutor(sampler, clicker)
        request = VisualNodeRequest(
            operation_id="operation-001",
            from_node=0,
            to_node=3,
            visual_fingerprint="e" * 64,
            visible_fields={"slot": "Weapon", "level": 85},
            resource_before={"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600},
            planned_cost={"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600},
            action_authorized=True,
        )

        unknown = executor.run_node(request)
        retried = executor.run_node(request)

        self.assertEqual(unknown.status, "fail_closed")
        self.assertTrue(unknown.click_sent)
        self.assertIn("unknown_result", unknown.stop_reasons)
        self.assertIn("resource_reconciliation_failed", unknown.stop_reasons)
        self.assertEqual(retried.status, "fail_closed")
        self.assertIn("single_action_already_attempted", retried.stop_reasons)
        self.assertFalse(retried.click_sent)
        self.assertEqual(clicker.calls, 1)

    def test_post_action_timestamp_must_increase(self):
        post = valid_evidence(
            sample_id="sample-002",
            captured_at="2026-07-26T10:00:00+08:00",
            phase="post_action",
            expected_node=3,
            stability={**valid_evidence()["stability"], "frame_hashes": ["f" * 64, "1" * 64, "2" * 64]},
            resource_preview={
                "visible": True,
                "materials": {"powder": 0, "lower_enhance_stone": 0, "upper_enhance_stone": 0},
                "gold": 0,
            },
        )
        clicker = RecordingVisualClicker()
        result = VisualOnlyEnhanceExecutor(ScriptedVisualSampler((valid_evidence(), post)), clicker).run_node(
            VisualNodeRequest(
                operation_id="operation-001",
                from_node=0,
                to_node=3,
                visual_fingerprint="e" * 64,
                visible_fields={"slot": "Weapon", "level": 85},
                resource_before={"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600},
                planned_cost={"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600},
                action_authorized=True,
            )
        )

        self.assertEqual(result.status, "fail_closed")
        self.assertIn("captured_at_not_increasing", result.stop_reasons)
        self.assertTrue(result.click_sent)
        self.assertEqual(clicker.calls, 1)

    def test_reused_post_action_frame_evidence_is_unknown_and_stops(self):
        post_reused = valid_evidence(
            sample_id="sample-002",
            captured_at="2026-07-26T10:00:01+08:00",
            phase="post_action",
            expected_node=3,
            resource_preview={
                "visible": True,
                "materials": {"powder": 0, "lower_enhance_stone": 0, "upper_enhance_stone": 0},
                "gold": 0,
            },
        )
        clicker = RecordingVisualClicker()
        result = VisualOnlyEnhanceExecutor(
            ScriptedVisualSampler((valid_evidence(), post_reused)), clicker
        ).run_node(
            VisualNodeRequest(
                operation_id="operation-001",
                from_node=0,
                to_node=3,
                visual_fingerprint="e" * 64,
                visible_fields={"slot": "Weapon", "level": 85},
                resource_before={"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600},
                planned_cost={"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600},
                action_authorized=True,
            )
        )

        self.assertEqual(result.status, "fail_closed")
        self.assertTrue(result.click_sent)
        self.assertIn("unknown_result", result.stop_reasons)
        self.assertIn("stale_visual_evidence_rejected", result.stop_reasons)
        self.assertEqual(clicker.calls, 1)


if __name__ == "__main__":
    unittest.main()
