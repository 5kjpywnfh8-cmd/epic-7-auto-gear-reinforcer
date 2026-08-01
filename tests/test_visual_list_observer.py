from __future__ import annotations

import copy
import unittest
import zlib

from src.e7_enhance.visual_adapter import StableFrames, UnstableFrameError, VisualFrame
from src.e7_enhance.visual_list_observer import (
    InMemoryPngListPageObserver,
    ListPageSampleFrames,
    ListPageSampleFrameCollector,
    RegisteredListPageRegions,
    RegisteredListRegion,
)


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


def png(seed=25):
    def chunk(kind, data):
        return len(data).to_bytes(4, "big") + kind + data + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")

    row = b"\x00" + bytes((seed, seed, seed)) * 100
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", (100).to_bytes(4, "big") + (100).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
        + chunk(b"IDAT", zlib.compress(row * 100))
        + chunk(b"IEND", b"")
    )


def stable_frames(payload=None):
    frame = VisualFrame.from_bytes(
        source="public-fixture-memory-png",
        payload=payload or png(),
        viewport=(100, 100),
        captured_at="2026-07-30T10:00:00+08:00",
    )
    return StableFrames((frame, frame, frame))


def sha(character):
    return character * 64


def registry():
    return RegisteredListPageRegions((
        RegisteredListRegion("list_header_region", {"left": 0.05, "top": 0.05, "right": 0.95, "bottom": 0.20}),
        RegisteredListRegion("candidate_list_region", {"left": 0.05, "top": 0.20, "right": 0.95, "bottom": 0.95}),
        RegisteredListRegion("candidate_card:1", {"left": 0.10, "top": 0.25, "right": 0.40, "bottom": 0.55}),
        RegisteredListRegion("candidate_card:2", {"left": 0.50, "top": 0.25, "right": 0.80, "bottom": 0.55}),
    ))


def candidate(candidate_id="candidate-001", region="candidate_card:1", fingerprint="c", **fields):
    values = {**TARGET, **fields}
    return {
        "candidate_id": candidate_id,
        "region": region,
        "visual_fingerprint": sha(fingerprint),
        "field_observations": [
            {"name": name, "value": value, "confidence": 0.99} for name, value in values.items()
        ],
    }


def local_observation(**overrides):
    value = {
        "anchors": [
            {"name": "list_header", "score": 0.99, "threshold": 0.98},
            {"name": "sort_button", "score": 0.99, "threshold": 0.98},
        ],
        "region_scores": {
            "list_header_region": {"score": 0.99, "threshold": 0.98},
            "candidate_list_region": {"score": 0.99, "threshold": 0.98},
        },
        "scroll_state": "not_scrolled",
        "page_boundary": {"top_visible": True, "bottom_visible": False},
        "candidates": [candidate()],
    }
    value.update(overrides)
    return value


class FakeRecognizer:
    def __init__(self, observation):
        self.observation = observation
        self.calls = []

    def observe(self, frame, regions):
        self.calls.append((frame, regions))
        return copy.deepcopy(self.observation)


class SequenceRecognizer:
    def __init__(self, observations):
        self.observations = [copy.deepcopy(item) for item in observations]
        self.calls = []

    def observe(self, frame, regions):
        self.calls.append(frame)
        return self.observations[len(self.calls) - 1]


class InMemoryPngListPageObserverTest(unittest.TestCase):
    def observe(self, local=None, frames=None):
        recognizer = FakeRecognizer(local or local_observation())
        result = InMemoryPngListPageObserver(registry(), recognizer).parse(
            "offline-fixture-operation", frames or stable_frames(), TARGET
        )
        return result, recognizer

    def test_stable_memory_png_and_registered_local_observation_construct_evidence(self):
        result, recognizer = self.observe()

        self.assertTrue(result.passed)
        self.assertEqual(result.evidence.viewport, (100, 100))
        self.assertEqual(result.evidence.stability["sample_count"], 3)
        self.assertTrue(result.evidence.stability["visual_fields_stable"])
        self.assertEqual(result.candidate_id, "candidate-001")
        self.assertNotIn("bounds", result.evidence.candidates[0])
        self.assertEqual(set(recognizer.calls[0][1]), {
            "list_header_region", "candidate_list_region", "candidate_card:1", "candidate_card:2"
        })

    def test_low_confidence_or_missing_registered_region_stops_before_evidence(self):
        low_confidence = local_observation()
        low_confidence["region_scores"]["candidate_list_region"]["score"] = 0.979
        missing_region = local_observation()
        missing_region["region_scores"].pop("candidate_list_region")

        for local, reason in ((low_confidence, "local_regions_not_confirmed"), (missing_region, "registered_region_scores_missing")):
            with self.subTest(reason=reason):
                result, _ = self.observe(local)
                self.assertEqual(result.status, "fail_closed")
                self.assertIn(reason, result.stop_reasons)
                self.assertIsNone(result.evidence)

    def test_unknown_scroll_duplicate_candidate_and_missing_field_stop_before_evidence(self):
        unknown_scroll = local_observation(scroll_state="unknown")
        duplicate = local_observation(candidates=[candidate(), candidate("candidate-002", "candidate_card:2", "c")])
        missing_field = local_observation()
        missing_field["candidates"][0]["field_observations"] = missing_field["candidates"][0]["field_observations"][1:]

        for local, reason in (
            (unknown_scroll, "scroll_or_page_boundary_unknown"),
            (duplicate, "duplicate_candidate_detected"),
            (missing_field, "candidate_fields_incomplete"),
        ):
            with self.subTest(reason=reason):
                result, _ = self.observe(local)
                self.assertEqual(result.status, "fail_closed")
                self.assertIn(reason, result.stop_reasons)
                self.assertIsNone(result.evidence)

    def test_unregistered_candidate_region_and_black_frame_fail_closed_without_recognizing(self):
        invalid_region = local_observation(candidates=[candidate(region="candidate_card:unknown")])
        result, recognizer = self.observe(invalid_region)
        self.assertEqual(result.stop_reasons, ("candidate_region_not_registered",))
        self.assertEqual(len(recognizer.calls), 1)

        black = stable_frames(png(seed=0))
        result, recognizer = self.observe(frames=black)
        self.assertEqual(result.stop_reasons, ("empty_or_black_frame",))
        self.assertEqual(recognizer.calls, [])

    def test_invalid_png_and_unstable_frame_records_fail_closed_before_recognizer(self):
        invalid = VisualFrame.from_bytes(
            source="public-fixture-memory-png",
            payload=b"not-a-png",
            viewport=(100, 100),
            captured_at="2026-07-30T10:00:00+08:00",
        )
        result, recognizer = self.observe(frames=StableFrames((invalid, invalid, invalid)))
        self.assertEqual(result.stop_reasons, ("invalid_memory_png",))
        self.assertEqual(recognizer.calls, [])

        result, recognizer = self.observe(frames=object())
        self.assertEqual(result.stop_reasons, ("stable_frames_not_confirmed",))
        self.assertEqual(recognizer.calls, [])

        changed = VisualFrame.from_bytes(
            source="public-fixture-memory-png",
            payload=png(seed=26),
            viewport=(100, 100),
            captured_at="2026-07-30T10:00:01+08:00",
        )
        with self.assertRaises(UnstableFrameError):
            StableFrames((stable_frames().frames[0], changed, changed))

    def test_list_page_batch_allows_png_hash_changes_when_visual_fields_match(self):
        frames = ListPageSampleFrames(tuple(
            VisualFrame.from_bytes(
                source="public-fixture-memory-png",
                payload=png(seed),
                viewport=(100, 100),
                captured_at=f"2026-07-30T10:00:0{index}+08:00",
            )
            for index, seed in enumerate((25, 26, 27))
        ))
        recognizer = SequenceRecognizer([local_observation()] * 3)
        result = InMemoryPngListPageObserver(registry(), recognizer).parse(
            "offline-fixture-operation", frames, TARGET
        )
        self.assertTrue(result.passed)
        self.assertEqual(len(set(result.evidence.stability["frame_hashes"])), 3)
        self.assertEqual(len(recognizer.calls), 3)

    def test_list_page_visual_field_candidate_and_anchor_drift_fail_closed(self):
        frames = ListPageSampleFrames(tuple(
            VisualFrame.from_bytes(
                source="public-fixture-memory-png",
                payload=png(seed),
                viewport=(100, 100),
                captured_at=f"2026-07-30T10:00:0{index}+08:00",
            )
            for index, seed in enumerate((25, 26, 27))
        ))
        cases = []
        changed_field = local_observation()
        changed_field["candidates"][0]["field_observations"][0]["value"] = "Armor"
        cases.append((changed_field, {"visual_fields_not_stable", "target_not_unique"}))
        changed_candidate = local_observation()
        changed_candidate["candidates"][0]["candidate_id"] = "candidate-002"
        cases.append((changed_candidate, {"visual_fields_not_stable", "target_not_unique"}))
        changed_region = local_observation()
        changed_region["candidates"][0]["region"] = "candidate_card:2"
        cases.append((changed_region, {"visual_fields_not_stable"}))
        changed_anchor = local_observation()
        changed_anchor["anchors"][0]["name"] = "other_header"
        cases.append((changed_anchor, {"visual_fields_not_stable", "list_anchors_not_confirmed"}))
        for changed, reasons in cases:
            recognizer = SequenceRecognizer([local_observation(), local_observation(), changed])
            result = InMemoryPngListPageObserver(registry(), recognizer).parse(
                "offline-fixture-operation", frames, TARGET
            )
            self.assertEqual(result.status, "fail_closed")
            self.assertTrue(set(result.stop_reasons) & reasons)

    def test_list_page_sample_collector_collects_exactly_three_frames(self):
        source_frames = iter(stable_frames().frames)
        batch = ListPageSampleFrameCollector(lambda: next(source_frames)).collect()
        self.assertEqual(batch.sample_count, 3)


if __name__ == "__main__":
    unittest.main()
