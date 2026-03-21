from __future__ import annotations

import struct


def encode_registers(value: object, data_type: str) -> list[int]:
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
    if data_type in {"bool", "uint16", "int16"}:
        return 1
    if data_type in {"uint32", "int32", "float32"}:
        return 2
    raise ValueError(f"unsupported data_type: {data_type}")


def _split_words(data: bytes) -> list[int]:
    return [int.from_bytes(data[0:2], "big"), int.from_bytes(data[2:4], "big")]
