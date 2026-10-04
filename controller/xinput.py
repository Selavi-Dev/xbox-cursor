"""Low-level Windows XInput driver using ctypes with zero external dependencies."""

import ctypes
import threading
import time
from typing import Optional, NamedTuple

_wgi_gamepads = []
try:
    from winrt.windows.gaming.input import Gamepad
    def _on_gamepad_added(sender, args):
        _wgi_gamepads.append(args)
    Gamepad.add_gamepad_added(_on_gamepad_added)
except ImportError:
    Gamepad = None

def get_wgi_paddles() -> int:
    if not Gamepad: return 0
    pads = list(Gamepad.gamepads)
    if not pads and not _wgi_gamepads:
        return 0
    pad = pads[0] if pads else _wgi_gamepads[0]
    try:
        b = pad.get_current_reading().buttons
        res = 0
        if b & 16384: res |= 0x10000
        if b & 32768: res |= 0x20000
        if b & 65536: res |= 0x40000
        if b & 131072: res |= 0x80000
        return res
    except Exception:
        return 0


# Button Flags
XINPUT_GAMEPAD_DPAD_UP = 0x0001
XINPUT_GAMEPAD_DPAD_DOWN = 0x0002
XINPUT_GAMEPAD_DPAD_LEFT = 0x0004
XINPUT_GAMEPAD_DPAD_RIGHT = 0x0008
XINPUT_GAMEPAD_START = 0x0010
XINPUT_GAMEPAD_BACK = 0x0020
XINPUT_GAMEPAD_LEFT_THUMB = 0x0040
XINPUT_GAMEPAD_RIGHT_THUMB = 0x0080
XINPUT_GAMEPAD_LEFT_SHOULDER = 0x0100
XINPUT_GAMEPAD_RIGHT_SHOULDER = 0x0200
XINPUT_GAMEPAD_A = 0x1000
XINPUT_GAMEPAD_B = 0x2000
XINPUT_GAMEPAD_X = 0x4000
XINPUT_GAMEPAD_Y = 0x8000
XINPUT_GAMEPAD_PADDLE1 = 0x10000
XINPUT_GAMEPAD_PADDLE2 = 0x20000
XINPUT_GAMEPAD_PADDLE3 = 0x40000
XINPUT_GAMEPAD_PADDLE4 = 0x80000

# Error Codes
ERROR_SUCCESS = 0
ERROR_DEVICE_NOT_CONNECTED = 1167


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.c_ulong),
        ("Gamepad", XINPUT_GAMEPAD),
    ]


class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = [
        ("wLeftMotorSpeed", ctypes.c_ushort),
        ("wRightMotorSpeed", ctypes.c_ushort),
    ]


class GamepadState(NamedTuple):
    packet_number: int
    buttons: int
    left_trigger: float   # 0.0 to 1.0
    right_trigger: float  # 0.0 to 1.0
    thumb_lx: float       # -1.0 to 1.0
    thumb_ly: float       # -1.0 to 1.0
    thumb_rx: float       # -1.0 to 1.0
    thumb_ry: float       # -1.0 to 1.0

    # Convenient Button Accessors
    @property
    def a(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_A)

    @property
    def b(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_B)

    @property
    def x(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_X)

    @property
    def y(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_Y)

    @property
    def dpad_up(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_DPAD_UP)

    @property
    def dpad_down(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_DPAD_DOWN)

    @property
    def dpad_left(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_DPAD_LEFT)

    @property
    def dpad_right(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_DPAD_RIGHT)

    @property
    def start(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_START)

    @property
    def back(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_BACK)

    @property
    def left_shoulder(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_LEFT_SHOULDER)

    @property
    def right_shoulder(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_RIGHT_SHOULDER)

    @property
    def left_thumb_click(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_LEFT_THUMB)

    @property
    def right_thumb_click(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_RIGHT_THUMB)

    @property
    def paddle1(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_PADDLE1)

    @property
    def paddle2(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_PADDLE2)

    @property
    def paddle3(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_PADDLE3)

    @property
    def paddle4(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_PADDLE4)

    @property
    def agl(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_PADDLE1)

    @property
    def agr(self) -> bool:
        return bool(self.buttons & XINPUT_GAMEPAD_PADDLE2)


class XInputDriver:
    """Manages communication with Windows XInput DLLs."""

    def __init__(self):
        self._dll = None
        self._dll_name = None
        self._init_dll()

    def _init_dll(self):
        dll_candidates = ["xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"]
        for name in dll_candidates:
            try:
                dll = ctypes.WinDLL(name)
                # Configure XInputGetState
                dll.XInputGetState.argtypes = [ctypes.c_ulong, ctypes.POINTER(XINPUT_STATE)]
                dll.XInputGetState.restype = ctypes.c_ulong
                # Configure XInputSetState
                dll.XInputSetState.argtypes = [ctypes.c_ulong, ctypes.POINTER(XINPUT_VIBRATION)]
                dll.XInputSetState.restype = ctypes.c_ulong

                self._dll = dll
                self._dll_name = name
                break
            except Exception:
                continue

        if not self._dll:
            raise RuntimeError("Could not load any Windows XInput library (xinput1_4, xinput1_3, xinput9_1_0).")

    @property
    def dll_name(self) -> str:
        return self._dll_name

    def is_connected(self, user_index: int = 0) -> bool:
        state = XINPUT_STATE()
        res = self._dll.XInputGetState(user_index, ctypes.byref(state))
        return res == ERROR_SUCCESS

    def find_connected_controller(self) -> Optional[int]:
        """Find the index (0-3) of the first connected controller."""
        for i in range(4):
            if self.is_connected(i):
                return i
        return None

    def get_state(self, user_index: int = 0) -> Optional[GamepadState]:
        """Poll the current state of controller at user_index."""
        raw_state = XINPUT_STATE()
        res = self._dll.XInputGetState(user_index, ctypes.byref(raw_state))
        if res != ERROR_SUCCESS:
            return None

        pad = raw_state.Gamepad

        # Normalize Triggers (0-255 -> 0.0 to 1.0)
        lt = pad.bLeftTrigger / 255.0
        rt = pad.bRightTrigger / 255.0

        # Normalize Thumbsticks (-32768..32767 -> -1.0 to 1.0)
        lx = pad.sThumbLX / 32768.0 if pad.sThumbLX < 0 else pad.sThumbLX / 32767.0
        ly = pad.sThumbLY / 32768.0 if pad.sThumbLY < 0 else pad.sThumbLY / 32767.0
        rx = pad.sThumbRX / 32768.0 if pad.sThumbRX < 0 else pad.sThumbRX / 32767.0
        ry = pad.sThumbRY / 32768.0 if pad.sThumbRY < 0 else pad.sThumbRY / 32767.0

        return GamepadState(
            packet_number=raw_state.dwPacketNumber,
            buttons=pad.wButtons | get_wgi_paddles(),
            left_trigger=lt,
            right_trigger=rt,
            thumb_lx=max(-1.0, min(1.0, lx)),
            thumb_ly=max(-1.0, min(1.0, ly)),
            thumb_rx=max(-1.0, min(1.0, rx)),
            thumb_ry=max(-1.0, min(1.0, ry)),
        )

    def set_vibration(self, user_index: int = 0, left_motor: float = 0.0, right_motor: float = 0.0) -> bool:
        """Set low-frequency (left) and high-frequency (right) rumble motors (0.0 to 1.0)."""
        left_val = int(max(0.0, min(1.0, left_motor)) * 65535)
        right_val = int(max(0.0, min(1.0, right_motor)) * 65535)
        vib = XINPUT_VIBRATION(left_val, right_val)
        res = self._dll.XInputSetState(user_index, ctypes.byref(vib))
        return res == ERROR_SUCCESS

    def pulse_vibration(
        self,
        user_index: int = 0,
        left_motor: float = 0.5,
        right_motor: float = 0.5,
        duration: float = 0.15,
        pattern: Optional[list] = None
    ):
        """Asynchronously triggers vibration pulses without blocking execution."""
        def _worker():
            try:
                if pattern:
                    # pattern format: [(left, right, duration_s), ...]
                    for l, r, d in pattern:
                        self.set_vibration(user_index, l, r)
                        time.sleep(d)
                    self.set_vibration(user_index, 0.0, 0.0)
                else:
                    self.set_vibration(user_index, left_motor, right_motor)
                    time.sleep(duration)
                    self.set_vibration(user_index, 0.0, 0.0)
            except Exception:
                pass

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
