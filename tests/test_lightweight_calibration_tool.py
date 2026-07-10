import unittest

from src.e7_enhance.models import Gear, Stat, validate_gear_structure
from tools.calibrate_full_category_lightweight import legal_full_category_templates, select_templates
from src.e7_enhance.enhance_simulator import STAT_TYPE_BY_KEY


class LightweightCalibrationToolTest(unittest.TestCase):
    def test_all_generated_category_templates_are_legal_gear_inputs(self):
        for template in legal_full_category_templates():
            with self.subTest(category=template["rule"]["category"], slot=template["slot"], count=template["count"]):
                gear = Gear(
                    set=template["set"],
                    slot=template["slot"],
                    main_stat=Stat(STAT_TYPE_BY_KEY[template["main_key"]], 0),
                    enhance=0,
                    level=85,
                    rank="Heroic" if template["count"] == 3 else "Epic",
                    substats=[Stat(STAT_TYPE_BY_KEY[key], 1) for key in template["keys"]],
                )
                validate_gear_structure(gear)

    def test_bounded_calibration_selection_varies_category_and_starts_with_speed_boot(self):
        templates = [item for item in legal_full_category_templates() if item["count"] == 4]
        selected = select_templates(templates, 3)

        self.assertEqual(selected[0]["slot"], "boot")
        self.assertEqual(len({item["rule"]["category"] for item in selected}), 3)


if __name__ == "__main__":
    unittest.main()
