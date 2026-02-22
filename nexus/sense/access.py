"""macOS accessibility tree via pyobjc AXUIElement API.

The eye of Nexus. Walks the accessibility tree of any app,
returns structured data about every interactive element on screen.
"""

from ApplicationServices import (
    AXUIElementCreateSystemWide,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXUIElementCopyAttributeNames,
    AXUIElementCopyActionNames,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    AXIsProcessTrusted,
    kAXErrorSuccess,
)
from AppKit import NSWorkspace
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    kCGWindowListExcludeDesktopElements,
)


# Roles worth showing to the AI — interactive or meaningful
INTERACTIVE_ROLES = {
    "AXButton", "AXTextField", "AXTextArea", "AXCheckBox",
    "AXRadioButton", "AXPopUpButton", "AXComboBox", "AXSlider",
    "AXLink", "AXMenuItem", "AXMenuButton", "AXTab",
    "AXList", "AXTable", "AXOutline",
    "AXToolbar", "AXImage", "AXStaticText",
    "AXSwitch", "AXToggle", "AXIncrementor",
    "AXColorWell", "AXDateField", "AXDisclosureTriangle",
    "AXSegmentedControl", "AXMenuBarItem",
}


def is_trusted():
    """Check if accessibility permissions are granted."""
    return AXIsProcessTrusted()


def ax_attr(element, attr):
    """Safely get an AX attribute. Returns None on any failure."""
    try:
        err, value = AXUIElementCopyAttributeValue(element, attr, None)
        if err == kAXErrorSuccess:
            return value
    except Exception:
        pass
    return None


def ax_actions(element):
    """Get available actions for an element."""
    try:
        err, actions = AXUIElementCopyActionNames(element, None)
        if err == kAXErrorSuccess and actions:
            return list(actions)
    except Exception:
        pass
    return []


def ax_perform(element, action):
    """Perform an action on an element (e.g. AXPress, AXConfirm)."""
    try:
        from ApplicationServices import AXUIElementPerformAction
        err = AXUIElementPerformAction(element, action)
        return err == kAXErrorSuccess
    except Exception:
        return False


def ax_set(element, attr, value):
    """Set an attribute on an element (e.g. AXValue for text fields)."""
    try:
        err = AXUIElementSetAttributeValue(element, attr, value)
        return err == kAXErrorSuccess
    except Exception:
        return False


def _extract_point(value):
    """Extract (x, y) from an AXValue position."""
    if value is None:
        return None
    try:
        # pyobjc may return a CGPoint or NSPoint directly
        return (int(value.x), int(value.y))
    except AttributeError:
        pass
    try:
        # Or it might be wrapped in an AXValue
        from Quartz import AXValueGetValue, kAXValueTypeCGPoint
        ok, point = AXValueGetValue(value, kAXValueTypeCGPoint, None)
        if ok:
            return (int(point.x), int(point.y))
    except Exception:
        pass
    return None


def _extract_size(value):
    """Extract (w, h) from an AXValue size."""
    if value is None:
        return None
    try:
        return (int(value.width), int(value.height))
    except AttributeError:
        pass
    try:
        from Quartz import AXValueGetValue, kAXValueTypeCGSize
        ok, size = AXValueGetValue(value, kAXValueTypeCGSize, None)
        if ok:
            return (int(size.width), int(size.height))
    except Exception:
        pass
    return None


def frontmost_app():
    """Get the frontmost application info."""
    ws = NSWorkspace.sharedWorkspace()
    app = ws.frontmostApplication()
    if not app:
        return None
    return {
        "name": app.localizedName(),
        "pid": app.processIdentifier(),
        "bundle_id": app.bundleIdentifier() or "",
    }


def running_apps():
    """Get all regular (visible) running applications."""
    ws = NSWorkspace.sharedWorkspace()
    apps = ws.runningApplications()
    result = []
    for a in apps:
        # 0 = NSApplicationActivationPolicyRegular (has dock icon)
        if a.activationPolicy() == 0:
            result.append({
                "name": a.localizedName() or "",
                "pid": a.processIdentifier(),
                "bundle_id": a.bundleIdentifier() or "",
                "active": bool(a.isActive()),
            })
    return result


def windows():
    """Get all visible on-screen windows."""
    opts = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    win_list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID)
    if not win_list:
        return []
    result = []
    for w in win_list:
        layer = w.get("kCGWindowLayer", 999)
        name = w.get("kCGWindowOwnerName", "")
        title = w.get("kCGWindowName", "")
        if layer == 0 and name:  # Normal window layer
            bounds = w.get("kCGWindowBounds", {})
            result.append({
                "app": name,
                "title": title or "",
                "pid": w.get("kCGWindowOwnerPID", 0),
                "bounds": {
                    "x": int(bounds.get("X", 0)),
                    "y": int(bounds.get("Y", 0)),
                    "w": int(bounds.get("Width", 0)),
                    "h": int(bounds.get("Height", 0)),
                },
            })
    return result


def focused_element(pid=None):
    """Get the currently focused UI element."""
    if pid is None:
        app = frontmost_app()
        if not app:
            return None
        pid = app["pid"]

    app_ref = AXUIElementCreateApplication(pid)
    el = ax_attr(app_ref, "AXFocusedUIElement")
    if not el:
        return None

    return _element_to_dict(el, focused=True)


def _element_to_dict(el, focused=False):
    """Convert an AX element to a clean dict."""
    role = ax_attr(el, "AXRole") or ""
    role_desc = ax_attr(el, "AXRoleDescription") or ""
    title = ax_attr(el, "AXTitle") or ""
    desc = ax_attr(el, "AXDescription") or ""
    value = ax_attr(el, "AXValue")
    enabled = ax_attr(el, "AXEnabled")
    is_focused = ax_attr(el, "AXFocused")

    pos = _extract_point(ax_attr(el, "AXPosition"))
    sz = _extract_size(ax_attr(el, "AXSize"))

    label = title or desc
    display_role = role_desc or role.replace("AX", "").lower()

    node = {"role": display_role, "label": label, "_ax_role": role}

    if value is not None:
        val_str = str(value)
        if val_str and val_str != label:
            node["value"] = val_str[:300]

    if pos:
        node["pos"] = pos
    if sz:
        node["size"] = sz
    if enabled is not None and not enabled:
        node["enabled"] = False
    if focused or is_focused:
        node["focused"] = True

    # Store raw ref for action execution (not serialized)
    node["_ref"] = el
    return node


def walk_tree(element, max_depth=8, depth=0, max_elements=150):
    """Walk accessibility tree, return flat list of meaningful elements."""
    if depth > max_depth:
        return []

    results = []
    role = ax_attr(element, "AXRole") or ""
    title = ax_attr(element, "AXTitle") or ""
    desc = ax_attr(element, "AXDescription") or ""
    label = title or desc

    # Include if interactive or has a label
    if role in INTERACTIVE_ROLES or label:
        node = _element_to_dict(element)
        # Skip noise: unlabeled static text, tiny elements
        if node["label"] or node["role"] not in ("static text", "image", "group"):
            results.append(node)

    if len(results) >= max_elements:
        return results

    # Recurse
    children = ax_attr(element, "AXChildren")
    if children:
        for child in children:
            results.extend(walk_tree(child, max_depth, depth + 1, max_elements))
            if len(results) >= max_elements:
                break

    return results[:max_elements]


def describe_app(pid=None, max_elements=150):
    """Get the full accessibility tree of an app's focused window.

    Args:
        pid: Process ID (default: frontmost app).
        max_elements: Maximum elements to collect (default 150).
    """
    if pid is None:
        app = frontmost_app()
        if not app:
            return []
        pid = app["pid"]

    app_ref = AXUIElementCreateApplication(pid)

    # Try focused window first, then main window, then first window
    window = ax_attr(app_ref, "AXFocusedWindow")
    if not window:
        window = ax_attr(app_ref, "AXMainWindow")
    if not window:
        win_list = ax_attr(app_ref, "AXWindows")
        if win_list and len(win_list) > 0:
            window = win_list[0]
    if not window:
        return []

    return walk_tree(window, max_elements=max_elements)


def find_elements(query, pid=None):
    """Find elements matching a text query (fuzzy)."""
    elements = describe_app(pid)
    query_lower = query.lower()
    matches = []

    for el in elements:
        label = el.get("label", "").lower()
        role = el.get("role", "").lower()
        value = (el.get("value", "") or "").lower()

        score = 0
        if query_lower == label:
            score = 100
        elif query_lower in label:
            score = 80
        elif query_lower in f"{role} {label}":
            score = 60
        elif query_lower in value:
            score = 40

        if score > 0:
            matches.append((score, el))

    matches.sort(key=lambda x: x[0], reverse=True)
    return [el for _, el in matches]


def window_title(pid=None):
    """Get the title of the focused window."""
    if pid is None:
        app = frontmost_app()
        if not app:
            return ""
        pid = app["pid"]

    app_ref = AXUIElementCreateApplication(pid)
    window = ax_attr(app_ref, "AXFocusedWindow") or ax_attr(app_ref, "AXMainWindow")
    if window:
        return ax_attr(window, "AXTitle") or ""
    return ""


def app_ref_for_pid(pid):
    """Get AXUIElement ref for an app by PID."""
    return AXUIElementCreateApplication(pid)


# ---------------------------------------------------------------------------
# Menu bar
# ---------------------------------------------------------------------------

def menu_bar(pid=None):
    """Walk the app's menu bar. Returns flat list of all menu items with paths."""
    if pid is None:
        app = frontmost_app()
        if not app:
            return []
        pid = app["pid"]

    app_ref = AXUIElementCreateApplication(pid)
    mb = ax_attr(app_ref, "AXMenuBar")
    if not mb:
        return []

    return _walk_menu(mb)


def _walk_menu(element, depth=0, max_depth=3, prefix=""):
    """Recursively walk menu items."""
    items = []
    children = ax_attr(element, "AXChildren")
    if not children:
        return items

    for child in children:
        title = ax_attr(child, "AXTitle") or ""
        enabled = ax_attr(child, "AXEnabled")

        # Skip Apple menu and separators
        if not title or title == "Apple":
            if depth < max_depth:
                items.extend(_walk_menu(child, depth, max_depth, prefix))
            continue

        path = title if not prefix else f"{prefix} > {title}"

        item = {"title": title, "path": path, "depth": depth, "_ref": child}

        # Keyboard shortcut
        cmd_char = ax_attr(child, "AXMenuItemCmdChar")
        if cmd_char:
            modifiers = ax_attr(child, "AXMenuItemCmdModifiers") or 0
            item["shortcut"] = _format_shortcut(cmd_char, modifiers)

        if enabled is not None and not enabled:
            item["enabled"] = False

        items.append(item)

        # Recurse into submenus
        if depth < max_depth:
            items.extend(_walk_menu(child, depth + 1, max_depth, path))

    return items


def _format_shortcut(char, modifiers):
    """Format keyboard shortcut from AXMenuItemCmdModifiers bitmask."""
    parts = []
    if isinstance(modifiers, int):
        if modifiers & 4:
            parts.append("Ctrl")
        if modifiers & 2:
            parts.append("Opt")
        if modifiers & 1:
            parts.append("Shift")
        if not (modifiers & 8):  # 8 = no Cmd
            parts.append("Cmd")
    else:
        parts.append("Cmd")
    parts.append(str(char))
    return "+".join(parts)


def find_menu_item(path, pid=None):
    """Find a menu item by path like 'File > Save' or just 'Save'."""
    items = menu_bar(pid)
    path_lower = path.lower().strip()

    # Exact path match
    for item in items:
        if item["path"].lower() == path_lower:
            return item

    # Match just the final item name
    target = path.split(">")[-1].strip().lower()
    for item in items:
        if item["title"].lower() == target:
            return item

    # Fuzzy
    for item in items:
        if target in item["title"].lower():
            return item

    return None


# ---------------------------------------------------------------------------
# Window geometry
# ---------------------------------------------------------------------------

def window_bounds_ax(pid=None):
    """Get the focused window's position and size via accessibility."""
    if pid is None:
        app = frontmost_app()
        if not app:
            return None
        pid = app["pid"]

    app_ref = AXUIElementCreateApplication(pid)
    window = ax_attr(app_ref, "AXFocusedWindow") or ax_attr(app_ref, "AXMainWindow")
    if not window:
        return None

    pos = _extract_point(ax_attr(window, "AXPosition"))
    sz = _extract_size(ax_attr(window, "AXSize"))
    title = ax_attr(window, "AXTitle") or ""

    return {
        "title": title,
        "x": pos[0] if pos else 0,
        "y": pos[1] if pos else 0,
        "w": sz[0] if sz else 0,
        "h": sz[1] if sz else 0,
        "_window_ref": window,
    }
