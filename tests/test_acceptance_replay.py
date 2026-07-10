import json
import unittest
from pathlib import Path

from src.e7_enhance.acceptance_replay import AcceptanceReplay
from src.e7_enhance.models import Gear


class AcceptanceReplayTest(unittest.TestCase):
    def load(self, name: str):
        data = json.loads((Path("samples/manual_acceptance") / name).read_text(encoding="utf-8"))
        return AcceptanceReplay(Gear.from_dict(data), data["itemSource"], data["replayPath"])

    def test_heroic_plus12_adds_fourth_substat_and_reset_keeps_source_unchanged(self):
        replay = self.load("08_normal_heroic_plus9_replay.json")
        initial = replay.initial_gear
        step = replay.next()
        self.assertEqual(step["gear"].enhance, 12)
        self.assertEqual(len(step["gear"].substats), 4)
        self.assertEqual(len(step["before_substats"]), 3)
        self.assertEqual(initial.enhance, 9)
        self.assertEqual(replay.reset()["gear"], initial)

    def test_normal_epic_replay_recomputes_exact_dp(self):
        replay = self.load("03_normal_epic_plus6_speed.json")
        self.assertEqual(replay.snapshot(None)["suggestion"]["summary"]["recommendation"], "continue")
        step = replay.next()
        self.assertEqual(step["gear"].enhance, 9)
        self.assertEqual(step["suggestion"]["debug"]["dp_assist"]["decision_mode"], "exact_dp")
        replay.next()
        final = replay.next()
        self.assertEqual(final["gear"].enhance, 15)
        self.assertEqual(final["suggestion"]["summary"]["recommendation"], "convert")

    def test_rift_rejects_normal_speed_roll(self):
        data = json.loads((Path("samples/manual_acceptance") / "04_rift_epic_plus0.json").read_text(encoding="utf-8"))
        replay = AcceptanceReplay(Gear.from_dict(data), data["itemSource"], [{"enhance": 3, "type": "Speed", "value": 2}])
        with self.assertRaisesRegex(ValueError, "3~4"):
            replay.next()


if __name__ == "__main__":
    unittest.main()
