"""Windows SendInput and Cursor Management API wrapper using ctypes."""

import ctypes
import time
from ctypes import wintypes
from typing import Tuple, List

# Win32 Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

# Virtual Screen Metrics
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# Virtual Key Codes
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_LWIN = 0x5B
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_BROWSER_BACK = 0xA6
VK_BROWSER_FORWARD = 0xA7
VK_BROWSER_REFRESH = 0xA8

# Keys that require KEYEVENTF_EXTENDEDKEY to be interpreted correctly
EXTENDED_KEYS = {VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN, VK_LWIN}

PUL = ctypes.POINTER(ctypes.c_ulong)

_dpi_awareness_applied = False


def enable_dpi_awareness() -> None:
    """Opt the process into per-monitor DPI awareness.

    Without this, Windows virtualizes cursor coordinates and screen metrics for
    scaled monitors (e.g. a 1920x1080 laptop panel at 125% reports as 1536x864),
    which causes cursor clamping errors and jumps on mixed-DPI multi-monitor setups.
    Must run before any window (including Tk) is created.
    """
    global _dpi_awareness_applied
    if _dpi_awareness_applied:
        return
    _dpi_awareness_applied = True
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == -4 (Windows 10 1703+)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", INPUT_UNION),
    ]


class Win32Input:
    """Provides high performance cursor positioning and synthetic input for Windows."""

    # Re-query virtual desktop often enough to pick up hot-plugged monitors /
    # arrangement changes without calling GetSystemMetrics every poll tick.
    _BOUNDS_REFRESH_INTERVAL_S = 1.0

    def __init__(self):
        enable_dpi_awareness()

        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
        self._user32.SendInput.restype = ctypes.c_uint
        self._user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        self._user32.GetCursorPos.restype = wintypes.BOOL
        self._user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self._user32.SetCursorPos.restype = wintypes.BOOL

        # Multi-monitor bounds
        self._bounds_checked_at = 0.0
        self.update_screen_bounds(force=True)

        # Sub-pixel accumulator
        cur_pos = self.get_cursor_pos()
        self._pos_x = float(cur_pos[0])
        self._pos_y = float(cur_pos[1])
        self._last_raw_x = cur_pos[0]
        self._last_raw_y = cur_pos[1]

        # Track button states
        self._left_down = False
        self._right_down = False
        self._middle_down = False

    def update_screen_bounds(self, force: bool = False):
        """Query multi-monitor virtual-desktop bounding box."""
        now = time.perf_counter()
        if not force and (now - self._bounds_checked_at) < self._BOUNDS_REFRESH_INTERVAL_S:
            return
        self._bounds_checked_at = now
        self.vx = self._user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        self.vy = self._user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        self.vw = self._user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        self.vh = self._user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        # Guard against transient 0x0 metrics during display reconfiguration.
        if self.vw <= 0 or self.vh <= 0:
            self.vx, self.vy = 0, 0
            self.vw = self._user32.GetSystemMetrics(0) or 1920  # SM_CXSCREEN
            self.vh = self._user32.GetSystemMetrics(1) or 1080  # SM_CYSCREEN
        self.max_x = self.vx + self.vw - 1
        self.max_y = self.vy + self.vh - 1

    def get_cursor_pos(self) -> Tuple[int, int]:
        pt = wintypes.POINT()
        self._user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def move_cursor_delta(self, dx: float, dy: float):
        """Apply fractional pixel delta with sub-pixel accumulator."""
        self.update_screen_bounds()
        cur_x, cur_y = self.get_cursor_pos()

        # If user moved physical mouse or cursor jumped externally, resync.
        # Keep this threshold modest so a failed cross-monitor SetCursorPos
        # (clipped to an edge) cannot permanently pin the accumulator.
        if abs(cur_x - self._last_raw_x) > 3 or abs(cur_y - self._last_raw_y) > 3:
            self._pos_x = float(cur_x)
            self._pos_y = float(cur_y)

        self._pos_x += dx
        self._pos_y += dy

        # Clamp within the full virtual desktop (all monitors), not primary only.
        self._pos_x = max(float(self.vx), min(float(self.max_x), self._pos_x))
        self._pos_y = max(float(self.vy), min(float(self.max_y), self._pos_y))

        new_x = int(round(self._pos_x))
        new_y = int(round(self._pos_y))

        if new_x != cur_x or new_y != cur_y:
            self._user32.SetCursorPos(new_x, new_y)
            # Read back — Windows may clip to a real monitor edge inside the
            # virtual rect (non-rectangular arrangements). Only snap the
            # accumulator when clipped so sub-pixel motion stays smooth.
            actual_x, actual_y = self.get_cursor_pos()
            self._last_raw_x = actual_x
            self._last_raw_y = actual_y
            if actual_x != new_x or actual_y != new_y:
                self._pos_x = float(actual_x)
                self._pos_y = float(actual_y)

    # ------------------------------------------------------------------ low level
    def _send(self, inputs: List[INPUT]):
        """Send a batch of inputs atomically in a single SendInput call (no sleeps
        on the polling thread)."""
        if not inputs:
            return
        arr = (INPUT * len(inputs))(*inputs)
        self._user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    @staticmethod
    def _mouse_input(flags: int, data: int = 0) -> INPUT:
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.u.mi.mouseData = ctypes.c_ulong(data & 0xFFFFFFFF).value
        inp.u.mi.dwFlags = flags
        return inp

    @staticmethod
    def _key_input(vk: int, is_up: bool) -> INPUT:
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki.wVk = vk
        flags = KEYEVENTF_KEYUP if is_up else 0
        if vk in EXTENDED_KEYS:
            flags |= KEYEVENTF_EXTENDEDKEY
        inp.u.ki.dwFlags = flags
        return inp

    # ------------------------------------------------------------------ mouse
    def left_down(self):
        if not self._left_down:
            self._send([self._mouse_input(MOUSEEVENTF_LEFTDOWN)])
            self._left_down = True

    def left_up(self):
        if self._left_down:
            self._send([self._mouse_input(MOUSEEVENTF_LEFTUP)])
            self._left_down = False

    def right_down(self):
        if not self._right_down:
            self._send([self._mouse_input(MOUSEEVENTF_RIGHTDOWN)])
            self._right_down = True

    def right_up(self):
        if self._right_down:
            self._send([self._mouse_input(MOUSEEVENTF_RIGHTUP)])
            self._right_down = False

    def middle_down(self):
        if not self._middle_down:
            self._send([self._mouse_input(MOUSEEVENTF_MIDDLEDOWN)])
            self._middle_down = True

    def middle_up(self):
        if self._middle_down:
            self._send([self._mouse_input(MOUSEEVENTF_MIDDLEUP)])
            self._middle_down = False

    def scroll_vertical(self, amount: int):
        """Scroll vertical wheel. Positive amount = scroll up, negative = scroll down.
        WHEEL_DELTA (120) is one notch; smaller values are high-resolution scroll."""
        if amount != 0:
            self._send([self._mouse_input(MOUSEEVENTF_WHEEL, int(amount))])

    def scroll_horizontal(self, amount: int):
        """Scroll horizontal wheel. Positive = right, negative = left."""
        if amount != 0:
            self._send([self._mouse_input(MOUSEEVENTF_HWHEEL, int(amount))])

    # ------------------------------------------------------------------ keyboard
    def key_down(self, vk: int):
        self._send([self._key_input(vk, False)])

    def key_up(self, vk: int):
        self._send([self._key_input(vk, True)])

    def key_press(self, vk: int):
        self._send([self._key_input(vk, False), self._key_input(vk, True)])

    def send_combo(self, vks: List[int]):
        """Presses keys down in sequence, then releases in reverse, as one batch."""
        downs = [self._key_input(vk, False) for vk in vks]
        ups = [self._key_input(vk, True) for vk in reversed(vks)]
        self._send(downs + ups)

    # Convenience System Actions
    def volume_up(self):
        self.key_press(VK_VOLUME_UP)

    def volume_down(self):
        self.key_press(VK_VOLUME_DOWN)

    def volume_mute(self):
        self.key_press(VK_VOLUME_MUTE)

    def media_play_pause(self):
        self.key_press(VK_MEDIA_PLAY_PAUSE)

    def media_next(self):
        self.key_press(VK_MEDIA_NEXT_TRACK)

    def media_prev(self):
        self.key_press(VK_MEDIA_PREV_TRACK)

    def browser_back(self):
        self.key_press(VK_BROWSER_BACK)

    def browser_forward(self):
        self.key_press(VK_BROWSER_FORWARD)

    def show_desktop(self):
        # Win + D
        self.send_combo([VK_LWIN, 0x44])

    def task_view(self):
        # Win + Tab
        self.send_combo([VK_LWIN, VK_TAB])

    def toggle_osk(self):
        """Toggle the Windows On-Screen Keyboard (Win + Ctrl + O)."""
        self.send_combo([VK_LWIN, VK_CONTROL, 0x4F])  # 0x4F is 'O'

    def release_all_mouse_buttons(self):
        """Release any stuck down mouse buttons."""
        self.left_up()
        self.right_up()
        self.middle_up()
