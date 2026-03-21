import struct
import unittest

from owen_gateway.encoding import encode_registers, register_width


class EncodingTests(unittest.TestCase):
    def test_bool_encoding(self) -> None:
        self.assertEqual(encode_registers(True, "bool"), [1])
        self.assertEqual(encode_registers(False, "bool"), [0])

    def test_int16_encoding(self) -> None:
        self.assertEqual(encode_registers(-1, "int16"), [0xFFFF])
        self.assertEqual(encode_registers(123, "int16"), [123])

    def test_uint32_encoding(self) -> None:
        self.assertEqual(encode_registers(0x12345678, "uint32"), [0x1234, 0x5678])

    def test_float32_encoding(self) -> None:
        expected = [
            int.from_bytes(struct.pack(">f", 1.5)[0:2], "big"),
            int.from_bytes(struct.pack(">f", 1.5)[2:4], "big"),
        ]
        self.assertEqual(encode_registers(1.5, "float32"), expected)

    def test_register_width(self) -> None:
        self.assertEqual(register_width("bool"), 1)
        self.assertEqual(register_width("float32"), 2)


if __name__ == "__main__":
    unittest.main()
