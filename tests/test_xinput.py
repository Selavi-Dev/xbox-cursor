"""Tests for the low-level XInput driver."""

import unittest
from controller.xinput import XInputDriver, GamepadState


class TestXInputDriver(unittest.TestCase):
    def setUp(self):
        self.driver = XInputDriver()

    def test_dll_loaded(self):
        self.assertIsNotNone(self.driver.dll_name)
        self.assertIn("xinput", self.driver.dll_name.lower())

    def test_controller_detection(self):
        controller_id = self.driver.find_connected_controller()
        # The user has an Xbox controller plugged in at index 0
        self.assertIsNotNone(controller_id)
        self.assertIn(controller_id, range(4))

    def test_get_state(self):
        controller_id = self.driver.find_connected_controller()
        if controller_id is not None:
            state = self.driver.get_state(controller_id)
            self.assertIsInstance(state, GamepadState)
            self.assertGreaterEqual(state.left_trigger, 0.0)
            self.assertLessEqual(state.left_trigger, 1.0)
            self.assertGreaterEqual(state.right_trigger, 0.0)
            self.assertLessEqual(state.right_trigger, 1.0)
            self.assertGreaterEqual(state.thumb_lx, -1.0)
            self.assertLessEqual(state.thumb_lx, 1.0)
            self.assertGreaterEqual(state.thumb_ly, -1.0)
            self.assertLessEqual(state.thumb_ly, 1.0)


if __name__ == "__main__":
    unittest.main()
