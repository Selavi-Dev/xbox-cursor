"""Main entry point for Xbox Desktop Controller."""

import argparse
import json
import os
import signal
import sys
import threading
import time
from typing import Optional

from controller.xinput import XInputDriver, GamepadState
from controller.win32_input import Win32Input
from controller.mapper import InputMapper


def load_config(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Warning] Failed to load {path}: {e}. Using defaults.")
    return {}


class ControllerService:
    """Manages the polling loop, reconnection, and mapper dispatch."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = load_config(config_path)
        self.driver = XInputDriver()
        self.win = Win32Input()
        self.mapper = InputMapper(self.config, self.driver, self.win)

        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.controller_index: Optional[int] = None

    def start(self):
        self.running = True
        self.worker_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        self.mapper.actions.release_all()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)

    def _poll_loop(self):
        """High-frequency polling loop (120Hz default)."""
        poll_hz = self.config.get("schemas", {}).get("desktop", {}).get("mouse", {}).get("poll_rate_hz", 120)
        poll_interval = 1.0 / max(30, min(240, poll_hz))

        reconnect_check_interval = 1.0
        last_reconnect_check = 0.0

        while self.running:
            t0 = time.perf_counter()

            # Controller connection discovery
            if self.controller_index is None:
                if t0 - last_reconnect_check > reconnect_check_interval:
                    self.controller_index = self.driver.find_connected_controller()
                    if self.controller_index is not None:
                        self.mapper.controller_index = self.controller_index
                        self.mapper.set_connected(True)
                        print(f"[Xbox Controller] Controller {self.controller_index} connected.")
                    last_reconnect_check = t0
                time.sleep(0.05)
                continue

            # Poll gamepad state
            state = self.driver.get_state(self.controller_index)
            if state is None:
                print(f"[Xbox Controller] Controller {self.controller_index} disconnected.")
                self.controller_index = None
                self.mapper.set_connected(False)
                continue

            # Process state
            self.mapper.process_frame(state)

            # High precision timing
            elapsed = time.perf_counter() - t0
            sleep_time = poll_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)


def run_cli_mode(service: ControllerService):
    """Runs in command-line interface mode with terminal feedback."""
    print("=" * 60)
    print(" 🎮 XBOX CONTROLLER DESKTOP NAVIGATOR (CLI MODE)")
    print("=" * 60)
    print("Status: Active")
    print("Press Ctrl+C to stop.")
    print("Tip: Hold Back + Start for 1.2s to toggle Desktop vs Game Mode.")
    print("=" * 60)

    service.start()

    def _signal_handler(sig, frame):
        print("\nStopping controller service...")
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        service.stop()


def run_gui_mode(service: ControllerService):
    """Launches the interactive Tkinter GUI control panel."""
    import tkinter as tk
    from ui.gui import ControllerAppGUI

    service.start()

    root = tk.Tk()
    
    # Store service stop on app for clean exit
    def _full_quit():
        service.stop()
        root.destroy()
        
    app = ControllerAppGUI(root, service.mapper, service.config_path)
    # Give the app a way to fully quit when Tray->Quit is clicked
    app._quit_callback = _full_quit

    root.mainloop()


def main():
    # Must run before Tk or any Win32 screen metrics are queried.
    from controller.win32_input import enable_dpi_awareness
    enable_dpi_awareness()

    parser = argparse.ArgumentParser(description="Xbox Controller Desktop Navigator")
    parser.add_argument("--cli", action="store_true", help="Run in headless console mode without GUI")
    parser.add_argument("--config", default="config.json", help="Path to config.json file")
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    service = ControllerService(config_path=config_path)

    if args.cli:
        run_cli_mode(service)
    else:
        run_gui_mode(service)


if __name__ == "__main__":
    main()
