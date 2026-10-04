"""Tests for the low-level XInput driver."""

import unittest
from controller.xinput import XInputDriver, GamepadState


def _connected_controller_index():
    try:
        return XInputDriver().find_connected_controller()
    except Exception:
        return None


@unittest.skipUnless(
    _connected_controller_index() is not None,
    "No Xbox controller connected (hardware test)",
)
class TestXInputDriver(unittest.TestCase):
    def setUp(self):
        self.driver = XInputDriver()

    def test_dll_loaded(self):
        self.assertIsNotNone(self.driver.dll_name)
        self.assertIn("xinput", self.driver.dll_name.lower())

    def test_controller_detection(self):
        controller_id = self.driver.find_connected_controller()
        self.assertIsNotNone(controller_id)
        self.assertIn(controller_id, range(4))

    def test_get_state(self):
        controller_id = self.driver.find_connected_controller()
        self.assertIsNotNone(controller_id)
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


class TestXInputDriverLoad(unittest.TestCase):
    """Runs without a physical controller."""

    def test_dll_loads_without_pad(self):
        driver = XInputDriver()
        self.assertIsNotNone(driver.dll_name)
        self.assertIn("xinput", driver.dll_name.lower())


if __name__ == "__main__":
    unittest.main()
