import pathlib
import sys
import unittest


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))

from safety_supervisor import (  # noqa: E402
    CommandWatchdog,
    FlightMode,
    ModeTransitionError,
    SafetySupervisor,
    validate_command,
)


def ready_supervisor():
    watchdog = CommandWatchdog(timeout_s=0.25, clock=lambda: 10.0)
    watchdog.update(validate_command(1500, 1500, 1500, 1000), now=10.0)
    supervisor = SafetySupervisor(
        watchdog, allow_rc=True, allow_arming=True, require_confirmed_fc_state=True
    )
    supervisor.set_fc_state_confirmed(True)
    return supervisor


class ModeTransitionTests(unittest.TestCase):
    def test_defaults_to_disarmed_and_blocks_arming(self):
        supervisor = SafetySupervisor(CommandWatchdog(0.25))
        self.assertEqual(supervisor.mode, FlightMode.DISARMED)
        with self.assertRaises(ModeTransitionError):
            supervisor.request_mode(FlightMode.ARMED)

    def test_forbids_disarmed_to_flying(self):
        supervisor = ready_supervisor()
        with self.assertRaises(ModeTransitionError):
            supervisor.request_mode(FlightMode.FLYING)

    def test_allows_staged_transition_when_all_gates_are_ready(self):
        supervisor = ready_supervisor()
        self.assertEqual(supervisor.request_mode(FlightMode.ARMED), FlightMode.ARMED)
        self.assertEqual(supervisor.request_mode(FlightMode.FLYING), FlightMode.FLYING)

    def test_repeated_mode_request_is_idempotent(self):
        supervisor = ready_supervisor()
        supervisor.request_mode(FlightMode.ARMED)
        self.assertEqual(supervisor.request_mode(FlightMode.ARMED), FlightMode.ARMED)

    def test_timeout_forces_disarmed(self):
        supervisor = ready_supervisor()
        supervisor.request_mode(FlightMode.ARMED)
        self.assertTrue(supervisor.enforce_timeout(now=10.25))
        self.assertEqual(supervisor.mode, FlightMode.DISARMED)


if __name__ == "__main__":
    unittest.main()
