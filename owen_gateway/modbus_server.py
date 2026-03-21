from __future__ import annotations

import asyncio
from dataclasses import dataclass

from owen_gateway.config import (
    ModbusConfig,
    PointConfig,
    StatusConfig,
    TelemetryConfig,
)
from owen_gateway.encoding import encode_registers


@dataclass(slots=True)
class _StoreAdapter:
    context: object

    def write(self, slave_id: int, point: PointConfig, value: object) -> None:
        self.write_value(
            slave_id,
            point.register_type,
            point.modbus_address,
            point.modbus_data_type,
            value,
        )

    def write_point_metadata(
        self,
        slave_id: int,
        point: PointConfig,
        *,
        time_mark: int | None = None,
        channel_status: int | None = None,
    ) -> None:
        if time_mark is not None and point.time_mark_address is not None:
            self.write_value(
                slave_id,
                point.register_type,
                point.time_mark_address,
                "uint16",
                time_mark,
            )
        if channel_status is not None and point.channel_status_address is not None:
            self.write_value(
                slave_id,
                point.register_type,
                point.channel_status_address,
                "uint16",
                channel_status,
            )

    def write_status(self, slave_id: int, status: StatusConfig, value: object) -> None:
        self.write_value(
            slave_id,
            status.register_type,
            status.modbus_address,
            status.modbus_data_type,
            value,
        )

    def write_value(
        self,
        slave_id: int,
        register_type: str,
        address: int,
        data_type: str,
        value: object,
    ) -> None:
        encoded = encode_registers(value, data_type)
        slave = self.context[slave_id]
        if register_type == "coil":
            slave.setValues(0x01, address, [bool(v) for v in encoded])
            return
        if register_type == "discrete_input":
            slave.setValues(0x02, address, [bool(v) for v in encoded])
            return
        if register_type == "holding_register":
            slave.setValues(0x03, address, encoded)
            return
        if register_type == "input_register":
            slave.setValues(0x04, address, encoded)
            return
        raise ValueError(f"unsupported register_type: {register_type}")


class ModbusPublisher:
    def __init__(
        self,
        *,
        modbus: ModbusConfig,
        status: StatusConfig,
        telemetry: TelemetryConfig,
        points: list[PointConfig],
        extra_slave_ids: list[int] | None = None,
    ) -> None:
        self.modbus = modbus
        self.status = status
        self.telemetry = telemetry
        self.points = points
        self._server_task: asyncio.Task[None] | None = None
        self._store = None
        self._slave_ids = sorted(
            {point.modbus_slave_id for point in points}.union(extra_slave_ids or [])
        )

    async def start(self) -> None:
        from pymodbus.datastore import (
            ModbusSlaveContext,
            ModbusSequentialDataBlock,
            ModbusServerContext,
        )
        from pymodbus.server import StartAsyncTcpServer

        max_coils = _calc_size(
            self.points,
            self.status,
            self.telemetry,
            {"coil", "discrete_input"},
        )
        max_regs = _calc_size(
            self.points,
            self.status,
            self.telemetry,
            {"holding_register", "input_register"},
        )
        contexts = {
            slave_id: ModbusSlaveContext(
                di=ModbusSequentialDataBlock(0, [0] * max_coils),
                co=ModbusSequentialDataBlock(0, [0] * max_coils),
                hr=ModbusSequentialDataBlock(0, [0] * max_regs),
                ir=ModbusSequentialDataBlock(0, [0] * max_regs),
            )
            for slave_id in self._slave_ids
        }
        self._store = _StoreAdapter(ModbusServerContext(slaves=contexts, single=False))
        self._server_task = asyncio.create_task(
            StartAsyncTcpServer(
                context=self._store.context,
                address=(self.modbus.host, self.modbus.port),
            )
        )
        await asyncio.sleep(0)

    async def stop(self) -> None:
        if self._server_task is None:
            return
        self._server_task.cancel()
        try:
            await self._server_task
        except asyncio.CancelledError:
            pass
        self._server_task = None

    def publish(self, slave_id: int, point: PointConfig, value: object) -> None:
        if self._store is None:
            raise RuntimeError("Modbus server is not started")
        self._store.write(slave_id, point, value)

    def publish_value(
        self,
        slave_id: int,
        register_type: str,
        address: int,
        data_type: str,
        value: object,
    ) -> None:
        if self._store is None:
            raise RuntimeError("Modbus server is not started")
        self._store.write_value(slave_id, register_type, address, data_type, value)

    def publish_point_metadata(
        self,
        slave_id: int,
        point: PointConfig,
        *,
        time_mark: int | None = None,
        channel_status: int | None = None,
    ) -> None:
        if self._store is None:
            raise RuntimeError("Modbus server is not started")
        self._store.write_point_metadata(
            slave_id,
            point,
            time_mark=time_mark,
            channel_status=channel_status,
        )

    def publish_status(self, slave_id: int, value: object) -> None:
        if self._store is None:
            raise RuntimeError("Modbus server is not started")
        if not self.status.enabled:
            return
        self._store.write_status(slave_id, self.status, value)

    def publish_telemetry(
        self,
        slave_id: int,
        *,
        last_error_code: int | None = None,
        success_counter: int | None = None,
        timeout_counter: int | None = None,
        protocol_error_counter: int | None = None,
        poll_cycle_counter: int | None = None,
    ) -> None:
        if self._store is None:
            raise RuntimeError("Modbus server is not started")
        if not self.telemetry.enabled:
            return
        telemetry = self.telemetry
        if last_error_code is not None:
            self._store.write_value(
                slave_id,
                telemetry.register_type,
                telemetry.last_error_code_address,
                "uint16",
                last_error_code,
            )
        if success_counter is not None:
            self._store.write_value(
                slave_id,
                telemetry.register_type,
                telemetry.success_counter_address,
                "uint16",
                success_counter,
            )
        if timeout_counter is not None:
            self._store.write_value(
                slave_id,
                telemetry.register_type,
                telemetry.timeout_counter_address,
                "uint16",
                timeout_counter,
            )
        if protocol_error_counter is not None:
            self._store.write_value(
                slave_id,
                telemetry.register_type,
                telemetry.protocol_error_counter_address,
                "uint16",
                protocol_error_counter,
            )
        if poll_cycle_counter is not None:
            self._store.write_value(
                slave_id,
                telemetry.register_type,
                telemetry.poll_cycle_counter_address,
                "uint16",
                poll_cycle_counter,
            )


def _calc_size(
    points: list[PointConfig],
    status: StatusConfig,
    telemetry: TelemetryConfig,
    register_types: set[str],
) -> int:
    max_index = 1
    for point in points:
        if point.register_type in register_types:
            width = 1 if point.modbus_data_type in {"bool", "uint16", "int16"} else 2
            max_index = max(max_index, point.modbus_address + width + 1)
            if point.time_mark_address is not None:
                max_index = max(max_index, point.time_mark_address + 2)
            if point.channel_status_address is not None:
                max_index = max(max_index, point.channel_status_address + 2)
    if status.enabled and status.register_type in register_types:
        width = 1 if status.modbus_data_type in {"bool", "uint16", "int16"} else 2
        max_index = max(max_index, status.modbus_address + width + 1)
    if telemetry.enabled and telemetry.register_type in register_types:
        max_index = max(
            max_index,
            telemetry.last_error_code_address + 2,
            telemetry.success_counter_address + 2,
            telemetry.timeout_counter_address + 2,
            telemetry.protocol_error_counter_address + 2,
            telemetry.poll_cycle_counter_address + 2,
        )
    return max_index
