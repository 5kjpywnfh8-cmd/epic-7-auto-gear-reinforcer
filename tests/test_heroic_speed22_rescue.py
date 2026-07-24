import unittest

from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.gui_support import debug_view_model
from src.e7_enhance.heroic_speed22_rescue import p22_exact, rescue_decision
from src.e7_enhance.models import Gear


def heroic_speed_gear(*, enhance=12, speed=14, rolls=4, slot="Helmet", rank="Heroic", with_speed=True):
    substats = [
        {"type": "Speed", "value": speed, "rolls": rolls},
        {"type": "HealthPercent", "value": 4, "rolls": 1},
        {"type": "DefensePercent", "value": 4, "rolls": 1},
        {"type": "EffectivenessPercent", "value": 4, "rolls": 1},
    ]
    if not with_speed:
        substats[0] = {"type": "CriticalHitChancePercent", "value": 4, "rolls": 1}
    if rank == "Heroic" and enhance < 12:
        substats = substats[:3]
    return Gear.from_dict(
        {
            "set": "Speed",
            "slot": slot,
            "mainStat": {"type": "Speed", "value": 45} if slot == "Boots" else {"type": "Health", "value": 2700},
            "enhance": enhance,
            "rank": rank,
            "substats": substats,
        }
    )


class HeroicSpeed22RescueTest(unittest.TestCase):
    def test_legal_plus12_fourteen_speed_four_rolls_is_rescued_and_debugged(self):
        gear = heroic_speed_gear()
        self.assertAlmostEqual(p22_exact(gear), 0.083057, places=6)

        result = advise_gear(gear, item_source="normal_85")
        rescue = result["debug"]["dp_assist"]["heroic_speed22_rescue"]
        view = debug_view_model(result)

        self.assertEqual(result["summary"]["recommendation"], "continue")
        self.assertEqual(rescue["baseline_action"], "stop")
        self.assertTrue(rescue["rescued"])
        self.assertAlmostEqual(rescue["p22"], 0.083057, places=6)
        self.assertEqual(view["heroic_speed22_rescue"]["当前节点"], 12)
        self.assertTrue(view["heroic_speed22_rescue"]["是否救回"])

    def test_p22_zero_is_not_rescued(self):
        gear = heroic_speed_gear(speed=12, rolls=1)
        decision = rescue_decision(gear, item_source="normal_85", baseline_continue=False)
        self.assertEqual(decision["p22"], 0.0)
        self.assertEqual(decision["action"], "stop")
        self.assertFalse(decision["rescued"])

    def test_scope_excludes_boot_epic_rift_and_missing_speed(self):
        cases = (
            (heroic_speed_gear(slot="Boots"), "normal_85"),
            (heroic_speed_gear(rank="Epic"), "normal_85"),
            (heroic_speed_gear(), "rift_85"),
            (heroic_speed_gear(with_speed=False), "normal_85"),
        )
        for gear, item_source in cases:
            with self.subTest(rank=gear.rank, slot=gear.slot, item_source=item_source):
                decision = rescue_decision(gear, item_source=item_source, baseline_continue=False)
                self.assertFalse(decision["applies"])
                self.assertFalse(decision["rescued"])
                self.assertEqual(decision["action"], "stop")

    def test_plus_zero_and_plus_three_are_not_in_scope(self):
        for enhance in (0, 3):
            with self.subTest(enhance=enhance):
                gear = heroic_speed_gear(enhance=enhance, speed=4, rolls=1)
                decision = rescue_decision(gear, item_source="normal_85", baseline_continue=False)
                self.assertFalse(decision["applies"])
                self.assertFalse(decision["rescued"])

    def test_base_continue_is_preserved_without_rescue_override(self):
        decision = rescue_decision(
            heroic_speed_gear(speed=12, rolls=1),
            item_source="normal_85",
            baseline_continue=True,
        )
        self.assertTrue(decision["applies"])
        self.assertEqual(decision["baseline_action"], "continue")
        self.assertEqual(decision["action"], "continue")
        self.assertFalse(decision["rescued"])


if __name__ == "__main__":
    unittest.main()
