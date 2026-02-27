"""System control recipes — volume, mute, dark mode, lock, sleep, screenshot, permissions."""

from nexus.via.recipe import recipe, applescript, cli


@recipe(r"set volume (?:to )?(\d+)")
def set_volume(m, pid=None):
    """Set system volume (0-100)."""
    level = min(100, max(0, int(m.group(1))))
    return applescript(f"set volume output volume {level}")


@recipe(r"(?:get |check )?(?:current )?volume")
def get_volume(m, pid=None):
    """Get current volume level."""
    return applescript("output volume of (get volume settings)")


@recipe(r"(?:toggle )?mute|unmute")
def toggle_mute(m, pid=None):
    """Toggle audio mute."""
    return applescript(
        "set volume with output muted (not (output muted of (get volume settings)))"
    )


@recipe(r"(?:toggle |switch (?:to )?)?dark mode|(?:enable|disable) dark mode")
def toggle_dark_mode(m, pid=None):
    """Toggle macOS dark mode."""
    return applescript(
        'tell app "System Events" to tell appearance preferences '
        "to set dark mode to not dark mode"
    )


@recipe(r"(?:lock|lock screen|lock display)")
def lock_screen(m, pid=None):
    """Lock the screen."""
    return cli(
        "/System/Library/CoreServices/Menu\\ Extras/User.menu"
        "/Contents/Resources/CGSession -suspend"
    )


@recipe(r"(?:sleep|sleep display|display sleep)")
def sleep_display(m, pid=None):
    """Put display to sleep."""
    return cli("pmset displaysleepnow")


@recipe(r"(?:take )?screenshot(?: (?:of )?(?:the )?(.+))?")
def screenshot(m, pid=None):
    """Take a screenshot. Optional region/window target."""
    import time
    path = f"/tmp/screenshot-{int(time.time())}.png"
    target = m.group(1)
    if target and target.strip().lower() in ("screen", "full", "desktop"):
        target = None
    if target:
        # Delegate to screencapture interactive if target specified
        return cli(f"screencapture -x -i {path}")
    return cli(f"screencapture -x {path}")


@recipe(r"(?:get |what is (?:the )?)?battery (?:level|status|percentage|%)")
def battery_status(m, pid=None):
    """Get battery percentage."""
    return cli("pmset -g batt | grep -o '[0-9]*%'")


@recipe(r"(?:get |check )?wifi (?:name|ssid|network)")
def wifi_name(m, pid=None):
    """Get current Wi-Fi network name."""
    return cli(
        "/System/Library/PrivateFrameworks/Apple80211.framework"
        "/Resources/airport -I | awk '/ SSID:/{print $2}'"
    )


@recipe(r"(?:set )?brightness (?:to )?(\d+)")
def set_brightness(m, pid=None):
    """Set display brightness (0-100). Requires brightness CLI tool."""
    level = min(100, max(0, int(m.group(1))))
    normalized = level / 100.0
    return applescript(
        f'tell app "System Events" to tell process "Control Center" '
        f"to set value of slider 1 of group 1 to {normalized}"
    )


@recipe(r"^(?:check |show |get )?permissions?(?: status)?$")
def check_permissions_recipe(m, pid=None):
    """Check Nexus permission status."""
    from nexus.mind.permissions import check_permissions

    result = check_permissions()
    return {"ok": True, "result": result["summary"], "text": result["summary"]}
