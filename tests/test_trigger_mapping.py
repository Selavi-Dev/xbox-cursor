"""Base Buttons LT/RT mapping vs LT/RT Shift chord layers."""

import json
import os
import unittest
from unittest.mock import MagicMock

from controller.mapper import InputMapper
from controller.xinput import GamepadState, XINPUT_GAMEPAD_A
from controller.win32_input import VK_RETURN


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


def frame(buttons=0, lt=0.0, rt=0.0):
    return GamepadState(0, buttons, lt, rt, 0.0, 0.0, 0.0, 0.0)


def make_mapper(config):
    config = json.loads(json.dumps(config))  # deep copy
    config.setdefault("features", {})["rumble_feedback"] = False
    win = MagicMock()
    m = InputMapper(config, MagicMock(), win)
    m.process_frame(frame(), now=-2 / 120)
    m.process_frame(frame(), now=-1 / 120)
    return m, win


class TestTriggerMapping(unittest.TestCase):
    def test_default_config_maps_lt_enter_and_rt_left_click(self):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
        m, win = make_mapper(config)

        # RT layer is non-empty → base RT is tap-on-release when no chord used
        m.process_frame(frame(rt=1.0), now=0.0)
        m.process_frame(frame(rt=0.0), now=0.05)
        win.left_down.assert_called()
        win.left_up.assert_called()

        win.reset_mock()
        # LT layer is non-empty → base LT is tap-on-release when no chord used
        m.process_frame(frame(lt=1.0), now=0.1)
        m.process_frame(frame(lt=0.0), now=0.15)
        win.key_press.assert_called_with(VK_RETURN)

    def test_base_rt_remap_changes_action(self):
        config = {
            "schemas": {
                "desktop": {
                    "mouse": {"base_speed": 5.0, "acceleration_exponent": 2.0, "deadzone": 0.2},
                    "scroll": {"vertical_speed": 4.0, "deadzone": 0.2},
                    "triggers": {"threshold": 0.3, "lt_precision_aim": False},
                    "buttons": {"rt": "middle_click", "lt": "enter"},
                    "lt_layer": {},
                    "rt_layer": {},
                }
            },
            "features": {"start_enabled": True},
        }
        m, win = make_mapper(config)
        m.process_frame(frame(rt=1.0), now=0.0)
        win.middle_down.assert_called_once()
        m.process_frame(frame(rt=0.0), now=0.05)
        win.middle_up.assert_called_once()
        win.left_down.assert_not_called()

    def test_explicit_empty_rt_is_unmapped_not_legacy_fallback(self):
        config = {
            "schemas": {
                "desktop": {
                    "mouse": {"base_speed": 5.0, "acceleration_exponent": 2.0, "deadzone": 0.2},
                    "scroll": {"vertical_speed": 4.0, "deadzone": 0.2},
                    "triggers": {
                        "threshold": 0.3,
                        "rt_left_click": True,
                        "lt_precision_aim": False,
                    },
                    "buttons": {"rt": "", "lt": ""},
                    "lt_layer": {},
                    "rt_layer": {},
                }
            },
            "features": {"start_enabled": True},
        }
        m, win = make_mapper(config)
        m.process_frame(frame(rt=1.0), now=0.0)
        m.process_frame(frame(rt=0.0), now=0.05)
        m.process_frame(frame(lt=1.0), now=0.1)
        m.process_frame(frame(lt=0.0), now=0.15)
        win.left_down.assert_not_called()
        win.key_press.assert_not_called()

    def test_absent_buttons_key_falls_back_to_triggers(self):
        config = {
            "schemas": {
                "desktop": {
                    "mouse": {"base_speed": 5.0, "acceleration_exponent": 2.0, "deadzone": 0.2},
                    "scroll": {"vertical_speed": 4.0, "deadzone": 0.2},
                    "triggers": {
                        "threshold": 0.3,
                        "rt_left_click": True,
                        "lt_action": "enter",
                        "lt_precision_aim": False,
                    },
                    "buttons": {},
                    "lt_layer": {},
                    "rt_layer": {},
                }
            },
            "features": {"start_enabled": True},
        }
        m, win = make_mapper(config)
        m.process_frame(frame(rt=1.0), now=0.0)
        win.left_down.assert_called_once()
        m.process_frame(frame(rt=0.0, lt=1.0), now=0.05)
        m.process_frame(frame(lt=0.0), now=0.1)
        win.key_press.assert_called_with(VK_RETURN)

    def test_lt_shift_chord_still_works(self):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
        m, win = make_mapper(config)
        # Hold LT then press A → copy (lt_layer), not base enter
        m.process_frame(frame(lt=1.0), now=0.0)
        m.process_frame(frame(XINPUT_GAMEPAD_A, lt=1.0), now=0.05)
        m.process_frame(frame(lt=1.0), now=0.1)
        m.process_frame(frame(lt=0.0), now=0.15)
        win.send_combo.assert_any_call([0x11, 0x43])  # Ctrl+C
        win.key_press.assert_not_called()


if __name__ == "__main__":
    unittest.main()
