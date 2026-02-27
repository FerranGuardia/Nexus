"""macOS native actions — accessibility actions + AppleScript.

Preferred over raw input because these are semantic:
"click the Save button" not "click at 340,220".
"""

import subprocess
from nexus.sense.access import (
    ax_attr, ax_perform, ax_set, ax_actions,
    find_elements, frontmost_app, describe_app,
    AXUIElementCreateApplication,
)
from nexus.state import emit


def click_element(name, pid=None, role=None):
    """Find an element by name and click it via accessibility action.

    Args:
        name: Text to search for (fuzzy matched against labels).
        pid: App PID (default: frontmost app).
        role: Optional role filter (e.g. "button", "link").

    Returns:
        dict with success/failure info.
    """
    matches = find_elements(name, pid)

    if role:
        role_lower = role.lower()
        from nexus.act.resolve import ROLE_MAP
        ax_target = ROLE_MAP.get(role_lower)
        matches = [
            m for m in matches
            if m.get("_ax_role") == ax_target or role_lower in m.get("role", "").lower()
        ]

    if not matches:
        # Give helpful feedback with fuzzy suggestions
        all_elements = describe_app(pid)
        available = [e["label"] for e in all_elements if e.get("label")]
        suggestions = _suggest(name, available)
        return {
            "ok": False,
            "error": f'Element "{name}" not found',
            "suggestions": suggestions,
            "available": available[:15],
        }

    target = matches[0]
    ref = target.get("_ref")
    label = target.get("label", name)
    role = target.get("role", "?")
    if not ref:
        return {"ok": False, "error": "No element reference available"}

    # Try AXPress first (buttons, links)
    actions = ax_actions(ref)
    if "AXPress" in actions:
        emit(f'Trying AXPress on [{role}] "{label}"...')
        success = ax_perform(ref, "AXPress")
        if success:
            return {
                "ok": True,
                "action": "AXPress",
                "element": _clean(target),
            }

    # Try AXConfirm
    if "AXConfirm" in actions:
        emit(f'Trying AXConfirm on [{role}] "{label}"...')
        success = ax_perform(ref, "AXConfirm")
        if success:
            return {
                "ok": True,
                "action": "AXConfirm",
                "element": _clean(target),
            }

    # Try AXShowMenu (for menus)
    if "AXShowMenu" in actions:
        emit(f'Trying AXShowMenu on [{role}] "{label}"...')
        success = ax_perform(ref, "AXShowMenu")
        if success:
            return {
                "ok": True,
                "action": "AXShowMenu",
                "element": _clean(target),
            }

    # Fallback: click at element center using coordinates
    pos = target.get("pos")
    size = target.get("size")
    if pos:
        from nexus.act.input import click as raw_click
        if size:
            cx = pos[0] + size[0] // 2
            cy = pos[1] + size[1] // 2
        else:
            cx, cy = pos[0], pos[1]  # pos IS the center (OCR/template elements)
        emit(f"AX actions failed, clicking at ({cx},{cy})...")
        raw_click(cx, cy)
        return {
            "ok": True,
            "action": "coordinate_click",
            "element": _clean(target),
            "at": [cx, cy],
        }

    return {
        "ok": False,
        "error": f'Found "{name}" but no way to click it',
        "actions_available": actions,
    }


def focus_element(name, pid=None):
    """Find and focus an element."""
    matches = find_elements(name, pid)
    if not matches:
        return {"ok": False, "error": f'Element "{name}" not found'}

    ref = matches[0].get("_ref")
    if ref:
        # Try to set focus
        success = ax_set(ref, "AXFocused", True)
        if success:
            return {"ok": True, "action": "focus", "element": _clean(matches[0])}

    # Fallback: click to focus
    return click_element(name, pid)


def set_value(name, value, pid=None):
    """Find an element and set its value (for text fields)."""
    matches = find_elements(name, pid)
    if not matches:
        return {"ok": False, "error": f'Element "{name}" not found'}

    ref = matches[0].get("_ref")
    if not ref:
        return {"ok": False, "error": "No element reference"}

    # Focus first
    ax_set(ref, "AXFocused", True)

    # Set value
    success = ax_set(ref, "AXValue", value)
    if success:
        return {"ok": True, "action": "set_value", "element": _clean(matches[0]), "value": value}

    # Fallback: focus + type
    focus_element(name, pid)
    from nexus.act.input import hotkey, type_text
    hotkey("command", "a")  # Select all existing text
    type_text(value)
    return {"ok": True, "action": "type_fallback", "element": _clean(matches[0]), "value": value}


def launch_app(name):
    """Launch an application by name via AppleScript.

    On macOS Sequoia, many apps launch without a window.
    If no window appears after activation, sends Cmd+N to create one.
    Returns the app's PID for use by callers (e.g. chain PID re-resolution).
    """
    script = f'tell application "{name}" to activate'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # Resolve PID and check for windows
    import time
    time.sleep(0.5)
    pid = _pid_for_app_name(name)

    if pid:
        app_ref = AXUIElementCreateApplication(pid)
        windows = ax_attr(app_ref, "AXWindows")
        if not windows or len(windows) == 0:
            # No window — send Cmd+N to create one (macOS convention)
            from nexus.act.input import hotkey
            hotkey("command", "n")
            time.sleep(0.3)

    return {"ok": True, "action": "launch", "app": name, "pid": pid}


def activate_window(app_name=None, title=None):
    """Bring a window to front."""
    if app_name:
        return launch_app(app_name)  # activate also brings to front
    return {"ok": False, "error": "Need app_name or title"}


def close_window():
    """Close the focused window via Cmd+W."""
    from nexus.act.input import hotkey
    hotkey("command", "w")
    return {"ok": True, "action": "close_window"}


def run_applescript(script):
    """Run arbitrary AppleScript and return the result."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "AppleScript timeout (30s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _suggest(query, labels, n=3):
    """Find the closest matching labels to a failed query.

    Scores each label based on:
      - Substring containment (bidirectional)
      - Shared word overlap
      - Length similarity as tiebreaker

    Returns the top N most similar labels.
    """
    if not labels:
        return []

    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored = []
    for label in labels:
        label_lower = label.lower()
        score = 0

        # Substring containment (bidirectional)
        if query_lower in label_lower:
            score += 3
        elif label_lower in query_lower:
            score += 2

        # Shared word overlap
        label_words = set(label_lower.split())
        shared = query_words & label_words
        if shared:
            score += len(shared) * 2

        # Partial word matches (prefix/suffix)
        if score == 0:
            for qw in query_words:
                for lw in label_words:
                    if lw.startswith(qw) or qw.startswith(lw):
                        score += 1

        if score > 0:
            # Length similarity as tiebreaker (closer length = higher)
            len_diff = abs(len(query) - len(label))
            score += max(0, 1 - len_diff / 20)
            scored.append((score, label))

    scored.sort(key=lambda x: -x[0])
    return [label for _, label in scored[:n]]


def _clean(el):
    """Remove internal _ref from element dict for serialization."""
    return {k: v for k, v in el.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Menu bar actions
# ---------------------------------------------------------------------------

def click_menu(path, pid=None):
    """Click a menu item by path (e.g. 'File > Save')."""
    from nexus.sense.access import find_menu_item, menu_bar
    item = find_menu_item(path, pid)
    if not item:
        available = [i["path"] for i in menu_bar(pid) if i.get("depth", 0) <= 1]
        return {
            "ok": False,
            "error": f'Menu item "{path}" not found',
            "available": available[:20],
        }

    ref = item.get("_ref")
    if ref:
        success = ax_perform(ref, "AXPress")
        if success:
            return {"ok": True, "action": "menu_click", "item": item["path"]}

    return {"ok": False, "error": f'Found "{path}" but could not click it'}


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------

def clipboard_read():
    """Read the system clipboard text."""
    result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
    return {"ok": True, "text": result.stdout}


def clipboard_write(text):
    """Write text to the system clipboard."""
    subprocess.run(["pbcopy"], input=text, text=True, timeout=5)
    return {"ok": True, "action": "clipboard_write", "length": len(text)}


# ---------------------------------------------------------------------------
# Window management
# ---------------------------------------------------------------------------

def _pid_for_app_name(name):
    """Resolve app name to PID from running apps."""
    from nexus.sense.access import running_apps
    name_lower = name.lower()
    for app in running_apps():
        if app["name"].lower() == name_lower:
            return app["pid"]
    # Partial match
    for app in running_apps():
        if name_lower in app["name"].lower():
            return app["pid"]
    return None


def move_window(app_name=None, x=None, y=None, w=None, h=None, window_index=1):
    """Move/resize a window via AppleScript System Events."""
    if not app_name:
        info = frontmost_app()
        if info:
            app_name = info["name"]
    if not app_name:
        return {"ok": False, "error": "No app specified"}

    parts = []
    if x is not None and y is not None:
        parts.append(f"set position of window {window_index} to {{{x}, {y}}}")
    if w is not None and h is not None:
        parts.append(f"set size of window {window_index} to {{{w}, {h}}}")

    if not parts:
        return {"ok": False, "error": "Need position (x,y) or size (w,h)"}

    actions = "\n            ".join(parts)
    script = f'''
        tell application "System Events"
            tell process "{app_name}"
                {actions}
            end tell
        end tell
    '''
    return run_applescript(script)


def minimize_window(app_name=None, window_index=1):
    """Minimize a window via AppleScript System Events."""
    if not app_name:
        info = frontmost_app()
        if info:
            app_name = info["name"]
    if not app_name:
        return {"ok": False, "error": "No app specified"}

    script = f'''
        tell application "System Events"
            tell process "{app_name}"
                set miniaturized of window {window_index} to true
            end tell
        end tell
    '''
    result = run_applescript(script)
    if result.get("ok"):
        return {"ok": True, "action": "minimize", "app": app_name, "window": window_index}
    return result


def unminimize_window(app_name=None):
    """Restore (unminimize) an app's window."""
    if not app_name:
        info = frontmost_app()
        if info:
            app_name = info["name"]
    if not app_name:
        return {"ok": False, "error": "No app specified"}

    script = f'''
        tell application "{app_name}" to activate
        delay 0.3
        tell application "System Events"
            tell process "{app_name}"
                try
                    set miniaturized of window 1 to false
                end try
            end tell
        end tell
    '''
    result = run_applescript(script)
    if result.get("ok"):
        return {"ok": True, "action": "unminimize", "app": app_name}
    return result


def resize_window(app_name=None, w=None, h=None, window_index=1):
    """Resize a window without moving it."""
    if not app_name:
        info = frontmost_app()
        if info:
            app_name = info["name"]
    if not app_name:
        return {"ok": False, "error": "No app specified"}
    if w is None or h is None:
        return {"ok": False, "error": "Need width and height"}

    script = f'''
        tell application "System Events"
            tell process "{app_name}"
                set size of window {window_index} to {{{w}, {h}}}
            end tell
        end tell
    '''
    result = run_applescript(script)
    if result.get("ok"):
        return {"ok": True, "action": "resize", "app": app_name, "size": [w, h]}
    return result


def fullscreen_window(app_name=None):
    """Toggle true macOS fullscreen (green button) for an app's window."""
    if not app_name:
        info = frontmost_app()
        if info:
            app_name = info["name"]
            pid = info["pid"]
        else:
            return {"ok": False, "error": "No app specified"}
    else:
        pid = _pid_for_app_name(app_name)
        if not pid:
            return {"ok": False, "error": f"App '{app_name}' not found"}

    # Try AXFullScreen attribute (most reliable)
    app_ref = AXUIElementCreateApplication(pid)
    window = ax_attr(app_ref, "AXFocusedWindow") or ax_attr(app_ref, "AXMainWindow")
    if window:
        current = ax_attr(window, "AXFullScreen")
        target = not bool(current) if current is not None else True
        success = ax_set(window, "AXFullScreen", target)
        if success:
            action = "enter_fullscreen" if target else "exit_fullscreen"
            return {"ok": True, "action": action, "app": app_name}

    # Fallback: Ctrl+Cmd+F (standard fullscreen shortcut)
    from nexus.act.input import hotkey
    launch_app(app_name)
    import time
    time.sleep(0.2)
    hotkey("command", "ctrl", "f")
    return {"ok": True, "action": "toggle_fullscreen", "app": app_name, "via": "shortcut"}


def window_info(app_name=None):
    """Get window position, size, and state for an app."""
    if not app_name:
        info = frontmost_app()
        if info:
            app_name = info["name"]
            pid = info["pid"]
        else:
            return {"ok": False, "error": "No app specified"}
    else:
        pid = _pid_for_app_name(app_name)
        if not pid:
            return {"ok": False, "error": f"App '{app_name}' not found"}

    from nexus.sense.access import _extract_point, _extract_size
    app_ref = AXUIElementCreateApplication(pid)
    window = ax_attr(app_ref, "AXFocusedWindow") or ax_attr(app_ref, "AXMainWindow")
    if not window:
        return {"ok": False, "error": f"No window found for {app_name}"}

    pos = _extract_point(ax_attr(window, "AXPosition"))
    sz = _extract_size(ax_attr(window, "AXSize"))
    title = ax_attr(window, "AXTitle") or ""
    minimized = ax_attr(window, "AXMinimized")
    fullscreen = ax_attr(window, "AXFullScreen")

    return {
        "ok": True,
        "action": "window_info",
        "app": app_name,
        "title": title,
        "x": pos[0] if pos else 0,
        "y": pos[1] if pos else 0,
        "w": sz[0] if sz else 0,
        "h": sz[1] if sz else 0,
        "minimized": bool(minimized) if minimized is not None else False,
        "fullscreen": bool(fullscreen) if fullscreen is not None else False,
    }


def tile_windows(app1, app2):
    """Tile two apps side by side (left/right halves)."""
    from nexus.act.input import screen_size
    sz = screen_size()
    half_w = sz["width"] // 2
    h = sz["height"] - 25  # Account for menu bar

    r1 = move_window(app1, x=0, y=25, w=half_w, h=h)
    r2 = move_window(app2, x=half_w, y=25, w=half_w, h=h)

    # Bring both to front
    launch_app(app1)
    launch_app(app2)

    ok = r1.get("ok", False) or r2.get("ok", False)
    return {"ok": ok, "action": "tile", "layout": "side_by_side", "apps": [app1, app2]}


def maximize_window(app_name=None):
    """Maximize a window to fill the screen (not fullscreen mode)."""
    from nexus.act.input import screen_size
    sz = screen_size()
    return move_window(app_name, x=0, y=25, w=sz["width"], h=sz["height"] - 25)


# ---------------------------------------------------------------------------
# App-specific AppleScript powers
# ---------------------------------------------------------------------------

def safari_url():
    """Get the current URL from Safari's front tab."""
    result = run_applescript(
        'tell application "Safari" to get URL of current tab of front window'
    )
    if result.get("ok"):
        return {"ok": True, "url": result["stdout"]}
    return result


def safari_tabs():
    """List all tab names in Safari's front window."""
    result = run_applescript(
        'tell application "Safari" to get name of every tab of front window'
    )
    if result.get("ok"):
        tabs = [t.strip() for t in result["stdout"].split(",")]
        return {"ok": True, "tabs": tabs}
    return result


def safari_source():
    """Get the HTML source of Safari's current page."""
    result = run_applescript(
        'tell application "Safari" to get source of current tab of front window'
    )
    if result.get("ok"):
        return {"ok": True, "source": result["stdout"][:5000]}
    return result


def finder_selection():
    """Get the currently selected files in Finder."""
    result = run_applescript(
        'tell application "Finder" to get POSIX path of (selection as alias list)'
    )
    if result.get("ok"):
        paths = [p.strip() for p in result["stdout"].split(",") if p.strip()]
        return {"ok": True, "paths": paths}
    return result


def notify(title, message=""):
    """Show a macOS notification."""
    msg_part = f'subtitle "{message}"' if message else ""
    script = f'display notification "{message}" with title "{title}"'
    return run_applescript(script)


def say(text):
    """Speak text aloud using macOS text-to-speech."""
    return run_applescript(f'say "{text}"')
