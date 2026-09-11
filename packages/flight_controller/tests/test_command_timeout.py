import pathlib
import sys
import unittest


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))

from safety_supervisor import CommandWatchdog, validate_command  # noqa: E402


class CommandTimeoutTests(unittest.TestCase):
    def test_command_expires_at_timeout_boundary(self):
        watchdog = CommandWatchdog(timeout_s=0.25)
        watchdog.update(validate_command(1500, 1500, 1500, 1000), now=10.0)
        self.assertTrue(watchdog.is_fresh(now=10.249999))
        self.assertFalse(watchdog.is_fresh(now=10.25))

    def test_missing_command_is_never_fresh(self):
        watchdog = CommandWatchdog(timeout_s=0.25)
        self.assertFalse(watchdog.is_fresh(now=10.0))

    def test_backward_clock_input_does_not_create_negative_age(self):
        watchdog = CommandWatchdog(timeout_s=0.25)
        watchdog.update(validate_command(1500, 1500, 1500, 1000), now=10.0)
        self.assertEqual(watchdog.age(now=9.0), 0.0)


if __name__ == "__main__":
    unittest.main()
