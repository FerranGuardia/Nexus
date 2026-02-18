"""Cortex Filters — query-scoped filtering for Nexus commands.

Filter at the source, not in context. Reduces tokens by 60-90% for focused queries.
Pure functions: take filter params + element list → return filtered list.
"""

import fnmatch
import re


# ---------------------------------------------------------------------------
# Focus presets: name → set of UIA ControlType IDs or web roles
# ---------------------------------------------------------------------------

# UIA ControlType IDs (from Microsoft docs)
_UIA_PRESETS = {
    "buttons": {50000, 50031},  # Button, SplitButton
    "inputs": {50002, 50003, 50004, 50013, 50015},  # CheckBox, ComboBox, Edit, Radio, Slider
    "interactive": {50000, 50002, 50003, 50004, 50005, 50007, 50011, 50013, 50015, 50019, 50024, 50031},
    "navigation": {50011, 50018, 50019, 50024, 50005},  # MenuItem, Tab, TabItem, TreeItem, Hyperlink
    "headings": set(),  # UIA has no heading type — filtered by name pattern
    "dialogs": set(),  # Detected by ControlTypeName, not ID
}

# Web AXTree role sets
_WEB_PRESETS = {
    "buttons": {"button"},
    "inputs": {"textbox", "checkbox", "radio", "combobox", "spinbutton", "slider", "searchbox"},
    "interactive": {"button", "link", "textbox", "checkbox", "radio", "combobox", "tab",
                    "menuitem", "spinbutton", "slider", "searchbox", "switch"},
    "navigation": {"link", "menuitem", "tab", "treeitem", "navigation"},
    "headings": {"heading"},
    "forms": {"textbox", "checkbox", "radio", "combobox", "spinbutton", "slider",
              "searchbox", "button", "form"},
    "errors": {"alert", "status"},
    "dialogs": {"dialog", "alertdialog"},
}

# UIA ControlTypeName strings for special presets
_UIA_TYPE_NAME_PRESETS = {
    "dialogs": {"WindowControl", "PaneControl"},  # Dialogs often appear as Window or Pane
}


def parse_focus(focus_str: str) -> dict:
    """Parse a --focus value into a filter spec.

    Returns:
        {"preset": str, "uia_type_ids": set|None, "web_roles": set|None,
         "uia_type_names": set|None, "name_pattern": str|None}
    """
    focus = focus_str.strip().lower()

    return {
        "preset": focus,
        "uia_type_ids": _UIA_PRESETS.get(focus),
        "web_roles": _WEB_PRESETS.get(focus),
        "uia_type_names": _UIA_TYPE_NAME_PRESETS.get(focus),
        "name_pattern": focus if focus not in _UIA_PRESETS and focus not in _WEB_PRESETS else None,
    }


def parse_region(region_str: str, screen_w: int = 1920, screen_h: int = 1080) -> dict:
    """Parse a --region value into a bounding rect.

    Accepts:
        "top" | "bottom" | "left" | "right" | "center" | "X,Y,W,H"

    Returns:
        {"x": int, "y": int, "w": int, "h": int}
    """
    region = region_str.strip().lower()

    presets = {
        "top": (0, 0, screen_w, int(screen_h * 0.2)),
        "bottom": (0, int(screen_h * 0.8), screen_w, int(screen_h * 0.2)),
        "left": (0, 0, int(screen_w * 0.25), screen_h),
        "right": (int(screen_w * 0.75), 0, int(screen_w * 0.25), screen_h),
        "center": (int(screen_w * 0.15), int(screen_h * 0.15),
                   int(screen_w * 0.7), int(screen_h * 0.7)),
    }

    if region in presets:
        x, y, w, h = presets[region]
        return {"x": x, "y": y, "w": w, "h": h}

    # Parse "X,Y,W,H"
    parts = [int(p) for p in region.split(",")]
    return {"x": parts[0], "y": parts[1], "w": parts[2], "h": parts[3]}


# ---------------------------------------------------------------------------
# UIA element filtering
# ---------------------------------------------------------------------------

def filter_uia_elements(
    elements: list[dict],
    focus: str | None = None,
    match: str | None = None,
    region: dict | None = None,
) -> list[dict]:
    """Filter a list of UIA element dicts by focus preset, name pattern, and/or region.

    Args:
        elements: list of element dicts from collect_named_elements()
        focus: preset name ("buttons", "inputs", etc.) or free text to match in names
        match: glob/regex pattern to match element names
        region: {"x": int, "y": int, "w": int, "h": int} bounding rect
    """
    result = elements

    if focus:
        spec = parse_focus(focus)

        if spec["uia_type_ids"]:
            # Filter by control type ID — need to map type name back to ID
            type_names = _type_ids_to_names(spec["uia_type_ids"])
            result = [el for el in result if el.get("type", "") in type_names]
        elif spec["uia_type_names"]:
            result = [el for el in result if el.get("type", "") in spec["uia_type_names"]]
        elif focus == "errors":
            # Match elements with error/warning/alert in name
            result = [el for el in result
                      if _name_has_error(el.get("name", ""))]
        elif spec["name_pattern"]:
            # Free text — treat as substring search in element names
            pattern_lower = spec["name_pattern"]
            result = [el for el in result
                      if pattern_lower in el.get("name", "").lower()]

    if match:
        result = _filter_by_match(result, match)

    if region:
        result = _filter_by_region(result, region)

    return result


def filter_web_nodes(
    nodes: list[dict],
    focus: str | None = None,
    match: str | None = None,
    region: dict | None = None,
) -> list[dict]:
    """Filter a list of web AX nodes by focus preset, name pattern, and/or region.

    Args:
        nodes: list of node dicts from web_ax()
        focus: preset name ("buttons", "inputs", etc.) or free text
        match: glob/regex pattern to match node names
        region: not typically used for web (no coordinates in AX tree)
    """
    result = nodes

    if focus:
        spec = parse_focus(focus)

        if spec["web_roles"]:
            roles = spec["web_roles"]
            result = [n for n in result if n.get("role", "") in roles]
        elif focus == "errors":
            result = [n for n in result
                      if n.get("role", "") in {"alert", "status"}
                      or _name_has_error(n.get("name", ""))]
        elif spec["name_pattern"]:
            pattern_lower = spec["name_pattern"]
            result = [n for n in result
                      if pattern_lower in n.get("name", "").lower()]

    if match:
        result = _filter_by_match(result, match)

    # region filtering for web nodes is a no-op (AX tree has no coordinates)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Reverse map: type ID → type name string (from nexus.uia ACTIONABLE_TYPE_IDS)
_TYPE_ID_TO_NAME = {
    50000: "ButtonControl",
    50002: "CheckBoxControl",
    50003: "ComboBoxControl",
    50004: "EditControl",
    50005: "HyperlinkControl",
    50007: "ListItemControl",
    50011: "MenuItemControl",
    50013: "RadioButtonControl",
    50015: "SliderControl",
    50018: "TabControl",
    50019: "TabItemControl",
    50024: "TreeItemControl",
    50031: "SplitButtonControl",
}


def _type_ids_to_names(type_ids: set) -> set:
    """Convert a set of UIA type IDs to type name strings."""
    return {_TYPE_ID_TO_NAME[tid] for tid in type_ids if tid in _TYPE_ID_TO_NAME}


def _name_has_error(name: str) -> bool:
    """Check if element name suggests an error/warning/alert."""
    lower = name.lower()
    return any(kw in lower for kw in ("error", "warning", "alert", "fail", "invalid"))


def _filter_by_match(elements: list[dict], pattern: str) -> list[dict]:
    """Filter elements by glob or regex pattern on name."""
    # Try as glob first (simpler, more intuitive)
    if any(c in pattern for c in "*?[]"):
        return [el for el in elements
                if fnmatch.fnmatch(el.get("name", ""), pattern)]

    # Try as regex
    try:
        rx = re.compile(pattern, re.IGNORECASE)
        return [el for el in elements if rx.search(el.get("name", ""))]
    except re.error:
        # Invalid regex — fall back to substring
        pattern_lower = pattern.lower()
        return [el for el in elements
                if pattern_lower in el.get("name", "").lower()]


def _filter_by_region(elements: list[dict], region: dict) -> list[dict]:
    """Filter elements whose center is within the region rect."""
    rx, ry, rw, rh = region["x"], region["y"], region["w"], region["h"]
    result = []
    for el in elements:
        bounds = el.get("bounds", {})
        cx = bounds.get("center_x", 0)
        cy = bounds.get("center_y", 0)
        if rx <= cx <= rx + rw and ry <= cy <= ry + rh:
            result.append(el)
    return result
