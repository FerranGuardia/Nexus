"""Unified perception — the `see` tool.

Fuses accessibility tree, window list, and screenshots into
a single, token-efficient text snapshot of the computer.
"""

from nexus.sense import access, screen

# Snapshot storage for diff mode
_last_snapshot = None


def see(app=None, query=None, screenshot=False, menus=False, diff=False):
    """Main perception function. Returns a text snapshot of the computer.

    Args:
        app: App name or PID to look at (default: frontmost).
        query: Search for specific elements instead of full tree.
        screenshot: Include a base64 screenshot.
        menus: Include the app's menu bar items (shows available commands).
        diff: Compare with previous snapshot — show what changed.

    Returns:
        dict with 'text' (always) and optionally 'image' (base64 JPEG).
    """
    global _last_snapshot

    trusted = access.is_trusted()

    pid = _resolve_pid(app)
    result_parts = []
    image_data = None

    if not trusted:
        result_parts.append(
            "NOTE: Accessibility permission not granted. "
            "Enable your terminal/IDE in System Settings > Privacy & Security > Accessibility. "
            "Showing limited info (windows + screenshot only)."
        )
        result_parts.append("")

    # App + Window header
    app_info = access.frontmost_app() if pid is None else _app_info_for_pid(pid)
    if app_info:
        win_title = access.window_title(pid)
        header = f"App: {app_info['name']}"
        if win_title:
            header += f' — "{win_title}"'
        result_parts.append(header)

    # Focused element
    focus = access.focused_element(pid)
    if focus:
        focus_line = f"Focus: {_format_element(focus)}"
        result_parts.append(focus_line)

    # Windows list
    wins = access.windows()
    if wins:
        result_parts.append("")
        result_parts.append(f"Windows ({len(wins)}):")
        for w in wins[:15]:
            title_part = f' — "{w["title"]}"' if w["title"] else ""
            result_parts.append(f'  {w["app"]}{title_part}')

    # Menu bar (what commands are available)
    if menus:
        menu_items = access.menu_bar(pid)
        if menu_items:
            result_parts.append("")
            result_parts.append(f"Menus ({len(menu_items)} items):")
            for item in menu_items:
                indent = "  " * (item["depth"] + 1)
                shortcut = f' ({item["shortcut"]})' if item.get("shortcut") else ""
                disabled = " (disabled)" if item.get("enabled") is False else ""
                result_parts.append(f'{indent}{item["path"]}{shortcut}{disabled}')

    # Elements (search or full tree)
    result_parts.append("")
    if query:
        elements = access.find_elements(query, pid)
        result_parts.append(f'Search "{query}" ({len(elements)} matches):')
    else:
        elements = access.describe_app(pid)
        result_parts.append(f"Elements ({len(elements)}):")

    for el in elements:
        result_parts.append(f"  {_format_element(el)}")

    if not elements:
        result_parts.append("  (no elements found)")

    # CDP web content — enrich when Chrome is active
    if app_info and _is_browser(app_info.get("name", "")):
        web_text = _web_content()
        if web_text:
            result_parts.append("")
            result_parts.append(web_text)

    # Diff mode — compare with previous snapshot
    current_snapshot = _snapshot(elements, wins, focus, app_info)
    if diff and _last_snapshot is not None:
        diff_text = _compute_diff(_last_snapshot, current_snapshot)
        if diff_text:
            result_parts.append("")
            result_parts.append(diff_text)
        else:
            result_parts.append("")
            result_parts.append("Changes: (none detected)")

    # Always store snapshot for next diff
    _last_snapshot = current_snapshot

    # Screenshot
    if screenshot:
        img = screen.capture_screen()
        image_data = screen.screenshot_to_base64(img)

    result = {"text": "\n".join(result_parts)}
    if image_data:
        result["image"] = image_data

    return result


def _format_element(el):
    """Format an element as a compact one-liner."""
    role = el.get("role", "?")
    label = el.get("label", "")
    value = el.get("value", "")
    pos = el.get("pos")
    focused = el.get("focused", False)
    enabled = el.get("enabled", True)

    parts = [f"[{role}]"]
    if label:
        parts.append(f'"{label}"')
    if value:
        # Truncate long values
        v = value if len(value) <= 60 else value[:57] + "..."
        parts.append(f"= {v}")
    if pos:
        parts.append(f"@ {pos[0]},{pos[1]}")
    if focused:
        parts.append("*focused*")
    if not enabled:
        parts.append("(disabled)")

    return " ".join(parts)


def _resolve_pid(app):
    """Resolve an app name/PID to a numeric PID."""
    if app is None:
        return None
    if isinstance(app, int):
        return app
    if isinstance(app, str) and app.isdigit():
        return int(app)

    # Search by name
    apps = access.running_apps()
    app_lower = app.lower()
    for a in apps:
        if a["name"].lower() == app_lower:
            return a["pid"]
    # Partial match
    for a in apps:
        if app_lower in a["name"].lower():
            return a["pid"]
    return None


def _app_info_for_pid(pid):
    """Get app info dict for a specific PID."""
    apps = access.running_apps()
    for a in apps:
        if a["pid"] == pid:
            return a
    return None


# ---------------------------------------------------------------------------
# Action verification — lightweight before/after snapshots
# ---------------------------------------------------------------------------

def snap(pid=None):
    """Take a lightweight snapshot for before/after comparison.

    Faster than see() — just grabs essentials for diffing.
    Returns an opaque snapshot dict.
    """
    if pid is None:
        app_info = access.frontmost_app()
        if app_info:
            pid = app_info["pid"]
    else:
        app_info = None

    if app_info is None:
        apps = access.running_apps()
        app_info = next((a for a in apps if a["pid"] == pid), None)

    focus = access.focused_element(pid)
    elements = access.describe_app(pid)
    wins = access.windows()

    return _snapshot(elements, wins, focus, app_info)


def verify(before, after):
    """Compare before/after snapshots and return a compact change summary.

    Returns a short string or empty string if nothing changed.
    """
    diff_text = _compute_diff(before, after)
    if not diff_text:
        return ""
    return diff_text


# ---------------------------------------------------------------------------
# Diff / change detection
# ---------------------------------------------------------------------------

def _element_key(el):
    """Create a hashable key for an element (role + label + pos)."""
    return (el.get("role", ""), el.get("label", ""), el.get("value", ""))


def _snapshot(elements, windows, focus, app_info):
    """Create a comparable snapshot of the current screen state."""
    return {
        "app": app_info["name"] if app_info else "",
        "focus": _element_key(focus) if focus else None,
        "windows": frozenset(
            (w["app"], w["title"]) for w in (windows or [])
        ),
        "elements": {
            _element_key(el): {
                "role": el.get("role", ""),
                "label": el.get("label", ""),
                "value": el.get("value", ""),
                "enabled": el.get("enabled", True),
            }
            for el in elements
        },
    }


def _compute_diff(old, new):
    """Compare two snapshots and return a human-readable diff string."""
    parts = []

    # App changed?
    if old["app"] != new["app"]:
        parts.append(f'App changed: "{old["app"]}" → "{new["app"]}"')

    # Focus changed?
    if old["focus"] != new["focus"]:
        if old["focus"]:
            old_f = f'[{old["focus"][0]}] "{old["focus"][1]}"'
        else:
            old_f = "(none)"
        if new["focus"]:
            new_f = f'[{new["focus"][0]}] "{new["focus"][1]}"'
        else:
            new_f = "(none)"
        parts.append(f"Focus moved: {old_f} → {new_f}")

    # Windows added/removed
    added_wins = new["windows"] - old["windows"]
    removed_wins = old["windows"] - new["windows"]
    for app, title in added_wins:
        t = f' — "{title}"' if title else ""
        parts.append(f"+ Window: {app}{t}")
    for app, title in removed_wins:
        t = f' — "{title}"' if title else ""
        parts.append(f"- Window: {app}{t}")

    # Elements added/removed/changed
    old_keys = set(old["elements"].keys())
    new_keys = set(new["elements"].keys())

    added = new_keys - old_keys
    removed = old_keys - new_keys

    # Group by role for compact output
    if added:
        by_role = {}
        for key in added:
            role = key[0]
            label = key[1] or "(unlabeled)"
            by_role.setdefault(role, []).append(label)
        for role, labels in sorted(by_role.items()):
            if len(labels) <= 3:
                parts.append(f"+ [{role}]: {', '.join(labels)}")
            else:
                parts.append(f"+ [{role}]: {len(labels)} new")

    if removed:
        by_role = {}
        for key in removed:
            role = key[0]
            label = key[1] or "(unlabeled)"
            by_role.setdefault(role, []).append(label)
        for role, labels in sorted(by_role.items()):
            if len(labels) <= 3:
                parts.append(f"- [{role}]: {', '.join(labels)}")
            else:
                parts.append(f"- [{role}]: {len(labels)} gone")

    # Values changed on existing elements
    common = old_keys & new_keys
    changed = []
    for key in common:
        old_el = old["elements"][key]
        new_el = new["elements"][key]
        if old_el != new_el:
            diffs = []
            if old_el.get("value") != new_el.get("value"):
                diffs.append(f'value: "{old_el.get("value", "")}" → "{new_el.get("value", "")}"')
            if old_el.get("enabled") != new_el.get("enabled"):
                diffs.append(f'enabled: {old_el.get("enabled")} → {new_el.get("enabled")}')
            if diffs:
                label = key[1] or key[0]
                changed.append(f'  [{key[0]}] "{label}": {", ".join(diffs)}')

    if changed:
        parts.append("Changed:")
        parts.extend(changed[:10])
        if len(changed) > 10:
            parts.append(f"  ... and {len(changed) - 10} more")

    if not parts:
        return ""

    header = f"Changes ({len(added)} new, {len(removed)} gone, {len(changed)} modified):"
    return header + "\n" + "\n".join(parts)


# ---------------------------------------------------------------------------
# CDP web content integration
# ---------------------------------------------------------------------------

_BROWSER_NAMES = {"google chrome", "chrome", "chromium"}


def _is_browser(name):
    """Check if the app name is a CDP-capable browser."""
    return name.lower() in _BROWSER_NAMES


def _web_content():
    """Get web page content via CDP (if available). Returns text or None."""
    try:
        from nexus.sense.web import cdp_available, page_content
        if not cdp_available():
            return None
        content = page_content()
        if content:
            return f"--- Web Page (via CDP) ---\n{content}"
    except Exception:
        pass
    return None
