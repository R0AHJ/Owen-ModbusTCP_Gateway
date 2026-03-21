import unittest
from unittest.mock import patch

from owen_gateway.cli import _prompt_channel_checklist


class CliTests(unittest.TestCase):
    def test_prompt_channel_checklist_toggles_and_saves(self) -> None:
        with patch("builtins.input", side_effect=["7", "8", "s"]):
            result = _prompt_channel_checklist([1, 7])

        self.assertEqual(result, [1, 8])

    def test_prompt_channel_checklist_can_cancel(self) -> None:
        with patch("builtins.input", side_effect=["q"]):
            result = _prompt_channel_checklist([1, 2])

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
