#!/usr/bin/env python3
"""Non-actuating ROS scaffold for the Duckiedrone flight-controller interface."""

import rospy

from duckietown.dtros import DTROS, NodeType
from duckietown_msgs.msg import DroneControl, DroneMode as DroneModeMsg
from duckietown_msgs.srv import SetDroneMode, SetDroneModeResponse

from safety_supervisor import (
    CommandLimits,
    CommandValidationError,
    CommandWatchdog,
    FlightMode,
    ModeTransitionError,
    SafetySupervisor,
    validate_command,
)


class FlightControllerNode(DTROS):
    """Validate ROS commands while all hardware transmission remains disabled."""

    def __init__(self) -> None:
        super(FlightControllerNode, self).__init__(
            node_name="flight_controller_node",
            node_type=NodeType.CONTROL,
        )

        serial_enabled = bool(rospy.get_param("~serial/enabled", False))
        allow_queries = bool(rospy.get_param("~transmission/allow_queries", False))
        allow_rc = bool(rospy.get_param("~transmission/allow_rc", False))
        allow_arming = bool(rospy.get_param("~transmission/allow_arming", False))

        if serial_enabled or allow_queries or allow_rc or allow_arming:
            raise RuntimeError(
                "Step 1F.2 is offline-only; serial and command transmission must remain disabled"
            )

        frequency_hz = float(rospy.get_param("~control/frequency_hz", 50.0))
        timeout_s = float(rospy.get_param("~control/command_timeout_s", 0.25))
        self._limits = CommandLimits(
            minimum=int(rospy.get_param("~control/rc_min", 1000)),
            maximum=int(rospy.get_param("~control/rc_max", 2000)),
        )
        self._watchdog = CommandWatchdog(timeout_s=timeout_s)
        self._supervisor = SafetySupervisor(
            watchdog=self._watchdog,
            allow_rc=False,
            allow_arming=False,
            require_confirmed_fc_state=True,
        )

        self._mode_pub = rospy.Publisher(
            "~mode/current", DroneModeMsg, queue_size=1, latch=True
        )
        self._command_sub = rospy.Subscriber(
            "~commands", DroneControl, self._command_cb, queue_size=1
        )
        self._mode_service = rospy.Service(
            "~mode/set", SetDroneMode, self._set_mode_cb
        )
        self._timer = rospy.Timer(
            rospy.Duration(1.0 / frequency_hz), self._timer_cb
        )
        self._publish_mode()
        self.loginfo("Offline safety scaffold initialized; all MSP transmission is disabled")

    def _command_cb(self, message: DroneControl) -> None:
        try:
            command = validate_command(
                message.roll,
                message.pitch,
                message.yaw,
                message.throttle,
                self._limits,
            )
        except CommandValidationError as error:
            self.logwarn("Rejected flight command: {}".format(error))
            return
        self._watchdog.update(command)

    def _set_mode_cb(self, request) -> SetDroneModeResponse:
        previous = self._supervisor.mode
        try:
            self._supervisor.request_mode(FlightMode(request.mode.mode))
        except (ModeTransitionError, ValueError) as error:
            self.logwarn("Rejected mode request: {}".format(error))
        current = self._supervisor.mode
        self._publish_mode()
        return SetDroneModeResponse(
            previous_mode=DroneModeMsg(mode=int(previous)),
            current_mode=DroneModeMsg(mode=int(current)),
        )

    def _timer_cb(self, _event) -> None:
        if self._supervisor.enforce_timeout():
            self.logwarn("Command timeout forced the requested mode to DISARMED")
        self._publish_mode()

    def _publish_mode(self) -> None:
        self._mode_pub.publish(DroneModeMsg(mode=int(self._supervisor.mode)))


if __name__ == "__main__":
    node = FlightControllerNode()
    rospy.spin()
