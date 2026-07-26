from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.e7_enhance.ocr_paddle import (
    BACKPACK_DETAIL_PANEL,
    BACKPACK_DETAIL_ENHANCE_EVIDENCE,
    BACKPACK_DETAIL_SET_NAME,
    BACKPACK_ENHANCE_PANEL,
    BACKPACK_SET_NAME,
    PaddleOcrError,
    _crop_bounds,
    _enhance_bounds,
    _configure_cache,
    _set_bounds,
    parse_backpack_enhance_lines,
)
from src.e7_enhance.ocr_regions import equipment_regions


class OcrPaddleTest(unittest.TestCase):
    def _base_lines(self, set_name: str = "伤口套装(0/4)", critical_confidence: float = 0.999):
        return [
            {"text": "85", "confidence": 0.999}, {"text": "传说武器", "confidence": 0.999},
            {"text": "攻击力", "confidence": 0.999}, {"text": "100", "confidence": 0.999},
            {"text": "生命值", "confidence": 0.999}, {"text": "8%", "confidence": 0.999},
            {"text": "攻击力", "confidence": 0.999}, {"text": "4%", "confidence": 0.999},
            {"text": "暴击伤害", "confidence": critical_confidence}, {"text": "5%", "confidence": 0.999},
            {"text": "生命值", "confidence": 0.999}, {"text": "159", "confidence": 0.999},
            {"text": "装备分数", "confidence": 0.999}, {"text": "25", "confidence": 0.999},
            {"text": set_name, "confidence": 0.999}, {"text": "exp0/525", "confidence": 0.999},
        ]

    def test_right_detail_crop_and_anchor_regions_are_stable_and_inside_image(self):
        self.assertEqual(_crop_bounds(1280, 720), (768, 58, 1242, 619))
        self.assertEqual(_set_bounds(1280, 720), (819, 547, 1216, 619))
        self.assertEqual(_enhance_bounds(1280, 720), (819, 115, 1216, 180))
        self.assertEqual(BACKPACK_DETAIL_PANEL["left"], 0.60)
        self.assertEqual(BACKPACK_DETAIL_SET_NAME["bottom"], 0.86)
        self.assertEqual(BACKPACK_DETAIL_ENHANCE_EVIDENCE["top"], 0.16)
        self.assertIs(BACKPACK_ENHANCE_PANEL, BACKPACK_DETAIL_PANEL)
        self.assertIs(BACKPACK_SET_NAME, BACKPACK_DETAIL_SET_NAME)
        self.assertEqual(_crop_bounds(1920, 1080), (1152, 87, 1863, 929))
        self.assertEqual(_set_bounds(1920, 1080), (1228, 821, 1824, 929))
        self.assertEqual(_enhance_bounds(1920, 1080), (1228, 173, 1824, 270))
        with self.assertRaises(PaddleOcrError):
            _crop_bounds(720, 1280)
        names = {region["name"] for region in equipment_regions()["regions"]}
        self.assertTrue({"detail_header_anchor", "set_anchor", "enhance_anchor", "detail_score_anchor"}.issubset(names))

    def test_enhance_evidence_requires_explicit_non_conflicting_text(self):
        direct = self._base_lines()
        direct[-1] = {"text": "+3", "confidence": 0.999}
        self.assertEqual(parse_backpack_enhance_lines(direct)["fields"]["enhance"]["normalized"], 3)
        self.assertEqual(parse_backpack_enhance_lines(self._base_lines() + [{"text": "+3", "confidence": 0.999}])["fields"]["enhance"]["normalized"], 3)

        no_evidence = self._base_lines()[:-1]
        parsed = parse_backpack_enhance_lines(no_evidence)
        self.assertFalse(parsed["accepted"])
        self.assertIn("missing:enhance", parsed["rejection_reasons"])

        nonzero_experience = self._base_lines()
        nonzero_experience[-1] = {"text": "exp1/525", "confidence": 0.999}
        parsed = parse_backpack_enhance_lines(nonzero_experience)
        self.assertFalse(parsed["accepted"])
        self.assertIn("unrecognized:enhance_from_experience_bar", parsed["rejection_reasons"])

        conflicting = self._base_lines()[:-1] + [
            {"text": "+0", "confidence": 0.999}, {"text": "+3", "confidence": 0.999},
        ]
        parsed = parse_backpack_enhance_lines(conflicting)
        self.assertFalse(parsed["accepted"])
        self.assertIn("conflicting:enhance_evidence", parsed["rejection_reasons"])

    def test_observed_low_confidence_set_remains_rejected(self):
        parsed = parse_backpack_enhance_lines([
            {**line, "confidence": 0.971498} if line["text"] == "命中套装(0/2)" else line
            for line in self._base_lines("命中套装(0/2)")
        ])
        self.assertFalse(parsed["accepted"])
        self.assertIn("low_confidence:set", parsed["rejection_reasons"])

    def test_cache_path_rejects_non_ascii_windows_path(self):
        with self.assertRaises(PaddleOcrError):
            _configure_cache(Path("中文缓存"))

    def test_cache_path_is_process_local_and_ascii(self):
        with tempfile.TemporaryDirectory(prefix="e7ocr-") as temporary:
            path = _configure_cache(Path(temporary))
            self.assertTrue(path.name == "userprofile")
            self.assertTrue(str(path).isascii())

    def test_parser_extracts_epic_ring_and_rejects_missing_enhance_low_set_confidence(self):
        texts = [
            ("85", 0.99), ("传说戒指", 0.999), ("智龙红玉", 0.999),
            ("生命值", 0.999), ("12%", 0.999),
            ("防御力", 0.999), ("5%", 0.999),
            ("暴击率", 0.999), ("5%", 0.999),
            ("攻击力", 0.999), ("6%", 0.999),
            ("攻击力", 0.999), ("38", 0.999),
            ("装备分数", 0.999), ("27", 0.999),
            ("速度套装(0/4)", 0.976382), ("exp0/525", 0.9931),
        ]
        parsed = parse_backpack_enhance_lines([
            {"text": text, "confidence": confidence} for text, confidence in texts
        ])
        self.assertFalse(parsed["accepted"])
        self.assertEqual(parsed["fields"]["rank"]["normalized"], "Epic")
        self.assertEqual(parsed["fields"]["slot"]["normalized"], "Ring")
        self.assertEqual(parsed["fields"]["set"]["normalized"], "SpeedSet")
        self.assertEqual(parsed["fields"]["mainStat"]["type"]["normalized"], "HealthPercent")
        self.assertEqual(
            [(row["type"]["normalized"], row["value"]["normalized"]) for row in parsed["fields"]["substats"]],
            [("DefensePercent", 5), ("CriticalHitChancePercent", 5), ("AttackPercent", 6), ("Attack", 38)],
        )
        self.assertEqual(parsed["fields"]["enhance"]["normalized"], 0)
        self.assertEqual(parsed["rejection_reasons"], ["low_confidence:set"])

    def test_parser_prefers_the_highest_confidence_set_name_pass(self):
        lines = [
            {"text": "传说戒指", "confidence": 0.999}, {"text": "85", "confidence": 0.999},
            {"text": "生命值", "confidence": 0.999}, {"text": "12%", "confidence": 0.999},
            {"text": "防御力", "confidence": 0.999}, {"text": "5%", "confidence": 0.999},
            {"text": "装备分数", "confidence": 0.999}, {"text": "27", "confidence": 0.999},
            {"text": "速度套装(0/4)", "confidence": 0.976}, {"text": "速度套装(0/4)", "confidence": 0.998},
            {"text": "exp0/525", "confidence": 0.993},
        ]
        parsed = parse_backpack_enhance_lines(lines)
        self.assertTrue(parsed["accepted"])
        self.assertEqual(parsed["fields"]["set"]["confidence"], 0.998)

    def test_unknown_set_rejects_closed(self):
        parsed = parse_backpack_enhance_lines(self._base_lines("未知套装(0/4)"))
        self.assertFalse(parsed["accepted"])
        self.assertIn("unrecognized:set", parsed["rejection_reasons"])

    def test_injury_set_uses_formal_aliases(self):
        parsed = parse_backpack_enhance_lines(self._base_lines())
        self.assertTrue(parsed["accepted"], parsed["rejection_reasons"])
        self.assertEqual(parsed["fields"]["set"]["normalized"], "InjurySet")

    def test_low_confidence_critical_damage_rejects_without_local_retry(self):
        parsed = parse_backpack_enhance_lines(self._base_lines(critical_confidence=0.949667))
        self.assertFalse(parsed["accepted"])
        self.assertIn("low_confidence:substats[2]", parsed["rejection_reasons"])

    def test_local_retry_accepts_only_after_it_reaches_threshold(self):
        lines = self._base_lines(critical_confidence=0.949667)
        lines.append({"text": "暴击伤害", "confidence": 0.981, "retry_for": 8})
        parsed = parse_backpack_enhance_lines(lines)
        self.assertTrue(parsed["accepted"], parsed["rejection_reasons"])
        critical = parsed["fields"]["substats"][2]["type"]
        self.assertEqual(critical["confidence"], 0.981)
        self.assertEqual(critical["local_retry"]["text"], "暴击伤害")

    def test_local_retry_below_threshold_keeps_low_confidence_rejection(self):
        lines = self._base_lines(critical_confidence=0.949667)
        lines.append({"text": "暴击伤害", "confidence": 0.979, "retry_for": 8})
        parsed = parse_backpack_enhance_lines(lines)
        self.assertFalse(parsed["accepted"])
        self.assertIn("low_confidence:substats[2]", parsed["rejection_reasons"])
        self.assertNotIn("local_retry", parsed["fields"]["substats"][2]["type"])


if __name__ == "__main__":
    unittest.main()
