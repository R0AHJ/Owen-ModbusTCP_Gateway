from __future__ import annotations

import struct


def encode_registers(value: object, data_type: str) -> list[int]:
    # The gateway keeps all published values in a canonical Modbus form:
    # a sequence of 16-bit big-endian registers. This is the single place
    # where Python values are converted into that wire representation.
    if data_type == "bool":
        return [1 if bool(value) else 0]
    if data_type == "uint16":
        ivalue = int(value)
        if not 0 <= ivalue <= 0xFFFF:
            raise ValueError(f"uint16 out of range: {ivalue}")
        return [ivalue]
    if data_type == "int16":
        ivalue = int(value)
        if not -0x8000 <= ivalue <= 0x7FFF:
            raise ValueError(f"int16 out of range: {ivalue}")
        return [ivalue & 0xFFFF]
    if data_type == "uint32":
        ivalue = int(value)
        if not 0 <= ivalue <= 0xFFFFFFFF:
            raise ValueError(f"uint32 out of range: {ivalue}")
        return _split_words(struct.pack(">I", ivalue))
    if data_type == "int32":
        ivalue = int(value)
        if not -0x80000000 <= ivalue <= 0x7FFFFFFF:
            raise ValueError(f"int32 out of range: {ivalue}")
        return _split_words(struct.pack(">i", ivalue))
    if data_type == "float32":
        return _split_words(struct.pack(">f", float(value)))
    raise ValueError(f"unsupported data_type: {data_type}")


def register_width(data_type: str) -> int:
    # Width is used by config validation and datastore sizing, so it must stay
    # consistent with the packing rules in encode_registers().
    if data_type in {"bool", "uint16", "int16"}:
        return 1
    if data_type in {"uint32", "int32", "float32"}:
        return 2
    raise ValueError(f"unsupported data_type: {data_type}")


def decode_registers(registers: list[int], data_type: str) -> object:
    # Modbus writes arrive as 16-bit registers and must be converted back into
    # the same Python value shapes that encode_registers() accepts.
    if data_type == "bool":
        if len(registers) != 1:
            raise ValueError(f"bool requires 1 register, got {len(registers)}")
        return bool(registers[0])
    if data_type == "uint16":
        if len(registers) != 1:
            raise ValueError(f"uint16 requires 1 register, got {len(registers)}")
        return registers[0]
    if data_type == "int16":
        if len(registers) != 1:
            raise ValueError(f"int16 requires 1 register, got {len(registers)}")
        value = registers[0]
        if value >= 0x8000:
            value -= 0x10000
        return value
    if data_type in {"uint32", "int32", "float32"}:
        if len(registers) != 2:
            raise ValueError(f"{data_type} requires 2 registers, got {len(registers)}")
        raw = registers[0].to_bytes(2, "big") + registers[1].to_bytes(2, "big")
        if data_type == "uint32":
            return struct.unpack(">I", raw)[0]
        if data_type == "int32":
            return struct.unpack(">i", raw)[0]
        return struct.unpack(">f", raw)[0]
    raise ValueError(f"unsupported data_type: {data_type}")


def _split_words(data: bytes) -> list[int]:
    # 32-bit values are published as two consecutive Modbus holding registers
    # in network byte order, matching the layout used throughout the gateway.
    return [int.from_bytes(data[0:2], "big"), int.from_bytes(data[2:4], "big")]
