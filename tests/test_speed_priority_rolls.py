import random
import unittest

from tools.speed_priority_rolls import speed_roll_distribution, sample_speed_roll


class SpeedPriorityRollsTest(unittest.TestCase):
    def test_normal_epic_uses_stove_distribution_without_one_speed(self):
        distribution = speed_roll_distribution("normal_85", "Epic")
        self.assertEqual(distribution, ((2, 0.33223), (3, 0.33223), (4, 0.33223), (5, 0.00332)))
        values = {sample_speed_roll(random.Random(seed), "normal_85", "Epic") for seed in range(500)}
        self.assertNotIn(1, values)
        self.assertTrue(values <= {2, 3, 4, 5})

    def test_normal_heroic_uses_confirmed_mirrored_tail_without_five_speed(self):
        distribution = speed_roll_distribution("normal_85", "Heroic")
        self.assertEqual(distribution, ((1, 0.00332), (2, 0.33223), (3, 0.33223), (4, 0.33223)))
        values = {sample_speed_roll(random.Random(seed), "normal_85", "Heroic") for seed in range(500)}
        self.assertNotIn(5, values)
        self.assertTrue(values <= {1, 2, 3, 4})

    def test_rare_speed_rolls_removed_renormalizes_only_remaining_normal_values(self):
        distribution = speed_roll_distribution("normal_85", "Epic", rare_speed_rolls_removed=True)
        self.assertEqual(distribution, ((2, 1 / 3), (3, 1 / 3), (4, 1 / 3)))

    def test_rift_remains_a_separate_distribution(self):
        self.assertNotEqual(
            speed_roll_distribution("rift_85", "Epic"),
            speed_roll_distribution("normal_85", "Epic"),
        )
        with self.assertRaisesRegex(ValueError, "Heroic.*rift_85"):
            speed_roll_distribution("rift_85", "Heroic")
