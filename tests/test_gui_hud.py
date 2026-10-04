"""Regression tests for HUD refresh with optional paddle widgets."""

import unittest
from unittest.mock import MagicMock

from ui.gui import ControllerAppGUI


class TestHudPaddleGuards(unittest.TestCase):
    def test_update_btn_visual_skips_missing_paddle_keys(self):
        gui = object.__new__(ControllerAppGUI)
        gui.hud = {
            "btn_a": 1,
            "txt_a": 2,
            "line_a": 3,
            "lbl_a": 4,
        }
        gui.cv = MagicMock()

        # Default config does not create paddle HUD items — must not raise.
        ControllerAppGUI._update_btn_visual(gui, "agl", True)
        ControllerAppGUI._update_btn_visual(gui, "agr", False)
        gui.cv.itemconfig.assert_not_called()

        ControllerAppGUI._update_btn_visual(gui, "a", True)
        self.assertTrue(gui.cv.itemconfig.called)


if __name__ == "__main__":
    unittest.main()
