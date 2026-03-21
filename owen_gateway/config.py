from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from owen_gateway.encoding import register_width


VALID_PROTOCOL_FORMATS = {
    "float32",
    "int16",
    "uint16",
    "uint32",
    "raw",
}

VALID_REGISTER_TYPES = {
    "coil",
    "discrete_input",
    "holding_register",
    "input_register",
}

SERVICE_SLAVE_ID = 1
DEFAULT_BUS_SLAVE_BASES = (10, 50, 90, 130)

VALID_MODBUS_DATA_TYPES = {
    "bool",
    "uint16",
    "int16",
    "uint32",
    "int32",
    "float32",
}

MAX_BUSES = 4
MAX_DEVICES_PER_BUS = 32
MAX_TOTAL_DEVICES = 128


@dataclass(slots=True)
class SerialConfig:
    port: str
    baudrate: int
    bytesize: int
    parity: str
    stopbits: int
    timeout_ms: int
    address_bits: int = 8


@dataclass(slots=True)
class BusConfig:
    name: str
    serial: SerialConfig
    poll_interval_ms: int
    modbus_slave_base: int | None = None


@dataclass(slots=True)
class ModbusConfig:
    host: str
    port: int


@dataclass(slots=True)
class StatusConfig:
    enabled: bool
    register_type: str
    modbus_address: int
    modbus_data_type: str


@dataclass(slots=True)
class TelemetryConfig:
    enabled: bool
    register_type: str
    last_error_code_address: int
    success_counter_address: int
    timeout_counter_address: int
    protocol_error_counter_address: int
    poll_cycle_counter_address: int


@dataclass(slots=True)
class HealthConfig:
    stale_after_cycles: int
    fault_after_failures: int
    recovery_poll_interval_cycles: int


@dataclass(slots=True)
class PointConfig:
    name: str
    bus: str
    device: int
    modbus_slave_id: int | None
    address: int
    parameter: str
    protocol_format: str
    register_type: str
    modbus_address: int
    modbus_data_type: str
    time_mark_address: int | None = None
    channel_status_address: int | None = None


@dataclass(slots=True)
class OwenGatewayConfig:
    buses: list[BusConfig]
    diagnostics: bool
    modbus: ModbusConfig
    status: StatusConfig
    telemetry: TelemetryConfig
    health: HealthConfig
    points: list[PointConfig]


def load_config(path: str | Path) -> OwenGatewayConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    buses = _load_buses(payload)
    points = [_load_point(entry, buses) for entry in payload["points"]]
    _resolve_modbus_slave_ids(points, buses)
    config = OwenGatewayConfig(
        buses=buses,
        diagnostics=payload.get("diagnostics", False),
        modbus=ModbusConfig(**payload["modbus"]),
        status=StatusConfig(**payload.get("status", _default_status_config())),
        telemetry=TelemetryConfig(
            **payload.get("telemetry", _default_telemetry_config())
        ),
        health=HealthConfig(**payload.get("health", _default_health_config())),
        points=points,
    )
    validate_config(config)
    return config


def validate_config(config: OwenGatewayConfig) -> None:
    if not config.buses:
        raise ValueError("at least one bus must be configured")
    if len(config.buses) > MAX_BUSES:
        raise ValueError(f"configured buses exceed limit: {len(config.buses)} > {MAX_BUSES}")
    bus_names: set[str] = set()
    for bus in config.buses:
        if bus.name in bus_names:
            raise ValueError(f"duplicate bus name: {bus.name}")
        bus_names.add(bus.name)
        if bus.poll_interval_ms <= 0:
            raise ValueError(f"bus {bus.name}: poll_interval_ms must be > 0")
        if bus.modbus_slave_base is None:
            raise ValueError(f"bus {bus.name}: modbus_slave_base is not resolved")
        if not (2 <= bus.modbus_slave_base <= 247):
            raise ValueError(
                f"bus {bus.name}: modbus_slave_base must be in range 2..247"
            )
        _validate_serial_config(bus.name, bus.serial)
    if not (1 <= config.modbus.port <= 65535):
        raise ValueError("modbus.port must be in range 1..65535")
    if config.status.enabled:
        if config.status.register_type not in VALID_REGISTER_TYPES:
            raise ValueError(
                f"unsupported status.register_type: {config.status.register_type}"
            )
        if config.status.modbus_data_type not in VALID_MODBUS_DATA_TYPES:
            raise ValueError(
                "unsupported status.modbus_data_type: "
                f"{config.status.modbus_data_type}"
            )
        if config.status.modbus_address < 0:
            raise ValueError("status.modbus_address must be >= 0")
    if config.telemetry.enabled:
        if config.telemetry.register_type not in VALID_REGISTER_TYPES:
            raise ValueError(
                f"unsupported telemetry.register_type: {config.telemetry.register_type}"
            )
        telemetry_addresses = [
            config.telemetry.last_error_code_address,
            config.telemetry.success_counter_address,
            config.telemetry.timeout_counter_address,
            config.telemetry.protocol_error_counter_address,
            config.telemetry.poll_cycle_counter_address,
        ]
        if any(address < 0 for address in telemetry_addresses):
            raise ValueError("telemetry register addresses must be >= 0")
    if (
        config.status.enabled
        and config.telemetry.enabled
        and config.status.register_type == config.telemetry.register_type
    ):
        status_indexes = set(
            range(
                config.status.modbus_address,
                config.status.modbus_address
                + register_width(config.status.modbus_data_type),
            )
        )
        telemetry_indexes = {
            config.telemetry.last_error_code_address,
            config.telemetry.success_counter_address,
            config.telemetry.timeout_counter_address,
            config.telemetry.protocol_error_counter_address,
            config.telemetry.poll_cycle_counter_address,
        }
        overlap = status_indexes.intersection(telemetry_indexes)
        if overlap:
            raise ValueError(
                "telemetry mapping overlaps status register at "
                f"{config.status.register_type}:{min(overlap)}"
            )
    if config.health.stale_after_cycles < 1:
        raise ValueError("health.stale_after_cycles must be >= 1")
    if config.health.fault_after_failures < 1:
        raise ValueError("health.fault_after_failures must be >= 1")
    if config.health.recovery_poll_interval_cycles < 1:
        raise ValueError("health.recovery_poll_interval_cycles must be >= 1")

    occupied: dict[tuple[int, str], set[int]] = {}
    devices_per_bus: dict[str, set[int]] = {bus.name: set() for bus in config.buses}
    device_to_slave: dict[tuple[str, int], int] = {}
    slave_to_device: dict[int, tuple[str, int]] = {}
    bus_ranges: list[tuple[str, int, int]] = []
    for bus in config.buses:
        assert bus.modbus_slave_base is not None
        bus_ranges.append(
            (
                bus.name,
                bus.modbus_slave_base,
                bus.modbus_slave_base + MAX_DEVICES_PER_BUS - 1,
            )
        )
    for index, (bus_name, start, end) in enumerate(bus_ranges):
        if SERVICE_SLAVE_ID >= start and SERVICE_SLAVE_ID <= end:
            raise ValueError(
                f"bus {bus_name}: slave id range {start}..{end} overlaps reserved service slave {SERVICE_SLAVE_ID}"
            )
        if end > 247:
            raise ValueError(
                f"bus {bus_name}: slave id range exceeds Modbus limit: {end} > 247"
            )
        for other_name, other_start, other_end in bus_ranges[index + 1:]:
            if start <= other_end and other_start <= end:
                raise ValueError(
                    f"slave id ranges overlap: {bus_name} {start}..{end} and {other_name} {other_start}..{other_end}"
                )
    for point in config.points:
        if point.bus not in bus_names:
            raise ValueError(f"unknown bus for {point.name}: {point.bus}")
        if not (1 <= point.device <= MAX_DEVICES_PER_BUS):
            raise ValueError(
                f"invalid device number for {point.name}: "
                f"{point.device}, expected 1..{MAX_DEVICES_PER_BUS}"
            )
        if point.modbus_slave_id is None:
            raise ValueError(f"modbus_slave_id is not resolved for {point.name}")
        if not (1 <= point.modbus_slave_id <= 247):
            raise ValueError(
                f"invalid modbus_slave_id for {point.name}: "
                f"{point.modbus_slave_id}, expected 1..247"
            )
        if point.modbus_slave_id == SERVICE_SLAVE_ID:
            raise ValueError(f"modbus_slave_id 1 is reserved for service tags: {point.name}")
        if point.address < 0 or point.address > 2047:
            raise ValueError(f"invalid OVEN address for {point.name}: {point.address}")
        if point.protocol_format not in VALID_PROTOCOL_FORMATS:
            raise ValueError(
                f"unsupported protocol_format for {point.name}: {point.protocol_format}"
            )
        if point.register_type not in VALID_REGISTER_TYPES:
            raise ValueError(
                f"unsupported register_type for {point.name}: {point.register_type}"
            )
        if point.modbus_data_type not in VALID_MODBUS_DATA_TYPES:
            raise ValueError(
                f"unsupported modbus_data_type for {point.name}: {point.modbus_data_type}"
            )
        if point.modbus_address < 0:
            raise ValueError(f"modbus_address must be >= 0 for {point.name}")
        if point.time_mark_address is not None and point.time_mark_address < 0:
            raise ValueError(f"time_mark_address must be >= 0 for {point.name}")
        if (
            point.channel_status_address is not None
            and point.channel_status_address < 0
        ):
            raise ValueError(f"channel_status_address must be >= 0 for {point.name}")

        device_key = (point.bus, point.device)
        existing_slave_id = device_to_slave.setdefault(device_key, point.modbus_slave_id)
        if existing_slave_id != point.modbus_slave_id:
            raise ValueError(
                f"inconsistent modbus_slave_id for {point.name}: "
                f"{point.modbus_slave_id} != {existing_slave_id}"
            )
        existing_device_key = slave_to_device.setdefault(point.modbus_slave_id, device_key)
        if existing_device_key != device_key:
            raise ValueError(
                f"duplicate modbus_slave_id {point.modbus_slave_id}: "
                f"used by {existing_device_key[0]}/device{existing_device_key[1]} "
                f"and {point.bus}/device{point.device}"
            )

        used = occupied.setdefault((point.modbus_slave_id, point.register_type), set())
        if config.status.enabled and point.register_type == config.status.register_type:
            used.update(
                range(
                    config.status.modbus_address,
                    config.status.modbus_address
                    + register_width(config.status.modbus_data_type),
                )
            )
        if config.telemetry.enabled and point.register_type == config.telemetry.register_type:
            used.update(
                {
                    config.telemetry.last_error_code_address,
                    config.telemetry.success_counter_address,
                    config.telemetry.timeout_counter_address,
                    config.telemetry.protocol_error_counter_address,
                    config.telemetry.poll_cycle_counter_address,
                }
            )
        width = register_width(point.modbus_data_type)
        indexes = set(range(point.modbus_address, point.modbus_address + width))
        if point.time_mark_address is not None:
            indexes.add(point.time_mark_address)
        if point.channel_status_address is not None:
            indexes.add(point.channel_status_address)
        overlap = used.intersection(indexes)
        if overlap:
            raise ValueError(
                f"overlapping Modbus mapping for {point.name} at "
                f"{point.register_type}:{min(overlap)}"
            )
        used.update(indexes)
        devices_per_bus[point.bus].add(point.device)

    total_devices = sum(len(devices) for devices in devices_per_bus.values())
    if total_devices > MAX_TOTAL_DEVICES:
        raise ValueError(
            f"configured devices exceed total limit: {total_devices} > {MAX_TOTAL_DEVICES}"
        )
    for bus_name, devices in devices_per_bus.items():
        if len(devices) > MAX_DEVICES_PER_BUS:
            raise ValueError(
                f"configured devices on {bus_name} exceed per-bus limit: "
                f"{len(devices)} > {MAX_DEVICES_PER_BUS}"
            )


def _load_buses(payload: dict[str, object]) -> list[BusConfig]:
    if "buses" in payload:
        raw_buses = payload["buses"]
        if not isinstance(raw_buses, list) or not raw_buses:
            raise ValueError("buses must be a non-empty list")
        return [
            BusConfig(
                name=entry["name"],
                serial=SerialConfig(**entry["serial"]),
                poll_interval_ms=entry["poll_interval_ms"],
                modbus_slave_base=entry.get("modbus_slave_base"),
            )
            for entry in raw_buses
        ]

    return [
        BusConfig(
            name="bus1",
            serial=SerialConfig(**payload["serial"]),
            poll_interval_ms=payload["poll_interval_ms"],
            modbus_slave_base=payload.get("modbus_slave_base"),
        )
    ]


def _load_point(entry: dict[str, object], buses: list[BusConfig]) -> PointConfig:
    point_data = dict(entry)
    if "bus" not in point_data:
        point_data["bus"] = buses[0].name
    if "device" not in point_data:
        point_data["device"] = 1
    if "modbus_slave_id" not in point_data:
        point_data["modbus_slave_id"] = None
    return PointConfig(**point_data)


def _resolve_modbus_slave_ids(points: list[PointConfig], buses: list[BusConfig]) -> None:
    bus_by_name = {bus.name: bus for bus in buses}
    for index, bus in enumerate(buses):
        if bus.modbus_slave_base is None:
            bus.modbus_slave_base = DEFAULT_BUS_SLAVE_BASES[index]
    grouped: dict[tuple[str, int], list[PointConfig]] = {}
    for point in points:
        grouped.setdefault((point.bus, point.device), []).append(point)

    for (bus_name, _device), device_points in grouped.items():
        explicit_ids = {
            point.modbus_slave_id
            for point in device_points
            if point.modbus_slave_id is not None
        }
        if len(explicit_ids) > 1:
            raise ValueError(
                f"inconsistent explicit modbus_slave_id values for {bus_name}/device"
            )
        if explicit_ids:
            resolved_id = next(iter(explicit_ids))
        else:
            bus = bus_by_name[bus_name]
            assert bus.modbus_slave_base is not None
            resolved_id = bus.modbus_slave_base + device_points[0].device - 1
        for point in device_points:
            point.modbus_slave_id = resolved_id


def _validate_serial_config(bus_name: str, serial: SerialConfig) -> None:
    if serial.bytesize not in {7, 8}:
        raise ValueError(f"bus {bus_name}: serial.bytesize must be 7 or 8")
    if serial.parity not in {"N", "E", "O"}:
        raise ValueError(f"bus {bus_name}: serial.parity must be N, E or O")
    if serial.stopbits not in {1, 2}:
        raise ValueError(f"bus {bus_name}: serial.stopbits must be 1 or 2")
    if serial.timeout_ms <= 0:
        raise ValueError(f"bus {bus_name}: serial.timeout_ms must be > 0")
    if serial.address_bits not in {8, 11}:
        raise ValueError(f"bus {bus_name}: serial.address_bits must be 8 or 11")


def _default_status_config() -> dict[str, object]:
    return {
        "enabled": True,
        "register_type": "holding_register",
        "modbus_address": 1,
        "modbus_data_type": "uint16",
    }


def _default_telemetry_config() -> dict[str, object]:
    return {
        "enabled": True,
        "register_type": "holding_register",
        "last_error_code_address": 2,
        "success_counter_address": 3,
        "timeout_counter_address": 4,
        "protocol_error_counter_address": 5,
        "poll_cycle_counter_address": 6,
    }


def _default_health_config() -> dict[str, object]:
    return {
        "stale_after_cycles": 3,
        "fault_after_failures": 10,
        "recovery_poll_interval_cycles": 5,
    }
