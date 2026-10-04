"""Zero-dependency active window and process tracker for context profiles & auto-pause."""

import ctypes
from ctypes import wintypes
from typing import Tuple, Optional

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

# Constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MONITOR_DEFAULTTONEAREST = 2

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD)
    ]

def get_active_window_info() -> Tuple[str, bool]:
    """
    Returns (process_name, is_fullscreen).
    process_name: Lowercase name of the active executable (e.g., 'chrome.exe').
    is_fullscreen: True if the window fills the monitor it is on.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", False

    # Get Process Name
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    
    h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    proc_name = ""
    if h_process:
        buffer = ctypes.create_unicode_buffer(260)
        if psapi.GetModuleBaseNameW(h_process, None, buffer, 260):
            proc_name = buffer.value.lower()
        kernel32.CloseHandle(h_process)

    # Ignore desktop and shell overlays
    if proc_name in ["explorer.exe", "searchapp.exe", "shellexperiencehost.exe"]:
        return proc_name, False

    # Check Fullscreen
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    
    hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not hmon:
        return proc_name, False
        
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
        return proc_name, False

    is_fullscreen = (
        rect.left <= mi.rcMonitor.left and
        rect.top <= mi.rcMonitor.top and
        rect.right >= mi.rcMonitor.right and
        rect.bottom >= mi.rcMonitor.bottom
    )

    return proc_name, is_fullscreen
