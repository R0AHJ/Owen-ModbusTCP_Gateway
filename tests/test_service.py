import unittest
from unittest.mock import AsyncMock
from unittest.mock import patch

from owen_gateway.config import (
    BusConfig,
    HealthConfig,
    ModbusConfig,
    OwenGatewayConfig,
    PointConfig,
    SerialConfig,
    StatusConfig,
    TelemetryConfig,
)
from owen_gateway.protocol import OwenFrame, hash_parameter_name
from owen_gateway.service import (
    OwenGatewayService,
    _decode_fixed_point,
    _evaluate_logic_unit,
)


class ServiceHelperTests(unittest.TestCase):
    def _base_runtime_config(self) -> OwenGatewayConfig:
        return OwenGatewayConfig(
            buses=[
                BusConfig(
                    name="bus1",
                    serial=SerialConfig(
                        port="COM1",
                        baudrate=9600,
                        bytesize=8,
                        parity="N",
                        stopbits=1,
                        timeout_ms=1000,
                    ),
                    poll_interval_ms=1000,
                    modbus_slave_base=10,
                )
            ],
            diagnostics=False,
            modbus=ModbusConfig(host="127.0.0.1", port=15020),
            status=StatusConfig(
                enabled=True,
                register_type="holding_register",
                modbus_address=1,
                modbus_data_type="uint16",
            ),
            telemetry=TelemetryConfig(
                enabled=True,
                register_type="holding_register",
                last_error_code_address=2,
                success_counter_address=3,
                timeout_counter_address=4,
                protocol_error_counter_address=5,
                poll_cycle_counter_address=6,
            ),
            health=HealthConfig(
                fault_after_failures=10,
                recovery_poll_interval_cycles=5,
            ),
            points=[],
        )

    def test_decode_fixed_point_unsigned(self) -> None:
        self.assertEqual(_decode_fixed_point(1, 1234, signed=False), 123.4)

    def test_decode_fixed_point_signed(self) -> None:
        self.assertEqual(_decode_fixed_point(2, 0xFF85, signed=True), -1.23)

    def test_direct_hysteresis_logic_keeps_previous_state_inside_band(self) -> None:
        self.assertTrue(
            _evaluate_logic_unit(
                channel_value=9.0,
                setpoint=10.0,
                hysteresis=1.0,
                al_type=1,
                previous_state=True,
            )
        )
        self.assertFalse(
            _evaluate_logic_unit(
                channel_value=11.0,
                setpoint=10.0,
                hysteresis=1.0,
                al_type=1,
                previous_state=False,
            )
        )

    def test_reverse_hysteresis_logic(self) -> None:
        self.assertTrue(
            _evaluate_logic_unit(
                channel_value=12.5,
                setpoint=10.0,
                hysteresis=1.0,
                al_type=2,
                previous_state=False,
            )
        )
        self.assertFalse(
            _evaluate_logic_unit(
                channel_value=8.5,
                setpoint=10.0,
                hysteresis=1.0,
                al_type=2,
                previous_state=True,
            )
        )

    def test_band_and_outside_band_logic(self) -> None:
        self.assertTrue(
            _evaluate_logic_unit(
                channel_value=10.5,
                setpoint=10.0,
                hysteresis=1.0,
                al_type=3,
                previous_state=False,
            )
        )

    def test_logic_mask_semantics_are_per_lu(self) -> None:
        mask = 0
        for lu_index, state in enumerate([True, False, True, False, False, False, False, True]):
            if state:
                mask |= 1 << lu_index
        self.assertEqual(mask, 0b10000101)
        self.assertTrue(
            _evaluate_logic_unit(
                channel_value=12.5,
                setpoint=10.0,
                hysteresis=1.0,
                al_type=4,
                previous_state=False,
            )
        )

    def test_publish_logic_unit_masks_uses_internal_alarm_type_points(self) -> None:
        config = self._base_runtime_config()
        config.points = [
            PointConfig(
                name="ch1_read",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="rEAd",
                parameter_index=None,
                protocol_format="float32",
                register_type="holding_register",
                modbus_address=16,
                modbus_data_type="float32",
            ),
            PointConfig(
                name="ch1_setpoint",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="C.SP",
                parameter_index=None,
                protocol_format="stored_dot",
                register_type="holding_register",
                modbus_address=56,
                modbus_data_type="float32",
            ),
            PointConfig(
                name="ch1_hyst",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="HYSt",
                parameter_index=None,
                protocol_format="stored_dot",
                register_type="holding_register",
                modbus_address=58,
                modbus_data_type="float32",
            ),
            PointConfig(
                name="ch1_al_t",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="AL.t",
                parameter_index=None,
                protocol_format="uint16",
                register_type="holding_register",
                modbus_address=0,
                modbus_data_type="uint16",
                publish_to_modbus=False,
            ),
        ]
        service = OwenGatewayService(config)

        published_values: list[tuple[int, str, int, str, object]] = []

        class DummyModbus:
            def publish_value(
                self,
                slave_id: int,
                register_type: str,
                address: int,
                data_type: str,
                value: object,
            ) -> None:
                published_values.append(
                    (slave_id, register_type, address, data_type, value)
                )

        service.modbus = DummyModbus()
        service.point_values["ch1_read"] = 8.0
        service.point_values["ch1_setpoint"] = 10.0
        service.point_values["ch1_hyst"] = 1.0
        service.point_values["ch1_al_t"] = 1

        service._publish_logic_unit_masks("bus1", 48, config.points)

        self.assertEqual(
            published_values,
            [(48, "holding_register", 48, "uint16", 1)],
        )

    def test_run_closes_started_serial_clients_when_startup_fails(self) -> None:
        config = self._base_runtime_config()
        config.buses = [
            config.buses[0],
            BusConfig(
                name="bus2",
                serial=SerialConfig(
                    port="COM2",
                    baudrate=9600,
                    bytesize=8,
                    parity="N",
                    stopbits=1,
                    timeout_ms=1000,
                ),
                poll_interval_ms=1000,
                modbus_slave_base=50,
            ),
        ]
        config.points = [
            PointConfig(
                name="ch1_read",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="rEAd",
                parameter_index=None,
                protocol_format="float32",
                register_type="holding_register",
                modbus_address=16,
                modbus_data_type="float32",
            ),
            PointConfig(
                name="ch2_read",
                bus="bus2",
                device=1,
                modbus_slave_id=96,
                address=96,
                parameter="rEAd",
                parameter_index=None,
                protocol_format="float32",
                register_type="holding_register",
                modbus_address=16,
                modbus_data_type="float32",
            ),
        ]
        service = OwenGatewayService(config)

        class DummyModbus:
            def __init__(self) -> None:
                self.start = AsyncMock()
                self.stop = AsyncMock()

            def publish_status(self, slave_id: int, value: object) -> None:
                return None

            def publish_telemetry(self, slave_id: int, **kwargs: object) -> None:
                return None

            def publish_value(
                self,
                slave_id: int,
                register_type: str,
                address: int,
                data_type: str,
                value: object,
            ) -> None:
                return None

        class DummyClient:
            def __init__(self, *, fail_on_connect: bool = False) -> None:
                self.fail_on_connect = fail_on_connect
                self.close_calls = 0

            def connect(self) -> None:
                if self.fail_on_connect:
                    raise RuntimeError("connect failed")

            def close(self) -> None:
                self.close_calls += 1

        modbus = DummyModbus()
        first_client = DummyClient()
        second_client = DummyClient(fail_on_connect=True)
        service.modbus = modbus
        service.serial_clients = {
            "bus1": first_client,
            "bus2": second_client,
        }

        with self.assertRaisesRegex(RuntimeError, "connect failed"):
            import asyncio

            asyncio.run(service.run())

        self.assertEqual(first_client.close_calls, 1)
        self.assertEqual(second_client.close_calls, 0)
        modbus.stop.assert_awaited_once()

    def test_handle_modbus_write_writes_device_and_updates_logic(self) -> None:
        config = self._base_runtime_config()
        config.points = [
            PointConfig(
                name="ch1_read",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="rEAd",
                parameter_index=None,
                protocol_format="float32",
                register_type="holding_register",
                modbus_address=16,
                modbus_data_type="float32",
            ),
            PointConfig(
                name="ch1_setpoint",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="C.SP",
                parameter_index=None,
                protocol_format="stored_dot",
                register_type="holding_register",
                modbus_address=56,
                modbus_data_type="float32",
                writable=True,
            ),
            PointConfig(
                name="ch1_hyst",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="HYSt",
                parameter_index=None,
                protocol_format="stored_dot",
                register_type="holding_register",
                modbus_address=58,
                modbus_data_type="float32",
            ),
            PointConfig(
                name="ch1_al_t",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="AL.t",
                parameter_index=None,
                protocol_format="uint16",
                register_type="holding_register",
                modbus_address=0,
                modbus_data_type="uint16",
                publish_to_modbus=False,
            ),
        ]
        service = OwenGatewayService(config)

        class DummyModbus:
            def __init__(self) -> None:
                self.published: list[tuple[int, str, object]] = []
                self.restored: list[tuple[int, int, list[int]]] = []
                self.logic: list[tuple[int, str, int, str, object]] = []

            def publish(self, slave_id: int, point: PointConfig, value: object) -> None:
                self.published.append((slave_id, point.name, value))

            def publish_point_metadata(
                self,
                slave_id: int,
                point: PointConfig,
                *,
                time_mark: int | None = None,
                channel_status: int | None = None,
            ) -> None:
                self.published.append((slave_id, f"{point.name}:status", channel_status))

            def publish_value(
                self,
                slave_id: int,
                register_type: str,
                address: int,
                data_type: str,
                value: object,
            ) -> None:
                self.logic.append((slave_id, register_type, address, data_type, value))

            def restore_holding_registers(
                self,
                slave_id: int,
                address: int,
                values: list[int],
            ) -> None:
                self.restored.append((slave_id, address, values))

        class DummyClient:
            def exchange_write(
                self,
                address: int,
                parameter_name: str,
                payload: bytes,
                parameter_index: int | None = None,
            ) -> tuple[bytes, bytes, OwenFrame]:
                return (
                    b"req",
                    b"resp",
                    OwenFrame(
                        address=address << 3,
                        request=False,
                        parameter_hash=hash_parameter_name(parameter_name),
                        payload=b"\x00",
                    ),
                )

            def exchange(
                self,
                address: int,
                parameter_name: str,
                parameter_index: int | None = None,
            ) -> tuple[bytes, bytes, OwenFrame]:
                return (
                    b"req",
                    b"resp",
                    OwenFrame(
                        address=address << 3,
                        request=False,
                        parameter_hash=hash_parameter_name(parameter_name),
                        payload=bytes.fromhex("1064"),
                    ),
                )

        service.modbus = DummyModbus()
        service.serial_clients["bus1"] = DummyClient()
        service.point_values["ch1_read"] = 8.0
        service.point_values["ch1_hyst"] = 1.0
        service.point_values["ch1_al_t"] = 1

        import asyncio

        asyncio.run(
            service._handle_modbus_holding_write(
                48,
                56,
                [0x4120, 0x0000],
                [0x0000, 0x0000],
            )
        )

        self.assertIn((48, "ch1_setpoint", 10.0), service.modbus.published)
        self.assertEqual(service.point_values["ch1_setpoint"], 10.0)
        self.assertEqual(service.modbus.restored, [])
        self.assertEqual(
            service.modbus.logic,
            [(48, "holding_register", 48, "uint16", 1)],
        )

    def test_handle_modbus_write_reverts_non_writable_address(self) -> None:
        config = self._base_runtime_config()
        config.points = [
            PointConfig(
                name="ch1_read",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="rEAd",
                parameter_index=None,
                protocol_format="float32",
                register_type="holding_register",
                modbus_address=16,
                modbus_data_type="float32",
            ),
        ]
        service = OwenGatewayService(config)

        class DummyModbus:
            def __init__(self) -> None:
                self.restored: list[tuple[int, int, list[int]]] = []

            def restore_holding_registers(
                self,
                slave_id: int,
                address: int,
                values: list[int],
            ) -> None:
                self.restored.append((slave_id, address, values))

        service.modbus = DummyModbus()

        import asyncio

        asyncio.run(service._handle_modbus_holding_write(48, 16, [1, 2], [3, 4]))

        self.assertEqual(service.modbus.restored, [(48, 16, [3, 4])])

    def test_handle_modbus_write_accepts_short_opaque_ack(self) -> None:
        config = self._base_runtime_config()
        config.diagnostics = True
        config.points = [
            PointConfig(
                name="ch1_setpoint",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="C.SP",
                parameter_index=None,
                protocol_format="stored_dot",
                register_type="holding_register",
                modbus_address=56,
                modbus_data_type="float32",
                writable=True,
            ),
        ]
        service = OwenGatewayService(config)

        class DummyModbus:
            def __init__(self) -> None:
                self.published: list[tuple[int, str, object]] = []
                self.restored: list[tuple[int, int, list[int]]] = []

            def publish(self, slave_id: int, point: PointConfig, value: object) -> None:
                self.published.append((slave_id, point.name, value))

            def publish_point_metadata(
                self,
                slave_id: int,
                point: PointConfig,
                *,
                time_mark: int | None = None,
                channel_status: int | None = None,
            ) -> None:
                self.published.append((slave_id, f"{point.name}:status", channel_status))

            def publish_value(
                self,
                slave_id: int,
                register_type: str,
                address: int,
                data_type: str,
                value: object,
            ) -> None:
                return None

            def restore_holding_registers(
                self,
                slave_id: int,
                address: int,
                values: list[int],
            ) -> None:
                self.restored.append((slave_id, address, values))

        class DummyClient:
            def exchange(
                self,
                address: int,
                parameter_name: str,
                parameter_index: int | None = None,
            ) -> tuple[bytes, bytes, OwenFrame]:
                return (
                    b"req",
                    b"resp",
                    OwenFrame(
                        address=address << 3,
                        request=False,
                        parameter_hash=hash_parameter_name(parameter_name),
                        payload=bytes.fromhex("1390"),
                    ),
                )

            def exchange_write(
                self,
                address: int,
                parameter_name: str,
                payload: bytes,
                parameter_index: int | None = None,
            ) -> tuple[bytes, bytes, None]:
                return (b"req", b"#opaque\x16", None)

        service.modbus = DummyModbus()
        service.serial_clients["bus1"] = DummyClient()

        import asyncio

        asyncio.run(
            service._handle_modbus_holding_write(
                48,
                56,
                [0x42B6, 0x6666],
                [0x42B4, 0x999A],
            )
        )

        self.assertEqual(service.modbus.restored, [])

    def test_poll_retries_after_timeout_and_uses_gap(self) -> None:
        config = self._base_runtime_config()
        config.buses[0].request_retries = 1
        config.buses[0].inter_request_delay_ms = 15
        config.points = [
            PointConfig(
                name="ch1_read",
                bus="bus1",
                device=1,
                modbus_slave_id=48,
                address=48,
                parameter="rEAd",
                parameter_index=None,
                protocol_format="float32",
                register_type="holding_register",
                modbus_address=16,
                modbus_data_type="float32",
            ),
        ]
        service = OwenGatewayService(config)

        class DummyModbus:
            def publish(self, slave_id: int, point: PointConfig, value: object) -> None:
                return None

            def publish_point_metadata(
                self,
                slave_id: int,
                point: PointConfig,
                *,
                time_mark: int | None = None,
                channel_status: int | None = None,
            ) -> None:
                return None

            def publish_value(
                self,
                slave_id: int,
                register_type: str,
                address: int,
                data_type: str,
                value: object,
            ) -> None:
                return None

            def publish_status(self, slave_id: int, value: object) -> None:
                return None

            def publish_telemetry(self, slave_id: int, **kwargs: object) -> None:
                return None

        class DummyClient:
            def __init__(self) -> None:
                self.calls = 0

            def exchange(
                self,
                address: int,
                parameter_name: str,
                parameter_index: int | None = None,
            ) -> tuple[bytes, bytes, OwenFrame]:
                self.calls += 1
                if self.calls == 1:
                    raise TimeoutError("slow device")
                return (
                    b"req",
                    b"resp",
                    OwenFrame(
                        address=address << 3,
                        request=False,
                        parameter_hash=hash_parameter_name(parameter_name),
                        payload=bytes.fromhex("42b1cb74"),
                    ),
                )

        service.modbus = DummyModbus()
        client = DummyClient()
        service.serial_clients["bus1"] = client

        import asyncio

        with patch("owen_gateway.service.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            asyncio.run(service._poll_bus_once(config.buses[0], {48: config.points}))

        self.assertEqual(client.calls, 2)
        self.assertTrue(sleep_mock.await_count >= 1)
        self.assertAlmostEqual(float(service.point_values["ch1_read"]), 88.8973, places=2)


if __name__ == "__main__":
    unittest.main()
