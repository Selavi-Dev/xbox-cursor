"""Zero-dependency active window and process tracker for context profiles & auto-pause."""

import ctypes
from ctypes import wintypes
from typing import Tuple, Optional
import os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Constants
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MONITOR_DEFAULTTONEAREST = 2

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD)
    ]

# 64-bit safe signatures
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]

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
    
    h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    proc_name = ""
    if h_process:
        buffer = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h_process, 0, buffer, ctypes.byref(size)):
            proc_name = os.path.basename(buffer.value).lower()
        kernel32.CloseHandle(h_process)

    # Ignore desktop, shell overlays, browsers, and media players for fullscreen detection
    ignore_list = [
        "explorer.exe", "searchapp.exe", "shellexperiencehost.exe",
        "chrome.exe", "msedge.exe", "firefox.exe", "vlc.exe", "mpc-hc64.exe"
    ]
    if proc_name in ignore_list:
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
