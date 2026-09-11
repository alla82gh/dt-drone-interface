import math
import pathlib
import sys
import unittest


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))

from safety_supervisor import (  # noqa: E402
    CommandLimits,
    CommandValidationError,
    validate_command,
)


class CommandValidationTests(unittest.TestCase):
    def test_accepts_inclusive_boundaries(self):
        command = validate_command(1000, 2000, 1500, 1000)
        self.assertEqual(command.as_tuple(), (1000, 2000, 1500, 1000))

    def test_rounds_finite_in_range_controller_output(self):
        command = validate_command(1500.2, 1499.8, 1500.4, 1200.6)
        self.assertEqual(command.as_tuple(), (1500, 1500, 1500, 1201))

    def test_rejects_out_of_range_atomically(self):
        with self.assertRaises(CommandValidationError):
            validate_command(999, 1500, 1500, 1000)
        with self.assertRaises(CommandValidationError):
            validate_command(1500, 2001, 1500, 1000)

    def test_rejects_non_finite_values(self):
        for invalid in (math.nan, math.inf, -math.inf):
            with self.assertRaises(CommandValidationError):
                validate_command(invalid, 1500, 1500, 1000)

    def test_rejects_bool_and_text(self):
        for invalid in (True, "1500", None):
            with self.assertRaises(CommandValidationError):
                validate_command(invalid, 1500, 1500, 1000)

    def test_rejects_invalid_limits(self):
        with self.assertRaises(ValueError):
            CommandLimits(2000, 1000)


if __name__ == "__main__":
    unittest.main()
