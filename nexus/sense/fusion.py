"""Unified perception — the `see` tool.

Fuses accessibility tree, window list, and screenshots into
a single, token-efficient text snapshot of the computer.
"""

from nexus.sense import access, screen


def see(app=None, query=None, screenshot=False, menus=False):
    """Main perception function. Returns a text snapshot of the computer.

    Args:
        app: App name or PID to look at (default: frontmost).
        query: Search for specific elements instead of full tree.
        screenshot: Include a base64 screenshot.
        menus: Include the app's menu bar items (shows available commands).

    Returns:
        dict with 'text' (always) and optionally 'image' (base64 JPEG).
    """
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
