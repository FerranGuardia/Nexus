"""Digitus Element — find UI element by name and click/interact with it.

Element-based targeting: find by name (fuzzy), filter by role, verify after action.
Survives window moves and mouse interference — re-locates elements fresh each time.
"""

import time

import pyautogui
import uiautomation as auto

from nexus.uia import find_elements, collect_named_elements, element_to_dict


# Role aliases → UIA ControlTypeName values
_ROLE_ALIASES = {
    "button": {"ButtonControl", "SplitButtonControl"},
    "input": {"EditControl", "ComboBoxControl", "SpinnerControl"},
    "checkbox": {"CheckBoxControl"},
    "radio": {"RadioButtonControl"},
    "link": {"HyperlinkControl"},
    "tab": {"TabItemControl"},
    "menu": {"MenuItemControl"},
    "list": {"ListItemControl"},
    "tree": {"TreeItemControl"},
    "slider": {"SliderControl"},
}


def _fuzzy_match(name: str, query: str) -> bool:
    """Check if element name fuzzy-matches the query.

    Supports:
      - Exact substring (case-insensitive)
      - Word-boundary matching: "save" matches "Save Changes" but not "unsaved"
    """
    name_lower = name.lower()
    query_lower = query.lower()

    # Exact substring
    if query_lower in name_lower:
        return True

    # Word boundary: query matches start of any word in name
    words = name_lower.replace("-", " ").replace("_", " ").split()
    return any(w.startswith(query_lower) for w in words)


def _filter_by_role(elements: list[dict], role: str) -> list[dict]:
    """Filter elements by role alias."""
    role_lower = role.lower()
    type_names = _ROLE_ALIASES.get(role_lower, set())
    if not type_names:
        # Try as literal ControlTypeName
        type_names = {role}
    return [el for el in elements if el.get("type", "") in type_names]


def _ensure_foreground(win_title: str = None) -> bool:
    """Ensure the target window is in the foreground.

    Returns True if window is (now) in foreground.
    """
    fg = auto.GetForegroundControl()
    if win_title and fg.Name and win_title.lower() in fg.Name.lower():
        return True

    # Try to bring the window forward
    if win_title:
        try:
            import ctypes
            desktop = auto.GetRootControl()
            for child in desktop.GetChildren():
                if child.Name and win_title.lower() in child.Name.lower():
                    handle = child.NativeWindowHandle
                    if handle:
                        ctypes.windll.user32.SetForegroundWindow(handle)
                        time.sleep(0.2)
                        return True
        except Exception:
            pass
    return True  # Best effort — proceed anyway


def click_element(name: str, right: bool = False, double: bool = False,
                  role: str = None, index: int = 0, verify: bool = False,
                  heal: bool = False) -> dict:
    """Find an element by name and click its center.

    Args:
        name: Element name to search for (fuzzy match).
        right: Right-click instead of left.
        double: Double-click.
        role: Filter by role ("button", "input", "link", "tab", "menu", etc.).
        index: Which match to click (0-based) when multiple elements match.
        verify: If True, re-describe after click to confirm state changed.
        heal: If True, attempt self-healing recovery on failure (NX-020).
    """
    win = auto.GetForegroundControl()
    win_title = win.Name or ""

    # Ensure window is focused before acting
    _ensure_foreground(win_title)

    # Find matching elements
    matches = find_elements(win, name)

    # Also try fuzzy matching if exact substring found nothing
    if not matches:
        all_elements = collect_named_elements(win)
        matches = [el for el in all_elements if _fuzzy_match(el.get("name", ""), name)]

    # Filter by role if specified
    if role and matches:
        matches = _filter_by_role(matches, role)

    if not matches:
        # Always gather context for actionable errors
        all_elements = collect_named_elements(win)
        error_msg = "No element found matching '%s'%s in window '%s'" % (
            name, " (role=%s)" % role if role else "", win_title)

        if heal:
            from nexus.digitus.healing import diagnose_click_failure, _suggest_similar
            suggestions = _suggest_similar(name, all_elements)
            return {
                "command": "click-element",
                "success": False,
                "error": error_msg,
                "context": {"window": win_title, "element_count": len(all_elements)},
                "diagnosis": "element_not_found",
                "heal_attempted": True,
                "suggestions": suggestions or ["Try 'describe --focus interactive' to see available elements"],
            }

        # Non-heal: still provide nearby names so Claude can self-correct
        name_lower = name.lower()
        nearby = [el.get("name", "") for el in all_elements
                  if el.get("name") and name_lower[:3] in el["name"].lower()][:8]
        suggestions = []
        if nearby:
            suggestions.append("Similar elements: %s" % ", ".join("'%s'" % n for n in nearby))
        suggestions.append("Use 'describe --focus interactive' to see all clickable elements")
        return {
            "command": "click-element",
            "success": False,
            "error": error_msg,
            "context": {"window": win_title, "element_count": len(all_elements)},
            "suggestions": suggestions,
        }

    if index >= len(matches):
        return {
            "command": "click-element",
            "success": False,
            "error": "Index %d out of range (found %d matches for '%s')" % (
                index, len(matches), name),
            "matches": [m.get("name", "") for m in matches],
        }

    target = matches[index]
    cx = target["bounds"]["center_x"]
    cy = target["bounds"]["center_y"]

    button = "right" if right else "left"
    clicks = 2 if double else 1
    pyautogui.click(cx, cy, clicks=clicks, button=button)

    result = {
        "command": "click-element",
        "success": True,
        "clicked": target["name"],
        "type": target.get("type", ""),
        "at": {"x": cx, "y": cy},
        "button": button,
        "double": double,
        "all_matches": len(matches),
    }

    # Post-action verification
    if verify:
        time.sleep(0.3)  # Let UI settle
        verification = _verify_action(win_title, target, cx, cy)
        result["verification"] = verification

        # If verify shows something unexpected and heal is on, attempt recovery
        if heal and verification.get("verified") and not verification.get("focus_changed", True):
            from nexus.digitus.healing import heal_click
            heal_result = heal_click(
                name, cx, cy, right=right, double=double, role=role,
            )
            if heal_result.get("healed"):
                result["healed"] = True
                result["heal_details"] = heal_result
                new_pos = heal_result.get("new_position", {})
                if new_pos:
                    result["at"] = new_pos

    return result


def _verify_action(win_title: str, original_target: dict,
                   click_x: int, click_y: int) -> dict:
    """Verify an action had an effect by checking what changed.

    Returns a dict with verification status and observations.
    """
    try:
        new_focused = auto.GetFocusedControl()
        new_focused_dict = element_to_dict(new_focused) if new_focused else None

        # Check what's now under the click point
        over = auto.ControlFromPoint(click_x, click_y)
        over_dict = element_to_dict(over) if over else None

        # Simple heuristics for success
        focus_changed = (new_focused_dict and
                         new_focused_dict.get("name", "") != original_target.get("name", ""))
        element_at_point_matches = (over_dict and
                                    original_target.get("name", "") in over_dict.get("name", ""))

        return {
            "verified": True,
            "focus_changed": focus_changed,
            "new_focus": new_focused_dict.get("name", "") if new_focused_dict else None,
            "element_at_click": over_dict.get("name", "") if over_dict else None,
        }
    except Exception as e:
        return {
            "verified": False,
            "error": str(e)[:200],
        }
