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


# ---------------------------------------------------------------------------
# Tree cache — avoids redundant walks within a short window (snap + action + snap)
# ---------------------------------------------------------------------------

import time as _time

_tree_cache = {}
_CACHE_TTL = 1.0  # seconds


def _cache_get(key):
    """Get a cached result if still fresh."""
    if key in _tree_cache:
        ts, result = _tree_cache[key]
        if _time.time() - ts < _CACHE_TTL:
            return result
    return None


def _cache_set(key, result):
    """Cache a result with current timestamp."""
    _tree_cache[key] = (_time.time(), result)


def invalidate_cache():
    """Clear the tree cache (call after mutations if needed)."""
    _tree_cache.clear()


# ---------------------------------------------------------------------------
# Group roles — containers that provide structural context in see() output
# ---------------------------------------------------------------------------

# Always create a group heading (with or without label)
_ALWAYS_GROUP_ROLES = {"AXToolbar", "AXSheet", "AXDialog", "AXTabGroup"}

# Create a group heading only when they have a meaningful label
_LABELED_GROUP_ROLES = {"AXGroup", "AXScrollArea", "AXSplitGroup"}

_GROUP_DISPLAY = {
    "AXToolbar": "Toolbar",
    "AXSheet": "Sheet",
    "AXDialog": "Dialog",
    "AXTabGroup": "Tabs",
    "AXGroup": "",
    "AXScrollArea": "",
    "AXSplitGroup": "Split",
}


def _make_group_label(role, label):
    """Create a display-friendly group heading from AX role + label."""
    display = _GROUP_DISPLAY.get(role, "")
    if display and label:
        return f"{display}: {label}"
    if display:
        return display
    if label:
        return label
    return None


# Known Electron bundle IDs — these need AXManualAccessibility
_ELECTRON_BUNDLE_IDS = {
    "com.microsoft.VSCode",
    "com.microsoft.VSCodeInsiders",
    "com.electron.",  # prefix match — catches generic Electron apps
    "com.github.Electron",
    "com.slack.Slack",
    "com.spotify.client",
    "com.discordapp.Discord",
    "com.obsidian",
    "com.hnc.Discord",
    "com.figma.Desktop",
    "com.notion.Notion",
    "com.1password.1password",
}

# Track which PIDs we've already enabled AXManualAccessibility on
_ax_manual_enabled = set()


def _is_electron(bundle_id):
    """Check if a bundle ID belongs to an Electron app."""
    if not bundle_id:
        return False
    for eid in _ELECTRON_BUNDLE_IDS:
        if bundle_id == eid or bundle_id.startswith(eid):
            return True
    return False


def _ensure_electron_accessibility(pid):
    """Enable AXManualAccessibility for Electron apps.

    Tells Chromium to build the full native accessibility tree
    without VoiceOver. Goes from ~5 elements to 200+ in VS Code.
    Only sets once per PID per session (the flag persists until app quits).

    On first enable, waits up to 2s for the tree to populate —
    Chromium builds it asynchronously.
    """
    if pid in _ax_manual_enabled:
        return

    from CoreFoundation import kCFBooleanTrue
    import time

    app_ref = AXUIElementCreateApplication(pid)
    err = AXUIElementSetAttributeValue(app_ref, "AXManualAccessibility", kCFBooleanTrue)
    if err == kAXErrorSuccess:
        _ax_manual_enabled.add(pid)
        # Chromium builds the tree asynchronously — wait for it
        # Typical time: 1-2 seconds. We poll to return as soon as ready.
        window = ax_attr(app_ref, "AXFocusedWindow") or ax_attr(app_ref, "AXMainWindow")
        if window:
            for _ in range(8):  # 8 x 250ms = 2s max
                time.sleep(0.25)
                children = ax_attr(window, "AXChildren")
                if children and len(children) > 4:
                    break  # Tree is populating


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
    else:
        app = None

    # Enable Electron accessibility if needed
    bundle_id = _bundle_id_for_pid(pid, app)
    if _is_electron(bundle_id):
        _ensure_electron_accessibility(pid)

    app_ref = AXUIElementCreateApplication(pid)
    el = ax_attr(app_ref, "AXFocusedUIElement")
    if not el:
        return None

    return _element_to_dict(el, focused=True)


def _element_to_dict(el, focused=False, content=False):
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
            # In content mode, allow longer values for text areas
            max_len = 2000 if content else 300
            node["value"] = val_str[:max_len]

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


def walk_tree(element, max_depth=8, depth=0, max_elements=150,
              _tables=None, _lists=None, _group=None):
    """Walk accessibility tree, return flat list of meaningful elements.

    Args:
        element: Root AXUIElement to walk.
        max_depth: Maximum recursion depth.
        depth: Current depth (internal).
        max_elements: Maximum elements to collect.
        _tables: If provided, collect AXTable refs here (single-pass).
        _lists: If provided, collect AXList/AXOutline refs here (single-pass).
        _group: Current container group label (internal, for hierarchy).

    Returns:
        Flat list of element dicts, annotated with '_group' when inside
        a meaningful container (toolbar, dialog, etc.).
    """
    if depth > max_depth:
        return []

    results = []
    role = ax_attr(element, "AXRole") or ""
    title = ax_attr(element, "AXTitle") or ""
    desc = ax_attr(element, "AXDescription") or ""
    label = title or desc

    # Collect tables/lists for structured rendering (skip recursing into them)
    if _tables is not None and role == "AXTable":
        _tables.append(element)
        return results
    if _lists is not None and role in ("AXList", "AXOutline"):
        _lists.append(element)
        return results

    # Track group context for hierarchy
    current_group = _group
    if role in _ALWAYS_GROUP_ROLES:
        current_group = _make_group_label(role, label) or current_group
    elif role in _LABELED_GROUP_ROLES and label:
        current_group = _make_group_label(role, label) or current_group

    # Include if interactive or has a label
    if role in INTERACTIVE_ROLES or label:
        node = _element_to_dict(element)
        # Skip noise: unlabeled static text, tiny elements
        if node["label"] or node["role"] not in ("static text", "image", "group"):
            if current_group:
                node["_group"] = current_group
            results.append(node)

    if len(results) >= max_elements:
        return results

    # Recurse
    children = ax_attr(element, "AXChildren")
    if children:
        for child in children:
            results.extend(walk_tree(child, max_depth, depth + 1, max_elements,
                                     _tables=_tables, _lists=_lists,
                                     _group=current_group))
            if len(results) >= max_elements:
                break

    return results[:max_elements]


def _get_window(pid):
    """Get the best window for a PID (focused > main > first). Returns (window, is_electron)."""
    app = None

    if pid is None:
        app = frontmost_app()
        if not app:
            return None, False
        pid = app["pid"]

    bundle_id = _bundle_id_for_pid(pid, app)
    is_electron = _is_electron(bundle_id)
    if is_electron:
        _ensure_electron_accessibility(pid)

    app_ref = AXUIElementCreateApplication(pid)

    window = ax_attr(app_ref, "AXFocusedWindow")
    if not window:
        window = ax_attr(app_ref, "AXMainWindow")
    if not window:
        win_list = ax_attr(app_ref, "AXWindows")
        if win_list and len(win_list) > 0:
            window = win_list[0]

    return window, is_electron


def describe_app(pid=None, max_elements=150):
    """Get the full accessibility tree of an app's focused window.

    Args:
        pid: Process ID (default: frontmost app).
        max_elements: Maximum elements to collect (default 150).

    For Electron apps (VS Code, Slack, Discord, etc.), automatically
    enables AXManualAccessibility to unlock the full tree (~5 → 200+ elements).

    Results are cached for 1 second to avoid redundant walks within
    a single do() invocation (snap → action → snap).
    """
    # Resolve pid for cache key
    resolved_pid = pid
    if resolved_pid is None:
        app = frontmost_app()
        if app:
            resolved_pid = app["pid"]

    cache_key = ("describe", resolved_pid, max_elements)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    window, is_electron = _get_window(pid)
    if not window:
        return []

    depth = 20 if is_electron else 8
    result = walk_tree(window, max_depth=depth, max_elements=max_elements)
    _cache_set(cache_key, result)
    return result


def full_describe(pid=None, max_elements=150):
    """Single-pass tree walk returning elements, tables, and lists.

    This is the preferred way for see() to get all data — one walk
    instead of three separate calls to describe_app + find_tables + find_lists.

    Results are cached for 1 second.

    Returns:
        dict with "elements" (flat list), "tables" (structured table dicts),
        "lists" (structured list dicts).
    """
    resolved_pid = pid
    if resolved_pid is None:
        app = frontmost_app()
        if app:
            resolved_pid = app["pid"]

    cache_key = ("full", resolved_pid, max_elements)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    window, is_electron = _get_window(pid)
    if not window:
        return {"elements": [], "tables": [], "lists": []}

    depth = 20 if is_electron else 8
    table_refs = []
    list_refs = []
    elements = walk_tree(window, max_depth=depth, max_elements=max_elements,
                         _tables=table_refs, _lists=list_refs)

    tables = [tbl for t in table_refs if (tbl := read_table(t))]
    lists = [lst for el in list_refs if (lst := read_list(el))]

    result = {"elements": elements, "tables": tables, "lists": lists}
    _cache_set(cache_key, result)

    # Also populate the describe_app cache (same elements)
    _cache_set(("describe", resolved_pid, max_elements), elements)

    return result


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


def read_content(pid=None, max_chars=5000):
    """Read text content from the focused app's text areas and documents.

    Extracts AXValue from text areas, text fields, and web areas.
    For richer content, tries AXSelectedText and visible text ranges.

    Args:
        pid: Process ID (default: frontmost app).
        max_chars: Maximum total characters to return.

    Returns:
        list of dicts with role, label, and content text.
    """
    if pid is None:
        app = frontmost_app()
        if not app:
            return []
        pid = app["pid"]

    # Content-bearing roles
    content_roles = {
        "AXTextArea", "AXTextField", "AXStaticText", "AXWebArea",
        "AXScrollArea", "AXGroup",
    }

    app_ref = AXUIElementCreateApplication(pid)
    window = ax_attr(app_ref, "AXFocusedWindow") or ax_attr(app_ref, "AXMainWindow")
    if not window:
        return []

    results = []
    total_chars = 0

    def _extract_content(element, depth=0):
        nonlocal total_chars
        if depth > 12 or total_chars >= max_chars:
            return

        role = ax_attr(element, "AXRole") or ""

        if role in content_roles:
            value = ax_attr(element, "AXValue")
            if value is not None:
                text = str(value).strip()
                if text and len(text) > 2:  # Skip trivial content
                    title = ax_attr(element, "AXTitle") or ax_attr(element, "AXDescription") or ""
                    role_desc = ax_attr(element, "AXRoleDescription") or role.replace("AX", "").lower()
                    remaining = max_chars - total_chars
                    truncated = text[:remaining]
                    results.append({
                        "role": role_desc,
                        "label": title,
                        "content": truncated,
                    })
                    total_chars += len(truncated)
                    if total_chars >= max_chars:
                        return

        children = ax_attr(element, "AXChildren")
        if children:
            for child in children:
                _extract_content(child, depth + 1)
                if total_chars >= max_chars:
                    break

    _extract_content(window)
    return results


def read_table(element):
    """Extract structured table data from an AXTable element.

    Walks AXRows and their AXCells to build a rows×columns matrix.
    Detects headers from AXHeader or the first row.

    Args:
        element: An AXUIElement with role AXTable.

    Returns:
        dict with headers, rows, row_refs (for clicking), and dimensions.
        Returns None if the element isn't a table or has no data.
    """
    role = ax_attr(element, "AXRole") or ""
    if role != "AXTable":
        return None

    title = ax_attr(element, "AXTitle") or ax_attr(element, "AXDescription") or ""

    # Try to get rows via AXRows (preferred) or AXChildren
    rows_list = ax_attr(element, "AXRows") or []
    if not rows_list:
        children = ax_attr(element, "AXChildren")
        if children:
            rows_list = [c for c in children if (ax_attr(c, "AXRole") or "") == "AXRow"]

    if not rows_list:
        return None

    # Try to get column headers from AXHeader
    headers = []
    header_el = ax_attr(element, "AXHeader")
    if header_el:
        header_cells = ax_attr(header_el, "AXChildren") or []
        for cell in header_cells:
            headers.append(_cell_text(cell))

    # Try AXColumns for header names if AXHeader didn't work
    if not headers:
        columns = ax_attr(element, "AXColumns") or []
        for col in columns:
            col_header = ax_attr(col, "AXTitle") or ax_attr(col, "AXHeader") or ""
            if col_header:
                headers.append(str(col_header))

    # Extract row data
    data_rows = []
    row_refs = []  # Keep AX refs for clicking rows later
    for row in rows_list:
        cells = ax_attr(row, "AXChildren") or []
        row_data = []
        for cell in cells:
            row_data.append(_cell_text(cell))
        if row_data:
            data_rows.append(row_data)
            row_refs.append(row)

    if not data_rows:
        return None

    # If no explicit headers, use first row as headers if it looks like one
    # (all strings, no numbers) — otherwise leave headers empty
    num_cols = max(len(r) for r in data_rows) if data_rows else 0
    if not headers and num_cols > 0:
        headers = [f"Col {i+1}" for i in range(num_cols)]

    # Normalize row lengths
    for row in data_rows:
        while len(row) < num_cols:
            row.append("")

    return {
        "title": title,
        "headers": headers[:num_cols] if headers else [],
        "rows": data_rows,
        "row_refs": row_refs,
        "num_rows": len(data_rows),
        "num_cols": num_cols,
    }


def read_list(element):
    """Extract structured list data from an AXList or AXOutline element.

    Args:
        element: An AXUIElement with role AXList or AXOutline.

    Returns:
        dict with items (label, value, index), item_refs, and metadata.
        Returns None if the element isn't a list or has no items.
    """
    role = ax_attr(element, "AXRole") or ""
    if role not in ("AXList", "AXOutline"):
        return None

    title = ax_attr(element, "AXTitle") or ax_attr(element, "AXDescription") or ""

    children = ax_attr(element, "AXChildren") or []
    if not children:
        return None

    items = []
    item_refs = []
    for i, child in enumerate(children):
        child_role = ax_attr(child, "AXRole") or ""
        label = ax_attr(child, "AXTitle") or ax_attr(child, "AXDescription") or ""
        value = ax_attr(child, "AXValue")
        selected = ax_attr(child, "AXSelected")

        # For rows in outlines, get the text from first child
        if not label and child_role == "AXRow":
            row_children = ax_attr(child, "AXChildren") or []
            for rc in row_children:
                label = ax_attr(rc, "AXTitle") or ax_attr(rc, "AXValue") or ""
                if label:
                    label = str(label)
                    break

        # For generic children, try value
        if not label and value is not None:
            label = str(value)

        item = {"index": i, "label": label}
        if value is not None and str(value) != label:
            item["value"] = str(value)
        if selected:
            item["selected"] = True

        items.append(item)
        item_refs.append(child)

    if not items:
        return None

    return {
        "title": title,
        "type": "outline" if role == "AXOutline" else "list",
        "items": items,
        "item_refs": item_refs,
        "count": len(items),
    }


def find_tables(pid=None):
    """Find all tables in the focused window.

    Returns list of structured table data (from read_table).
    """
    if pid is None:
        app = frontmost_app()
        if not app:
            return []
        pid = app["pid"]

    app_ref = AXUIElementCreateApplication(pid)
    window = ax_attr(app_ref, "AXFocusedWindow") or ax_attr(app_ref, "AXMainWindow")
    if not window:
        return []

    tables = []
    _find_role(window, "AXTable", tables, max_depth=10)
    return [tbl for t in tables if (tbl := read_table(t))]


def find_lists(pid=None):
    """Find all lists in the focused window.

    Returns list of structured list data (from read_list).
    """
    if pid is None:
        app = frontmost_app()
        if not app:
            return []
        pid = app["pid"]

    app_ref = AXUIElementCreateApplication(pid)
    window = ax_attr(app_ref, "AXFocusedWindow") or ax_attr(app_ref, "AXMainWindow")
    if not window:
        return []

    lists = []
    _find_role(window, "AXList", lists, max_depth=10)
    _find_role(window, "AXOutline", lists, max_depth=10)
    return [lst for el in lists if (lst := read_list(el))]


def _find_role(element, target_role, results, depth=0, max_depth=10):
    """Recursively find elements with a specific role."""
    if depth > max_depth:
        return

    role = ax_attr(element, "AXRole") or ""
    if role == target_role:
        results.append(element)
        return  # Don't recurse into tables/lists themselves

    children = ax_attr(element, "AXChildren")
    if children:
        for child in children:
            _find_role(child, target_role, results, depth + 1, max_depth)


def _cell_text(cell):
    """Extract text content from a table cell element.

    Tries AXValue, AXTitle, then recurses into children.
    """
    value = ax_attr(cell, "AXValue")
    if value is not None:
        return str(value).strip()

    title = ax_attr(cell, "AXTitle")
    if title:
        return str(title).strip()

    desc = ax_attr(cell, "AXDescription")
    if desc:
        return str(desc).strip()

    # Recurse into children (cells often wrap content in static text)
    children = ax_attr(cell, "AXChildren")
    if children:
        for child in children:
            text = _cell_text(child)
            if text:
                return text

    return ""


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


def _bundle_id_for_pid(pid, app_info=None):
    """Get bundle ID for a PID. Uses cached app_info if available."""
    if app_info and app_info.get("bundle_id"):
        return app_info["bundle_id"]
    # Look up from running apps
    for a in running_apps():
        if a["pid"] == pid:
            return a.get("bundle_id", "")
    return ""


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
