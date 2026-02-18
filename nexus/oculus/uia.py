"""Oculus UIA — desktop awareness via Windows UI Automation.

Read-only. Every function takes explicit params and returns a dict.
"""

import pyautogui
import uiautomation as auto

from nexus.uia import rect_to_dict, element_to_dict, collect_named_elements, find_elements


def describe(max_depth: int = None, focus: str = None,
             match: str = None, region: str = None) -> dict:
    """Describe the active window: named elements, focused element, cursor.

    Args:
        max_depth: Max tree depth for fallback traversal. None = use default (6).
        focus: Filter preset ("buttons", "inputs", "interactive", "errors", "dialogs",
               "navigation") or free text to match in element names.
        match: Glob or regex pattern to match element names.
        region: Spatial filter — "top", "bottom", "left", "right", "center", or "X,Y,W,H".
    """
    pos = pyautogui.position()
    win = auto.GetForegroundControl()
    focused_ctrl = auto.GetFocusedControl()

    cursor_ctrl = auto.ControlFromPoint(pos.x, pos.y)
    cursor_element = element_to_dict(cursor_ctrl) if cursor_ctrl else None
    focused_element = element_to_dict(focused_ctrl) if focused_ctrl else None

    kwargs = {}
    if max_depth is not None:
        kwargs["max_depth"] = max_depth
    elements = collect_named_elements(win, **kwargs)

    # Apply filters if any
    if focus or match or region:
        from nexus.cortex.filters import filter_uia_elements, parse_region
        region_dict = parse_region(region) if region else None
        elements = filter_uia_elements(elements, focus=focus, match=match, region=region_dict)

    result = {
        "command": "describe",
        "window": {
            "title": win.Name or "",
            "type": win.ControlTypeName,
            "bounds": rect_to_dict(win.BoundingRectangle),
        },
        "cursor": {
            "x": pos.x,
            "y": pos.y,
            "over_element": cursor_element,
        },
        "focused_element": focused_element,
        "elements": elements,
        "element_count": len(elements),
    }

    # Explain empty results so Claude doesn't guess
    if not elements:
        win_bounds = win.BoundingRectangle
        is_minimized = (win_bounds.right - win_bounds.left) <= 0
        hints = []
        if is_minimized:
            hints.append("Window appears minimized — restore it first")
        elif not win.Name:
            hints.append("Foreground control has no title — may be a desktop or overlay")
        elif focus or match or region:
            hints.append("No elements matched filters (focus=%s, match=%s, region=%s) — try without filters or use 'describe' with no args" % (focus, match, region))
        else:
            hints.append("Window has no named UIA elements — try ocr_screen or web_describe instead")
        result["suggestions"] = hints

    return result


def windows() -> dict:
    """List all open windows with visibility status."""
    desktop = auto.GetRootControl()
    foreground = auto.GetForegroundControl()
    fg_name = foreground.Name if foreground else ""

    wins = []
    for child in desktop.GetChildren():
        name = child.Name or ""
        if not name.strip():
            continue
        rect = child.BoundingRectangle
        is_visible = (rect.right - rect.left) > 0 and (rect.bottom - rect.top) > 0
        wins.append({
            "title": name,
            "type": child.ControlTypeName,
            "is_visible": is_visible,
            "is_foreground": name == fg_name,
            "bounds": rect_to_dict(rect) if is_visible else None,
        })

    return {"command": "windows", "windows": wins, "count": len(wins)}


def find(query: str, focus: str = None, region: str = None) -> dict:
    """Search for UI elements by name in the active window.

    Args:
        query: Text to search for in element names.
        focus: Optional filter preset to narrow results by type.
        region: Optional spatial filter.
    """
    win = auto.GetForegroundControl()
    matches = find_elements(win, query)

    if focus or region:
        from nexus.cortex.filters import filter_uia_elements, parse_region
        region_dict = parse_region(region) if region else None
        matches = filter_uia_elements(matches, focus=focus, region=region_dict)

    return {
        "command": "find",
        "query": query,
        "window": win.Name or "",
        "matches": matches,
        "count": len(matches),
    }


def focused() -> dict:
    """Report which element currently has keyboard focus."""
    ctrl = auto.GetFocusedControl()
    if not ctrl:
        return {"command": "focused", "element": None, "parent_chain": []}

    parents = []
    parent = ctrl.GetParentControl()
    for _ in range(5):
        if not parent or not parent.Name:
            break
        parents.append({"name": parent.Name, "type": parent.ControlTypeName})
        parent = parent.GetParentControl()

    return {
        "command": "focused",
        "element": element_to_dict(ctrl),
        "parent_chain": parents,
    }
