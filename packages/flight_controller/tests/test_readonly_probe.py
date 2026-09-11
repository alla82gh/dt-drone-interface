import pathlib
import sys
import unittest


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))

from msp_protocol import (  # noqa: E402
    MSP_RAW_IMU,
    MSP_SET_RAW_RC,
    UnsafeMspCommandError,
    decode_frame,
    encode_frame,
)
from readonly_msp_probe import ReadOnlyMspProbe  # noqa: E402


class FakeTransport:
    def __init__(self):
        self.requests = []

    def transact(self, request):
        self.requests.append(request)
        decoded = decode_frame(request, expected_direction=b"<")
        return encode_frame(b">", decoded.command, b"\x01\x02")


class ReadOnlyProbeTests(unittest.TestCase):
    def test_allows_measurement_query(self):
        transport = FakeTransport()
        result = ReadOnlyMspProbe(transport).request(MSP_RAW_IMU)
        self.assertEqual(result.command, MSP_RAW_IMU)
        self.assertEqual(result.payload, b"\x01\x02")
        self.assertEqual(len(transport.requests), 1)

    def test_write_command_is_rejected_before_transport(self):
        transport = FakeTransport()
        with self.assertRaises(UnsafeMspCommandError):
            ReadOnlyMspProbe(transport).request(MSP_SET_RAW_RC)
        self.assertEqual(transport.requests, [])


if __name__ == "__main__":
    unittest.main()
