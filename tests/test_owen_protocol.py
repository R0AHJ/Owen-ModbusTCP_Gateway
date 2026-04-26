import struct
import unittest

from owen_gateway.protocol import (
    OwenFrame,
    build_read_frame,
    build_write_frame,
    crc16,
    decode_frame,
    decode_payload,
    encode_payload,
    encode_frame,
    hash_parameter_name,
)
from owen_gateway.serial_client import _normalize_frame_response
from owen_gateway.serial_client import _read_oven_response


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

    def test_encode_and_decode_indexed_read_frame(self) -> None:
        raw = build_read_frame(16, "C.SP", 3)
        frame = decode_frame(raw)
        self.assertEqual(frame.address, 16)
        self.assertTrue(frame.request)
        self.assertEqual(frame.parameter_hash, hash_parameter_name("C.SP"))
        self.assertEqual(frame.payload, bytes.fromhex("0003"))

    def test_encode_and_decode_write_frame(self) -> None:
        raw = build_write_frame(16, "C.SP", bytes.fromhex("13E8"), 3)
        frame = decode_frame(raw)
        self.assertEqual(frame.address, 16)
        self.assertFalse(frame.request)
        self.assertEqual(frame.parameter_hash, hash_parameter_name("C.SP"))
        self.assertEqual(frame.payload, bytes.fromhex("13E80003"))

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

    def test_decode_uint16_with_index_suffix(self) -> None:
        payload = bytes.fromhex("00020003")
        self.assertEqual(decode_payload(payload, "uint16"), 2)

    def test_decode_uint16_single_byte(self) -> None:
        self.assertEqual(decode_payload(bytes.fromhex("01"), "uint16"), 1)

    def test_decode_int16_with_index_suffix(self) -> None:
        payload = bytes.fromhex("FFFE0001")
        self.assertEqual(decode_payload(payload, "int16"), -2)

    def test_crc_is_stable(self) -> None:
        data = bytes.fromhex("1010ABCD")
        self.assertEqual(crc16(data), crc16(data))

    def test_decode_stored_dot_integer_values(self) -> None:
        self.assertEqual(decode_payload(bytes.fromhex("004B"), "stored_dot"), 75)
        self.assertEqual(decode_payload(bytes.fromhex("0117"), "stored_dot"), 279)

    def test_decode_stored_dot_fractional_value(self) -> None:
        self.assertEqual(decode_payload(bytes.fromhex("2BC2"), "stored_dot"), 30.1)
        self.assertEqual(decode_payload(bytes.fromhex("13E8"), "stored_dot"), 100.0)

    def test_decode_stored_dot_three_byte_fractional_value(self) -> None:
        self.assertEqual(decode_payload(bytes.fromhex("2024EA"), "stored_dot"), 94.5)
        self.assertEqual(decode_payload(bytes.fromhex("20251C"), "stored_dot"), 95.0)

    def test_encode_stored_dot_matches_known_device_examples(self) -> None:
        self.assertEqual(encode_payload(-10.38, "stored_dot"), bytes([164, 14]))
        self.assertEqual(encode_payload(350.0, "stored_dot"), bytes([29, 172]))
        self.assertEqual(encode_payload(410.0, "stored_dot"), bytes([16, 16, 4]))
        self.assertEqual(encode_payload(0.0, "stored_dot"), bytes([16]))

    def test_encode_stored_dot_tolerates_float32_rounding_noise(self) -> None:
        self.assertEqual(encode_payload(1.100000023841858, "stored_dot"), bytes([0x1B]))

    def test_normalize_frame_response_appends_missing_carriage_return(self) -> None:
        raw = bytes.fromhex(
            "23 4a 47 47 4d 4f 4e 4f 4b 4b 49 52 48 53 48 56 52 4e 55 55 56 53 4c 54"
        )
        normalized = _normalize_frame_response(raw)
        self.assertTrue(normalized.endswith(b"\r"))

    def test_read_oven_response_collects_fragmented_frame(self) -> None:
        class FakeSerial:
            def __init__(self) -> None:
                self.timeout = 1.0
                self._chunks = [
                    b"#",
                    b"JGGMONO",
                    b"KKIRHSHV",
                    b"RNUUVSLT\r",
                ]

            @property
            def in_waiting(self) -> int:
                if not self._chunks:
                    return 0
                return len(self._chunks[0])

            def read(self, _size: int) -> bytes:
                if not self._chunks:
                    return b""
                return self._chunks.pop(0)

        serial_port = FakeSerial()

        response = _read_oven_response(serial_port, 1.0)

        self.assertEqual(
            response,
            bytes.fromhex(
                "23 4a 47 47 4d 4f 4e 4f 4b 4b 49 52 48 53 48 56 52 4e 55 55 56 53 4c 54 0d"
            ),
        )
        self.assertEqual(serial_port.timeout, 1.0)

    def test_read_oven_response_accepts_short_write_ack(self) -> None:
        class FakeSerial:
            def __init__(self) -> None:
                self.timeout = 1.0
                self._chunks = [b"#", b"JGGH", b"\x16"]

            @property
            def in_waiting(self) -> int:
                if not self._chunks:
                    return 0
                return len(self._chunks[0])

            def read(self, _size: int) -> bytes:
                if not self._chunks:
                    return b""
                return self._chunks.pop(0)

        response = _read_oven_response(FakeSerial(), 1.0)

        self.assertEqual(response, b"#JGGH\x16")


if __name__ == "__main__":
    unittest.main()
