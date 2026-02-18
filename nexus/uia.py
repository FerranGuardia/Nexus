"""UIA helpers — Windows UI Automation tree traversal utilities.

Pure functions. No output, no side effects — just data transformation.
Uses COM FindAll() with property conditions for fast, native-level filtering.
"""

import comtypes
import uiautomation as auto

MAX_TREE_DEPTH = 6
MAX_ELEMENTS = 120

# ControlType IDs for actionable controls (ones a user/agent can interact with)
# See: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controltype-ids
ACTIONABLE_TYPE_IDS = {
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

# UIA property IDs
UIA_CONTROL_TYPE_PROPERTY_ID = 30003

# TreeScope values
TREE_SCOPE_DESCENDANTS = 4
TREE_SCOPE_CHILDREN = 2


def _get_uia_com():
    """Get the raw IUIAutomation COM instance (cached per-thread)."""
    CLSID = '{FF48DBA4-60EF-4201-AA87-54103EEF594E}'
    return comtypes.CoCreateInstance(
        comtypes.GUID(CLSID),
        interface=comtypes.gen.UIAutomationClient.IUIAutomation,
    )


def _build_actionable_condition(uia_com):
    """Build an OR condition matching all actionable control types."""
    conds = [uia_com.CreatePropertyCondition(UIA_CONTROL_TYPE_PROPERTY_ID, tid)
             for tid in ACTIONABLE_TYPE_IDS]
    result = conds[0]
    for c in conds[1:]:
        result = uia_com.CreateOrCondition(result, c)
    return result


def _com_rect_to_dict(rect) -> dict:
    """Convert a COM RECT struct to a plain dict."""
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    return {
        "left": rect.left,
        "top": rect.top,
        "right": rect.right,
        "bottom": rect.bottom,
        "width": w,
        "height": h,
        "center_x": (rect.left + rect.right) // 2,
        "center_y": (rect.top + rect.bottom) // 2,
    }


def _com_element_to_dict(com_elem) -> dict:
    """Extract useful info from a raw COM IUIAutomationElement."""
    try:
        name = com_elem.CurrentName or ""
        control_type_id = com_elem.CurrentControlType
        class_name = com_elem.CurrentClassName or ""
        automation_id = com_elem.CurrentAutomationId or ""
        is_enabled = bool(com_elem.CurrentIsEnabled)
        rect = com_elem.CurrentBoundingRectangle
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        type_name = ACTIONABLE_TYPE_IDS.get(control_type_id, "Control(%d)" % control_type_id)
        return {
            "name": name,
            "type": type_name,
            "class": class_name,
            "automation_id": automation_id,
            "bounds": _com_rect_to_dict(rect),
            "is_visible": w > 0 and h > 0,
            "is_enabled": is_enabled,
        }
    except Exception:
        return None


def rect_to_dict(rect) -> dict:
    """Convert a uiautomation Rect to a plain dict."""
    return {
        "left": rect.left,
        "top": rect.top,
        "right": rect.right,
        "bottom": rect.bottom,
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top,
        "center_x": (rect.left + rect.right) // 2,
        "center_y": (rect.top + rect.bottom) // 2,
    }


def element_to_dict(ctrl) -> dict:
    """Extract useful info from a UI Automation control (uiautomation wrapper)."""
    rect = ctrl.BoundingRectangle
    is_enabled = True
    try:
        is_enabled = bool(ctrl.Element.CurrentIsEnabled)
    except Exception:
        pass
    return {
        "name": ctrl.Name or "",
        "type": ctrl.ControlTypeName,
        "class": ctrl.ClassName or "",
        "automation_id": ctrl.AutomationId or "",
        "bounds": rect_to_dict(rect),
        "is_visible": (rect.right - rect.left) > 0 and (rect.bottom - rect.top) > 0,
        "is_enabled": is_enabled,
    }


def collect_named_elements(
    control,
    max_depth: int = MAX_TREE_DEPTH,
    max_elements: int = MAX_ELEMENTS,
) -> list[dict]:
    """Collect visible, named, actionable elements using COM FindAll().

    Uses native COM-level filtering for control types, then filters
    for visibility and non-empty names in Python.
    Falls back to recursive walk if COM fails.
    """
    try:
        return _collect_via_com(control, max_elements)
    except Exception:
        return _collect_via_walk(control, max_depth, max_elements)


def _collect_via_com(control, max_elements: int) -> list[dict]:
    """Fast path: COM FindAll with actionable type condition."""
    uia_com = _get_uia_com()
    condition = _build_actionable_condition(uia_com)
    elem = control.Element
    found = elem.FindAll(TREE_SCOPE_DESCENDANTS, condition)

    results = []
    count = found.Length
    for i in range(min(count, max_elements * 2)):  # over-fetch, filter below
        child = found.GetElement(i)
        d = _com_element_to_dict(child)
        if d and d["name"].strip() and d["is_visible"]:
            results.append(d)
            if len(results) >= max_elements:
                break
    return results


def _collect_via_walk(control, max_depth: int, max_elements: int) -> list[dict]:
    """Fallback: recursive Python walk (original implementation)."""
    results = []

    def _walk(node, depth):
        if depth > max_depth or len(results) >= max_elements:
            return
        try:
            children = node.GetChildren()
        except Exception:
            return
        for child in children:
            if len(results) >= max_elements:
                return
            name = child.Name or ""
            rect = child.BoundingRectangle
            is_visible = (rect.right - rect.left) > 0 and (rect.bottom - rect.top) > 0
            if name.strip() and is_visible:
                results.append(element_to_dict(child))
            _walk(child, depth + 1)

    _walk(control, 0)
    return results


def find_elements(
    control,
    query: str,
    max_depth: int = MAX_TREE_DEPTH,
    max_elements: int = MAX_ELEMENTS,
) -> list[dict]:
    """Search for visible elements whose name contains `query` (case-insensitive).

    Uses COM FindAll for speed, then filters by query in Python.
    """
    try:
        return _find_via_com(control, query, max_elements)
    except Exception:
        return _find_via_walk(control, query, max_depth, max_elements)


def _find_via_com(control, query: str, max_elements: int) -> list[dict]:
    """Fast path: COM FindAll then filter by name in Python."""
    uia_com = _get_uia_com()
    # Use TrueCondition to search all elements (query filtering in Python)
    true_cond = uia_com.CreateTrueCondition()
    elem = control.Element
    found = elem.FindAll(TREE_SCOPE_DESCENDANTS, true_cond)

    query_lower = query.lower()
    results = []
    count = found.Length
    for i in range(min(count, 500)):  # scan up to 500, filter down
        child = found.GetElement(i)
        try:
            name = child.CurrentName or ""
            if query_lower not in name.lower():
                continue
            rect = child.CurrentBoundingRectangle
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 and h <= 0:
                continue
            d = _com_element_to_dict(child)
            if d:
                results.append(d)
                if len(results) >= max_elements:
                    break
        except Exception:
            continue
    return results


def _find_via_walk(control, query: str, max_depth: int, max_elements: int) -> list[dict]:
    """Fallback: recursive Python walk with query filter."""
    results = []
    query_lower = query.lower()

    def _walk(node, depth):
        if depth > max_depth or len(results) >= max_elements:
            return
        try:
            children = node.GetChildren()
        except Exception:
            return
        for child in children:
            if len(results) >= max_elements:
                return
            name = child.Name or ""
            if query_lower in name.lower():
                rect = child.BoundingRectangle
                is_visible = (rect.right - rect.left) > 0 and (rect.bottom - rect.top) > 0
                if is_visible:
                    results.append(element_to_dict(child))
            _walk(child, depth + 1)

    _walk(control, 0)
    return results
