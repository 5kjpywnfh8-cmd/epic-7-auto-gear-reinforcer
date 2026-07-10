import io
import unittest
from contextlib import redirect_stdout

from src.e7_enhance.cli import main


class CliTest(unittest.TestCase):
    def test_suggest_accepts_gui_saved_single_speed_hit_file(self):
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["suggest", "--input", "1跳速度.json", "--debug"])

        self.assertEqual(exit_code, 0)
        self.assertIn('"recommendation": "continue"', output.getvalue())
        self.assertIn('"dp_decision": "continue"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
