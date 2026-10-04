# Xbox Controller Desktop Navigator

Turn any standard Xbox controller (wired USB, Xbox Wireless USB Adapter, or Bluetooth) into a smooth, high-precision mouse and desktop media remote for Windows 10/11.

Built for high responsiveness (120Hz polling), multi-monitor setups, and couch desktop navigation without third-party bloatware or external drivers.

---

## Key Features

- **Smooth cursor control:** Radial deadzone filtering with dynamic power acceleration. Fine pixel accuracy for links and window chrome, plus fast travel across multi-monitor setups.
- **Smooth scrolling:** Right stick scrolls vertically and horizontally.
- **Auto-turbo:** Hold the left stick at full tilt to ramp into a speed boost for long monitor crossings.
- **Game Mode pass-through (Back + Start):** Hold `Back + Start` for 1.2 seconds to pause desktop control so the pad talks only to games. Haptic rumble confirms the switch. Fullscreen games can also auto-pause desktop control.
- **Haptic rumble feedback** on mode toggles and dictation.
- **Couch dictation:** `Y` toggles Windows Voice Typing (`Win+H`).
- **Radial media menu:** Hold `Back` and aim the right stick to pick volume / track actions; D-Pad while holding Back is a media layer.
- **Real-time control panel GUI:** Dark Tkinter dashboard with live stick HUD, trigger meters, button mapping, and sensitivity sliders.
- **Minimal dependencies:** Core path is pure Python + native Win32 (`xinput1_4.dll` & `user32.dll`). Tray icon uses `pystray` + Pillow.

---

## Controls & Button Mapping

Defaults below match the shipped [`config.json`](config.json). Remap anything in the GUI **Button Mapping** tab or by editing that file.

```
                 [ LB: Browser Back ]         [ RB: Browser Fwd ]
                 [ LT: Enter (Tap)  ]         [ RT: Left Click  ]
                  [  + LT Layers    ]          [  + RT Layers   ]
                           \                         /
                            \                       /
                       (D-Pad)                     (Y) Voice Dictation
             [Up]    Arrow Up                (X)         (B) Right Click
            [Down]   Arrow Down              Enter
            [Left]   Arrow Left                    (A) Left Click
            [Right]  Arrow Right
                                [Back]     [Start]
                         Radial / Media     Win Key
                                     \     /
                         [Hold Back + Start: Game Mode Toggle]
                 (Left Stick)                      (Right Stick)
            Mouse Cursor Move                  Scroll Wheel (V & H)
           [Click: Desktop Left]              [Click: Desktop Right]
```

| Controller Input | Default action | Notes |
| :--- | :--- | :--- |
| **Left Stick** | Mouse cursor | Auto-turbo at full tilt |
| **Right Stick** | Scroll wheel | Vertical + horizontal |
| **Right Trigger (RT)** | Left click (hold to drag) | With RT layer mapped, tap if no layer button used |
| **Left Trigger (LT)** | Enter | Hold LT + face/bumper for LT layer (copy/paste/undo/save) |
| **A** | Left click | |
| **B** | Right click | Double-tap: Backspace |
| **X** | Enter | |
| **Y** | Voice dictation (`Win+H`) | |
| **LB / RB** | Browser Back / Forward | Chrome/Edge: prev/next tab via `app_profiles` |
| **LS / RS click** | Virtual desktop left / right | `Win+Ctrl+Left/Right` |
| **D-Pad** | Arrow keys | Hold **Back**: volume / media prev-next |
| **Start** | Windows key | |
| **Back** | Radial menu modifier | Hold + right stick = radial; double-tap = Task View |
| **Hold Back + Start (1.2s)** | Toggle Game Mode | Pure pass-through while paused — no remapping |

### LT / RT layers (defaults)

| Layer | Binding | Action |
| :--- | :--- | :--- |
| LT + A/B/X/Y | copy / paste / undo / save | |
| LT + RB | desktop_right | |
| RT + LB | desktop_left | |

### Sidewings (PowerA / 8BitDo / PDP)

If paddles only mirror face buttons in hardware, program left paddle → LS click and right paddle → RS click (already mapped to desktop left/right).

If the controller exposes independent paddles in software, set `"discrete_paddles": true` under `features` in `config.json` (optional `winrt-Windows.Gaming.Input` package) and map `agl` / `agr` in the GUI.

---

## Quick Start

### GUI dashboard

```powershell
pip install -r requirements.txt
python run.py
```

### Headless console

```powershell
python run.py --cli
```

Optional launchers: `start_controller.bat`, `start_controller_silent.vbs`.

### Packaged exe

```powershell
pip install -r requirements-build.txt
.\build_exe.ps1
```

---

## Customization (`config.json`)

Sensitivities, curves, and button assignments live in [`config.json`](config.json). Important desktop mouse keys:

| Key | Meaning |
| :--- | :--- |
| `base_speed` | Cursor speed at full stick deflection (per reference tick) |
| `acceleration_exponent` | Power curve (higher = finer near-center, faster at edge) |
| `deadzone` | Inner stick radius ignored (drift filter) |
| `precision_multiplier` | Used when `lt_precision_aim` is enabled |
| `poll_rate_hz` | Polling rate (clamped 30–240) |

**Game Mode** does not load a second binding schema. While paused (manual toggle or fullscreen auto-pause), the app issues no desktop input so the controller reaches the foreground game unchanged.

---

## Running tests

```powershell
python -m unittest discover -s tests
```

Hardware XInput tests skip automatically when no controller is connected.
