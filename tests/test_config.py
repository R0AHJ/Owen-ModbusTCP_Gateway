import json
import os
import tempfile
import unittest

from owen_gateway.config import load_config


def _base_config() -> dict[str, object]:
    return {
        "serial": {
            "port": "COM6",
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "timeout_ms": 1000,
            "address_bits": 8,
        },
        "poll_interval_ms": 1000,
        "modbus": {
            "host": "127.0.0.1",
            "port": 15020,
        },
        "status": {
            "enabled": True,
            "register_type": "holding_register",
            "modbus_address": 1,
            "modbus_data_type": "uint16",
        },
        "telemetry": {
            "enabled": True,
            "register_type": "holding_register",
            "last_error_code_address": 2,
            "success_counter_address": 3,
            "timeout_counter_address": 4,
            "protocol_error_counter_address": 5,
            "poll_cycle_counter_address": 6,
        },
        "health": {
            "fault_after_failures": 10,
            "recovery_poll_interval_cycles": 5,
        },
    }


class ConfigTests(unittest.TestCase):
    def _load(self, payload: dict[str, object]):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(payload, handle)
            temp_path = handle.name
        try:
            return load_config(temp_path)
        finally:
            os.unlink(temp_path)

    def test_modbus_slave_id_defaults_to_device_base_address(self) -> None:
        payload = _base_config()
        payload["points"] = [
            {
                "name": "ch1",
                "device": 3,
                "address": 96,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 16,
                "modbus_data_type": "float32",
                "time_mark_address": 18,
                "channel_status_address": 19,
            }
        ]

        config = self._load(payload)

        self.assertEqual(config.points[0].modbus_slave_id, 96)

    def test_same_register_map_is_allowed_on_different_slave_ids(self) -> None:
        payload = _base_config()
        payload["points"] = [
            {
                "name": "dev1_ch1",
                "device": 1,
                "modbus_slave_id": 96,
                "address": 96,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 16,
                "modbus_data_type": "float32",
                "time_mark_address": 18,
                "channel_status_address": 19,
            },
            {
                "name": "dev2_ch1",
                "device": 2,
                "modbus_slave_id": 196,
                "address": 196,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 16,
                "modbus_data_type": "float32",
                "time_mark_address": 18,
                "channel_status_address": 19,
            },
        ]

        config = self._load(payload)

        self.assertEqual([point.modbus_slave_id for point in config.points], [96, 196])

    def test_modbus_slave_id_uses_device_base_address_for_each_line(self) -> None:
        payload = _base_config()
        payload.pop("serial")
        payload.pop("poll_interval_ms")
        payload["buses"] = [
            {
                "name": "line1",
                "serial": {
                    "port": "COM5",
                    "baudrate": 9600,
                    "bytesize": 8,
                    "parity": "N",
                    "stopbits": 1,
                    "timeout_ms": 1000,
                    "address_bits": 8,
                },
                "poll_interval_ms": 1000,
                "modbus_slave_base": 10,
            },
            {
                "name": "line2",
                "serial": {
                    "port": "COM6",
                    "baudrate": 2400,
                    "bytesize": 8,
                    "parity": "E",
                    "stopbits": 1,
                    "timeout_ms": 1200,
                    "address_bits": 8,
                },
                "poll_interval_ms": 1500,
                "modbus_slave_base": 50,
            },
        ]
        payload["points"] = [
            {
                "name": "line1_ch1",
                "bus": "line1",
                "device": 1,
                "address": 96,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 16,
                "modbus_data_type": "float32",
            },
            {
                "name": "line1_ch2",
                "bus": "line1",
                "device": 1,
                "address": 97,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 20,
                "modbus_data_type": "float32",
            },
            {
                "name": "line2_ch1",
                "bus": "line2",
                "device": 1,
                "address": 48,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 16,
                "modbus_data_type": "float32",
            },
            {
                "name": "line2_ch2",
                "bus": "line2",
                "device": 1,
                "address": 49,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 20,
                "modbus_data_type": "float32",
            },
        ]

        config = self._load(payload)

        slave_ids = {point.name: point.modbus_slave_id for point in config.points}
        self.assertEqual(slave_ids["line1_ch1"], 96)
        self.assertEqual(slave_ids["line1_ch2"], 96)
        self.assertEqual(slave_ids["line2_ch1"], 48)
        self.assertEqual(slave_ids["line2_ch2"], 48)

    def test_explicit_modbus_slave_id_is_preserved_for_sparse_channels(self) -> None:
        payload = _base_config()
        payload["points"] = [
            {
                "name": "dev1_ch1",
                "device": 1,
                "modbus_slave_id": 96,
                "address": 102,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 28,
                "modbus_data_type": "float32",
            }
        ]

        config = self._load(payload)

        self.assertEqual(config.points[0].modbus_slave_id, 96)

    def test_parameter_index_is_loaded_and_validated(self) -> None:
        payload = _base_config()
        payload["points"] = [
            {
                "name": "dev1_lu1_setpoint",
                "device": 1,
                "address": 96,
                "parameter": "C.SP",
                "parameter_index": 0,
                "protocol_format": "stored_dot",
                "register_type": "holding_register",
                "modbus_address": 100,
                "modbus_data_type": "float32",
            }
        ]

        config = self._load(payload)

        self.assertEqual(config.points[0].parameter_index, 0)

    def test_internal_point_can_be_excluded_from_modbus_publication(self) -> None:
        payload = _base_config()
        payload["points"] = [
            {
                "name": "dev1_ch1",
                "device": 1,
                "address": 96,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 16,
                "modbus_data_type": "float32",
                "channel_status_address": 40,
            },
            {
                "name": "dev1_ch1_al_t_internal",
                "device": 1,
                "address": 96,
                "parameter": "AL.t",
                "protocol_format": "uint16",
                "register_type": "holding_register",
                "modbus_address": 0,
                "modbus_data_type": "uint16",
                "publish_to_modbus": False,
            },
        ]

        config = self._load(payload)

        self.assertFalse(config.points[1].publish_to_modbus)

    def test_writable_point_is_loaded(self) -> None:
        payload = _base_config()
        payload["points"] = [
            {
                "name": "dev1_ch1_sp",
                "device": 1,
                "address": 96,
                "parameter": "C.SP",
                "protocol_format": "stored_dot",
                "register_type": "holding_register",
                "modbus_address": 56,
                "modbus_data_type": "float32",
                "writable": True,
            }
        ]

        config = self._load(payload)

        self.assertTrue(config.points[0].writable)

    def test_writable_internal_point_is_rejected(self) -> None:
        payload = _base_config()
        payload["points"] = [
            {
                "name": "dev1_ch1_al_t_internal",
                "device": 1,
                "address": 96,
                "parameter": "AL.t",
                "protocol_format": "uint16",
                "register_type": "holding_register",
                "modbus_address": 0,
                "modbus_data_type": "uint16",
                "publish_to_modbus": False,
                "writable": True,
            }
        ]

        with self.assertRaisesRegex(ValueError, "writable point must be published"):
            self._load(payload)

    def test_writable_type_mismatch_is_rejected(self) -> None:
        payload = _base_config()
        payload["points"] = [
            {
                "name": "dev1_ch1_sp",
                "device": 1,
                "address": 96,
                "parameter": "C.SP",
                "protocol_format": "stored_dot",
                "register_type": "holding_register",
                "modbus_address": 56,
                "modbus_data_type": "uint16",
                "writable": True,
            }
        ]

        with self.assertRaisesRegex(ValueError, "incompatible protocol/modbus types"):
            self._load(payload)

    def test_legacy_stale_after_cycles_is_ignored(self) -> None:
        payload = _base_config()
        payload["health"]["stale_after_cycles"] = 99
        payload["points"] = [
            {
                "name": "ch1",
                "device": 1,
                "address": 96,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 16,
                "modbus_data_type": "float32",
            }
        ]

        config = self._load(payload)

        self.assertEqual(config.health.fault_after_failures, 10)
        self.assertEqual(config.health.recovery_poll_interval_cycles, 5)

    def test_duplicate_modbus_slave_id_for_different_devices_is_rejected(self) -> None:
        payload = _base_config()
        payload["points"] = [
            {
                "name": "dev1_ch1",
                "device": 1,
                "modbus_slave_id": 96,
                "address": 96,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 16,
                "modbus_data_type": "float32",
            },
            {
                "name": "dev2_ch1",
                "device": 2,
                "modbus_slave_id": 96,
                "address": 96,
                "parameter": "rEAd",
                "protocol_format": "float32",
                "register_type": "holding_register",
                "modbus_address": 16,
                "modbus_data_type": "float32",
            },
        ]

        with self.assertRaisesRegex(ValueError, "duplicate modbus_slave_id 96"):
            self._load(payload)


if __name__ == "__main__":
    unittest.main()
