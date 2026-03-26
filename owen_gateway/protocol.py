from __future__ import annotations

import struct
from dataclasses import dataclass


START_MARKER = b"#"
END_MARKER = b"\r"
NIBBLE_TO_ASCII = bytes(b"GHIJKLMNOPQRSTUV")
ASCII_TO_NIBBLE = {value: index for index, value in enumerate(NIBBLE_TO_ASCII)}


@dataclass(slots=True)
class OwenFrame:
    address: int
    request: bool
    parameter_hash: int
    payload: bytes = b""


def build_read_frame(
    address: int,
    parameter_name: str,
    parameter_index: int | None = None,
) -> bytes:
    payload = b""
    if parameter_index is not None:
        if not 0 <= parameter_index <= 0xFFFF:
            raise ValueError(f"parameter_index out of range: {parameter_index}")
        payload = parameter_index.to_bytes(2, "big")
    frame = OwenFrame(
        address=address,
        request=True,
        parameter_hash=hash_parameter_name(parameter_name),
        payload=payload,
    )
    return encode_frame(frame)


def expand_network_address(address: int, address_bits: int) -> int:
    if address_bits == 11:
        if not 0 <= address <= 0x7FF:
            raise ValueError(f"11-bit address out of range: {address}")
        return address
    if address_bits == 8:
        if not 0 <= address <= 0xFF:
            raise ValueError(f"8-bit address out of range: {address}")
        return address << 3
    raise ValueError(f"unsupported address_bits: {address_bits}")


def encode_frame(frame: OwenFrame) -> bytes:
    if not 0 <= frame.address <= 0x7FF:
        raise ValueError(f"address out of range: {frame.address}")
    if len(frame.payload) > 15:
        raise ValueError("payload too large")

    body = _encode_body(frame)
    return START_MARKER + _nibble_encode(body) + END_MARKER


def decode_frame(raw_frame: bytes) -> OwenFrame:
    if not raw_frame.startswith(START_MARKER) or not raw_frame.endswith(END_MARKER):
        raise ValueError("invalid frame markers")

    # OVEN frames are ASCII nibble-encoded on the wire, so the body must be
    # restored before CRC and header fields can be validated.
    body = _nibble_decode(raw_frame[1:-1])
    if len(body) < 4:
        raise ValueError("frame is too short")

    received_crc = int.from_bytes(body[-2:], "big")
    header_and_data = body[:-2]
    calculated_crc = crc16(header_and_data)
    if received_crc != calculated_crc:
        raise ValueError(
            f"crc mismatch: received=0x{received_crc:04X} expected=0x{calculated_crc:04X}"
        )

    # The compact 2-byte header stores 11-bit network address, request flag
    # and payload size in a packed bit layout defined by the OVEN protocol.
    header = header_and_data[0:2]
    block = header_and_data[2:]
    address = (header[0] << 3) | ((header[1] >> 5) & 0x07)
    request = bool((header[1] >> 4) & 0x01)
    size = (header[1] & 0x0F) + 2
    if len(block) != size:
        raise ValueError(f"invalid block size: {len(block)} != {size}")
    parameter_hash = int.from_bytes(block[0:2], "big")
    payload = block[2:]
    return OwenFrame(
        address=address,
        request=request,
        parameter_hash=parameter_hash,
        payload=payload,
    )


def decode_payload(payload: bytes, protocol_format: str) -> object:
    if protocol_format == "float32":
        if len(payload) == 4:
            return struct.unpack(">f", payload)[0]
        if len(payload) == 6:
            # Indexed values and operational values with a time mark both append
            # 2 service bytes after the 4-byte float payload.
            return struct.unpack(">f", payload[:4])[0]
        raise ValueError(f"float32 payload must be 4 or 6 bytes, got {len(payload)}")
    if protocol_format == "int16":
        if len(payload) == 1:
            value = payload[0]
            if value >= 0x80:
                value -= 0x100
            return value
        if len(payload) != 2:
            if len(payload) == 4:
                return struct.unpack(">h", payload[:2])[0]
            raise ValueError(f"int16 payload must be 2 or 4 bytes, got {len(payload)}")
        return struct.unpack(">h", payload)[0]
    if protocol_format == "stored_dot":
        if len(payload) == 3:
            sign = -1 if (payload[0] & 0x80) else 1
            exponent = (payload[0] >> 4) & 0x07
            mantissa = int.from_bytes(payload[1:], "big")
            return sign * (mantissa / (10**exponent))
        if len(payload) not in {1, 2}:
            raise ValueError(f"stored_dot payload must be 1, 2 or 3 bytes, got {len(payload)}")
        raw = int.from_bytes(payload.rjust(2, b"\x00"), "big")
        sign = -1 if (raw & 0x8000) else 1
        exponent = (raw >> 12) & 0x07
        mantissa = raw & 0x0FFF
        return sign * (mantissa / (10**exponent))
    if protocol_format == "uint16":
        if len(payload) == 1:
            return payload[0]
        if len(payload) != 2:
            if len(payload) == 4:
                return struct.unpack(">H", payload[:2])[0]
            raise ValueError(f"uint16 payload must be 2 or 4 bytes, got {len(payload)}")
        return struct.unpack(">H", payload)[0]
    if protocol_format == "uint32":
        if len(payload) != 4:
            if len(payload) == 6:
                return struct.unpack(">I", payload[:4])[0]
            raise ValueError(f"uint32 payload must be 4 or 6 bytes, got {len(payload)}")
        return struct.unpack(">I", payload)[0]
    if protocol_format == "raw":
        return payload
    raise ValueError(f"unsupported protocol_format: {protocol_format}")


def hash_parameter_name(name: str) -> int:
    normalized = _normalize_name(name)
    if not 1 <= len(normalized) <= 4:
        raise ValueError("OVEN parameter name must be 1..4 encoded symbols")
    # OVEN hashes parameter names as a fixed-width 4-symbol field padded with
    # spaces, with the "dot" attribute folded into each symbol code.
    while len(normalized) < 4:
        normalized.append(39 * 2)

    crc = 0
    for code in normalized:
        crc = _hash_byte((code << 1) & 0xFF, 7, crc)
    return crc


def crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc = _hash_byte(byte, 8, crc)
    return crc


def _normalize_name(name: str) -> list[int]:
    result: list[int] = []
    index = 0
    while index < len(name):
        char = name[index]
        has_dot = index + 1 < len(name) and name[index + 1] == "."
        if has_dot:
            index += 1

        upper = char.upper()
        if "0" <= upper <= "9":
            code = ord(upper) - ord("0")
        elif "A" <= upper <= "Z":
            code = ord(upper) - ord("A") + 10
        elif upper == "-":
            code = 36
        elif upper == "_":
            code = 37
        elif upper == "/":
            code = 38
        elif upper == " ":
            code = 39
        else:
            raise ValueError(f"unsupported symbol in parameter name: {char!r}")

        code *= 2
        if has_dot:
            code += 1
        result.append(code)
        index += 1
    return result


def _hash_byte(byte: int, bit_count: int, crc: int) -> int:
    for _ in range(bit_count):
        if ((byte ^ (crc >> 8)) & 0x80) != 0:
            crc = ((crc << 1) & 0xFFFF) ^ 0x8F57
        else:
            crc = (crc << 1) & 0xFFFF
        byte = (byte << 1) & 0xFF
    return crc


def _encode_body(frame: OwenFrame) -> bytes:
    block = frame.parameter_hash.to_bytes(2, "big") + frame.payload
    size = len(block)
    if not 2 <= size <= 17:
        raise ValueError("block size must be in range 2..17")

    header = bytes(
        [
            (frame.address >> 3) & 0xFF,
            ((frame.address & 0x07) << 5)
            | ((1 if frame.request else 0) << 4)
            | ((size - 2) & 0x0F),
        ]
    )
    crc = crc16(header + block)
    return header + block + crc.to_bytes(2, "big")


def _nibble_encode(body: bytes) -> bytes:
    encoded = bytearray()
    for byte in body:
        encoded.append(NIBBLE_TO_ASCII[(byte >> 4) & 0x0F])
        encoded.append(NIBBLE_TO_ASCII[byte & 0x0F])
    return bytes(encoded)


def _nibble_decode(encoded: bytes) -> bytes:
    if len(encoded) % 2 != 0:
        raise ValueError("nibble-encoded body must have even length")
    decoded = bytearray()
    for index in range(0, len(encoded), 2):
        try:
            hi = ASCII_TO_NIBBLE[encoded[index]]
            lo = ASCII_TO_NIBBLE[encoded[index + 1]]
        except KeyError as exc:
            raise ValueError(f"invalid nibble symbol: 0x{encoded[index]:02X}") from exc
        decoded.append((hi << 4) | lo)
    return bytes(decoded)
