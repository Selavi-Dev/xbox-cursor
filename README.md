# 🎮 Xbox Controller Desktop Navigator

Turn any standard Xbox controller (wired USB, Xbox Wireless USB Adapter, or Bluetooth) into a smooth, high-precision mouse and desktop media remote for Windows 10/11.

Built specifically for high responsiveness (120Hz polling), multi-monitor setups, and couch desktop navigation without third-party bloatware or external drivers.

---

## 🌟 Key Features

- **🚀 Silky Smooth Cursor Control:** Radial deadzone filtering paired with dynamic power acceleration curves (\(v \propto r^{1.85}\)). Ultra-fine pixel accuracy for clicking hyperlinks and closing window tabs, plus high-speed travel across multi-monitor setups.
- **📜 Smooth Scrolling:** Tilt the Right Stick to scroll vertically and horizontally through web pages, feeds, and code.
- **🎯 Sniper / Precision Aim Mode:** Pull Left Trigger (`LT`) to instantly reduce cursor speed by ~70% for microscopic targeting.
- **🏎️ Turbo Sprint:** Click Left Stick (`LS`) to boost speed across multi-monitor displays.
- **🎮 Game Mode Bypass (Back + Start):** Hold `Back + Start` for 1.2 seconds to toggle desktop control on or off anytime. A distinct haptic vibration confirms the mode switch so your desktop mouse doesn't interfere when playing games.
- **📳 Haptic Rumble Feedback:** Physical vibration confirmation on mode toggles.
- **⌨️ Couch Typing (On-Screen Keyboard):** Press `Y` to instantly toggle the Windows Touch / On-Screen Keyboard.
- **📊 Real-Time Control Panel GUI:** Dark-themed Tkinter dashboard with live stick deflection canvases, trigger meters, active button badges, and live sensitivity sliders.
- **⚡ Zero External Dependencies:** Powered by pure Python and native Windows Win32 APIs (`xinput1_4.dll` & `user32.dll`).

---

## 🕹️ Controls & Button Mapping

```
                 [ LB: Browser Back ]         [ RB: Browser Fwd ]
                 [ LT: Precision Aim]         [ RT: Left Click  ]
                           \                         /
                            \                       /
                       (D-Pad)                     (Y) Toggle Keyboard
             [Up]    Arrow Up                (X)         (B) Escape
            [Down]   Arrow Down         Right Click
            [Left]   Arrow Left                    (A) Left Click
            [Right]  Arrow Right
                                [Back]     [Start]
                               Alt+Tab      Win Key
                                     \     /
                         [Hold Back + Start: Game Mode Toggle]
                 (Left Stick)                      (Right Stick)
            Mouse Cursor Move                  Scroll Wheel (V & H)
           [Click: Play / Pause]              [Click: Middle Click]
```

| Controller Input | Windows Desktop Action | Function |
| :--- | :--- | :--- |
| **Left Stick** | Mouse Cursor | Smooth movement (Auto-Turbo at edge) |
| **Right Stick** | Mouse Wheel | Vertical and horizontal scroll |
| **Right Trigger (RT)** | Primary Left Click | Pull to click, hold to drag / select text |
| **A Button** | Primary Left Click | Standard click |
| **B Button** | Escape | Back / cancel / close menus |
| **X Button** | Secondary Right Click | Context menu |
| **Left Trigger (LT)** | Precision Aim Mode | Slows down cursor by 70% |
| **Y Button** | On-Screen Keyboard | Couch typing access |
| **Left Bumper (LB)** | Browser Back | Navigate back |
| **Right Bumper (RB)** | Browser Forward | Navigate forward |
| **Left Stick Click (LS)** | Play / Pause | Toggle media playback |
| **Right Stick Click (RS)**| Middle Click | Open links in new tab / auto-scroll |
| **D-Pad** | Arrow Keys | Up, Down, Left, Right (auto-repeats) |
| **Start (Menu)** | Windows Key | Open Start Menu |
| **Back (View)** | Alt + Tab | Switch active applications |
| **Hold Back + D-Pad** | Media Layer | Volume Up/Down, Prev/Next track |
| **Back + Start (Hold 1.2s)** | **Toggle Game Mode** | Pauses/Resumes desktop control |

---

## 🚀 Quick Start

### 1. Launch with GUI Dashboard
Run the control panel to see live stick visualizers, button status, and tweak sensitivity sliders on the fly:

```powershell
python run.py
```

### 2. Launch in Headless Console Mode
If you prefer running cleanly in the background without a window:

```powershell
python run.py --cli
```

---

## ⚙️ Customization (`config.json`)

All sensitivities, curves, and button assignments are stored in [config.json](file:///c:/Users/croma/Documents/antigravity/brave-pythagoras/config.json):

```json
{
  "mouse": {
    "base_speed": 22.0,
    "acceleration_exponent": 1.85,
    "deadzone": 0.18,
    "turbo_multiplier": 2.3,
    "precision_multiplier": 0.28,
    "poll_rate_hz": 120
  },
  "scroll": {
    "vertical_speed": 4.5,
    "horizontal_speed": 3.5,
    "deadzone": 0.22,
    "horizontal_enabled": true
  },
  "triggers": {
    "rt_left_click": true,
    "lt_precision_aim": true,
    "threshold": 0.3
  }
}
```

- **`base_speed`**: Maximum cursor speed when the stick is fully pushed.
- **`acceleration_exponent`**: Exponent of the power curve (\(1.85\) is ideal: subtle tilts move slowly for fine targeting, large tilts move fast).
- **`deadzone`**: Inner radius where stick input is ignored (prevents controller stick drift).
- **`precision_multiplier`**: Speed ratio applied when holding `LT` (default `0.28` cuts speed to ~28%).

---

## 🧪 Running Automated Tests

Run the test suite to verify XInput detection, deadzones, and input mapping:

```powershell
python -m unittest discover -s tests
```
