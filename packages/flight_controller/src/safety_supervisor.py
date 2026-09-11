#!/usr/bin/env python3
"""Hardware-independent command validation and flight-mode supervision."""

from dataclasses import dataclass
from enum import IntEnum
import math
import numbers
import time
from typing import Callable, Iterable, Optional, Tuple


class SafetyError(ValueError):
    """Base class for rejected commands and mode requests."""


class CommandValidationError(SafetyError):
    """Raised when a control command fails validation."""


class ModeTransitionError(SafetyError):
    """Raised when a requested mode transition is not currently safe."""


class FlightMode(IntEnum):
    DISARMED = 0
    ARMED = 1
    FLYING = 2


@dataclass(frozen=True)
class CommandLimits:
    minimum: int = 1000
    maximum: int = 2000

    def __post_init__(self) -> None:
        if self.minimum >= self.maximum:
            raise ValueError("minimum command limit must be below maximum")


@dataclass(frozen=True)
class ValidatedCommand:
    roll: int
    pitch: int
    yaw: int
    throttle: int

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return self.roll, self.pitch, self.yaw, self.throttle


def _validate_value(name: str, value: object, limits: CommandLimits) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise CommandValidationError("{} must be a real number".format(name))
    number = float(value)
    if not math.isfinite(number):
        raise CommandValidationError("{} must be finite".format(name))
    if number < limits.minimum or number > limits.maximum:
        raise CommandValidationError(
            "{}={} is outside [{}, {}]".format(
                name, number, limits.minimum, limits.maximum
            )
        )
    return int(round(number))


def validate_command(
    roll: object,
    pitch: object,
    yaw: object,
    throttle: object,
    limits: CommandLimits = CommandLimits(),
) -> ValidatedCommand:
    """Validate all four logical RC values atomically."""
    return ValidatedCommand(
        roll=_validate_value("roll", roll, limits),
        pitch=_validate_value("pitch", pitch, limits),
        yaw=_validate_value("yaw", yaw, limits),
        throttle=_validate_value("throttle", throttle, limits),
    )


class CommandWatchdog:
    """Track command freshness using a monotonic clock."""

    def __init__(
        self,
        timeout_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("command timeout must be positive")
        self.timeout_s = float(timeout_s)
        self._clock = clock
        self._command = None  # type: Optional[ValidatedCommand]
        self._updated_at = None  # type: Optional[float]

    def update(self, command: ValidatedCommand, now: Optional[float] = None) -> None:
        if not isinstance(command, ValidatedCommand):
            raise TypeError("watchdog accepts ValidatedCommand instances only")
        self._command = command
        self._updated_at = self._clock() if now is None else float(now)

    def age(self, now: Optional[float] = None) -> float:
        if self._updated_at is None:
            return math.inf
        current = self._clock() if now is None else float(now)
        return max(0.0, current - self._updated_at)

    def is_fresh(self, now: Optional[float] = None) -> bool:
        return self._command is not None and self.age(now) < self.timeout_s

    def fresh_command(self, now: Optional[float] = None) -> Optional[ValidatedCommand]:
        return self._command if self.is_fresh(now) else None

    def clear(self) -> None:
        self._command = None
        self._updated_at = None


class SafetySupervisor:
    """Conservative mode state machine with actuation disabled by default."""

    def __init__(
        self,
        watchdog: CommandWatchdog,
        allow_rc: bool = False,
        allow_arming: bool = False,
        require_confirmed_fc_state: bool = True,
    ) -> None:
        self.watchdog = watchdog
        self.allow_rc = bool(allow_rc)
        self.allow_arming = bool(allow_arming)
        self.require_confirmed_fc_state = bool(require_confirmed_fc_state)
        self.fc_state_confirmed = False
        self.mode = FlightMode.DISARMED

    def set_fc_state_confirmed(self, confirmed: bool) -> None:
        self.fc_state_confirmed = bool(confirmed)

    def _require_actuation_readiness(self) -> None:
        if not self.allow_rc:
            raise ModeTransitionError("RC transmission is disabled")
        if not self.allow_arming:
            raise ModeTransitionError("arming is disabled")
        if self.require_confirmed_fc_state and not self.fc_state_confirmed:
            raise ModeTransitionError("flight-controller state is unconfirmed")
        if not self.watchdog.is_fresh():
            raise ModeTransitionError("no fresh validated command is available")

    def request_mode(self, requested: FlightMode) -> FlightMode:
        try:
            requested = FlightMode(requested)
        except (TypeError, ValueError):
            raise ModeTransitionError("unknown flight mode")

        if requested == FlightMode.DISARMED:
            self.mode = FlightMode.DISARMED
            return self.mode

        self._require_actuation_readiness()
        if requested == self.mode:
            return self.mode
        if requested == FlightMode.ARMED:
            if self.mode not in (FlightMode.DISARMED, FlightMode.FLYING):
                raise ModeTransitionError("illegal transition to ARMED")
            self.mode = FlightMode.ARMED
            return self.mode

        if requested == FlightMode.FLYING:
            if self.mode != FlightMode.ARMED:
                raise ModeTransitionError("FLYING requires the ARMED state")
            self.mode = FlightMode.FLYING
            return self.mode

        raise ModeTransitionError("unsupported mode transition")

    def enforce_timeout(self, now: Optional[float] = None) -> bool:
        """Force the requested state to DISARMED when command freshness is lost."""
        if self.mode != FlightMode.DISARMED and not self.watchdog.is_fresh(now):
            self.mode = FlightMode.DISARMED
            return True
        return False
