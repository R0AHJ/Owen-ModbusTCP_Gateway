from __future__ import annotations

from owen_gateway.config import SerialConfig
from owen_gateway.protocol import (
    OwenFrame,
    build_read_frame,
    build_write_frame,
    decode_frame,
    expand_network_address,
)


class OwenSerialClient:
    def __init__(self, config: SerialConfig) -> None:
        self.config = config
        self._serial = None

    def connect(self) -> None:
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError(
                "pyserial is not installed. Install requirements before running the gateway."
            ) from exc

        self._serial = serial.Serial(
            port=self.config.port,
            baudrate=self.config.baudrate,
            bytesize=self.config.bytesize,
            parity=self.config.parity,
            stopbits=self.config.stopbits,
            timeout=self.config.timeout_ms / 1000,
        )
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def exchange(
        self,
        address: int,
        parameter_name: str,
        parameter_index: int | None = None,
    ) -> tuple[bytes, bytes, OwenFrame]:
        if self._serial is None:
            raise RuntimeError("serial client is not connected")

        # OVEN devices are polled with their native ASCII-nibble protocol even
        # though the gateway publishes the results further upstream as Modbus TCP.
        request = build_read_frame(
            expand_network_address(address, self.config.address_bits),
            parameter_name,
            parameter_index,
        )
        self._serial.reset_input_buffer()
        self._serial.write(request)
        self._serial.flush()
        response = _read_oven_response(self._serial, self.config.timeout_ms / 1000)
        if not response:
            raise TimeoutError(
                f"no response from OVEN device address={address} parameter={parameter_name}"
            )
        normalized_response = _normalize_frame_response(response)
        return request, normalized_response, decode_frame(normalized_response)

    def exchange_write(
        self,
        address: int,
        parameter_name: str,
        payload: bytes,
        parameter_index: int | None = None,
    ) -> tuple[bytes, bytes, OwenFrame | None]:
        if self._serial is None:
            raise RuntimeError("serial client is not connected")

        request = build_write_frame(
            expand_network_address(address, self.config.address_bits),
            parameter_name,
            payload,
            parameter_index,
        )
        self._serial.reset_input_buffer()
        self._serial.write(request)
        self._serial.flush()
        response = _read_oven_response(self._serial, self.config.timeout_ms / 1000)
        if not response:
            raise TimeoutError(
                f"no write response from OVEN device address={address} parameter={parameter_name}"
            )
        normalized_response = _normalize_frame_response(response)
        try:
            return request, normalized_response, decode_frame(normalized_response)
        except ValueError:
            # Some TRM138 write operations return a short control-style
            # acknowledgement instead of a regular framed payload. Keep the
            # raw response and let the service validate by readback polling.
            return request, response, None

    def read_parameter(
        self,
        address: int,
        parameter_name: str,
        parameter_index: int | None = None,
    ) -> OwenFrame:
        _request, _response, frame = self.exchange(
            address,
            parameter_name,
            parameter_index,
        )
        return frame

    def write_parameter(
        self,
        address: int,
        parameter_name: str,
        payload: bytes,
        parameter_index: int | None = None,
    ) -> OwenFrame | None:
        _request, _response, frame = self.exchange_write(
            address,
            parameter_name,
            payload,
            parameter_index,
        )
        return frame

    def read_modbus_holding_registers(
        self,
        unit_id: int,
        register_address: int,
        register_count: int,
    ) -> list[int]:
        if self._serial is None:
            raise RuntimeError("serial client is not connected")
        if not (1 <= unit_id <= 247):
            raise ValueError(f"invalid Modbus unit id: {unit_id}")
        if not (0 <= register_address <= 0xFFFF):
            raise ValueError(f"invalid Modbus register address: {register_address}")
        if not (1 <= register_count <= 125):
            raise ValueError(f"invalid Modbus register count: {register_count}")

        # This helper is only for diagnostics when the field device itself may
        # speak Modbus RTU. Normal gateway runtime does not use this path.
        request_wo_crc = bytes(
            [
                unit_id,
                0x03,
                (register_address >> 8) & 0xFF,
                register_address & 0xFF,
                (register_count >> 8) & 0xFF,
                register_count & 0xFF,
            ]
        )
        request = request_wo_crc + _modbus_crc(request_wo_crc).to_bytes(2, "little")
        expected_length = 5 + register_count * 2

        self._serial.reset_input_buffer()
        self._serial.write(request)
        self._serial.flush()
        response = self._serial.read(expected_length)
        if not response:
            raise TimeoutError(
                f"no Modbus response from unit={unit_id} register={register_address} count={register_count}"
            )
        if len(response) < 5:
            raise RuntimeError(f"short Modbus response: {response.hex(' ')}")

        response_wo_crc = response[:-2]
        received_crc = int.from_bytes(response[-2:], "little")
        calculated_crc = _modbus_crc(response_wo_crc)
        if received_crc != calculated_crc:
            raise RuntimeError(
                f"Modbus CRC mismatch: received=0x{received_crc:04X} expected=0x{calculated_crc:04X}"
            )
        if response[0] != unit_id:
            raise RuntimeError(
                f"unexpected Modbus unit id: {response[0]} != {unit_id}"
            )
        if response[1] & 0x80:
            if len(response) < 5:
                raise RuntimeError(f"short Modbus exception response: {response.hex(' ')}")
            raise RuntimeError(f"Modbus exception code: {response[2]}")
        if response[1] != 0x03:
            raise RuntimeError(f"unexpected Modbus function: {response[1]}")
        byte_count = response[2]
        if byte_count != register_count * 2:
            raise RuntimeError(
                f"unexpected Modbus byte count: {byte_count} != {register_count * 2}"
            )
        data = response[3:-2]
        return [
            int.from_bytes(data[index : index + 2], "big")
            for index in range(0, len(data), 2)
        ]


def _modbus_crc(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def _normalize_frame_response(response: bytes) -> bytes:
    # Some USB-RS485 adapters deliver a complete ASCII-nibble OVEN frame
    # without the trailing CR terminator. Treat this as a transport quirk and
    # restore the expected marker for normal '#' frames before decoding.
    if response.startswith(b"#") and not response.endswith(b"\r"):
        return response + b"\r"
    return response


def _read_oven_response(serial_port: object, timeout_seconds: float) -> bytes:
    original_timeout = getattr(serial_port, "timeout", None)
    inter_byte_timeout = _inter_byte_timeout(timeout_seconds)
    empty_reads = 0
    response = bytearray()
    try:
        serial_port.timeout = timeout_seconds
        first_chunk = serial_port.read(1)
        if not first_chunk:
            return b""
        response.extend(first_chunk)
        serial_port.timeout = inter_byte_timeout
        while len(response) < 128:
            if response.endswith(b"\r") or response.endswith(b"\x16"):
                return bytes(response)
            chunk_size = max(1, int(getattr(serial_port, "in_waiting", 0) or 0))
            chunk = serial_port.read(chunk_size)
            if chunk:
                response.extend(chunk)
                empty_reads = 0
                continue
            empty_reads += 1
            if empty_reads >= 2:
                return bytes(response)
        return bytes(response)
    finally:
        serial_port.timeout = original_timeout


def _inter_byte_timeout(timeout_seconds: float) -> float:
    if timeout_seconds <= 0:
        return 0.05
    return min(max(timeout_seconds / 5, 0.02), 0.2)
