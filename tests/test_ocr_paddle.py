from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.e7_enhance.ocr_paddle import (
    PaddleOcrError,
    _crop_bounds,
    _configure_cache,
    _set_bounds,
    parse_backpack_enhance_lines,
)


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

    def test_backpack_crop_is_stable_and_inside_image(self):
        self.assertEqual(_crop_bounds(1280, 720), (20, 70, 390, 500))
        self.assertEqual(_set_bounds(1280, 720), (65, 430, 220, 470))

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
