"""Via player — replay recorded routes with 3-tier fallback.

Replays a saved Via recording step by step. For each click, tries:
  1. AX locator (role + label) → click at element's CURRENT position
  2. Relative coordinates → window bounds + (rel_x, rel_y)
  3. Absolute coordinates → original (x, y) as last resort

For key events, replays the keystroke directly.
Checks for system dialogs between steps and handles them automatically.

Usage:
    from nexus.via.player import replay
    result = replay("gmail-login", speed=1.0)
"""

import time

from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListExcludeDesktopElements,
    kCGNullWindowID,
)

from nexus.act import input as raw_input
from nexus.mind import db
from nexus.sense.access import describe_app


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def replay(route_id, speed=1.0, pid=None):
    """Replay a saved Via route.

    Args:
        route_id: ID of the route to replay.
        speed: Timing multiplier (1.0 = original speed, 2.0 = 2x faster, 0 = no delays).
        pid: Target app PID (optional, overrides recorded PID).

    Returns dict with results.
    """
    route = db.via_route_get(route_id)
    if not route:
        return {"ok": False, "error": f'Via route "{route_id}" not found'}

    steps = db.via_steps_for_route(route_id)
    if not steps:
        return {"ok": False, "error": f'Via route "{route_id}" has no steps'}

    results = []
    prev_offset = 0

    for i, step in enumerate(steps):
        # Timing: respect original delays between events
        if speed > 0 and i > 0:
            delay = (step["ts_offset_ms"] - prev_offset) / 1000.0
            delay /= speed
            if delay > 0:
                # Cap delay at 5s to avoid extremely long waits
                time.sleep(min(delay, 5.0))
        prev_offset = step["ts_offset_ms"]

        # Check for system dialogs
        _handle_system_dialog()

        # Replay the event
        event_type = step["event_type"]
        step_result = {"step": i + 1, "type": event_type}

        if event_type == "click":
            result = _replay_click(step, pid=pid)
        elif event_type == "key":
            result = _replay_key(step)
        elif event_type == "scroll":
            result = _replay_scroll(step)
        else:
            result = {"ok": False, "error": f"Unknown event type: {event_type}"}

        step_result["ok"] = result.get("ok", False)
        step_result["method"] = result.get("method", "?")
        if not result.get("ok"):
            step_result["error"] = result.get("error", "unknown")
            results.append(step_result)
            return {
                "ok": False,
                "action": "via_replay",
                "route": route_id,
                "error": f"Step {i + 1} failed: {result.get('error', 'unknown')}",
                "completed": i,
                "total": len(steps),
                "steps": results,
            }

        results.append(step_result)

        # Brief pause between steps for UI to settle
        if i < len(steps) - 1:
            time.sleep(0.05)

    return {
        "ok": True,
        "action": "via_replay",
        "route": route_id,
        "completed": len(steps),
        "total": len(steps),
        "steps": results,
    }


# ---------------------------------------------------------------------------
# Click replay — 3-tier fallback
# ---------------------------------------------------------------------------

def _replay_click(step, pid=None):
    """Replay a click event with 3-tier fallback.

    Tier 1: AX locator (find element by role+label, click at current position)
    Tier 2: Relative coordinates (compute from current window bounds)
    Tier 3: Absolute coordinates (original screen position)
    """
    target_pid = pid or step.get("pid")
    ax_role = step.get("ax_role")
    ax_label = step.get("ax_label")
    button = step.get("button", "left")

    # Tier 1: AX locator — find element by role+label
    if ax_role and ax_label:
        pos = _find_element_position(ax_role, ax_label, target_pid)
        if pos:
            _do_click(pos[0], pos[1], button, step.get("modifiers"))
            return {"ok": True, "method": "ax_locator",
                    "target": f"{ax_label} ({ax_role.replace('AX', '')})"}

    # Tier 2: Relative coordinates
    if step.get("rel_x") is not None and step.get("rel_y") is not None:
        abs_pos = _relative_to_absolute(step, target_pid)
        if abs_pos:
            _do_click(abs_pos[0], abs_pos[1], button, step.get("modifiers"))
            return {"ok": True, "method": "relative_coords",
                    "at": abs_pos}

    # Tier 3: Absolute coordinates (original position)
    if step.get("x") is not None and step.get("y") is not None:
        _do_click(step["x"], step["y"], button, step.get("modifiers"))
        return {"ok": True, "method": "absolute_coords",
                "at": (step["x"], step["y"])}

    return {"ok": False, "error": "No position data for click"}


def _find_element_position(ax_role, ax_label, pid=None):
    """Find an element by AX role and label, return its center position.

    Returns (x, y) tuple or None.
    """
    try:
        elements = describe_app(pid=pid, max_elements=200)
        if not elements:
            return None

        for el in elements:
            if el.get("_ax_role") == ax_role and el.get("label") == ax_label:
                pos = el.get("pos")
                size = el.get("size")
                if pos and size:
                    # Return center of element
                    return (pos[0] + size[0] // 2, pos[1] + size[1] // 2)
                elif pos:
                    return pos
    except Exception:
        pass
    return None


def _relative_to_absolute(step, pid=None):
    """Convert relative coordinates to absolute using current window bounds.

    Returns (x, y) tuple or None.
    """
    rel_x = step["rel_x"]
    rel_y = step["rel_y"]

    # Get current window bounds for the app
    try:
        # Try to find any window for this app
        app_name = step.get("app_name")
        if pid or app_name:
            windows = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
                kCGNullWindowID,
            )
            for w in windows:
                wpid = w.get("kCGWindowOwnerPID")
                wname = w.get("kCGWindowOwnerName", "")
                if (pid and wpid == pid) or (app_name and wname == app_name):
                    bounds = w.get("kCGWindowBounds")
                    if bounds:
                        wx = int(bounds.get("X", 0))
                        wy = int(bounds.get("Y", 0))
                        ww = int(bounds.get("Width", 0))
                        wh = int(bounds.get("Height", 0))
                        if ww > 0 and wh > 0:
                            abs_x = int(wx + ww * rel_x)
                            abs_y = int(wy + wh * rel_y)
                            return (abs_x, abs_y)
                    break
    except Exception:
        pass

    # Fallback: use original window bounds from recording
    if all(step.get(k) is not None for k in ("window_x", "window_y", "window_w", "window_h")):
        abs_x = int(step["window_x"] + step["window_w"] * rel_x)
        abs_y = int(step["window_y"] + step["window_h"] * rel_y)
        return (abs_x, abs_y)

    return None


def _do_click(x, y, button="left", modifiers=None):
    """Execute a click at (x, y) with optional modifiers."""
    # Move to position
    raw_input.move_to(x, y)
    time.sleep(0.02)

    # Determine modifier keys to hold
    mod_keys = []
    if modifiers:
        if modifiers.get("cmd"):
            mod_keys.append("command")
        if modifiers.get("shift"):
            mod_keys.append("shift")
        if modifiers.get("ctrl"):
            mod_keys.append("ctrl")
        if modifiers.get("opt"):
            mod_keys.append("option")

    if button == "right":
        raw_input.right_click(x, y)
    elif mod_keys:
        raw_input.modifier_click(x, y, mod_keys)
    else:
        raw_input.click(x, y)


# ---------------------------------------------------------------------------
# Key replay
# ---------------------------------------------------------------------------

def _replay_key(step):
    """Replay a keyboard event."""
    key_char = step.get("key_char", "")
    key_code = step.get("key_code")
    modifiers = step.get("modifiers", {})

    if not key_char and key_code is None:
        return {"ok": False, "error": "No key data"}

    # Check if this is a shortcut (has modifiers beyond the key itself)
    has_mods = any(modifiers.get(m) for m in ("cmd", "ctrl", "opt"))

    if has_mods:
        # Keyboard shortcut: press as hotkey
        parts = []
        if modifiers.get("cmd"):
            parts.append("command")
        if modifiers.get("ctrl"):
            parts.append("ctrl")
        if modifiers.get("opt"):
            parts.append("option")
        if modifiers.get("shift"):
            parts.append("shift")
        # Extract the base key (last part of key_char after modifiers)
        base_key = key_char.split("+")[-1] if "+" in key_char else key_char
        parts.append(base_key)
        raw_input.hotkey(*parts)
        return {"ok": True, "method": "hotkey", "key": key_char}
    else:
        # Regular key press
        base_key = key_char.split("+")[-1] if "+" in key_char else key_char
        # For printable characters, type them; for special keys, press them
        if len(base_key) == 1:
            if modifiers.get("shift"):
                raw_input.hotkey("shift", base_key)
            else:
                raw_input.type_text(base_key)
        else:
            raw_input.press_key(base_key)
        return {"ok": True, "method": "keypress", "key": key_char}


# ---------------------------------------------------------------------------
# Scroll replay
# ---------------------------------------------------------------------------

def _replay_scroll(step):
    """Replay a scroll event."""
    x = step.get("x", 0)
    y = step.get("y", 0)
    direction = step.get("button", "down")

    clicks = 3 if direction == "down" else -3
    raw_input.scroll(clicks, x=x, y=y)
    return {"ok": True, "method": "scroll", "direction": direction}


# ---------------------------------------------------------------------------
# System dialog handling
# ---------------------------------------------------------------------------

def _handle_system_dialog():
    """Check for and auto-dismiss system dialogs during replay."""
    try:
        from nexus.sense.system import detect_system_dialogs
        dialogs = detect_system_dialogs()
        if not dialogs:
            return

        for dialog in dialogs:
            dtype = dialog.get("type", "unknown")
            # Auto-click the primary/allow button for known dialog types
            action = dialog.get("suggested_action")
            coords = dialog.get("button_coords", {})
            if action and action in coords:
                bx, by = coords[action]
                raw_input.click(bx, by)
                time.sleep(0.5)  # Wait for dialog to dismiss
    except Exception:
        pass
