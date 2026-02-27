"""System Settings recipes — open panes via URL schemes."""

from nexus.via.recipe import recipe, url_scheme


_PANE_URLS = {
    "wifi": "x-apple.systempreferences:com.apple.wifi-settings-extension",
    "wi-fi": "x-apple.systempreferences:com.apple.wifi-settings-extension",
    "bluetooth": "x-apple.systempreferences:com.apple.BluetoothSettings",
    "sound": "x-apple.systempreferences:com.apple.Sound-Settings.extension",
    "audio": "x-apple.systempreferences:com.apple.Sound-Settings.extension",
    "display": "x-apple.systempreferences:com.apple.Displays-Settings.extension",
    "displays": "x-apple.systempreferences:com.apple.Displays-Settings.extension",
    "keyboard": "x-apple.systempreferences:com.apple.Keyboard-Settings.extension",
    "trackpad": "x-apple.systempreferences:com.apple.Trackpad-Settings.extension",
    "mouse": "x-apple.systempreferences:com.apple.Mouse-Settings.extension",
    "accessibility": "x-apple.systempreferences:com.apple.Accessibility-Settings.extension",
    "privacy": "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension",
    "security": "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension",
    "notifications": "x-apple.systempreferences:com.apple.Notifications-Settings.extension",
    "general": "x-apple.systempreferences:com.apple.General-Settings.extension",
    "network": "x-apple.systempreferences:com.apple.Network-Settings.extension",
    "battery": "x-apple.systempreferences:com.apple.Battery-Settings.extension",
    "wallpaper": "x-apple.systempreferences:com.apple.Wallpaper-Settings.extension",
    "screen saver": "x-apple.systempreferences:com.apple.ScreenSaver-Settings.extension",
    "screensaver": "x-apple.systempreferences:com.apple.ScreenSaver-Settings.extension",
    "desktop": "x-apple.systempreferences:com.apple.Desktop-Settings.extension",
    "dock": "x-apple.systempreferences:com.apple.Desktop-Settings.extension",
    "focus": "x-apple.systempreferences:com.apple.Focus-Settings.extension",
    "siri": "x-apple.systempreferences:com.apple.Siri-Settings.extension",
    "spotlight": "x-apple.systempreferences:com.apple.Spotlight-Settings.extension",
    "printers": "x-apple.systempreferences:com.apple.Print-Scan-Settings.extension",
    "printers & scanners": "x-apple.systempreferences:com.apple.Print-Scan-Settings.extension",
    "date": "x-apple.systempreferences:com.apple.Date-Time-Settings.extension",
    "time": "x-apple.systempreferences:com.apple.Date-Time-Settings.extension",
    "users": "x-apple.systempreferences:com.apple.Users-Groups-Settings.extension",
    "sharing": "x-apple.systempreferences:com.apple.Sharing-Settings.extension",
    "startup": "x-apple.systempreferences:com.apple.LoginItems-Settings.extension",
    "login items": "x-apple.systempreferences:com.apple.LoginItems-Settings.extension",
    "storage": "x-apple.systempreferences:com.apple.settings.Storage",
    "vpn": "x-apple.systempreferences:com.apple.NetworkExtensionSettingsUI.NESettingsUIExtension",
}


@recipe(r"(?:open )?(?:system )?settings?\s+(?:for\s+)?(.+)")
def open_settings(m, pid=None):
    """Open a System Settings pane by name."""
    pane = m.group(1).lower().strip()
    url = _PANE_URLS.get(pane)
    if url:
        return url_scheme(url)
    # Try partial match
    for key, val in _PANE_URLS.items():
        if pane in key or key in pane:
            return url_scheme(val)
    known = ", ".join(sorted(_PANE_URLS.keys()))
    return {"ok": False, "error": f"Unknown pane: {pane}. Known: {known}"}
