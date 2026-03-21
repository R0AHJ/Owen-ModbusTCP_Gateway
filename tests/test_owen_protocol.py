import struct
import unittest

from owen_gateway.protocol import (
    OwenFrame,
    build_read_frame,
    crc16,
    decode_frame,
    decode_payload,
    encode_frame,
    hash_parameter_name,
)


class OwenProtocolTests(unittest.TestCase):
    def test_known_hash_values(self) -> None:
        self.assertEqual(hash_parameter_name("Addr"), 0x9F62)
        self.assertEqual(hash_parameter_name("A.Len"), 0x1ED2)
        self.assertEqual(hash_parameter_name("dev"), 0xD681)
        self.assertEqual(hash_parameter_name("ver"), 0x2D5B)

    def test_encode_and_decode_read_frame(self) -> None:
        raw = build_read_frame(16, "rEAd")
        frame = decode_frame(raw)
        self.assertEqual(frame.address, 16)
        self.assertTrue(frame.request)
        self.assertEqual(frame.parameter_hash, hash_parameter_name("rEAd"))
        self.assertEqual(frame.payload, b"")

    def test_encode_and_decode_response_frame(self) -> None:
        payload = struct.pack(">f", 12.5)
        encoded = encode_frame(
            OwenFrame(
                address=16,
                request=False,
                parameter_hash=hash_parameter_name("rEAd"),
                payload=payload,
            )
        )
        frame = decode_frame(encoded)
        self.assertEqual(frame.address, 16)
        self.assertFalse(frame.request)
        self.assertEqual(decode_payload(frame.payload, "float32"), 12.5)

    def test_decode_float32_with_time_suffix(self) -> None:
        payload = struct.pack(">f", 12.5) + bytes.fromhex("1234")
        self.assertEqual(decode_payload(payload, "float32"), 12.5)

    def test_crc_is_stable(self) -> None:
        data = bytes.fromhex("1010ABCD")
        self.assertEqual(crc16(data), crc16(data))


if __name__ == "__main__":
    unittest.main()
