"""High-level desktop actions executor mapped from controller inputs."""

from typing import Callable, Dict, Set, Tuple
from .win32_input import (
    Win32Input,
    VK_RETURN,
    VK_ESCAPE,
    VK_TAB,
    VK_MENU,
    VK_LWIN,
    VK_BACK,
    VK_UP,
    VK_DOWN,
    VK_LEFT,
    VK_RIGHT,
)


class ActionManager:
    """Dispatches button actions.

    Holdable actions (mouse buttons) are reference-counted per input source, so two
    inputs bound to the same action (e.g. A and RT both = left click) don't cancel
    each other: releasing A while dragging with RT will not drop the drag.
    """

    def __init__(self, win_input: Win32Input):
        self.win = win_input

        self._hold_actions: Dict[str, Tuple[Callable[[], None], Callable[[], None]]] = {
            "left_click": (win_input.left_down, win_input.left_up),
            "right_click": (win_input.right_down, win_input.right_up),
            "middle_click": (win_input.middle_down, win_input.middle_up),
        }
        
        # Standard keys for gaming schema
        standard_keys = {
            "w": 0x57, "a": 0x41, "s": 0x53, "d": 0x44,
            "q": 0x51, "e": 0x45, "r": 0x52, "f": 0x46, "c": 0x43,
            "space": 0x20, "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
            "esc": VK_ESCAPE, "tab": VK_TAB, "enter": VK_RETURN,
            "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34
        }
        for k_name, vk in standard_keys.items():
            # lambda v=vk preserves the local variable
            self._hold_actions[f"key_{k_name}"] = (
                lambda v=vk: win_input.key_down(v),
                lambda v=vk: win_input.key_up(v)
            )

        self._holders: Dict[str, Set[str]] = {}

        w = win_input
        self._tap_actions: Dict[str, Callable[[], None]] = {
            "volume_up": w.volume_up,
            "volume_down": w.volume_down,
            "volume_mute": w.volume_mute,
            "media_next": w.media_next,
            "media_prev": w.media_prev,
            "media_play_pause": w.media_play_pause,
            "browser_back": w.browser_back,
            "browser_forward": w.browser_forward,
            "browser_next_tab": lambda: w.send_combo([VK_LWIN, VK_TAB]) if False else w.send_combo([0x11, VK_TAB]), # Ctrl+Tab
            "browser_prev_tab": lambda: w.send_combo([0x11, 0x10, VK_TAB]), # Ctrl+Shift+Tab
            "show_desktop": w.show_desktop,
            "task_view": w.task_view,
            "toggle_osk": w.toggle_osk,
            "alt_tab": lambda: w.send_combo([VK_MENU, VK_TAB]),
            "enter": lambda: w.key_press(VK_RETURN),
            "escape": lambda: w.key_press(VK_ESCAPE),
            "backspace": lambda: w.key_press(VK_BACK),
            "win_key": lambda: w.key_press(VK_LWIN),
            "arrow_up": lambda: w.key_press(VK_UP),
            "arrow_down": lambda: w.key_press(VK_DOWN),
            "arrow_left": lambda: w.key_press(VK_LEFT),
            "arrow_right": lambda: w.key_press(VK_RIGHT),
            "dictation_toggle": self._dictation_toggle,
            "copy": lambda: w.send_combo([0x11, 0x43]),
            "paste": lambda: w.send_combo([0x11, 0x56]),
            "undo": lambda: w.send_combo([0x11, 0x5A]),
            "save": lambda: w.send_combo([0x11, 0x53]),
            "new_tab": lambda: w.send_combo([0x11, 0x54]),
            "close_tab": lambda: w.send_combo([0x11, 0x57]),
            "close_window": lambda: w.send_combo([VK_MENU, 0x73]),
            "desktop_left": lambda: w.send_combo([0x11, VK_LWIN, VK_LEFT]),
            "desktop_right": lambda: w.send_combo([0x11, VK_LWIN, VK_RIGHT]),
        }

    def _dictation_toggle(self):
        import time
        self.win.left_down()
        self.win.left_up()
        time.sleep(0.05)
        self.win.send_combo([VK_LWIN, 0x48])

    @property
    def known_actions(self) -> Set[str]:
        return set(self._hold_actions) | set(self._tap_actions)

    def execute_press(self, action_name: str, source: str = "default"):
        """Called when a mapped input is pressed (or auto-repeats)."""
        if action_name in self._hold_actions:
            holders = self._holders.setdefault(action_name, set())
            if not holders:
                self._hold_actions[action_name][0]()
            holders.add(source)
            return
        fn = self._tap_actions.get(action_name)
        if fn:
            fn()

    def execute_release(self, action_name: str, source: str = "default"):
        """Called when a mapped input is released."""
        holders = self._holders.get(action_name)
        if not holders or source not in holders:
            return
        holders.discard(source)
        if not holders:
            self._hold_actions[action_name][1]()

    def tap(self, action_name: str, source: str = "default"):
        """Press and immediately release."""
        self.execute_press(action_name, source)
        self.execute_release(action_name, source)

    def release_all(self):
        """Drop every held mouse button regardless of source."""
        self._holders.clear()
        self.win.release_all_mouse_buttons()
