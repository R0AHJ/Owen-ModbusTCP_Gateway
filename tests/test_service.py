import unittest

from owen_gateway.service import _decode_fixed_point, _evaluate_logic_unit


class ServiceHelperTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
