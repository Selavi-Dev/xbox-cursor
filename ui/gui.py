"""Modern Dark Theme Tkinter Dashboard for Xbox Desktop Controller featuring a Spatial Vector HUD."""

import json
import math
import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional
import threading
import winreg
import pystray
from PIL import Image, ImageDraw

from controller.xinput import GamepadState
from controller.mapper import InputMapper
from ui.radial import RadialMenu

class ControllerAppGUI:
    """Live telemetry monitor, interactive spatial HUD, and configuration GUI."""

    def __init__(self, root: tk.Tk, mapper: InputMapper, config_path: str):
        self.root = root
        self.mapper = mapper
        self.config_path = config_path

        self.root.title("Xbox Desktop Navigator - Control Panel")
        self.root.geometry("960x780")
        self.root.minsize(860, 680)
        self.root.configure(bg="#18181b")

        self.root.protocol("WM_DELETE_WINDOW", self._hide_window)
        self.tray_icon = None

        # Define Radial Menu slices
        radial_actions = [
            {"label": "Volume Up\n(Up)", "action": "volume_up"},
            {"label": "Next Track\n(Right)", "action": "media_next"},
            {"label": "Volume Down\n(Down)", "action": "volume_down"},
            {"label": "Prev Track\n(Left)", "action": "media_prev"},
        ]
        self.radial = RadialMenu(radial_actions, lambda act: self.mapper.actions.tap(act, source="radial"))

        # Telemetry storage
        self._current_state: Optional[GamepadState] = None
        self._is_enabled = self.mapper.is_enabled
        self._connected = False

        self.hud = {}  # Stores canvas item IDs for high-speed dynamic updates

        # Register mapper callbacks
        self.mapper.on_state_update = self._on_telemetry
        self.mapper.on_mode_change = self._on_mode_change

        self._setup_styles()
        self._build_ui()
        
        self._pending_mode: Optional[bool] = None
        self._apply_mode_ui(self._is_enabled)

        # Start periodic GUI refresh (40 Hz)
        self.root.after(25, self._refresh_gui_loop)

    def _create_tray_image(self):
        image = Image.new('RGB', (64, 64), color=(24, 24, 27))
        dc = ImageDraw.Draw(image)
        dc.rectangle((16, 16, 48, 48), fill=(16, 185, 129)) # green
        return image

    def _hide_window(self):
        self.root.withdraw()
        if not self.tray_icon:
            menu = pystray.Menu(
                pystray.MenuItem("Show Control Panel", self._show_window, default=True),
                pystray.MenuItem("Quit Xbox Navigator", self._quit_app)
            )
            self.tray_icon = pystray.Icon("xbox_desktop", self._create_tray_image(), "Xbox Desktop Navigator", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_window(self, icon, item):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.after(0, self.root.deiconify)

    def _quit_app(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        if hasattr(self, "_quit_callback"):
            self.root.after(0, self._quit_callback)
        else:
            self.root.after(0, self.root.quit)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        bg_color = "#18181b"
        card_bg = "#27272a"
        fg_color = "#f4f4f5"

        style.configure(".", background=bg_color, foreground=fg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("TButton", background=[("active", "#3f3f46")])

        # Style the Notebook and Tabs for 10-foot UI & Dark Mode Readability
        style.configure("TNotebook", background=bg_color, borderwidth=0)
        style.configure("TNotebook.Tab", 
                        background="#18181b", 
                        foreground="#71717a", 
                        padding=[20, 10], 
                        font=("Segoe UI", 12, "bold"),
                        borderwidth=0)
        
        style.map("TNotebook.Tab",
                  background=[("selected", "#27272a"), ("active", "#27272a")],
                  foreground=[("selected", "#ffffff"), ("active", "#e4e4e7")],
                  expand=[("selected", [1, 1, 1, 0])])

        # Style Combobox for Button Mapping Tab
        style.configure("Dark.TCombobox", 
                        fieldbackground="#3f3f46", 
                        background="#52525b", 
                        foreground="#ffffff", 
                        arrowcolor="#ffffff", 
                        font=("Segoe UI", 11))
        style.map("Dark.TCombobox", 
                  fieldbackground=[("readonly", "#3f3f46")], 
                  selectbackground=[("readonly", "#10b981")], 
                  selectforeground=[("readonly", "#ffffff")])

    def _build_ui(self):
        # Header banner
        header = tk.Frame(self.root, bg="#18181b", padx=20, pady=14)
        header.pack(fill=tk.X)

        title_lbl = tk.Label(header, text="🎮 Xbox Desktop Navigator", font=("Segoe UI", 18, "bold"), bg="#18181b", fg="#ffffff")
        title_lbl.pack(side=tk.LEFT)

        self.mode_badge = tk.Label(header, text="Desktop Mode Active", font=("Segoe UI", 11, "bold"), bg="#065f46", fg="#34d399", padx=14, pady=5)
        self.mode_badge.pack(side=tk.RIGHT, padx=5)

        self.toggle_btn = tk.Button(
            header, text="Pause (Game Mode)", font=("Segoe UI", 10, "bold"),
            bg="#3b82f6", fg="#ffffff", activebackground="#2563eb", activeforeground="#ffffff",
            relief="flat", padx=10, pady=4, command=self._toggle_mode
        )
        self.toggle_btn.pack(side=tk.RIGHT, padx=10)

        # Notebook tabs
        tab_control = ttk.Notebook(self.root)
        self.tab_hud = ttk.Frame(tab_control, padding=12)
        self.tab_mapping = ttk.Frame(tab_control, padding=12)
        self.tab_tuning = ttk.Frame(tab_control, padding=12)

        tab_control.add(self.tab_hud, text="  Live Spatial HUD  ")
        tab_control.add(self.tab_mapping, text="  Button Mapping  ")
        tab_control.add(self.tab_tuning, text="  Speed & Tuning  ")
        tab_control.pack(expand=1, fill="both", padx=14, pady=8)

        self._build_hud_tab()
        self._build_mapping_tab()
        self._build_tuning_tab()

        # Footer
        footer = tk.Frame(self.root, bg="#18181b", pady=8, padx=20)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        self.conn_label = tk.Label(footer, text="Checking controller...", font=("Segoe UI", 10, "bold"), bg="#18181b", fg="#a1a1aa")
        self.conn_label.pack(side=tk.LEFT)
        
        tip_lbl = tk.Label(footer, text="Tip: Hold Back + Start for 1.2s to toggle Game Mode", font=("Segoe UI", 9, "italic"), bg="#18181b", fg="#71717a")
        tip_lbl.pack(side=tk.RIGHT)

    # -------------------------------------------------------------------------
    # SPATIAL VECTOR HUD (DIGITAL TWIN)
    # -------------------------------------------------------------------------
    def _build_hud_tab(self):
        cv = tk.Canvas(self.tab_hud, width=900, height=540, bg="#18181b", highlightthickness=0)
        cv.pack(expand=True, fill="both")
        self.cv = cv
        
        cx, cy = 450, 270

        # Controller Body Silhouette
        body_pts = [
            cx - 90, cy - 140,   # Top flat left
            cx + 90, cy - 140,   # Top flat right
            cx + 170, cy - 120,  # RB area
            cx + 220, cy - 30,   # Right upper outer
            cx + 230, cy + 90,   # Right lower outer
            cx + 170, cy + 190,  # Right bottom
            cx + 100, cy + 170,  # Right bottom inner
            cx + 60, cy + 50,    # Center right dip
            cx - 60, cy + 50,    # Center left dip
            cx - 100, cy + 170,  # Left bottom inner
            cx - 170, cy + 190,  # Left bottom
            cx - 230, cy + 90,   # Left lower outer
            cx - 220, cy - 30,   # Left upper outer
            cx - 170, cy - 120,  # LB area
        ]
        cv.create_polygon(body_pts, smooth=True, fill="#222225", outline="#3f3f46", width=2)
        
        # Center Guide Bezel
        cv.create_oval(cx - 30, cy - 130, cx + 30, cy - 70, fill="#18181b", outline="#3f3f46", width=2)
        self.hud['guide_txt'] = cv.create_text(cx, cy - 100, text="X", fill="#52525b", font=("Segoe UI", 12, "bold"))
        self.hud['guide_line'] = cv.create_line(cx, cy - 135, cx, cy - 175, fill="#3f3f46", width=2)
        self.hud['guide_callout'] = cv.create_text(cx, cy - 185, text="Xbox Controller Active", fill="#52525b", font=("Segoe UI", 10), justify="center")

        # Map components dynamically based on current config
        btn_cfg = self.mapper.config.get("schemas", {}).get("desktop", {}).get("buttons", {})
        
        def _get_callout(btn: str, fallback: str) -> str:
            action = btn_cfg.get(btn)
            return action.replace("_", " ").title() if action else fallback

        self._add_button("a", "A", cx + 120, cy - 20, cx + 290, cy - 5, "w", _get_callout("a", "Left Click"))
        self._add_button("b", "B", cx + 150, cy - 50, cx + 290, cy - 35, "w", _get_callout("b", "Right Click"))
        self._add_button("x", "X", cx + 90, cy - 50, cx + 290, cy - 65, "w", _get_callout("x", "Enter"))
        self._add_button("y", "Y", cx + 120, cy - 80, cx + 290, cy - 95, "w", _get_callout("y", "Voice Dictation"))

        self._add_button("lb", "LB", cx - 130, cy - 135, cx - 290, cy - 135, "e", _get_callout("lb", "Browser Back"))
        self._add_button("rb", "RB", cx + 130, cy - 135, cx + 290, cy - 135, "w", _get_callout("rb", "Browser Forward"))
        
        self._add_button("back", "Back", cx - 50, cy - 60, cx - 290, cy - 180, "e", _get_callout("back", "Alt + Tab / Modifier"))
        self._add_button("start", "Start", cx + 50, cy - 60, cx + 290, cy - 180, "w", _get_callout("start", "Windows Menu"))

        # D-Pad
        dpad_x, dpad_y = cx - 70, cy + 50
        self._draw_dpad(dpad_x, dpad_y)
        
        # Sticks
        ls_x, ls_y = cx - 120, cy - 50
        ls_click_act = _get_callout("ls_click", "Play/Pause")
        self._add_stick("ls", ls_x, ls_y, cx - 290, cy + 20, "e", f"Move Cursor\n(Click: {ls_click_act})")
        
        rs_x, rs_y = cx + 70, cy + 50
        rs_click_act = _get_callout("rs_click", "Middle Click")
        self._add_stick("rs", rs_x, rs_y, cx + 290, cy + 50, "w", f"Scroll Wheel\n(Click: {rs_click_act})")

        # Triggers
        self._add_trigger("lt", cx - 130, cy - 165, cx - 290, cy - 105, "e", "Precision Aim (Slow)")
        self._add_trigger("rt", cx + 130, cy - 165, cx + 290, cy - 105, "w", "Left Click (Drag)")
        
        # Sidewings (AGL / AGR)
        agl_pts = [cx - 215, cy + 30, cx - 245, cy + 60, cx - 245, cy + 90, cx - 200, cy + 120]
        agr_pts = [cx + 215, cy + 30, cx + 245, cy + 60, cx + 245, cy + 90, cx + 200, cy + 120]
        self._add_sidewing("agl", agl_pts, cx - 290, cy + 100, "e", _get_callout("agl", "Desktop Left"))
        self._add_sidewing("agr", agr_pts, cx + 290, cy + 100, "w", _get_callout("agr", "Desktop Right"))
        
        # Central Game Mode combo hint
        cv.create_text(cx, cy + 140, text="Hold Back + Start for 1.2s to toggle Game Mode", fill="#52525b", font=("Segoe UI", 10, "italic"))

    def _add_button(self, name, label, x, y, tx, ty, anchor, callout):
        r = 13
        bg = self.cv.create_oval(x-r, y-r, x+r, y+r, fill="#27272a", outline="#52525b", width=1.5)
        txt = self.cv.create_text(x, y, text=label, fill="#a1a1aa", font=("Segoe UI", 9, "bold"))
        
        line = self.cv.create_line(x + (r if anchor=="w" else -r), y, tx, ty, fill="#3f3f46", width=2)
        lbl = self.cv.create_text(tx + (10 if anchor=="w" else -10), ty, text=callout, fill="#a1a1aa", anchor=anchor, font=("Segoe UI", 10))
        
        self.hud[f'btn_{name}'] = bg
        self.hud[f'txt_{name}'] = txt
        self.hud[f'line_{name}'] = line
        self.hud[f'lbl_{name}'] = lbl

    def _draw_dpad(self, x, y):
        w, l = 12, 35
        pts = [
            x-w, y-w,  x-w, y-l,  x+w, y-l,  x+w, y-w,  # Up arm
            x+l, y-w,  x+l, y+w,  x+w, y+w,             # Right arm
            x+w, y+l,  x-w, y+l,  x-w, y+w,             # Down arm
            x-l, y+w,  x-l, y-w,                        # Left arm
        ]
        self.hud['dpad_bg'] = self.cv.create_polygon(pts, fill="#27272a", outline="#52525b", width=1.5)
        
        tx, ty = x - 220, y + 80
        self.hud['line_dpad'] = self.cv.create_line(x-l, y, tx, ty, fill="#3f3f46", width=2)
        self.hud['lbl_dpad'] = self.cv.create_text(tx - 10, ty, text="Arrow Keys\n(Hold Back: Media Layer)", fill="#a1a1aa", anchor="e", font=("Segoe UI", 10))

    def _add_stick(self, name, x, y, tx, ty, anchor, callout):
        R = 30
        self.cv.create_oval(x-R, y-R, x+R, y+R, fill="#18181b", outline="#3f3f46", width=2)
        self.hud[f'stick_dz_{name}'] = self.cv.create_oval(x, y, x, y, outline="#ef4444", dash=(2,2)) # deadzone dynamically updated
        self.hud[f'stick_dot_{name}'] = self.cv.create_oval(x-15, y-15, x+15, y+15, fill="#3f3f46", outline="#71717a")
        
        self.hud[f'line_{name}'] = self.cv.create_line(x + (R if anchor=="w" else -R), y, tx, ty, fill="#3f3f46", width=2)
        self.hud[f'lbl_{name}'] = self.cv.create_text(tx + (10 if anchor=="w" else -10), ty, text=callout, fill="#a1a1aa", anchor=anchor, font=("Segoe UI", 10))
        self.hud[f'base_x_{name}'] = x
        self.hud[f'base_y_{name}'] = y

    def _add_trigger(self, name, x, y, tx, ty, anchor, callout):
        w, h = 30, 8
        self.cv.create_rectangle(x-w, y-h, x+w, y+h, fill="#18181b", outline="#52525b")
        self.hud[f'trig_bar_{name}'] = self.cv.create_rectangle(x-w, y-h, x-w, y+h, fill="#34d399", outline="")
        
        self.hud[f'line_{name}'] = self.cv.create_line(x + (w if anchor=="w" else -w), y, tx, ty, fill="#3f3f46", width=2)
        self.hud[f'lbl_{name}'] = self.cv.create_text(tx + (10 if anchor=="w" else -10), ty, text=callout, fill="#a1a1aa", anchor=anchor, font=("Segoe UI", 10))
        self.hud[f'base_x_{name}'] = x
        self.hud[f'base_y_{name}'] = y

    def _add_sidewing(self, name, x_pts, tx, ty, anchor, callout):
        bg = self.cv.create_polygon(x_pts, smooth=True, fill="#27272a", outline="#52525b", width=1.5)
        mid_x = sum(x_pts[0::2]) / (len(x_pts) // 2)
        mid_y = sum(x_pts[1::2]) / (len(x_pts) // 2)
        line = self.cv.create_line(mid_x, mid_y, tx, ty, fill="#3f3f46", width=2)
        lbl = self.cv.create_text(tx + (10 if anchor=="w" else -10), ty, text=callout, fill="#a1a1aa", anchor=anchor, font=("Segoe UI", 10))
        
        self.hud[f'btn_{name}'] = bg
        self.hud[f'line_{name}'] = line
        self.hud[f'lbl_{name}'] = lbl
        self.hud[f'txt_{name}'] = self.cv.create_text(-1000, -1000, text="")

    # -------------------------------------------------------------------------
    # MAPPING TAB
    # -------------------------------------------------------------------------
    def _load_schema_mappings(self):
        schema_name = "gaming" if (getattr(self, "_last_auto_paused", False) or not self._is_enabled) else "desktop"
        self._current_mapping_schema_name = schema_name
        
        if hasattr(self, "mapping_title_lbl"):
            self.mapping_title_lbl.config(text=f"{schema_name.capitalize()} Button Mapping")
            
        cfg = self.mapper.config.get("schemas", {}).get(schema_name, {})
        
        group_key = getattr(self, "_mapping_groups", {}).get(getattr(self, "mapping_group_var", tk.StringVar(value="Base Buttons")).get(), "buttons")
        buttons_cfg = cfg.get(group_key, {})
        
        if hasattr(self, "mapping_vars"):
            for btn, var in self.mapping_vars.items():
                internal_val = buttons_cfg.get(btn, "")
                display_val = internal_val.replace("_", " ").title()
                var.set(display_val)

    def _build_mapping_tab(self):
        container = tk.Frame(self.tab_mapping, bg="#27272a", padx=20, pady=18)
        container.pack(fill=tk.BOTH, expand=True)

        header_frame = tk.Frame(container, bg="#27272a")
        header_frame.pack(fill=tk.X, pady=(0, 15))

        self.mapping_title_lbl = tk.Label(header_frame, text="Desktop Button Mapping", font=("Segoe UI", 13, "bold"), bg="#27272a", fg="#ffffff")
        self.mapping_title_lbl.pack(side=tk.LEFT)

        tk.Label(header_frame, text="Layer: ", font=("Segoe UI", 11), bg="#27272a", fg="#e4e4e7").pack(side=tk.LEFT, padx=(30, 5))

        self.mapping_group_var = tk.StringVar(value="Base Buttons")
        self._mapping_groups = {
            "Base Buttons": "buttons",
            "LT Shift Layer": "lt_layer",
            "RT Shift Layer": "rt_layer",
            "Double Clicks": "double_clicks"
        }
        
        group_cb = ttk.Combobox(header_frame, textvariable=self.mapping_group_var, values=list(self._mapping_groups.keys()), state="readonly", width=18, style="Dark.TCombobox", font=("Segoe UI", 11))
        group_cb.pack(side=tk.LEFT)
        group_cb.bind("<<ComboboxSelected>>", lambda e: self._load_schema_mappings())

        self.mapping_vars = {}
        self._current_mapping_schema_name = "desktop"
        
        grid_frame = tk.Frame(container, bg="#27272a")
        grid_frame.pack(fill=tk.BOTH, expand=True)
        
        buttons_list = [
            "a", "b", "x", "y", 
            "lb", "rb", "ls_click", "rs_click", 
            "dpad_up", "dpad_down", "dpad_left", "dpad_right", 
            "start", "back", "agl", "agr"
        ]
        
        actions_list = [
            "", "left_click", "right_click", "middle_click",
            "escape", "enter", "backspace", "win_key", "alt_tab",
            "task_view", "show_desktop", "dictation_toggle", "toggle_osk",
            "copy", "paste", "undo", "save", "close_window",
            "new_tab", "close_tab", "browser_prev_tab", "browser_next_tab",
            "desktop_left", "desktop_right",
            "arrow_up", "arrow_down", "arrow_left", "arrow_right",
            "media_play_pause", "media_next", "media_prev", "volume_up", "volume_down", "volume_mute",
            "radial_menu_modifier"
        ]
        
        friendly_btn_names = {
            "a": "A Button", "b": "B Button", "x": "X Button", "y": "Y Button",
            "lb": "Left Bumper", "rb": "Right Bumper", 
            "ls_click": "Left Stick Click", "rs_click": "Right Stick Click",
            "dpad_up": "D-Pad Up", "dpad_down": "D-Pad Down", 
            "dpad_left": "D-Pad Left", "dpad_right": "D-Pad Right",
            "start": "Start (Menu)", "back": "Back (View)",
            "agl": "AGL (Left Grip)", "agr": "AGR (Right Grip)"
        }
        
        display_actions = [a.replace("_", " ").title() for a in actions_list]
        
        for i, btn in enumerate(buttons_list):
            row = i % 8
            col = (i // 8) * 2
            
            friendly_name = friendly_btn_names.get(btn, btn.upper())
            lbl = tk.Label(grid_frame, text=friendly_name + ": ", font=("Segoe UI", 11, "bold"), bg="#27272a", fg="#f4f4f5", width=16, anchor="e")
            lbl.grid(row=row, column=col, padx=(0, 10), pady=12, sticky="e")
            
            var = tk.StringVar()
            self.mapping_vars[btn] = var
            
            cb = ttk.Combobox(grid_frame, textvariable=var, values=display_actions, state="readonly", width=22, style="Dark.TCombobox", font=("Segoe UI", 11))
            cb.grid(row=row, column=col+1, padx=(0, 40), pady=12, sticky="w")
            
        btn_frame = tk.Frame(container, bg="#27272a")
        btn_frame.pack(anchor="w", pady=(20, 0))
        
        save_btn = tk.Button(
            btn_frame, text="Save Mappings to Config", font=("Segoe UI", 10, "bold"),
            bg="#10b981", fg="#ffffff", activebackground="#059669", activeforeground="#ffffff",
            relief="flat", padx=16, pady=6, command=self._save_settings
        )
        save_btn.pack(side=tk.LEFT)
        
        self._load_schema_mappings()

    # -------------------------------------------------------------------------
    # SETTINGS TAB
    # -------------------------------------------------------------------------
    def _build_tuning_tab(self):
        container = tk.Frame(self.tab_tuning, bg="#27272a", padx=20, pady=18)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(container, text="Sensitivity & Dynamic Acceleration", font=("Segoe UI", 13, "bold"), bg="#27272a", fg="#ffffff").pack(anchor="w", pady=(0, 15))

        desktop_cfg = self.mapper.config.setdefault("schemas", {}).setdefault("desktop", {})
        mouse_cfg = desktop_cfg.get("mouse", {})
        scroll_cfg = desktop_cfg.get("scroll", {})

        self.speed_var = tk.DoubleVar(value=mouse_cfg.get("base_speed", 5.0))
        self._create_slider(container, "Cursor Base Speed:", self.speed_var, 1.0, 30.0, 0.5, "pixels/tick")

        self.exp_var = tk.DoubleVar(value=mouse_cfg.get("acceleration_exponent", 1.85))
        self._create_slider(container, "Acceleration Exponent (Curve):", self.exp_var, 1.0, 3.0, 0.05, "power")

        self.dz_var = tk.DoubleVar(value=mouse_cfg.get("deadzone", 0.18))
        self._create_slider(container, "Stick Deadzone Filter:", self.dz_var, 0.05, 0.40, 0.01, "radial")

        self.scroll_var = tk.DoubleVar(value=scroll_cfg.get("vertical_speed", 20.0))
        self._create_slider(container, "Scroll Speed (full tilt):", self.scroll_var, 2.0, 60.0, 1.0, "notch/s")

        self.prec_var = tk.DoubleVar(value=mouse_cfg.get("precision_multiplier", 0.28))
        self._create_slider(container, "LT Precision Aim Multiplier:", self.prec_var, 0.1, 0.6, 0.02, "factor")

        # Run on Startup Toggle
        self.startup_var = tk.BooleanVar(value=self._check_startup())
        startup_cb = tk.Checkbutton(
            container, text="Run on Windows Startup (System Tray)", 
            variable=self.startup_var, command=self._toggle_startup,
            font=("Segoe UI", 11, "bold"), bg="#27272a", fg="#ffffff", 
            selectcolor="#3f3f46", activebackground="#27272a", activeforeground="#10b981"
        )
        startup_cb.pack(anchor="w", pady=(20, 10))

        # Action Buttons
        act_frame = tk.Frame(container, bg="#27272a", pady=15)
        act_frame.pack(fill=tk.X)

        tk.Button(
            act_frame, text="💾 Save & Apply Settings", font=("Segoe UI", 10, "bold"),
            bg="#10b981", fg="#ffffff", activebackground="#059669", relief="flat", padx=14, pady=6,
            command=self._save_settings
        ).pack(side=tk.LEFT)

        tk.Button(
            act_frame, text="📳 Test Controller Rumble", font=("Segoe UI", 10),
            bg="#3f3f46", fg="#ffffff", relief="flat", padx=12, pady=6,
            command=self._test_rumble
        ).pack(side=tk.LEFT, padx=12)

    def _create_slider(self, parent, label_text: str, var: tk.DoubleVar, min_v: float, max_v: float, res: float, unit: str):
        row = tk.Frame(parent, bg="#27272a", pady=6)
        row.pack(fill=tk.X)
        val_lbl = tk.Label(row, text=f"{var.get():.2f} {unit}", font=("Segoe UI", 10, "bold"), bg="#27272a", fg="#34d399", width=12, anchor="e")
        val_lbl.pack(side=tk.RIGHT)
        
        def _on_change(val):
            val_lbl.config(text=f"{float(val):.2f} {unit}")
            self._apply_tuning_in_memory()

        scale = tk.Scale(
            row, from_=min_v, to=max_v, resolution=res, orient=tk.HORIZONTAL,
            variable=var, showvalue=0, command=_on_change, bg="#27272a",
            troughcolor="#18181b", activebackground="#3b82f6", highlightthickness=0, bd=0
        )
        scale.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)
        tk.Label(row, text=label_text, font=("Segoe UI", 10), bg="#27272a", fg="#e4e4e7", width=26, anchor="w").pack(side=tk.LEFT)

    def _get_startup_key(self):
        return winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)

    def _check_startup(self):
        try:
            with self._get_startup_key() as key:
                winreg.QueryValueEx(key, "XboxDesktopNavigator")
                return True
        except FileNotFoundError:
            return False

    def _toggle_startup(self):
        try:
            with self._get_startup_key() as key:
                if self.startup_var.get():
                    import sys
                    config_abs = os.path.abspath(self.config_path)
                    if getattr(sys, 'frozen', False):
                        target = f'"{sys.executable}" --config "{config_abs}"'
                    else:
                        target = f'"{sys.executable}" "{os.path.abspath("run.py")}" --config "{config_abs}"'
                    winreg.SetValueEx(key, "XboxDesktopNavigator", 0, winreg.REG_SZ, target)
                else:
                    winreg.DeleteValue(key, "XboxDesktopNavigator")
        except Exception as e:
            messagebox.showerror("Registry Error", f"Failed to modify startup registry: {e}")

    def _apply_tuning_in_memory(self):
        schema_name = getattr(self, "_current_mapping_schema_name", "desktop")
        active_cfg = self.mapper.config.setdefault("schemas", {}).setdefault(schema_name, {})
        
        # Only overwrite tuning fields if we are editing the desktop schema (or if we want them globally)
        # But we actually only track one slider for tuning. Let's just always write tuning to desktop 
        # or the active schema. Since tuning is mostly for desktop, let's keep it simple:
        desktop_cfg = self.mapper.config.setdefault("schemas", {}).setdefault("desktop", {})
        desktop_cfg.setdefault("mouse", {})
        desktop_cfg["mouse"]["base_speed"] = float(self.speed_var.get())
        desktop_cfg["mouse"]["acceleration_exponent"] = float(self.exp_var.get())
        desktop_cfg["mouse"]["deadzone"] = float(self.dz_var.get())
        desktop_cfg["mouse"]["precision_multiplier"] = float(self.prec_var.get())

        desktop_cfg.setdefault("scroll", {})
        desktop_cfg["scroll"]["vertical_speed"] = float(self.scroll_var.get())
        
        # Save button mappings to the ACTIVELY VIEWED schema and layer!
        if hasattr(self, "mapping_vars"):
            group_key = getattr(self, "_mapping_groups", {}).get(getattr(self, "mapping_group_var", tk.StringVar(value="Base Buttons")).get(), "buttons")
            buttons_cfg = active_cfg.setdefault(group_key, {})
            for btn, var in self.mapping_vars.items():
                display_val = var.get().strip()
                if display_val:
                    internal_val = display_val.lower().replace(" ", "_")
                    buttons_cfg[btn] = internal_val
                else:
                    buttons_cfg.pop(btn, None)

    def _save_settings(self):
        self._apply_tuning_in_memory()
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.mapper.config, f, indent=2)
            messagebox.showinfo("Saved", "Settings saved successfully to config.json!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def _test_rumble(self):
        self.mapper.driver.pulse_vibration(self.mapper.controller_index, pattern=[(0.6, 0.8, 0.15), (0.0, 0.0, 0.05), (0.8, 1.0, 0.2)])

    # -------------------------------------------------------------------------
    # STATE & THREAD SYNC
    # -------------------------------------------------------------------------
    def _toggle_mode(self):
        self.mapper.request_toggle()

    def _on_mode_change(self, is_enabled: bool):
        self._pending_mode = is_enabled

    def _apply_mode_ui(self, is_enabled: bool, auto_paused: bool = False):
        self._is_enabled = is_enabled
        if auto_paused:
            self.mode_badge.config(text="Game Detected (Auto-Paused)", bg="#7f1d1d", fg="#f87171")
            self.toggle_btn.config(text="Force Resume", bg="#10b981")
            self.cv.itemconfig(self.hud['guide_txt'], fill="#ef4444")
            self.cv.itemconfig(self.hud['guide_callout'], text="Game Mode (Auto-Paused)", fill="#ef4444", font=("Segoe UI", 10))
            self.cv.itemconfig(self.hud['guide_line'], fill="#ef4444")
        elif is_enabled:
            self.mode_badge.config(text="Desktop Mode Active", bg="#065f46", fg="#34d399")
            self.toggle_btn.config(text="Pause (Game Mode)", bg="#ef4444")
            self.cv.itemconfig(self.hud['guide_txt'], fill="#34d399")
            self.cv.itemconfig(self.hud['guide_callout'], text="Desktop Mode Active", fill="#34d399", font=("Segoe UI", 10, "bold"))
            self.cv.itemconfig(self.hud['guide_line'], fill="#10b981")
        else:
            self.mode_badge.config(text="Game Mode (Paused)", bg="#7f1d1d", fg="#f87171")
            self.toggle_btn.config(text="Resume Desktop", bg="#10b981")
            self.cv.itemconfig(self.hud['guide_txt'], fill="#ef4444")
            self.cv.itemconfig(self.hud['guide_callout'], text="Game Mode (Paused)", fill="#ef4444", font=("Segoe UI", 10))
            self.cv.itemconfig(self.hud['guide_line'], fill="#ef4444")

        # Sync the mapping tab dropdowns to match the actively running schema
        self._load_schema_mappings()

    def _on_telemetry(self, state: GamepadState, is_enabled: bool, auto_paused: bool = False):
        self._current_state = state
        self._connected = True
        
        # Only update mode UI if it actually changed
        if is_enabled != self._is_enabled or auto_paused != getattr(self, "_last_auto_paused", False):
            self._is_enabled = is_enabled
            self._last_auto_paused = auto_paused
            self._pending_mode = (is_enabled, auto_paused)


    # -------------------------------------------------------------------------
    # DYNAMIC RENDER LOOP
    # -------------------------------------------------------------------------
    def _update_btn_visual(self, name: str, is_pressed: bool):
        if is_pressed:
            self.cv.itemconfig(self.hud[f'btn_{name}'], fill="#10b981", outline="#34d399")
            self.cv.itemconfig(self.hud[f'txt_{name}'], fill="#ffffff")
            self.cv.itemconfig(self.hud[f'line_{name}'], fill="#10b981")
            self.cv.itemconfig(self.hud[f'lbl_{name}'], fill="#34d399", font=("Segoe UI", 10, "bold"))
        else:
            self.cv.itemconfig(self.hud[f'btn_{name}'], fill="#27272a", outline="#52525b")
            self.cv.itemconfig(self.hud[f'txt_{name}'], fill="#a1a1aa")
            self.cv.itemconfig(self.hud[f'line_{name}'], fill="#3f3f46")
            self.cv.itemconfig(self.hud[f'lbl_{name}'], fill="#a1a1aa", font=("Segoe UI", 10))

    def _refresh_gui_loop(self):
        try:
            pending = self._pending_mode
            if pending is not None:
                self._pending_mode = None
                if isinstance(pending, tuple):
                    self._apply_mode_ui(pending[0], pending[1])
                else:
                    self._apply_mode_ui(pending)

            if not self.mapper.connected:
                self._current_state = None
                
            state = self._current_state
            if state:
                # Triggers
                lt_w = 30 * state.left_trigger * 2
                self.cv.coords(self.hud['trig_bar_lt'], self.hud['base_x_lt'] - 30, self.hud['base_y_lt'] - 8, self.hud['base_x_lt'] - 30 + lt_w, self.hud['base_y_lt'] + 8)
                rt_w = 30 * state.right_trigger * 2
                self.cv.coords(self.hud['trig_bar_rt'], self.hud['base_x_rt'] - 30, self.hud['base_y_rt'] - 8, self.hud['base_x_rt'] - 30 + rt_w, self.hud['base_y_rt'] + 8)

                if state.left_trigger > 0.1:
                    self.cv.itemconfig(self.hud['line_lt'], fill="#10b981")
                    self.cv.itemconfig(self.hud['lbl_lt'], fill="#34d399", font=("Segoe UI", 10, "bold"))
                else:
                    self.cv.itemconfig(self.hud['line_lt'], fill="#3f3f46")
                    self.cv.itemconfig(self.hud['lbl_lt'], fill="#a1a1aa", font=("Segoe UI", 10))
                    
                if state.right_trigger > 0.1:
                    self.cv.itemconfig(self.hud['line_rt'], fill="#10b981")
                    self.cv.itemconfig(self.hud['lbl_rt'], fill="#34d399", font=("Segoe UI", 10, "bold"))
                else:
                    self.cv.itemconfig(self.hud['line_rt'], fill="#3f3f46")
                    self.cv.itemconfig(self.hud['lbl_rt'], fill="#a1a1aa", font=("Segoe UI", 10))

                # Buttons
                self._update_btn_visual("a", state.a)
                self._update_btn_visual("b", state.b)
                self._update_btn_visual("x", state.x)
                self._update_btn_visual("y", state.y)
                self._update_btn_visual("lb", state.left_shoulder)
                self._update_btn_visual("rb", state.right_shoulder)
                self._update_btn_visual("start", state.start)
                self._update_btn_visual("back", state.back)
                self._update_btn_visual("agl", getattr(state, "agl", False))
                self._update_btn_visual("agr", getattr(state, "agr", False))

                # D-Pad Cross & Media Layer dynamic callout
                dpad_active = state.dpad_up or state.dpad_down or state.dpad_left or state.dpad_right
                if dpad_active:
                    self.cv.itemconfig(self.hud['dpad_bg'], fill="#10b981", outline="#34d399")
                    self.cv.itemconfig(self.hud['line_dpad'], fill="#10b981")
                    self.cv.itemconfig(self.hud['lbl_dpad'], fill="#34d399", font=("Segoe UI", 10, "bold"))
                else:
                    self.cv.itemconfig(self.hud['dpad_bg'], fill="#27272a", outline="#52525b")
                    self.cv.itemconfig(self.hud['line_dpad'], fill="#3f3f46")
                    self.cv.itemconfig(self.hud['lbl_dpad'], fill="#a1a1aa", font=("Segoe UI", 10))
                
                # Contextual D-pad text
                if state.back:
                    self.cv.itemconfig(self.hud['lbl_dpad'], text="Vol Up/Down, Prev/Next Track")
                else:
                    self.cv.itemconfig(self.hud['lbl_dpad'], text="Arrow Keys\n(Hold Back: Media Layer)")

                desktop_cfg = self.mapper.config.get("schemas", {}).get("desktop", {})
                
                # Sticks (Positions & Clicks)
                dz = float(self.dz_var.get())
                rs_dz = float(desktop_cfg.get("scroll", {}).get("deadzone", 0.22))
                
                ls_r = 30 * dz
                self.cv.coords(self.hud['stick_dz_ls'], self.hud['base_x_ls'] - ls_r, self.hud['base_y_ls'] - ls_r, self.hud['base_x_ls'] + ls_r, self.hud['base_y_ls'] + ls_r)
                ls_dot_x = self.hud['base_x_ls'] + (state.thumb_lx * 20)
                ls_dot_y = self.hud['base_y_ls'] - (state.thumb_ly * 20)
                self.cv.coords(self.hud['stick_dot_ls'], ls_dot_x - 15, ls_dot_y - 15, ls_dot_x + 15, ls_dot_y + 15)
                
                rs_r = 30 * rs_dz
                self.cv.coords(self.hud['stick_dz_rs'], self.hud['base_x_rs'] - rs_r, self.hud['base_y_rs'] - rs_r, self.hud['base_x_rs'] + rs_r, self.hud['base_y_rs'] + rs_r)
                rs_dot_x = self.hud['base_x_rs'] + (state.thumb_rx * 20)
                rs_dot_y = self.hud['base_y_rs'] - (state.thumb_ry * 20)
                self.cv.coords(self.hud['stick_dot_rs'], rs_dot_x - 15, rs_dot_y - 15, rs_dot_x + 15, rs_dot_y + 15)

                if state.left_thumb_click:
                    self.cv.itemconfig(self.hud['stick_dot_ls'], fill="#34d399")
                    self.cv.itemconfig(self.hud['line_ls'], fill="#10b981")
                    self.cv.itemconfig(self.hud['lbl_ls'], fill="#34d399", font=("Segoe UI", 10, "bold"))
                else:
                    self.cv.itemconfig(self.hud['stick_dot_ls'], fill="#3f3f46" if math.hypot(state.thumb_lx, state.thumb_ly) < dz else "#10b981")
                    self.cv.itemconfig(self.hud['line_ls'], fill="#3f3f46")
                    self.cv.itemconfig(self.hud['lbl_ls'], fill="#a1a1aa", font=("Segoe UI", 10))
                    
                if state.right_thumb_click:
                    self.cv.itemconfig(self.hud['stick_dot_rs'], fill="#34d399")
                    self.cv.itemconfig(self.hud['line_rs'], fill="#10b981")
                    self.cv.itemconfig(self.hud['lbl_rs'], fill="#34d399", font=("Segoe UI", 10, "bold"))
                else:
                    self.cv.itemconfig(self.hud['stick_dot_rs'], fill="#3f3f46" if math.hypot(state.thumb_rx, state.thumb_ry) < rs_dz else "#10b981")
                    self.cv.itemconfig(self.hud['line_rs'], fill="#3f3f46")
                    self.cv.itemconfig(self.hud['lbl_rs'], fill="#a1a1aa", font=("Segoe UI", 10))

                # Radial Menu Trigger (Back button)
                schema = self.mapper.get_active_schema()
                if state.back and schema:
                    self.radial.show()
                    # Feed right stick inverted Y for standard cartesian math
                    self.radial.update_stick(state.thumb_rx, state.thumb_ry)
                else:
                    self.radial.hide()

                self.conn_label.config(text=f"🟢 Controller {self.mapper.controller_index} Connected", fg="#34d399")
            else:
                self.radial.hide()
                self.conn_label.config(text="🔴 No Xbox controller detected. Plug it in via USB or Wireless.", fg="#ef4444")

        except Exception:
            pass

        self.root.after(25, self._refresh_gui_loop)
