"""Input mapper that translates raw controller telemetry into smooth desktop movements and actions."""

import math
import time
from typing import Dict, Any, Optional, Callable
from .xinput import GamepadState, XInputDriver
from .win32_input import Win32Input
from .actions import ActionManager

# Speeds in config are expressed per tick at this reference rate; motion is scaled
# by the real frame time so speed doesn't change with poll rate or timer jitter.
REFERENCE_HZ = 120.0
MAX_FRAME_DT = 0.05

WHEEL_DELTA = 120  # one physical wheel notch
WHEEL_CHUNK = 40   # emit high-resolution 1/3-notch steps for smooth scrolling

REPEAT_DELAY_S = 0.40
REPEAT_INTERVAL_S = 0.08
REPEATABLE_ACTIONS = {
    "volume_up", "volume_down",
    "arrow_up", "arrow_down", "arrow_left", "arrow_right",
}

COMBO_BUTTONS = ("back", "start")
MODIFIER_ACTIONS = {"turbo_speed"}


class InputMapper:
    """Processes controller frames and issues Windows mouse/keyboard/media commands."""

    def __init__(self, config: Dict[str, Any], driver: XInputDriver, win_input: Win32Input):
        self.config = config
        self.driver = driver
        self.win = win_input
        self.actions = ActionManager(win_input)

        self.is_enabled = config.get("features", {}).get("start_enabled", True)
        self.controller_index = 0
        self.connected = False

        # Button edge tracking (kept up to date even while disabled so that
        # resuming never produces phantom presses/releases)
        self._button_states: Dict[str, bool] = {}
        self._repeat_next: Dict[str, float] = {}
        # Action bound at press time (base binding or Back-layer binding)
        self._active_action: Dict[str, str] = {}

        # Auto-turbo: time the left stick has been held at full tilt
        self._full_tilt_since: Optional[float] = None

        # Scroll accumulators (wheel units)
        self._scroll_accum_v = 0.0
        self._scroll_accum_h = 0.0

        # Trigger hysteresis
        self._rt_down = False
        self._lt_down = False

        # Back+Start combo tracking
        self._combo_start_time: Optional[float] = None
        self._combo_triggered = False
        self._combo_consumed = False

        # Cross-thread toggle request (GUI thread -> poll thread)
        self._toggle_requested = False
        self._last_frame_time: Optional[float] = None

        # Listeners (invoked on the polling thread — must not touch Tk widgets directly)
        self.on_state_update: Optional[Callable[[GamepadState, bool], None]] = None
        self.on_mode_change: Optional[Callable[[bool], None]] = None

    # ------------------------------------------------------------------ control
    def request_toggle(self):
        """Thread-safe: ask the polling thread to toggle on its next frame."""
        self._toggle_requested = True

    def set_connected(self, connected: bool):
        self.connected = connected
        if not connected:
            self._reset_input_state()
            self._last_frame_time = None

    def _reset_input_state(self):
        """Reset all tracked state to prevent stuck keys and phantom inputs."""
        self.actions.release_all()
        self._rt_down = False
        self._lt_down = False
        self._button_states.clear()
        self._repeat_next.clear()
        self._active_action.clear()
        if hasattr(self, "_wasd_state"):
            self._wasd_state.clear()
        self._combo_start_time = None
        self._combo_triggered = False
        self._combo_consumed = False
        self._scroll_accum_v = self._scroll_accum_h = 0.0

    def toggle_enabled(self) -> bool:
        """Toggle desktop control mode on/off."""
        if getattr(self, "_auto_paused", False) and not getattr(self, "_force_resume", False):
            self._force_resume = True
            self.is_enabled = True
        else:
            self.is_enabled = not self.is_enabled
            self._force_resume = False
            
        self._reset_input_state()
        rumble = self.config.get("features", {}).get("rumble_feedback", True)

        if rumble:
            if self.is_enabled:
                # Short double-buzz confirmation for ENABLED
                self.driver.pulse_vibration(
                    self.controller_index,
                    pattern=[(0.5, 0.7, 0.1), (0.0, 0.0, 0.06), (0.7, 0.9, 0.12)]
                )
            else:
                # Single longer low-buzz for DISABLED / GAME MODE
                self.driver.pulse_vibration(
                    self.controller_index, left_motor=0.6, right_motor=0.0, duration=0.35
                )

        if self.on_mode_change:
            self.on_mode_change(self.is_enabled)

        return self.is_enabled

    def update_config(self, new_config: Dict[str, Any]):
        """Hot-reload configuration."""
        self.config = new_config

    # ------------------------------------------------------------------ math
    def _calc_radial_deadzone_and_curve(self, x: float, y: float, deadzone: float, exponent: float) -> tuple[float, float]:
        """Calculates smooth radial deadzone and power curve."""
        magnitude = math.hypot(x, y)
        if magnitude <= deadzone or magnitude == 0:
            return 0.0, 0.0

        norm_mag = (magnitude - deadzone) / (1.0 - deadzone)
        norm_mag = max(0.0, min(1.0, norm_mag))
        curved_mag = math.pow(norm_mag, exponent)

        scale = curved_mag / magnitude
        return x * scale, y * scale

    @staticmethod
    def _scroll_axis(value: float, deadzone: float, notches_per_sec: float, dt: float, accum: float) -> tuple[int, float]:
        """Returns (wheel units to emit now, new accumulator)."""
        if abs(value) <= deadzone:
            return 0, 0.0
        norm = min(1.0, (abs(value) - deadzone) / (1.0 - deadzone))
        curved = math.copysign(norm ** 1.5, value)
        accum += curved * notches_per_sec * WHEEL_DELTA * dt
        chunks = int(accum / WHEEL_CHUNK)  # truncates toward zero
        emit = chunks * WHEEL_CHUNK
        return emit, accum - emit

    # ------------------------------------------------------------------ frame
    def get_active_schema(self) -> Dict[str, Any]:
        schemas = self.config.get("schemas")
        if not schemas:
            return self.config
            
        is_auto = getattr(self, "_auto_paused", False)
        force = getattr(self, "_force_resume", False)
        
        if not self.is_enabled or (is_auto and not force):
            return {}
        return schemas.get("desktop", {})

    def process_frame(self, state: GamepadState, now: Optional[float] = None):
        """Processes a single controller poll tick."""
        now = time.perf_counter() if now is None else now
        if self._last_frame_time is None:
            dt = 1.0 / REFERENCE_HZ
        else:
            dt = max(0.0, min(MAX_FRAME_DT, now - self._last_frame_time))
        self._last_frame_time = now

        # Window Tracking for Auto-Pause and Profiles (Pillars 1 & 2)
        features_cfg = self.config.get("features", {})
        if now - getattr(self, "_last_win_check", 0.0) > 0.5:
            self._last_win_check = now
            try:
                from .win_tracker import get_active_window_info
                proc, is_fs = get_active_window_info()
                self._active_proc = proc
                if not is_fs:
                    self._force_resume = False
                self._auto_paused = is_fs and features_cfg.get("auto_pause_in_fullscreen_games", True)
            except Exception:
                self._active_proc = ""
                self._auto_paused = False

        if self._toggle_requested:
            self._toggle_requested = False
            self.toggle_enabled()

        combo_enabled = features_cfg.get("toggle_combo_enabled", True)

        # 1. Back + Start hold -> toggle Game Mode
        if combo_enabled and state.back and state.start:
            self._combo_consumed = True
            if self._combo_start_time is None:
                self._combo_start_time = now
            elif not self._combo_triggered and now - self._combo_start_time >= features_cfg.get("toggle_hold_seconds", 1.2):
                self.toggle_enabled()
                self._combo_triggered = True
        else:
            self._combo_start_time = None
            self._combo_triggered = False

        if self.on_state_update:
            self.on_state_update(state, self.is_enabled, getattr(self, "_auto_paused", False))

        # Core Routing: We always process input, but we route it to the active schema!
        schema = self.get_active_schema()
        
        # Reset input state if the schema changed (e.g. via auto-pause)
        old_schema_id = id(getattr(self, "_last_schema", None))
        if id(schema) != old_schema_id:
            self._reset_input_state()
            self._last_schema = schema

        if schema:
            self._process_motion(state, dt, now, schema)
            self._process_right_trigger(state, schema)
            self._process_left_trigger(state, schema)
            self._process_buttons(state, now, combo_enabled, schema)

        if not state.back and not state.start:
            self._combo_consumed = False

    def _turbo_multiplier(self, state: GamepadState, now: float, schema: Dict[str, Any]) -> float:
        mouse_cfg = schema.get("mouse", {})
        turbo = mouse_cfg.get("turbo_multiplier", 2.3)
        auto = mouse_cfg.get("auto_turbo", {})
        if not auto.get("enabled", True):
            return 1.0
        if math.hypot(state.thumb_lx, state.thumb_ly) < auto.get("full_tilt_threshold", 0.95):
            self._full_tilt_since = None
            return 1.0
        if self._full_tilt_since is None:
            self._full_tilt_since = now
        held = now - self._full_tilt_since - auto.get("delay_seconds", 0.4)
        if held <= 0:
            return 1.0
        ramp = min(1.0, held / max(1e-6, auto.get("ramp_seconds", 0.5)))
        return 1.0 + (turbo - 1.0) * ramp

    def _process_motion(self, state: GamepadState, dt: float, now: float, schema: Dict[str, Any]):
        mouse_cfg = schema.get("mouse", {})
        scroll_cfg = schema.get("scroll", {})
        triggers_cfg = schema.get("triggers", {})
        tick_scale = dt * REFERENCE_HZ

        # Left Stick Mode Routing (Mouse vs WASD)
        if schema.get("left_stick_mode", "mouse") == "wasd":
            thresh = 0.4
            new_wasd = {
                "key_w": state.thumb_ly > thresh,
                "key_s": state.thumb_ly < -thresh,
                "key_a": state.thumb_lx < -thresh,
                "key_d": state.thumb_lx > thresh,
            }
            if not hasattr(self, "_wasd_state"):
                self._wasd_state = {"key_w": False, "key_s": False, "key_a": False, "key_d": False}
            for key, active in new_wasd.items():
                if active and not self._wasd_state[key]:
                    self.actions.execute_press(key, source="ls_wasd")
                elif not active and self._wasd_state[key]:
                    self.actions.execute_release(key, source="ls_wasd")
                self._wasd_state[key] = active
        else:
            if hasattr(self, "_wasd_state"):
                for key in self._wasd_state:
                    if self._wasd_state[key]:
                        self.actions.execute_release(key, source="ls_wasd")
                self._wasd_state.clear()
                
            speed_multiplier = self._turbo_multiplier(state, now, schema)
            if triggers_cfg.get("lt_precision_aim", True) and state.left_trigger > triggers_cfg.get("threshold", 0.3):
                speed_multiplier *= mouse_cfg.get("precision_multiplier", 0.28)
                
            cx, cy = self._calc_radial_deadzone_and_curve(
                state.thumb_lx, state.thumb_ly,
                mouse_cfg.get("deadzone", 0.18),
                mouse_cfg.get("acceleration_exponent", 1.85),
            )
            if cx != 0.0 or cy != 0.0:
                speed = mouse_cfg.get("base_speed", 5.0) * speed_multiplier * tick_scale
                self.win.move_cursor_delta(cx * speed, -cy * speed)

        # Right stick scroll
        rs_deadzone = scroll_cfg.get("deadzone", 0.22)
        emit, self._scroll_accum_v = self._scroll_axis(
            state.thumb_ry, rs_deadzone, scroll_cfg.get("vertical_speed", 20.0), dt, self._scroll_accum_v
        )
        if emit:
            self.win.scroll_vertical(emit)

        if scroll_cfg.get("horizontal_enabled", True):
            emit, self._scroll_accum_h = self._scroll_axis(
                state.thumb_rx, rs_deadzone, scroll_cfg.get("horizontal_speed", 15.0), dt, self._scroll_accum_h
            )
            if emit:
                self.win.scroll_horizontal(emit)

    def _process_right_trigger(self, state: GamepadState, schema: Dict[str, Any]):
        triggers_cfg = schema.get("triggers", {})
        if not triggers_cfg.get("rt_left_click", True):
            return
        threshold = triggers_cfg.get("threshold", 0.3)
        if state.right_trigger > threshold and not self._rt_down:
            self._rt_down = True
            self.actions.execute_press("left_click", source="rt")
        elif state.right_trigger <= threshold - 0.08 and self._rt_down:
            self._rt_down = False
            self.actions.execute_release("left_click", source="rt")

    def _process_left_trigger(self, state: GamepadState, schema: Dict[str, Any]):
        triggers_cfg = schema.get("triggers", {})
        action = triggers_cfg.get("lt_action")
        if triggers_cfg.get("lt_precision_aim", True) and not action:
            return
        threshold = triggers_cfg.get("threshold", 0.3)
        if state.left_trigger > threshold and not self._lt_down:
            self._lt_down = True
            if action:
                self._active_action["lt"] = action
                self.actions.execute_press(action, source="lt")
        elif state.left_trigger <= threshold - 0.08 and self._lt_down:
            self._lt_down = False
            prev_action = self._active_action.pop("lt", None)
            if prev_action:
                self.actions.execute_release(prev_action, source="lt")

    def _process_buttons(self, state: GamepadState, now: float, combo_enabled: bool, schema: Dict[str, Any]):
        buttons_cfg = schema.get("buttons", {})
        back_layer = self.config.get("back_layer", {})
        lt_layer = schema.get("lt_layer", {})
        rt_layer = schema.get("rt_layer", {})
        double_clicks = schema.get("double_clicks", {})
        
        current_buttons = {
            "a": state.a,
            "b": state.b,
            "x": state.x,
            "y": state.y,
            "lb": state.left_shoulder,
            "rb": state.right_shoulder,
            "ls_click": state.left_thumb_click,
            "rs_click": state.right_thumb_click,
            "dpad_up": state.dpad_up,
            "dpad_down": state.dpad_down,
            "dpad_left": state.dpad_left,
            "dpad_right": state.dpad_right,
            "start": state.start,
            "back": state.back,
            "paddle1": getattr(state, 'paddle1', False),
            "paddle2": getattr(state, 'paddle2', False),
            "paddle3": getattr(state, 'paddle3', False),
            "paddle4": getattr(state, 'paddle4', False),
            "agl": getattr(state, 'agl', False),
            "agr": getattr(state, 'agr', False),
        }

        for name, is_down in current_buttons.items():
            was_down = self._button_states.get(name, False)
            self._button_states[name] = is_down

            if combo_enabled and name in COMBO_BUTTONS:
                action = buttons_cfg.get(name)
                if (action and action not in MODIFIER_ACTIONS and was_down and not is_down
                        and not self._combo_consumed):
                    self.actions.tap(action, source=name)
                continue

            if is_down and not was_down:
                if not hasattr(self, "_last_press_times"):
                    self._last_press_times = {}
                last_press = self._last_press_times.get(name, 0.0)
                self._last_press_times[name] = now
                is_double_tap = (now - last_press) < 0.35

                app_profiles = self.config.get("app_profiles", {})
                active_proc = getattr(self, "_active_proc", "")
                
                action = None
                if is_double_tap and name in double_clicks:
                    action = double_clicks[name]
                    # Release the single tap action that was triggered on the first press
                    prev = self._active_action.pop(name, None)
                    if prev:
                        self.actions.execute_release(prev, source=name)
                elif state.back and name in back_layer:
                    action = back_layer[name]
                    self._combo_consumed = True  # Back was used as a modifier
                elif state.left_trigger > 0.3 and name in lt_layer:
                    action = lt_layer[name]
                elif state.right_trigger > 0.3 and name in rt_layer:
                    action = rt_layer[name]
                elif active_proc in app_profiles and name in app_profiles[active_proc]:
                    action = app_profiles[active_proc][name]
                else:
                    action = buttons_cfg.get(name)
                    
                if not action or action in MODIFIER_ACTIONS:
                    continue
                self._active_action[name] = action
                self.actions.execute_press(action, source=name)
                
                if action == "dictation_toggle":
                    self._dictation_active = not getattr(self, "_dictation_active", False)
                    if self._dictation_active:
                        self.driver.pulse_vibration(self.controller_index, pattern=[(0.4, 0.4, 0.15)])
                    else:
                        self.driver.pulse_vibration(self.controller_index, pattern=[(0.4, 0.4, 0.1), (0.0, 0.0, 0.05), (0.4, 0.4, 0.1)])

                if action in REPEATABLE_ACTIONS:
                    self._repeat_next[name] = now + REPEAT_DELAY_S
            elif is_down and was_down:
                action = self._active_action.get(name)
                next_repeat = self._repeat_next.get(name)
                if action and next_repeat is not None and now >= next_repeat:
                    self.actions.execute_press(action, source=name)
                    self._repeat_next[name] = now + REPEAT_INTERVAL_S
            elif was_down and not is_down:
                self._repeat_next.pop(name, None)
                action = self._active_action.pop(name, None)
                if action:
                    self.actions.execute_release(action, source=name)
