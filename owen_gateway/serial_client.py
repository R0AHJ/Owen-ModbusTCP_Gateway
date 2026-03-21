from __future__ import annotations

from owen_gateway.config import SerialConfig
from owen_gateway.protocol import (
    OwenFrame,
    build_read_frame,
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

    def exchange(self, address: int, parameter_name: str) -> tuple[bytes, bytes, OwenFrame]:
        if self._serial is None:
            raise RuntimeError("serial client is not connected")

        request = build_read_frame(
            expand_network_address(address, self.config.address_bits),
            parameter_name,
        )
        self._serial.reset_input_buffer()
        self._serial.write(request)
        self._serial.flush()
        response = self._serial.read_until(b"\r")
        if not response:
            raise TimeoutError(
                f"no response from OVEN device address={address} parameter={parameter_name}"
            )
        return request, response, decode_frame(response)

    def read_parameter(self, address: int, parameter_name: str) -> OwenFrame:
        _request, _response, frame = self.exchange(address, parameter_name)
        return frame
