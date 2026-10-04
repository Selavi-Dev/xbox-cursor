"""Xbox Desktop Controller Package"""

try:
    from version import __version__, VERSION_ID, CONTROL_PANEL_VERSION_ID
except ImportError:
    __version__ = "1.0.0"
    VERSION_ID = f"v{__version__}"
    CONTROL_PANEL_VERSION_ID = f"XboxDesktopNavigator-ControlPanel-{VERSION_ID}"
