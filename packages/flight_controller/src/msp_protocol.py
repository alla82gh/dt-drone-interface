#!/usr/bin/env python3
"""Pure, hardware-independent helpers for MultiWii Serial Protocol v1.

This module performs no serial I/O.  The read-only request helper enforces a
strict allowlist so that an audit probe cannot construct an actuator or
configuration-write request by mistake.
"""

from dataclasses import dataclass
import struct
from typing import Iterable, Optional


MSP_IDENT = 100
MSP_STATUS = 101
MSP_RAW_IMU = 102
MSP_RC = 105
MSP_ATTITUDE = 108
MSP_ANALOG = 110

MSP_SET_RAW_RC = 200
MSP_SET_PID = 202
MSP_ACC_CALIBRATION = 205
MSP_MAG_CALIBRATION = 206
MSP_RESET_CONF = 208
MSP_EEPROM_WRITE = 250

READ_ONLY_COMMANDS = frozenset(
    {MSP_IDENT, MSP_STATUS, MSP_RAW_IMU, MSP_RC, MSP_ATTITUDE, MSP_ANALOG}
)
WRITE_COMMANDS = frozenset(
    {
        MSP_SET_RAW_RC,
        MSP_SET_PID,
        MSP_ACC_CALIBRATION,
        MSP_MAG_CALIBRATION,
        MSP_RESET_CONF,
        MSP_EEPROM_WRITE,
    }
)

_PREFIX = b"$M"
_REQUEST = b"<"
_RESPONSE = b">"
_ERROR = b"!"
_VALID_DIRECTIONS = frozenset({_REQUEST, _RESPONSE, _ERROR})


class MspProtocolError(ValueError):
    """Raised when an MSP frame is malformed or internally inconsistent."""


class UnsafeMspCommandError(MspProtocolError):
    """Raised when a command is outside the read-only audit allowlist."""


@dataclass(frozen=True)
class MspFrame:
    direction: bytes
    command: int
    payload: bytes


def _validate_command_id(command: int) -> int:
    if isinstance(command, bool) or not isinstance(command, int):
        raise MspProtocolError("MSP command ID must be an integer")
    if not 0 <= command <= 255:
        raise MspProtocolError("MSP command ID must be in [0, 255]")
    return command


def checksum(size: int, command: int, payload: bytes = b"") -> int:
    """Return the MSP v1 XOR checksum for a frame body."""
    value = size ^ command
    for byte in payload:
        value ^= byte
    return value & 0xFF


def encode_frame(direction: bytes, command: int, payload: bytes = b"") -> bytes:
    """Encode one complete MSP v1 frame without performing I/O."""
    command = _validate_command_id(command)
    if direction not in _VALID_DIRECTIONS:
        raise MspProtocolError("invalid MSP direction")
    if not isinstance(payload, bytes):
        raise MspProtocolError("MSP payload must be bytes")
    if len(payload) > 255:
        raise MspProtocolError("MSP v1 payload exceeds 255 bytes")
    size = len(payload)
    return _PREFIX + direction + bytes((size, command)) + payload + bytes(
        (checksum(size, command, payload),)
    )


def encode_read_request(command: int) -> bytes:
    """Encode a zero-payload request only when it is audit-safe."""
    command = _validate_command_id(command)
    if command not in READ_ONLY_COMMANDS:
        raise UnsafeMspCommandError(
            "MSP command {} is not in the read-only allowlist".format(command)
        )
    return encode_frame(_REQUEST, command)


def decode_frame(frame: bytes, expected_direction: Optional[bytes] = None) -> MspFrame:
    """Validate and decode exactly one complete MSP v1 frame."""
    if not isinstance(frame, bytes):
        raise MspProtocolError("MSP frame must be bytes")
    if len(frame) < 6:
        raise MspProtocolError("MSP frame is shorter than the minimum length")
    if frame[:2] != _PREFIX:
        raise MspProtocolError("invalid MSP frame prefix")

    direction = frame[2:3]
    if direction not in _VALID_DIRECTIONS:
        raise MspProtocolError("invalid MSP frame direction")
    if expected_direction is not None and direction != expected_direction:
        raise MspProtocolError("unexpected MSP frame direction")

    size = frame[3]
    command = frame[4]
    expected_length = 6 + size
    if len(frame) != expected_length:
        raise MspProtocolError(
            "MSP length mismatch: expected {}, got {}".format(
                expected_length, len(frame)
            )
        )

    payload = frame[5 : 5 + size]
    received_checksum = frame[-1]
    expected_checksum = checksum(size, command, payload)
    if received_checksum != expected_checksum:
        raise MspProtocolError("MSP checksum mismatch")

    return MspFrame(direction=direction, command=command, payload=payload)


def pack_u16_channels(channels: Iterable[int]) -> bytes:
    """Pack eight validated unsigned 16-bit values for offline tests only."""
    values = tuple(channels)
    if len(values) != 8:
        raise MspProtocolError("exactly eight RC channels are required")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in values):
        raise MspProtocolError("RC channel values must be integers")
    if any(v < 0 or v > 65535 for v in values):
        raise MspProtocolError("RC channel value is outside uint16 range")
    return struct.pack("<8H", *values)
