"""Unit tests for InputMapper math, deadzones, curves, and logic."""

import unittest
from unittest.mock import MagicMock
from controller.mapper import InputMapper
from controller.xinput import GamepadState


class TestInputMapper(unittest.TestCase):
    def setUp(self):
        self.mock_driver = MagicMock()
        self.mock_win = MagicMock()
        self.config = {
            "mouse": {
                "base_speed": 20.0,
                "acceleration_exponent": 2.0,
                "deadzone": 0.2,
                "turbo_multiplier": 2.0,
                "precision_multiplier": 0.5,
            },
            "scroll": {
                "vertical_speed": 4.0,
                "horizontal_speed": 3.0,
                "deadzone": 0.2,
                "horizontal_enabled": True,
            },
            "triggers": {
                "rt_left_click": True,
                "lt_precision_aim": True,
                "threshold": 0.3,
            },
            "buttons": {
                "a": "left_click",
                "b": "right_click",
                "dpad_up": "volume_up",
            },
            "features": {
                "toggle_combo_enabled": True,
                "toggle_hold_seconds": 0.5,
                "rumble_feedback": True,
                "start_enabled": True,
            },
        }
        self.mapper = InputMapper(self.config, self.mock_driver, self.mock_win)

    def test_deadzone_below_threshold(self):
        # Stick within deadzone (0.1 < 0.2)
        cx, cy = self.mapper._calc_radial_deadzone_and_curve(0.1, 0.1, 0.2, 2.0)
        self.assertEqual(cx, 0.0)
        self.assertEqual(cy, 0.0)

    def test_deadzone_above_threshold(self):
        # Stick at magnitude 0.6 (> 0.2)
        cx, cy = self.mapper._calc_radial_deadzone_and_curve(0.6, 0.0, 0.2, 2.0)
        self.assertGreater(cx, 0.0)
        self.assertEqual(cy, 0.0)

    def test_full_deflection(self):
        # Stick at 1.0 magnitude should output 1.0 magnitude
        cx, cy = self.mapper._calc_radial_deadzone_and_curve(1.0, 0.0, 0.2, 2.0)
        self.assertAlmostEqual(cx, 1.0, places=5)
        self.assertEqual(cy, 0.0)

    def test_button_press_and_release(self):
        # Frame 1: Press A
        state1 = GamepadState(
            packet_number=1,
            buttons=0x1000,  # A button
            left_trigger=0.0,
            right_trigger=0.0,
            thumb_lx=0.0,
            thumb_ly=0.0,
            thumb_rx=0.0,
            thumb_ry=0.0,
        )
        self.mapper.process_frame(state1)
        self.mock_win.left_down.assert_called_once()

        # Frame 2: Release A
        state2 = GamepadState(
            packet_number=2,
            buttons=0x0000,
            left_trigger=0.0,
            right_trigger=0.0,
            thumb_lx=0.0,
            thumb_ly=0.0,
            thumb_rx=0.0,
            thumb_ry=0.0,
        )
        self.mapper.process_frame(state2)
        self.mock_win.left_up.assert_called_once()

    def test_toggle_enabled(self):
        self.assertTrue(self.mapper.is_enabled)
        res = self.mapper.toggle_enabled()
        self.assertFalse(res)
        self.assertFalse(self.mapper.is_enabled)
        self.mock_win.release_all_mouse_buttons.assert_called_once()


if __name__ == "__main__":
    unittest.main()
