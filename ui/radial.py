"""Transparent Radial Menu Tkinter Overlay"""

import tkinter as tk
import math
from typing import Callable, List, Optional

class RadialMenu:
    def __init__(self, actions: List[dict], on_select: Callable[[str], None]):
        self.actions = actions
        self.on_select = on_select
        
        self.root = tk.Toplevel()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Transparent background trick
        self.bg_color = "#010101"
        self.root.config(bg=self.bg_color)
        self.root.attributes("-transparentcolor", self.bg_color)
        
        self.size = 500
        self.root.geometry(f"{self.size}x{self.size}")
        
        # Center the window on screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = int((screen_width / 2) - (self.size / 2))
        y = int((screen_height / 2) - (self.size / 2))
        self.root.geometry(f"+{x}+{y}")
        
        self.canvas = tk.Canvas(self.root, width=self.size, height=self.size, bg=self.bg_color, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.is_open = False
        self.selected_index = -1
        self.root.withdraw()

    def update_stick(self, x: float, y: float):
        if not self.is_open:
            return
            
        mag = math.hypot(x, y)
        if mag > 0.4:
            angle = math.degrees(math.atan2(y, x))
            if angle < 0:
                angle += 360
                
            num_slices = len(self.actions)
            slice_angle = 360 / num_slices
            
            # Offset by half a slice so stick straight right = index 0 perfectly centered
            adjusted = (angle + (slice_angle / 2)) % 360
            idx = int(adjusted // slice_angle)
            
            if idx != self.selected_index:
                self.selected_index = idx
                self.draw()
        else:
            if self.selected_index != -1:
                self.selected_index = -1
                self.draw()

    def draw(self):
        self.canvas.delete("all")
        
        cx = self.size / 2
        cy = self.size / 2
        outer_r = 200
        inner_r = 60
        
        num_slices = len(self.actions)
        slice_angle = 360 / num_slices
        
        for i, item in enumerate(self.actions):
            start_ang = i * slice_angle - (slice_angle / 2)
            
            # Colors
            if i == self.selected_index:
                fill = "#10b981" # Emerald active
                outline = "#34d399"
                txt_fill = "#ffffff"
            else:
                fill = "#27272a" # Zinc inactive
                outline = "#3f3f46"
                txt_fill = "#a1a1aa"
                
            # Draw slice (using an arc)
            self.canvas.create_arc(
                cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r,
                start=start_ang, extent=slice_angle,
                fill=fill, outline=outline, width=3, style=tk.PIESLICE
            )
            
            # Draw label
            mid_ang = math.radians(start_ang + (slice_angle / 2))
            # Text radius
            tr = inner_r + (outer_r - inner_r) / 2
            tx = cx + math.cos(mid_ang) * tr
            ty = cy - math.sin(mid_ang) * tr # Invert Y for canvas
            
            self.canvas.create_text(tx, ty, text=item["label"], fill=txt_fill, font=("Segoe UI", 12, "bold"), justify="center")
            
        # Draw inner cutout to make it a ring
        self.canvas.create_oval(cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r, fill=self.bg_color, outline="#3f3f46", width=4)
        
        # Center dot/icon
        self.canvas.create_oval(cx - 15, cy - 15, cx + 15, cy + 15, fill="#3f3f46", outline="#71717a")

    def show(self):
        if not self.is_open:
            self.is_open = True
            self.selected_index = -1
            self.draw()
            self.root.deiconify()
            self.root.lift()

    def hide(self):
        if self.is_open:
            self.is_open = False
            self.root.withdraw()
            if self.selected_index != -1 and self.selected_index < len(self.actions):
                action = self.actions[self.selected_index]["action"]
                self.on_select(action)
