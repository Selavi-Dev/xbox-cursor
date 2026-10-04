"""Regression tests for bugs found in the controls audit."""

import unittest
from unittest.mock import MagicMock
from controller.mapper import InputMapper, WHEEL_DELTA
from controller.xinput import (
    GamepadState,
    XINPUT_GAMEPAD_A,
    XINPUT_GAMEPAD_BACK,
    XINPUT_GAMEPAD_START,
    XINPUT_GAMEPAD_DPAD_UP,
)


def frame(buttons=0, rt=0.0, ry=0.0, n=0):
    return GamepadState(n, buttons, 0.0, rt, 0.0, 0.0, 0.0, ry)


def make_mapper():
    config = {
        "mouse": {"base_speed": 22.0, "acceleration_exponent": 1.85, "deadzone": 0.18},
        "scroll": {"vertical_speed": 20.0, "horizontal_speed": 15.0, "deadzone": 0.22},
        "triggers": {"rt_left_click": True, "lt_precision_aim": True, "threshold": 0.3},
        "buttons": {
            "a": "left_click",
            "dpad_up": "volume_up",
            "start": "enter",
            "back": "show_desktop",
        },
        "features": {"toggle_combo_enabled": True, "toggle_hold_seconds": 1.2,
                     "rumble_feedback": False, "start_enabled": True},
    }
    win = MagicMock()
    m = InputMapper(config, MagicMock(), win)
    m.process_frame(frame(0), now=-2/120)
    m.process_frame(frame(0), now=-1/120)
    return m, win


class TestAuditRegressions(unittest.TestCase):
    def test_combo_does_not_fire_back_or_start_actions(self):
        m, win = make_mapper()
        t = 0.0
        m.process_frame(frame(XINPUT_GAMEPAD_BACK), now=t)              # Back first
        m.process_frame(frame(XINPUT_GAMEPAD_BACK | XINPUT_GAMEPAD_START), now=t + 0.1)
        m.process_frame(frame(XINPUT_GAMEPAD_BACK | XINPUT_GAMEPAD_START), now=t + 1.5)
        self.assertFalse(m.is_enabled)                                    # toggled
        m.process_frame(frame(XINPUT_GAMEPAD_START), now=t + 1.6)       # release Back
        m.process_frame(frame(0), now=t + 1.7)                           # release Start
        win.show_desktop.assert_not_called()
        win.key_press.assert_not_called()

    def test_back_tap_still_works(self):
        m, win = make_mapper()
        m.process_frame(frame(XINPUT_GAMEPAD_BACK), now=0.0)
        win.show_desktop.assert_not_called()  # fires on release, not press
        m.process_frame(frame(0), now=0.1)
        win.show_desktop.assert_called_once()

    def test_a_release_does_not_break_rt_drag(self):
        m, win = make_mapper()
        m.process_frame(frame(rt=1.0), now=0.00)                          # RT drag starts
        m.process_frame(frame(XINPUT_GAMEPAD_A, rt=1.0), now=0.01)
        m.process_frame(frame(rt=1.0), now=0.02)                          # A released
        win.left_up.assert_not_called()
        m.process_frame(frame(rt=0.0), now=0.03)                          # RT released
        win.left_up.assert_called_once()
        win.left_down.assert_called_once()

    def test_scroll_rate_is_sane(self):
        m, win = make_mapper()
        t = 0.0
        for _ in range(120):  # one second at 120 Hz, full tilt
            m.process_frame(frame(ry=1.0), now=t)
            t += 1 / 120
        total = sum(c.args[0] for c in win.scroll_vertical.call_args_list)
        notches = total / WHEEL_DELTA
        self.assertGreater(notches, 15)
        self.assertLess(notches, 25)  # previously ~540 notches/s

    def test_no_phantom_input_after_resume(self):
        m, win = make_mapper()
        m.toggle_enabled()                                                # pause
        m.process_frame(frame(rt=1.0), now=0.0)                           # RT pulled while paused
        m.toggle_enabled()                                                # resume, RT still held
        m.process_frame(frame(rt=1.0), now=0.01)
        win.left_down.assert_not_called()
        m.process_frame(frame(rt=0.0), now=0.02)
        m.process_frame(frame(rt=1.0), now=0.03)                          # fresh pull works
        win.left_down.assert_called_once()

    def test_dpad_volume_auto_repeat(self):
        m, win = make_mapper()
        t = 0.0
        while t < 1.0:
            m.process_frame(frame(XINPUT_GAMEPAD_DPAD_UP), now=t)
            t += 1 / 120
        # 1 initial + repeats every 80ms after a 400ms delay
        self.assertGreaterEqual(win.volume_up.call_count, 7)

    def test_gui_toggle_request_is_applied_on_poll_thread(self):
        m, _ = make_mapper()
        m.request_toggle()
        self.assertTrue(m.is_enabled)
        m.process_frame(frame(0), now=0.0)
        self.assertFalse(m.is_enabled)

    def test_radial_modifier_is_not_tapped_on_back_release(self):
        config = {
            "schemas": {
                "desktop": {
                    "mouse": {"base_speed": 5.0, "acceleration_exponent": 2.0, "deadzone": 0.2},
                    "scroll": {"vertical_speed": 4.0, "horizontal_speed": 3.0, "deadzone": 0.2},
                    "triggers": {"rt_left_click": True, "threshold": 0.3},
                    "buttons": {"back": "radial_menu_modifier", "start": "win_key"},
                }
            },
            "features": {
                "toggle_combo_enabled": True,
                "toggle_hold_seconds": 1.2,
                "rumble_feedback": False,
                "start_enabled": True,
            },
        }
        win = MagicMock()
        m = InputMapper(config, MagicMock(), win)
        m.process_frame(frame(0), now=-2 / 120)
        m.process_frame(frame(0), now=-1 / 120)
        m.process_frame(frame(XINPUT_GAMEPAD_BACK), now=0.0)
        m.process_frame(frame(0), now=0.1)
        # Modifier must not become a synthetic key/mouse action.
        win.key_press.assert_not_called()
        win.send_combo.assert_not_called()
        win.show_desktop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
