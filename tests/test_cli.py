import unittest
from unittest.mock import patch

from owen_gateway.cli import _prompt_channel_checklist, _prompt_serial_port_choice


class CliTests(unittest.TestCase):
    def test_prompt_channel_checklist_toggles_and_saves(self) -> None:
        with patch("builtins.input", side_effect=["7", "8", "s"]):
            result = _prompt_channel_checklist([1, 7])

        self.assertEqual(result, [1, 8])

    def test_prompt_channel_checklist_can_cancel(self) -> None:
        with patch("builtins.input", side_effect=["q"]):
            result = _prompt_channel_checklist([1, 2])

        self.assertIsNone(result)

    def test_prompt_serial_port_choice_selects_detected_port(self) -> None:
        ports = [
            {"path": "/dev/serial/by-id/usb-A", "target": "/dev/ttyACM0", "source": "by-id"},
            {"path": "/dev/serial/by-id/usb-B", "target": "/dev/ttyACM1", "source": "by-id"},
        ]
        with patch("owen_gateway.cli.list_serial_ports", return_value=ports), patch(
            "builtins.input", side_effect=["2"]
        ):
            result = _prompt_serial_port_choice("/dev/serial/by-id/usb-A")

        self.assertEqual(result, "/dev/serial/by-id/usb-B")

    def test_prompt_serial_port_choice_allows_manual_entry(self) -> None:
        with patch("owen_gateway.cli.list_serial_ports", return_value=[]), patch(
            "builtins.input", side_effect=["m", "/dev/owen-line1"]
        ):
            result = _prompt_serial_port_choice()

        self.assertEqual(result, "/dev/owen-line1")


if __name__ == "__main__":
    unittest.main()
