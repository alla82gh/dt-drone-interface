import pathlib
import sys
import unittest


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))

from msp_protocol import (  # noqa: E402
    MSP_SET_RAW_RC,
    MSP_STATUS,
    MspProtocolError,
    UnsafeMspCommandError,
    decode_frame,
    encode_frame,
    encode_read_request,
    pack_u16_channels,
)


class MspProtocolTests(unittest.TestCase):
    def test_encodes_known_status_request(self):
        self.assertEqual(encode_read_request(MSP_STATUS), b"$M<\x00ee")

    def test_decodes_valid_response(self):
        raw = encode_frame(b">", MSP_STATUS, b"\x01\x02")
        decoded = decode_frame(raw, expected_direction=b">")
        self.assertEqual(decoded.command, MSP_STATUS)
        self.assertEqual(decoded.payload, b"\x01\x02")

    def test_rejects_write_command_in_readonly_request(self):
        with self.assertRaises(UnsafeMspCommandError):
            encode_read_request(MSP_SET_RAW_RC)

    def test_rejects_bad_checksum(self):
        raw = bytearray(encode_frame(b">", MSP_STATUS, b"\x01"))
        raw[-1] ^= 0xFF
        with self.assertRaises(MspProtocolError):
            decode_frame(bytes(raw))

    def test_rejects_bad_length(self):
        raw = encode_frame(b">", MSP_STATUS, b"\x01") + b"\x00"
        with self.assertRaises(MspProtocolError):
            decode_frame(raw)

    def test_packs_exactly_eight_channels_little_endian(self):
        payload = pack_u16_channels([1000, 1500, 2000, 1000, 1000, 1000, 1000, 1000])
        self.assertEqual(len(payload), 16)
        self.assertEqual(payload[:2], b"\xe8\x03")


if __name__ == "__main__":
    unittest.main()
