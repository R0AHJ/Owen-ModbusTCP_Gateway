from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from owen_gateway.config import (
    BusConfig,
    OwenGatewayConfig,
    PointConfig,
    SERVICE_SLAVE_ID,
)
from owen_gateway.modbus_server import ModbusPublisher
from owen_gateway.protocol import decode_payload, hash_parameter_name
from owen_gateway.serial_client import OwenSerialClient


STATUS_OK = 1
STATUS_DEGRADED = 2
STATUS_OFFLINE = 3
STATUS_PROTOCOL_ERROR = 4

ERROR_NONE = 0
ERROR_TIMEOUT = 1
ERROR_BAD_FLAG = 2
ERROR_HASH_MISMATCH = 3
ERROR_DECODE = 4
ERROR_IO = 5

CHANNEL_DISABLED = 0
CHANNEL_OK = 1
CHANNEL_COMM_ERROR = 2
CHANNEL_PROTOCOL_ERROR = 3
CHANNEL_FAILED = 4

SERVICE_LINE_STATUS_BASE = 10
LOGIC_UNIT_MASK_REGISTER = 48
LOGIC_UNIT_COUNT = 8


@dataclass(slots=True)
class PointState:
    consecutive_failures: int = 0
    channel_status: int = CHANNEL_COMM_ERROR
    recovery_skip_cycles: int = 0


@dataclass(slots=True)
class DeviceState:
    status: int = STATUS_OFFLINE
    success_counter: int = 0
    timeout_counter: int = 0
    protocol_error_counter: int = 0
    poll_cycle_counter: int = 0
    last_error_code: int = ERROR_NONE


class OwenGatewayService:
    def __init__(self, config: OwenGatewayConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("owen_gateway")
        self.serial_clients = {
            bus.name: OwenSerialClient(bus.serial) for bus in config.buses
        }
        self.buses = {bus.name: bus for bus in config.buses}
        self.points_by_bus = _group_points_by_bus_device(config.points)
        self.modbus = ModbusPublisher(
            modbus=config.modbus,
            status=config.status,
            telemetry=config.telemetry,
            points=config.points,
            extra_slave_ids=[SERVICE_SLAVE_ID],
            extra_holding_registers=[LOGIC_UNIT_MASK_REGISTER],
        )
        self.point_states = {point.name: PointState() for point in config.points}
        self.point_values: dict[str, object | None] = {
            point.name: None for point in config.points
        }
        self.device_logic_masks: dict[tuple[str, int], int] = {
            (point.bus, point.modbus_slave_id): 0
            for point in config.points
        }
        self.device_states = {
            (point.bus, point.modbus_slave_id): DeviceState()
            for point in config.points
        }
        self.bus_statuses = {bus.name: STATUS_OFFLINE for bus in config.buses}
        self.gateway_success_counter = 0
        self.gateway_timeout_counter = 0
        self.gateway_protocol_error_counter = 0
        self.gateway_poll_cycle_counter = 0
        self.gateway_last_error_code = ERROR_NONE
        self._state_lock = asyncio.Lock()

    async def run(self) -> None:
        started_buses: list[str] = []
        try:
            await self.modbus.start()
            self.modbus.publish_status(SERVICE_SLAVE_ID, STATUS_OFFLINE)
            self.modbus.publish_telemetry(
                SERVICE_SLAVE_ID,
                last_error_code=ERROR_NONE,
                success_counter=0,
                timeout_counter=0,
                protocol_error_counter=0,
                poll_cycle_counter=0,
            )
            self._publish_line_statuses()
            for slave_id in sorted({point.modbus_slave_id for point in self.config.points}):
                self.modbus.publish_status(slave_id, STATUS_OFFLINE)
                self.modbus.publish_telemetry(
                    slave_id,
                    last_error_code=ERROR_NONE,
                    success_counter=0,
                    timeout_counter=0,
                    protocol_error_counter=0,
                    poll_cycle_counter=0,
                )
            for bus in self.config.buses:
                self.serial_clients[bus.name].connect()
                started_buses.append(bus.name)
                self.logger.info(
                    "bus started: name=%s serial=%s %s,%s%s%s",
                    bus.name,
                    bus.serial.port,
                    bus.serial.baudrate,
                    bus.serial.bytesize,
                    bus.serial.parity,
                    bus.serial.stopbits,
                )
            self.logger.info(
                "modbus started: %s:%s",
                self.config.modbus.host,
                self.config.modbus.port,
            )
            tasks = [
                asyncio.create_task(self._poll_bus_loop(bus))
                for bus in self.config.buses
            ]
            await asyncio.gather(*tasks)
        finally:
            try:
                # Startup may fail after opening only part of the configured
                # serial buses, so shutdown must tolerate a partially started
                # Modbus stack and close only successfully opened ports.
                self.modbus.publish_status(SERVICE_SLAVE_ID, STATUS_OFFLINE)
                for bus in self.config.buses:
                    self.bus_statuses[bus.name] = STATUS_OFFLINE
                self._publish_line_statuses()
                for slave_id in sorted({point.modbus_slave_id for point in self.config.points}):
                    self.modbus.publish_status(slave_id, STATUS_OFFLINE)
            except RuntimeError:
                pass
            for bus_name in started_buses:
                self.serial_clients[bus_name].close()
            await self.modbus.stop()

    async def _poll_bus_loop(self, bus: BusConfig) -> None:
        while True:
            await self._poll_bus_once(bus, self.points_by_bus.get(bus.name, {}))
            await asyncio.sleep(bus.poll_interval_ms / 1000)

    async def _poll_bus_once(
        self,
        bus: BusConfig,
        points_by_slave: dict[int, list[PointConfig]],
    ) -> None:
        if not points_by_slave:
            return

        for slave_id, points in points_by_slave.items():
            failures = 0
            protocol_failures = 0
            last_error_code = ERROR_NONE
            device_state = self.device_states[(bus.name, slave_id)]
            for point in points:
                point_state = self.point_states[point.name]
                if point_state.recovery_skip_cycles > 0:
                    point_state.recovery_skip_cycles -= 1
                    self.modbus.publish_point_metadata(
                        slave_id,
                        point,
                        channel_status=CHANNEL_FAILED,
                    )
                    self.logger.debug(
                        "skipping failed point bus=%s slave=%s %s remaining_skip_cycles=%s",
                        bus.name,
                        slave_id,
                        point.name,
                        point_state.recovery_skip_cycles,
                    )
                    failures += 1
                    continue
                frame = None
                try:
                    request, response, frame = await asyncio.to_thread(
                        self.serial_clients[bus.name].exchange,
                        point.address,
                        point.parameter,
                        point.parameter_index,
                    )
                    if self.config.diagnostics:
                        self.logger.info(
                            "diag bus=%s slave=%s point=%s request=%s response=%s",
                            bus.name,
                            slave_id,
                            point.name,
                            request.hex(" "),
                            response.hex(" "),
                        )
                    if frame.request:
                        raise RuntimeError(
                            f"invalid response for {point.name}: request flag is set in response"
                        )
                    expected_hash = hash_parameter_name(point.parameter)
                    if frame.parameter_hash != expected_hash:
                        raise RuntimeError(
                            f"invalid response for {point.name}: hash mismatch "
                            f"0x{frame.parameter_hash:04X} != 0x{expected_hash:04X}"
                        )
                    time_mark = _extract_time_mark(frame.payload)
                    if frame.payload == b"":
                        point_state.consecutive_failures = 0
                        point_state.channel_status = CHANNEL_DISABLED
                        self.modbus.publish_point_metadata(
                            slave_id,
                            point,
                            time_mark=None,
                            channel_status=CHANNEL_DISABLED,
                        )
                        self.logger.info(
                            "empty payload bus=%s slave=%s %s address=%s parameter=%s",
                            bus.name,
                            slave_id,
                            point.name,
                            point.address,
                            point.parameter,
                        )
                        self.point_values[point.name] = None
                        continue
                    value: object = decode_payload(frame.payload, point.protocol_format)
                    if self.config.diagnostics:
                        self.logger.debug(
                            "decoded bus=%s slave=%s point=%s value=%r",
                            bus.name,
                            slave_id,
                            point.name,
                            value,
                        )
                    self.point_values[point.name] = value
                    self.modbus.publish(slave_id, point, value)
                    point_state.consecutive_failures = 0
                    point_state.channel_status = CHANNEL_OK
                    self.modbus.publish_point_metadata(
                        slave_id,
                        point,
                        time_mark=time_mark,
                        channel_status=point_state.channel_status,
                    )
                    async with self._state_lock:
                        device_state.success_counter = _inc_counter(
                            device_state.success_counter
                        )
                        self.gateway_success_counter = _inc_counter(
                            self.gateway_success_counter
                        )
                    target_description = (
                        f"{point.register_type}:{point.modbus_address}"
                        if point.publish_to_modbus
                        else "internal-only"
                    )
                    self.logger.debug(
                        "processed bus=%s slave=%s %s=%r from address=%s parameter=%s target=%s mark=%s status=%s",
                        bus.name,
                        slave_id,
                        point.name,
                        value,
                        point.address,
                        point.parameter,
                        target_description,
                        time_mark,
                        point_state.channel_status,
                    )
                except TimeoutError:
                    failures += 1
                    point_state.consecutive_failures += 1
                    point_state.channel_status = _failure_status(
                        point_state,
                        self.config.health.fault_after_failures,
                        self.config.health.recovery_poll_interval_cycles,
                        CHANNEL_COMM_ERROR,
                    )
                    self.modbus.publish_point_metadata(
                        slave_id,
                        point,
                        channel_status=point_state.channel_status,
                    )
                    async with self._state_lock:
                        device_state.timeout_counter = _inc_counter(
                            device_state.timeout_counter
                        )
                        self.gateway_timeout_counter = _inc_counter(
                            self.gateway_timeout_counter
                        )
                    last_error_code = ERROR_TIMEOUT
                    self.logger.warning(
                        "timeout reading bus=%s slave=%s %s address=%s parameter=%s",
                        bus.name,
                        slave_id,
                        point.name,
                        point.address,
                        point.parameter,
                    )
                except (ValueError, RuntimeError):
                    failures += 1
                    protocol_failures += 1
                    point_state.consecutive_failures += 1
                    point_state.channel_status = _failure_status(
                        point_state,
                        self.config.health.fault_after_failures,
                        self.config.health.recovery_poll_interval_cycles,
                        CHANNEL_PROTOCOL_ERROR,
                    )
                    self.modbus.publish_point_metadata(
                        slave_id,
                        point,
                        channel_status=point_state.channel_status,
                    )
                    async with self._state_lock:
                        device_state.protocol_error_counter = _inc_counter(
                            device_state.protocol_error_counter
                        )
                        self.gateway_protocol_error_counter = _inc_counter(
                            self.gateway_protocol_error_counter
                        )
                    last_error_code = _map_protocol_error(point, frame)
                    self.logger.exception(
                        "protocol error for bus=%s slave=%s %s address=%s parameter=%s",
                        bus.name,
                        slave_id,
                        point.name,
                        point.address,
                        point.parameter,
                    )
                except Exception:
                    failures += 1
                    point_state.consecutive_failures += 1
                    point_state.channel_status = _failure_status(
                        point_state,
                        self.config.health.fault_after_failures,
                        self.config.health.recovery_poll_interval_cycles,
                        CHANNEL_COMM_ERROR,
                    )
                    self.modbus.publish_point_metadata(
                        slave_id,
                        point,
                        channel_status=point_state.channel_status,
                    )
                    async with self._state_lock:
                        self.gateway_timeout_counter = _inc_counter(
                            self.gateway_timeout_counter
                        )
                    last_error_code = ERROR_IO
                    self.logger.exception(
                        "poll failed for bus=%s slave=%s %s address=%s parameter=%s",
                        bus.name,
                        slave_id,
                        point.name,
                        point.address,
                        point.parameter,
                    )

            self._publish_logic_unit_masks(bus.name, slave_id, points)
            if failures == 0:
                device_status = STATUS_OK
            elif protocol_failures == len(points):
                device_status = STATUS_PROTOCOL_ERROR
            elif failures == len(points):
                device_status = STATUS_OFFLINE
            else:
                device_status = STATUS_DEGRADED
            await self._record_device_result(
                bus.name,
                slave_id,
                device_status,
                last_error_code,
            )

    async def _record_device_result(
        self,
        bus_name: str,
        slave_id: int,
        device_status: int,
        last_error_code: int,
    ) -> None:
        async with self._state_lock:
            device_state = self.device_states[(bus_name, slave_id)]
            device_state.status = device_status
            device_state.last_error_code = last_error_code
            device_state.poll_cycle_counter = _inc_counter(device_state.poll_cycle_counter)
            self.bus_statuses[bus_name] = _aggregate_status(
                device.status
                for (device_bus, _slave), device in self.device_states.items()
                if device_bus == bus_name
            )
            self.gateway_last_error_code = last_error_code
            self.gateway_poll_cycle_counter = _inc_counter(self.gateway_poll_cycle_counter)
            self.modbus.publish_status(slave_id, device_state.status)
            self.modbus.publish_telemetry(
                slave_id,
                last_error_code=device_state.last_error_code,
                success_counter=device_state.success_counter,
                timeout_counter=device_state.timeout_counter,
                protocol_error_counter=device_state.protocol_error_counter,
                poll_cycle_counter=device_state.poll_cycle_counter,
            )
            self.modbus.publish_status(
                SERVICE_SLAVE_ID,
                _aggregate_status(self.bus_statuses.values()),
            )
            self.modbus.publish_telemetry(
                SERVICE_SLAVE_ID,
                last_error_code=self.gateway_last_error_code,
                success_counter=self.gateway_success_counter,
                timeout_counter=self.gateway_timeout_counter,
                protocol_error_counter=self.gateway_protocol_error_counter,
                poll_cycle_counter=self.gateway_poll_cycle_counter,
            )
            self._publish_line_statuses()

    def _publish_line_statuses(self) -> None:
        for index, bus in enumerate(self.config.buses, start=0):
            self.modbus.publish_value(
                SERVICE_SLAVE_ID,
                "holding_register",
                SERVICE_LINE_STATUS_BASE + index,
                "uint16",
                self.bus_statuses[bus.name],
            )

    def _publish_logic_unit_masks(
        self,
        bus_name: str,
        slave_id: int,
        points: list[PointConfig],
    ) -> None:
        device_key = (bus_name, slave_id)
        previous_mask = self.device_logic_masks.setdefault(device_key, 0)
        measured_points = {
            point.address: point for point in points if point.parameter == "rEAd"
        }
        setpoints = {
            point.address: self.point_values.get(point.name)
            for point in points
            if point.parameter == "C.SP"
        }
        hysteresis_values = {
            point.address: self.point_values.get(point.name)
            for point in points
            if point.parameter == "HYSt"
        }
        characteristics = {
            point.address: self.point_values.get(point.name)
            for point in points
            if point.parameter == "AL.t"
        }

        mask = 0
        # LU1..LU8 are derived from channel addresses starting at the device
        # base address / SlaveID. Previous mask state is reused for hysteresis
        # modes that should hold their output inside the dead band.
        for lu_index, channel_address in enumerate(range(slave_id, slave_id + LOGIC_UNIT_COUNT)):
            setpoint = _as_float(setpoints.get(channel_address))
            hysteresis = abs(_as_float(hysteresis_values.get(channel_address), default=0.0))
            al_type = _as_int(characteristics.get(channel_address))
            measured_point = measured_points.get(channel_address)
            channel_value = (
                _as_float(self.point_values.get(measured_point.name))
                if measured_point is not None
                else None
            )
            previous_state = bool(previous_mask & (1 << lu_index))
            if channel_value is None:
                state = False
            else:
                state = _evaluate_logic_unit(
                    channel_value=channel_value,
                    setpoint=setpoint,
                    hysteresis=hysteresis,
                    al_type=al_type,
                    previous_state=previous_state,
                )
            if state:
                mask |= 1 << lu_index
        self.modbus.publish_value(
            slave_id,
            "holding_register",
            LOGIC_UNIT_MASK_REGISTER,
            "uint16",
            mask,
        )
        self.device_logic_masks[device_key] = mask


def _inc_counter(value: int) -> int:
    return (value + 1) & 0xFFFF


def _aggregate_status(statuses: object) -> int:
    status_list = list(statuses)
    if not status_list:
        return STATUS_OFFLINE
    if all(status == STATUS_OK for status in status_list):
        return STATUS_OK
    if all(status == STATUS_PROTOCOL_ERROR for status in status_list):
        return STATUS_PROTOCOL_ERROR
    if all(status == STATUS_OFFLINE for status in status_list):
        return STATUS_OFFLINE
    return STATUS_DEGRADED


def _group_points_by_bus_device(
    points: list[PointConfig],
) -> dict[str, dict[int, list[PointConfig]]]:
    grouped: dict[str, dict[int, list[PointConfig]]] = {}
    for point in points:
        grouped.setdefault(point.bus, {}).setdefault(point.modbus_slave_id, []).append(point)
    return grouped


def _map_protocol_error(point: object, frame: object) -> int:
    # Keep telemetry coarse-grained: bad request flag and parameter hash
    # mismatches are tracked separately, everything else is counted as decode.
    if frame is not None and getattr(frame, "request", False):
        return ERROR_BAD_FLAG
    if frame is not None and getattr(point, "parameter", None) is not None:
        expected_hash = hash_parameter_name(point.parameter)
        if getattr(frame, "parameter_hash", expected_hash) != expected_hash:
            return ERROR_HASH_MISMATCH
    return ERROR_DECODE


def _extract_time_mark(payload: bytes) -> int | None:
    # Operational OVEN values may append a 2-byte time mark after the payload.
    if len(payload) == 6:
        return int.from_bytes(payload[4:6], "big")
    return None


def _decode_fixed_point(dot_position: int, raw_value: int, *, signed: bool) -> float:
    if signed and raw_value >= 0x8000:
        raw_value -= 0x10000
    if not (0 <= dot_position <= 3):
        raise ValueError(f"unsupported decimal point position: {dot_position}")
    return raw_value / (10**dot_position)


def _as_float(value: object | None, *, default: float | None = None) -> float | None:
    if value is None:
        return default
    return float(value)


def _as_int(value: object | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _evaluate_logic_unit(
    *,
    channel_value: float,
    setpoint: float | None,
    hysteresis: float,
    al_type: int | None,
    previous_state: bool,
) -> bool:
    if setpoint is None or al_type is None:
        return False
    low = setpoint - hysteresis
    high = setpoint + hysteresis
    if al_type == 1:
        if channel_value < low:
            return True
        if channel_value > high:
            return False
        return previous_state
    if al_type == 2:
        if channel_value > high:
            return True
        if channel_value < low:
            return False
        return previous_state
    if al_type == 3:
        return low < channel_value < high
    if al_type == 4:
        return channel_value < low or channel_value > high
    return False


def _failure_status(
    point_state: PointState,
    fault_after_failures: int,
    recovery_poll_interval_cycles: int,
    transient_status: int,
) -> int:
    if point_state.consecutive_failures >= fault_after_failures:
        point_state.recovery_skip_cycles = recovery_poll_interval_cycles - 1
        return CHANNEL_FAILED
    return transient_status
