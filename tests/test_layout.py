"""Tests for the approved default button layout (loaded from config.json)."""

import json
import os
import unittest
from unittest.mock import MagicMock
from controller.mapper import InputMapper
from controller.xinput import (
    GamepadState,
    XINPUT_GAMEPAD_A, XINPUT_GAMEPAD_B, XINPUT_GAMEPAD_X,
    XINPUT_GAMEPAD_BACK, XINPUT_GAMEPAD_START,
    XINPUT_GAMEPAD_DPAD_UP, XINPUT_GAMEPAD_DPAD_RIGHT,
    XINPUT_GAMEPAD_LEFT_THUMB, XINPUT_GAMEPAD_RIGHT_THUMB,
)
from controller.win32_input import VK_ESCAPE, VK_LWIN, VK_UP, VK_MENU, VK_TAB, VK_RETURN, VK_LEFT, VK_RIGHT

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


def frame(buttons=0, lx=0.0):
    return GamepadState(0, buttons, 0.0, 0.0, lx, 0.0, 0.0, 0.0)


class TestDefaultLayout(unittest.TestCase):
    def setUp(self):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
        config["features"]["rumble_feedback"] = False
        self.win = MagicMock()
        self.m = InputMapper(config, MagicMock(), self.win)
        self.t = 0.0
        self.m.process_frame(frame(0), now=-2/120)
        self.m.process_frame(frame(0), now=-1/120)

    def tap(self, buttons):
        self.m.process_frame(frame(buttons), now=self.t)
        self.m.process_frame(frame(0), now=self.t + 0.05)
        self.t += 0.1

    def test_face_buttons(self):
        self.tap(XINPUT_GAMEPAD_A)
        self.win.left_down.assert_called_once()
        self.tap(XINPUT_GAMEPAD_X)
        self.win.key_press.assert_called_with(VK_RETURN)
        self.tap(XINPUT_GAMEPAD_B)
        self.win.right_down.assert_called_once()

    def test_stick_clicks(self):
        self.tap(XINPUT_GAMEPAD_LEFT_THUMB)
        self.win.send_combo.assert_any_call([0x11, VK_LWIN, VK_LEFT])
        self.tap(XINPUT_GAMEPAD_RIGHT_THUMB)
        self.win.send_combo.assert_any_call([0x11, VK_LWIN, VK_RIGHT])

    def test_dpad_is_arrows(self):
        self.tap(XINPUT_GAMEPAD_DPAD_UP)
        self.win.key_press.assert_called_with(VK_UP)
        self.win.volume_up.assert_not_called()

    def test_start_and_back_taps(self):
        self.tap(XINPUT_GAMEPAD_START)
        self.win.key_press.assert_called_with(VK_LWIN)
        self.tap(XINPUT_GAMEPAD_BACK)
        self.win.send_combo.assert_not_called()

    def test_back_layer_media_and_no_alt_tab(self):
        B, U, R = XINPUT_GAMEPAD_BACK, XINPUT_GAMEPAD_DPAD_UP, XINPUT_GAMEPAD_DPAD_RIGHT
        self.m.process_frame(frame(B), now=0.0)
        self.m.process_frame(frame(B | U), now=0.05)
        self.m.process_frame(frame(B), now=0.10)
        self.m.process_frame(frame(B | R), now=0.15)
        self.m.process_frame(frame(B), now=0.20)
        self.m.process_frame(frame(0), now=0.25)
        self.win.volume_up.assert_called_once()
        self.win.media_next.assert_called_once()
        self.win.send_combo.assert_not_called()   # Back was a modifier, no Alt+Tab
        self.win.key_press.assert_not_called()    # no arrow keys either

    def test_auto_turbo_ramps_at_full_tilt(self):
        def dx_at(t):
            self.win.move_cursor_delta.reset_mock()
            self.m.process_frame(frame(lx=1.0), now=t)
            return self.win.move_cursor_delta.call_args.args[0]

        t, base = 0.0, None
        while t < 1.5:
            d = dx_at(t)
            base = d if base is None else base
            t += 1 / 120
        self.assertAlmostEqual(d / base, 2.3, places=1)

    def test_no_turbo_below_full_tilt(self):
        t, first = 0.0, None
        while t < 1.5:
            self.m.process_frame(frame(lx=0.8), now=t)
            d = self.win.move_cursor_delta.call_args.args[0]
            first = d if first is None else first
            t += 1 / 120
        self.assertAlmostEqual(d, first, places=5)


if __name__ == "__main__":
    unittest.main()
