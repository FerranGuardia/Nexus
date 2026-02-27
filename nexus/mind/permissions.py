"""Runtime permission checker — probes macOS permission state.

Returns a structured report of what Nexus can and cannot do.
No new dependencies — uses existing pyobjc + subprocess.
"""

import os
import subprocess
from pathlib import Path


def check_permissions():
    """Check all permission types relevant to Nexus.

    Returns dict with:
        accessibility: bool
        apple_events: dict[str, bool]
        full_disk_access: bool
        screen_recording: bool
        sudoers: bool
        auto_dismiss: bool
        all_ok: bool
        summary: str
    """
    result = {}

    result["accessibility"] = _check_accessibility()
    result["apple_events"] = _check_apple_events()
    result["full_disk_access"] = _check_full_disk_access()
    result["screen_recording"] = _check_screen_recording()
    result["sudoers"] = _check_sudoers()
    result["auto_dismiss"] = _check_auto_dismiss()

    result["all_ok"] = result["accessibility"] and result["screen_recording"]
    result["summary"] = _format_summary(result)

    return result


def _check_accessibility():
    """Check AXIsProcessTrusted."""
    try:
        from ApplicationServices import AXIsProcessTrusted

        return bool(AXIsProcessTrusted())
    except Exception:
        return False


def _check_apple_events():
    """Test Apple Events consent for key apps.

    Runs a harmless osascript for each app.  If consent is not
    granted, osascript returns error code -1743.
    """
    apps = ["System Events", "Finder"]
    results = {}
    for app in apps:
        try:
            r = subprocess.run(
                ["osascript", "-e", f'tell application "{app}" to return ""'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            results[app] = r.returncode == 0
        except Exception:
            results[app] = False
    return results


def _check_full_disk_access():
    """Check if we can read the TCC database (requires FDA)."""
    tcc = Path.home() / "Library/Application Support/com.apple.TCC/TCC.db"
    try:
        return tcc.exists() and os.access(str(tcc), os.R_OK)
    except Exception:
        return False


def _check_screen_recording():
    """Check screen recording permission via 1x1 screenshot attempt."""
    try:
        from Quartz import (
            CGImageGetWidth,
            CGRectMake,
            CGWindowListCreateImage,
            kCGNullWindowID,
            kCGWindowImageDefault,
            kCGWindowListOptionOnScreenOnly,
        )

        img = CGWindowListCreateImage(
            CGRectMake(0, 0, 1, 1),
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
            kCGWindowImageDefault,
        )
        return img is not None and CGImageGetWidth(img) > 0
    except Exception:
        return False


def _check_sudoers():
    """Check if /etc/sudoers.d/nexus exists."""
    return Path("/etc/sudoers.d/nexus").exists()


def _check_auto_dismiss():
    """Check the auto_dismiss memory preference."""
    try:
        from nexus.mind.store import _get

        val = _get("auto_dismiss")
        return val in (True, "true", "True", "1")
    except Exception:
        return False


def _format_summary(result):
    """Format a compact text summary of permission status."""
    lines = []

    def _status(ok, label, critical=False):
        mark = "OK" if ok else ("MISSING" if critical else "off")
        lines.append(f"  {label}: {mark}")

    lines.append("Nexus Permission Status:")
    _status(result["accessibility"], "Accessibility", critical=True)
    _status(result["screen_recording"], "Screen Recording", critical=True)
    _status(result["full_disk_access"], "Full Disk Access")
    _status(result["sudoers"], "Sudoers (NOPASSWD)")

    ae = result.get("apple_events", {})
    ae_ok = all(ae.values()) if ae else False
    _status(ae_ok, f"Apple Events ({len(ae)} apps)")

    _status(result["auto_dismiss"], "Auto-dismiss dialogs")

    if not result["accessibility"]:
        lines.append("")
        lines.append("  Run ./nexus-setup.sh or enable in System Settings >")
        lines.append("  Privacy & Security > Accessibility.")

    if not result["screen_recording"]:
        lines.append("")
        lines.append("  Screen Recording needed for screenshots.")
        lines.append("  Enable in System Settings > Privacy & Security > Screen Recording.")

    return "\n".join(lines)
