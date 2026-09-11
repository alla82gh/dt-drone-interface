#!/usr/bin/env python3
"""Transport-agnostic, read-only MSP audit probe.

No serial transport is implemented in Step 1F.2.  A later safety gate may add
one only after the offline tests and hardware-independent review are accepted.
"""

from dataclasses import dataclass
from typing import Protocol

from msp_protocol import MspFrame, decode_frame, encode_read_request


class ProbeTransport(Protocol):
    def transact(self, request: bytes) -> bytes:
        """Return one complete response frame for one request frame."""


@dataclass(frozen=True)
class ProbeResult:
    command: int
    payload: bytes


class ReadOnlyMspProbe:
    def __init__(self, transport: ProbeTransport) -> None:
        self._transport = transport

    def request(self, command: int) -> ProbeResult:
        request = encode_read_request(command)
        response = decode_frame(self._transport.transact(request), expected_direction=b">")
        if response.command != command:
            raise ValueError(
                "response command {} does not match request {}".format(
                    response.command, command
                )
            )
        return ProbeResult(command=response.command, payload=response.payload)


def main() -> None:
    raise SystemExit(
        "Hardware transport is intentionally unavailable in Step 1F.2"
    )


if __name__ == "__main__":
    main()
