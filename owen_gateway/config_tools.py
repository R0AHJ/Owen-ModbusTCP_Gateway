from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from owen_gateway.config import (
    DEFAULT_BUS_SLAVE_BASES,
    MAX_BUSES,
    MAX_DEVICES_PER_BUS,
    SERVICE_SLAVE_ID,
    _default_health_config,
    _default_status_config,
    _default_telemetry_config,
    load_config,
)


TRM138_CHANNEL_COUNT = 8
TRM138_REGISTER_BASE = 16
TRM138_VALUE_REGISTERS_PER_CHANNEL = 2
TRM138_TIME_MARK_BASE = TRM138_REGISTER_BASE + (
    TRM138_CHANNEL_COUNT * TRM138_VALUE_REGISTERS_PER_CHANNEL
)
TRM138_STATUS_BASE = TRM138_TIME_MARK_BASE + TRM138_CHANNEL_COUNT


def load_config_document(path: str | Path) -> dict[str, object]:
    config_path = Path(path)
    if not config_path.exists():
        return _new_config_document()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    _normalize_legacy_payload(payload)
    return payload


def save_config_document(path: str | Path, payload: dict[str, object]) -> None:
    config_path = Path(path)
    config_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def export_config_document(
    source_path: str | Path,
    target_path: str | Path,
    payload: dict[str, object],
) -> tuple[Path, Path]:
    source = Path(source_path)
    target = Path(target_path)
    save_config_document(target, payload)
    write_generated_modbus_map(target, payload)
    return source, target


def write_generated_modbus_map(path: str | Path, payload: dict[str, object]) -> Path:
    config_path = Path(path)
    map_path = config_path.with_name(f"{config_path.stem}.modbus_map.md")
    map_path.write_text(render_modbus_map(payload, config_path.name), encoding="utf-8")
    return map_path


def render_config_summary(payload: dict[str, object]) -> str:
    resolved = _resolve_runtime_config(payload)
    devices = _collect_devices(payload)
    lines = [
        f"Modbus TCP: {resolved.modbus.host}:{resolved.modbus.port}",
        f"Service SlaveID: {SERVICE_SLAVE_ID}",
    ]
    for bus in resolved.buses:
        lines.append(
            f"{bus.name}: {bus.serial.port} {bus.serial.baudrate} {bus.serial.bytesize}{bus.serial.parity}{bus.serial.stopbits}, "
            f"poll={bus.poll_interval_ms}ms, slave_base={bus.modbus_slave_base}"
        )
        for device in devices.get(bus.name, []):
            lines.append(
                f"  device {device['device']} -> SlaveID {device['slave_id']}, "
                f"base_address={device['base_address']}, tag={device['tag']}, "
                f"channels={device['channels']}"
            )
    return "\n".join(lines)


def render_line_devices(payload: dict[str, object], line: int) -> str:
    bus_name = _line_name(line)
    devices = get_line_devices(payload, line)
    if not devices:
        return f"{bus_name}: no devices configured"
    lines = [f"{bus_name} devices:"]
    for index, device in enumerate(devices, start=1):
        lines.append(
            f"{index}. device={device['device']} SlaveID={device['slave_id']} "
            f"base_address={device['base_address']} tag={device['tag']} channels={device['channels']}"
        )
    return "\n".join(lines)


def render_device_details(
    payload: dict[str, object],
    *,
    line: int,
    device: int | None = None,
    base_address: int | None = None,
    tag: str | None = None,
) -> str:
    bus_name = _line_name(line)
    grouped = get_line_devices(payload, line)
    selected = _select_collected_device(
        grouped,
        device=device,
        base_address=base_address,
        tag=tag,
    )
    lines = [
        f"{bus_name} device {selected['device']}",
        f"SlaveID: {selected['slave_id']}",
        f"Base address: {selected['base_address']}",
        f"Tag: {selected['tag']}",
        "",
        "| Channel | OVEN Address | Value Register | Time Mark | Status | Type |",
        "|---|---:|---|---:|---:|---|",
    ]
    for row in selected["channel_rows"]:
        if row["value_start"] == row["value_end"]:
            value_register = f"`{row['value_start']}`"
        else:
            value_register = f"`{row['value_start']},{row['value_end']}`"
        lines.append(
            f"| `{row['channel']}` | `{row['address']}` | {value_register} | "
            f"`{row['time_mark']}` | `{row['status']}` | `{row['value_type']}` |"
        )
    return "\n".join(lines)


def get_line_devices(payload: dict[str, object], line: int) -> list[dict[str, object]]:
    bus_name = _line_name(line)
    return _collect_devices(payload).get(bus_name, [])


def render_modbus_map(payload: dict[str, object], config_name: str) -> str:
    resolved = _resolve_runtime_config(payload)
    devices = _collect_devices(payload)
    lines = [
        f"# Generated Modbus Map: {config_name}",
        "",
        "## Endpoint",
        "",
        f"- Modbus TCP: `{resolved.modbus.host}:{resolved.modbus.port}`",
        f"- Service `SlaveID`: `{SERVICE_SLAVE_ID}`",
        "",
        "## Service Registers",
        "",
        "| Register | Meaning |",
        "|---|---|",
        "| `HR1` | aggregated gateway status |",
        "| `HR2` | aggregated last error code |",
        "| `HR3` | aggregated success counter |",
        "| `HR4` | aggregated timeout counter |",
        "| `HR5` | aggregated protocol error counter |",
        "| `HR6` | aggregated poll cycle counter |",
        "| `HR10` | line 1 status |",
        "| `HR11` | line 2 status |",
        "| `HR12` | line 3 status |",
        "| `HR13` | line 4 status |",
        "",
        "Gateway status codes:",
        "",
        "- `1` ok",
        "- `2` degraded",
        "- `3` offline",
        "- `4` protocol error",
        "",
        "Last error codes:",
        "",
        "- `0` none",
        "- `1` timeout",
        "- `2` bad flag",
        "- `3` hash mismatch",
        "- `4` decode error",
        "- `5` io error",
        "",
    ]
    for bus in resolved.buses:
        lines.extend(
            [
                f"## {bus.name}",
                "",
                f"- serial: `{bus.serial.port}`, `{bus.serial.baudrate} {bus.serial.bytesize}{bus.serial.parity}{bus.serial.stopbits}`",
                f"- poll interval: `{bus.poll_interval_ms} ms`",
                f"- slave base: `{bus.modbus_slave_base}`",
                "",
            ]
        )
        bus_devices = devices.get(bus.name, [])
        if not bus_devices:
            lines.extend(["No devices configured on this line.", ""])
            continue
        lines.extend(
            [
                "| Device | SlaveID | Base Address | Tag | Channels |",
                "|------:|--------:|-------------:|-----|----------|",
            ]
        )
        for device in bus_devices:
            lines.append(
                f"| `{device['device']}` | `{device['slave_id']}` | `{device['base_address']}` | "
                f"`{device['tag']}` | `{device['channels']}` |"
            )
        lines.extend(
            [
                "",
                "Channel map for each device on this line:",
                "",
                "| Channel | OVEN Address | Value Register | Time Mark | Status | Type |",
                "|--------:|-------------:|----------------|----------:|-------:|------|",
            ]
        )
        example = bus_devices[0]
        for channel in example["channel_rows"]:
            if channel["value_start"] == channel["value_end"]:
                value_register = f"`{channel['value_start']}`"
            else:
                value_register = f"`{channel['value_start']},{channel['value_end']}`"
            lines.append(
                f"| `{channel['channel']}` | `{channel['address']}` | "
                f"{value_register} | `{channel['time_mark']}` | `{channel['status']}` | "
                f"`{channel['value_type']}` |"
            )
        lines.extend(
            [
                "",
                "Logic unit result masks:",
                "",
                "| Register | Meaning |",
                "|---|---|",
                "| `HR48` | LU state mask, bit0..bit7 -> LU1..LU8 |",
                "",
                "Channel status codes:",
                "",
                "- `0` disabled / no data / empty payload",
                "- `1` ok",
                "- `2` temporary communication error",
                "- `3` protocol error",
                "- `4` failed, reduced polling",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def set_line(
    payload: dict[str, object],
    *,
    line: int,
    port: str,
    baudrate: int,
    bytesize: int,
    parity: str,
    stopbits: int,
    timeout_ms: int,
    poll_interval_ms: int,
    address_bits: int = 8,
    modbus_slave_base: int | None = None,
) -> dict[str, object]:
    buses = _get_buses(payload)
    bus_name = _line_name(line)
    bus_index = line - 1
    slave_base = (
        modbus_slave_base
        if modbus_slave_base is not None
        else DEFAULT_BUS_SLAVE_BASES[bus_index]
    )
    bus_payload = {
        "name": bus_name,
        "modbus_slave_base": slave_base,
        "serial": {
            "port": port,
            "baudrate": baudrate,
            "bytesize": bytesize,
            "parity": parity,
            "stopbits": stopbits,
            "timeout_ms": timeout_ms,
            "address_bits": address_bits,
        },
        "poll_interval_ms": poll_interval_ms,
    }

    for index, bus in enumerate(buses):
        if bus["name"] == bus_name:
            buses[index] = bus_payload
            break
    else:
        buses.append(bus_payload)
        buses.sort(key=lambda entry: entry["name"])
    return bus_payload


def add_trm138_device(
    payload: dict[str, object],
    *,
    line: int,
    base_address: int,
    channels: list[int],
    tag: str,
    parameter: str = "rEAd",
) -> dict[str, int | str]:
    buses = _get_buses(payload)
    bus_name = _line_name(line)
    if not any(bus["name"] == bus_name for bus in buses):
        raise ValueError(f"{bus_name} is not configured")

    points = _get_points(payload)
    requested_channels = sorted(set(channels))
    if not requested_channels:
        raise ValueError("at least one channel must be selected")
    for channel in requested_channels:
        if not 1 <= channel <= TRM138_CHANNEL_COUNT:
            raise ValueError(
                f"invalid channel {channel}, expected 1..{TRM138_CHANNEL_COUNT}"
            )

    requested_addresses = {base_address + channel - 1 for channel in requested_channels}
    for point in points:
        if point.get("bus") == bus_name and point.get("address") in requested_addresses:
            raise ValueError(
                f"address overlap on {bus_name}: OVEN address {point['address']} is already used"
            )

    devices = sorted(
        {
            int(point["device"])
            for point in points
            if point.get("bus") == bus_name and "device" in point
        }
    )
    device = _next_device_number(devices)
    tag_slug = _slugify(tag) or f"trm138_{bus_name}_addr{base_address}"

    _append_trm138_points(
        points,
        bus_name=bus_name,
        device=device,
        base_address=base_address,
        channels=requested_channels,
        tag_slug=tag_slug,
        parameter=parameter,
    )

    points.sort(key=lambda entry: (entry.get("bus", ""), int(entry.get("device", 0)), int(entry.get("address", 0))))
    return {
        "bus": bus_name,
        "device": device,
        "base_address": base_address,
        "channels": len(requested_channels),
        "tag": tag_slug,
    }


def remove_line(payload: dict[str, object], *, line: int) -> dict[str, int]:
    buses = _get_buses(payload)
    bus_name = _line_name(line)
    points = _get_points(payload)
    removed_points = sum(1 for point in points if point.get("bus") == bus_name)
    payload["points"] = [point for point in points if point.get("bus") != bus_name]
    removed_buses = 0
    new_buses = [bus for bus in buses if bus.get("name") != bus_name]
    if len(new_buses) != len(buses):
        removed_buses = 1
    payload["buses"] = new_buses
    if removed_buses == 0:
        raise ValueError(f"{bus_name} is not configured")
    return {"line": line, "removed_buses": removed_buses, "removed_points": removed_points}


def remove_trm138_device(
    payload: dict[str, object],
    *,
    line: int,
    device: int | None = None,
    base_address: int | None = None,
    tag: str | None = None,
) -> dict[str, int | str]:
    bus_name = _line_name(line)
    points = _get_points(payload)
    grouped = _group_bus_devices(points, bus_name)
    matched_device = _match_device(
        grouped,
        bus_name=bus_name,
        device=device,
        base_address=base_address,
        tag=tag,
    )
    removed_points = len(grouped[matched_device])
    payload["points"] = [
        point
        for point in points
        if not (point.get("bus") == bus_name and int(point.get("device", 0)) == matched_device)
    ]
    removed = grouped[matched_device]
    return {
        "bus": bus_name,
        "device": matched_device,
        "base_address": min(int(point["address"]) for point in removed),
        "tag": _common_tag_prefix([str(point["name"]) for point in removed]),
        "removed_points": removed_points,
    }


def update_trm138_channels(
    payload: dict[str, object],
    *,
    line: int,
    channels: list[int],
    device: int | None = None,
    base_address: int | None = None,
    tag: str | None = None,
) -> dict[str, int | str]:
    bus_name = _line_name(line)
    points = _get_points(payload)
    requested_channels = sorted(set(channels))
    if not requested_channels:
        raise ValueError("at least one channel must be selected")
    for channel in requested_channels:
        if not 1 <= channel <= TRM138_CHANNEL_COUNT:
            raise ValueError(
                f"invalid channel {channel}, expected 1..{TRM138_CHANNEL_COUNT}"
            )

    grouped = _group_bus_devices(points, bus_name)
    matched_device = _match_device(
        grouped,
        bus_name=bus_name,
        device=device,
        base_address=base_address,
        tag=tag,
    )
    current_points = grouped[matched_device]
    base = min(
        int(point["address"])
        - (_channel_number_from_modbus_address(int(point["modbus_address"])) - 1)
        for point in current_points
    )
    tag_slug = _common_tag_prefix([str(point["name"]) for point in current_points])
    parameter = str(current_points[0].get("parameter", "rEAd"))

    payload["points"] = [
        point
        for point in points
        if not (point.get("bus") == bus_name and int(point.get("device", 0)) == matched_device)
    ]
    target_points = _get_points(payload)
    _append_trm138_points(
        target_points,
        bus_name=bus_name,
        device=matched_device,
        base_address=base,
        channels=requested_channels,
        tag_slug=tag_slug,
        parameter=parameter,
    )
    target_points.sort(
        key=lambda entry: (
            entry.get("bus", ""),
            int(entry.get("device", 0)),
            int(entry.get("address", 0)),
        )
    )
    return {
        "bus": bus_name,
        "device": matched_device,
        "base_address": base,
        "tag": tag_slug,
        "channels": ",".join(f"CH{channel}" for channel in requested_channels),
    }


def parse_channels(raw_value: str) -> list[int]:
    channels: set[int] = set()
    for part in raw_value.split(","):
        chunk = part.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_raw, end_raw = chunk.split("-", 1)
            start = int(start_raw)
            end = int(end_raw)
            if end < start:
                raise ValueError(f"invalid channel range: {chunk}")
            channels.update(range(start, end + 1))
            continue
        channels.add(int(chunk))
    ordered = sorted(channels)
    if not ordered:
        raise ValueError("channels list is empty")
    return ordered


def _new_config_document() -> dict[str, object]:
    return {
        "buses": [],
        "diagnostics": True,
        "modbus": {
            "host": "0.0.0.0",
            "port": 15020,
        },
        "status": _default_status_config(),
        "telemetry": _default_telemetry_config(),
        "health": _default_health_config(),
        "points": [],
    }


def _normalize_legacy_payload(payload: dict[str, object]) -> None:
    payload.setdefault("diagnostics", True)
    payload.setdefault("modbus", {"host": "0.0.0.0", "port": 15020})
    payload.setdefault("status", _default_status_config())
    payload.setdefault("telemetry", _default_telemetry_config())
    payload.setdefault("health", _default_health_config())
    if "points" not in payload:
        payload["points"] = []
    if "buses" in payload:
        return
    if "serial" not in payload or "poll_interval_ms" not in payload:
        payload["buses"] = []
        return
    payload["buses"] = [
        {
            "name": "line1",
            "modbus_slave_base": payload.pop("modbus_slave_base", DEFAULT_BUS_SLAVE_BASES[0]),
            "serial": payload.pop("serial"),
            "poll_interval_ms": payload.pop("poll_interval_ms"),
        }
    ]


def _get_buses(payload: dict[str, object]) -> list[dict[str, object]]:
    _normalize_legacy_payload(payload)
    buses = payload.setdefault("buses", [])
    if not isinstance(buses, list):
        raise ValueError("buses must be a list")
    if len(buses) > MAX_BUSES:
        raise ValueError(f"configured buses exceed limit: {len(buses)} > {MAX_BUSES}")
    return buses


def _get_points(payload: dict[str, object]) -> list[dict[str, object]]:
    _normalize_legacy_payload(payload)
    points = payload.setdefault("points", [])
    if not isinstance(points, list):
        raise ValueError("points must be a list")
    return points


def _line_name(line: int) -> str:
    if not 1 <= line <= MAX_BUSES:
        raise ValueError(f"line must be in range 1..{MAX_BUSES}")
    return f"line{line}"


def _next_device_number(devices: list[int]) -> int:
    for candidate in range(1, MAX_DEVICES_PER_BUS + 1):
        if candidate not in devices:
            return candidate
    raise ValueError(
        f"configured devices on line exceed limit: {len(devices)} >= {MAX_DEVICES_PER_BUS}"
    )


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _append_trm138_points(
    points: list[dict[str, object]],
    *,
    bus_name: str,
    device: int,
    base_address: int,
    channels: list[int],
    tag_slug: str,
    parameter: str,
) -> None:
    for channel in channels:
        modbus_address = _value_register_start(channel)
        points.append(
            {
                "name": f"{tag_slug}_ch{channel}",
                "bus": bus_name,
                "device": device,
                "address": base_address + channel - 1,
                "parameter": parameter,
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": modbus_address,
                "modbus_data_type": "float32",
                "time_mark_address": _time_mark_register(channel),
                "channel_status_address": _status_register(channel),
            }
        )


def _group_bus_devices(
    points: list[dict[str, object]],
    bus_name: str,
) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for point in points:
        if point.get("bus") != bus_name:
            continue
        grouped.setdefault(int(point["device"]), []).append(point)
    return grouped


def _match_device(
    grouped: dict[int, list[dict[str, object]]],
    *,
    bus_name: str,
    device: int | None,
    base_address: int | None,
    tag: str | None,
) -> int:
    matched_device: int | None = None
    normalized_tag = _slugify(tag) if tag is not None else None
    for device_number, device_points in grouped.items():
        device_base_address = min(int(point["address"]) for point in device_points)
        device_tag = _common_tag_prefix([str(point["name"]) for point in device_points])
        if device is not None and device_number != device:
            continue
        if base_address is not None and device_base_address != base_address:
            continue
        if normalized_tag is not None and device_tag != normalized_tag:
            continue
        if matched_device is not None:
            raise ValueError("device selector is ambiguous")
        matched_device = device_number
    if matched_device is None:
        raise ValueError(f"device not found on {bus_name}")
    return matched_device


def _resolve_runtime_config(payload: dict[str, object]):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        temp_path = handle.name
    try:
        return load_config(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def _collect_devices(payload: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    resolved = _resolve_runtime_config(payload)
    devices: dict[str, list[dict[str, object]]] = {bus.name: [] for bus in resolved.buses}
    grouped: dict[tuple[str, int], list[object]] = {}
    for point in resolved.points:
        grouped.setdefault((point.bus, point.device), []).append(point)
    for (bus_name, device_number), points in grouped.items():
        ordered_points = sorted(points, key=lambda point: point.address)
        first = ordered_points[0]
        base_address = min(
            point.address - (_channel_number_from_modbus_address(point.modbus_address) - 1)
            for point in ordered_points
        )
        devices[bus_name].append(
            {
                "device": device_number,
                "slave_id": first.modbus_slave_id,
                "base_address": base_address,
                "tag": _common_tag_prefix([point.name for point in ordered_points]),
                "channels": ",".join(
                    f"CH{_channel_number_from_modbus_address(point.modbus_address)}"
                    for point in ordered_points
                ),
                "channel_rows": [
                    {
                        "channel": _channel_number_from_modbus_address(point.modbus_address),
                        "address": point.address,
                        "value_start": point.modbus_address,
                        "value_end": point.modbus_address + 1,
                        "time_mark": point.time_mark_address,
                        "status": point.channel_status_address,
                        "value_type": point.modbus_data_type,
                    }
                    for point in ordered_points
                ],
            }
        )
    for bus_name in devices:
        devices[bus_name].sort(key=lambda item: int(item["device"]))
    return devices


def _select_collected_device(
    devices: list[dict[str, object]],
    *,
    device: int | None = None,
    base_address: int | None = None,
    tag: str | None = None,
) -> dict[str, object]:
    normalized_tag = _slugify(tag) if tag is not None else None
    selected: dict[str, object] | None = None
    for item in devices:
        if device is not None and int(item["device"]) != device:
            continue
        if base_address is not None and int(item["base_address"]) != base_address:
            continue
        if normalized_tag is not None and str(item["tag"]) != normalized_tag:
            continue
        if selected is not None:
            raise ValueError("device selector is ambiguous")
        selected = item
    if selected is None:
        raise ValueError("device not found")
    return selected


def _common_tag_prefix(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return re.sub(r"_ch\d+$", "", names[0])
    prefix = names[0]
    for name in names[1:]:
        while not name.startswith(prefix) and prefix:
            prefix = prefix[:-1]
    prefix = prefix.rstrip("_")
    prefix = re.sub(r"_ch$", "", prefix)
    return re.sub(r"_ch\d+$", "", prefix)


def _channel_number_from_modbus_address(modbus_address: int) -> int:
    return (
        (modbus_address - TRM138_REGISTER_BASE) // TRM138_VALUE_REGISTERS_PER_CHANNEL
    ) + 1


def _value_register_start(channel: int) -> int:
    return TRM138_REGISTER_BASE + (channel - 1) * TRM138_VALUE_REGISTERS_PER_CHANNEL


def _time_mark_register(channel: int) -> int:
    return TRM138_TIME_MARK_BASE + channel - 1


def _status_register(channel: int) -> int:
    return TRM138_STATUS_BASE + channel - 1
