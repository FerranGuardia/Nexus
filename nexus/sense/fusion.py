"""Unified perception — the `see` tool.

Fuses accessibility tree, window list, screenshots, OCR fallback,
and system dialog detection into a single, token-efficient text
snapshot of the computer.
"""

from nexus.sense import access, screen
from nexus.hooks import fire

# Snapshot storage for diff mode
_last_snapshot = None


def see(app=None, query=None, screenshot=False, menus=False, diff=False, content=False, observe=False, max_elements=50):
    """Main perception function. Returns a text snapshot of the computer.

    Args:
        app: App name or PID to look at (default: frontmost).
        query: Search for specific elements instead of full tree.
        screenshot: Include a base64 screenshot.
        menus: Include the app's menu bar items (shows available commands).
        diff: Compare with previous snapshot — show what changed.
        content: Include text content from documents, text areas, and fields.
            Shows what's written in the app, not just the UI structure.
        observe: Start observing this app for changes. Events are buffered
            and included in subsequent see() calls automatically.
        max_elements: Max elements to display (default 80). Use query= to
            search within large apps instead of raising this.

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

    # Windows list (capped at 8 for token efficiency)
    wins = access.windows()
    if wins:
        result_parts.append("")
        result_parts.append(f"Windows ({len(wins)}):")
        for w in wins[:8]:
            title_part = f' — "{w["title"]}"' if w["title"] else ""
            result_parts.append(f'  {w["app"]}{title_part}')
        if len(wins) > 8:
            result_parts.append(f"  ... and {len(wins) - 8} more")

    # Menu bar (what commands are available) — capped to 150
    max_menu_items = 150
    if menus:
        menu_items = access.menu_bar(pid)
        if menu_items:
            # Show top-level menus fully, submenus up to 2 levels deep
            shown = []
            for item in menu_items:
                if len(shown) >= max_menu_items:
                    break
                # depth 0 = top-level menu, depth 1 = submenu, depth 2 = sub-submenu
                if item["depth"] <= 2:
                    shown.append(item)

            total = len(menu_items)
            result_parts.append("")
            result_parts.append(f"Menus ({total} items):")
            for item in shown:
                indent = "  " * (item["depth"] + 1)
                shortcut = f' ({item["shortcut"]})' if item.get("shortcut") else ""
                disabled = " (disabled)" if item.get("enabled") is False else ""
                result_parts.append(f'{indent}{item["path"]}{shortcut}{disabled}')
            remaining = total - len(shown)
            if remaining > 0:
                result_parts.append(f"  ... and {remaining} more menu items")

    # Observation — start if requested, always drain buffered events
    obs_pid = pid or (app_info["pid"] if app_info else None)
    if observe and obs_pid:
        from nexus.sense.observe import start_observing, is_observing
        if not is_observing(obs_pid):
            app_name = app_info["name"] if app_info else ""
            start_observing(obs_pid, app_name)

    from nexus.sense.observe import drain_events, format_events
    obs_events = drain_events()
    if obs_events:
        result_parts.append("")
        result_parts.append(format_events(obs_events))

    # Elements (search or full tree)
    result_parts.append("")
    tables = []
    lists = []
    fetch_limit = max(max_elements * 2, 150)
    cached_elements = None
    if query:
        elements = access.find_elements(query, pid)
        result_parts.append(f'Search "{query}" ({len(elements)} matches):')
        # Show all search results unfiltered
        for el in elements:
            result_parts.append(f"  {_format_element(el)}")
    else:
        # Perception pipeline: run all layers (AX → OCR → templates)

        # Hook: before_see — spatial cache read, app skill loading
        before_ctx = fire("before_see", {
            "pid": pid, "query": query, "app_info": app_info,
            "fetch_limit": fetch_limit,
        })
        cached_elements = before_ctx.get("cached_elements")

        if cached_elements is not None:
            elements = cached_elements
            tables = []  # Can't cache (contain AX refs)
            lists = []
        else:
            from nexus.sense.plugins import run_pipeline
            effective_pid = pid or (app_info["pid"] if app_info else None)
            bounds = _app_window_bounds(effective_pid) if effective_pid else None
            elements, pipeline_ctx = run_pipeline(
                pid, app_info=app_info, bounds=bounds,
                fetch_limit=fetch_limit,
            )
            tables = pipeline_ctx.get("tables", [])
            lists = pipeline_ctx.get("lists", [])

        # Filter out noise (unlabeled static text/images, wrapper groups)
        clean = [el for el in elements if not _is_noise_element(el)]
        clean = _suppress_wrapper_groups(clean)

        total = len(clean)
        shown = clean[:max_elements]
        result_parts.append(f"Elements ({total}):")
        result_parts.extend(_render_grouped_elements(shown))
        remaining = total - len(shown)
        if remaining > 0:
            result_parts.append(f"  ... and {remaining} more (use query= to search)")

    if not elements:
        result_parts.append("  (no elements found)")

    # Hook: after_see — OCR fallback, system dialog detection, spatial cache write
    fire("after_see", {
        "pid": pid, "elements": elements, "app_info": app_info,
        "result_parts": result_parts, "query": query,
        "fetch_limit": fetch_limit,
        "from_cache": cached_elements is not None,
    })

    # Structured tables — from the single-pass walk (or separate for query mode)
    if not tables and not query:
        pass  # Already collected above
    elif query:
        tables = access.find_tables(pid)
    if tables:
        result_parts.append("")
        for tbl in tables:
            result_parts.append(_format_table(tbl))

    # Structured lists — from the single-pass walk (or separate for query mode)
    if not lists and not query:
        pass  # Already collected above
    elif query:
        lists = access.find_lists(pid)
    if lists:
        result_parts.append("")
        for lst in lists:
            result_parts.append(_format_list(lst))

    # Content reading — show what's *in* text areas, documents, fields
    if content:
        content_items = access.read_content(pid)
        if content_items:
            result_parts.append("")
            result_parts.append("Content:")
            for item in content_items:
                label_part = f' "{item["label"]}"' if item["label"] else ""
                text = item["content"]
                # Show first lines, indent for readability
                lines = text.split("\n")
                if len(lines) <= 5:
                    preview = text
                else:
                    preview = "\n".join(lines[:5]) + f"\n... ({len(lines)} lines total)"
                result_parts.append(f'  [{item["role"]}]{label_part}:')
                for line in preview.split("\n"):
                    result_parts.append(f"    {line}")

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


def _is_noise_element(el):
    """Return True for unlabeled static text / images — they add no value for the AI."""
    label = el.get("label", "")
    role = el.get("_ax_role", "") or el.get("role", "")
    if not label:
        ax_role = role.replace("AX", "").lower() if role.startswith("AX") else role.lower()
        if ax_role in ("statictext", "static text", "image"):
            return True
    return False


def _suppress_wrapper_groups(elements):
    """Remove AXGroup elements that just duplicate nearby interactive elements.

    Catches the common macOS pattern where a group wraps a single button:
        [group "Save"] [button "Save"]  →  keep only [button "Save"]

    Only suppresses groups whose label matches a non-group element.
    Groups with unique labels (no matching interactive element) are kept.
    """
    non_group_labels = set()
    for el in elements:
        label = el.get("label", "")
        if label and el.get("_ax_role") != "AXGroup":
            non_group_labels.add(label)

    return [el for el in elements
            if el.get("_ax_role") != "AXGroup"
            or el.get("label", "") not in non_group_labels]


def _render_grouped_elements(elements):
    """Render elements with container group headings.

    Two-pass: first count non-container elements per group, then render.
    Only shows headings for groups with 2+ useful elements.
    Suppresses redundant container elements under their own heading.

    Returns:
        list of formatted lines.
    """
    # Pass 1: count useful (non-container) elements per group
    group_counts = {}
    for el in elements:
        group = el.get("_group")
        if not _is_group_container(el):
            group_counts[group] = group_counts.get(group, 0) + 1

    # Pass 2: render
    lines = []
    current_group = None
    MIN_FOR_HEADING = 2

    for el in elements:
        group = el.get("_group")
        useful_count = group_counts.get(group, 0)
        show_heading = group is not None and useful_count >= MIN_FOR_HEADING

        if group != current_group:
            current_group = group
            if show_heading:
                display = group[:60] + "..." if len(group) > 60 else group
                lines.append(f"  {display}:")

        # Skip container noise under its own heading
        if show_heading and _is_group_container(el):
            continue

        indent = "    " if show_heading else "  "
        lines.append(f"{indent}{_format_element(el)}")

    return lines


# Container AX roles — these create group headings, so showing them
# as elements under their own heading is redundant noise.
_GROUP_AX_ROLES = frozenset({
    "AXToolbar", "AXSheet", "AXDialog", "AXTabGroup",
    "AXGroup", "AXScrollArea", "AXSplitGroup",
})


def _is_group_container(el):
    """Is this element a group container (redundant when shown under its heading)?"""
    return el.get("_ax_role", "") in _GROUP_AX_ROLES


def _format_element(el, show_pos=False):
    """Format an element as a compact one-liner.

    Args:
        show_pos: Include position coordinates (default False — saves tokens).
            Positions are still available via see(query=...) or element dicts.
    """
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
        v = value if len(value) <= 40 else value[:37] + "..."
        parts.append(f"= {v}")
    if show_pos and pos:
        parts.append(f"@ {pos[0]},{pos[1]}")
    if focused:
        parts.append("*focused*")
    if not enabled:
        parts.append("(disabled)")
    # Show source for non-AX elements (OCR, template, etc.)
    source = el.get("source")
    if source and source != "ax":
        parts.append(f"({source})")

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
# Post-action state — compact view for merged do()+see() responses
# ---------------------------------------------------------------------------

def compact_state(pid=None, max_elements=15):
    """Return a compact text summary of the current screen state.

    Designed for post-action responses — shows enough for the agent
    to decide its next action without a separate see() call.
    Reuses cached tree data from snap(), so this is nearly free.

    Returns a text string (never None).
    """
    if pid is None:
        app_info = access.frontmost_app()
        if app_info:
            pid = app_info["pid"]
    else:
        app_info = _app_info_for_pid(pid)

    if app_info is None and pid:
        apps = access.running_apps()
        app_info = next((a for a in apps if a["pid"] == pid), None)

    parts = []

    # App + window
    if app_info:
        win_title = access.window_title(pid)
        header = f"App: {app_info['name']}"
        if win_title:
            header += f' — "{win_title}"'
        parts.append(header)

    # Focused element (critical for knowing what to type/press next)
    focus = access.focused_element(pid)
    if focus:
        parts.append(f"Focus: {_format_element(focus)}")

    # Key interactive elements (compact — tries spatial cache, falls back to tree)
    try:
        from nexus.mind.session import spatial_get, spatial_put
        cached, _ = spatial_get(pid)
    except Exception:
        cached = None

    if cached is not None:
        elements = cached
    else:
        elements = access.describe_app(pid)
        try:
            spatial_put(pid, elements)
        except Exception:
            pass
    if elements:
        clean = [el for el in elements if not _is_noise_element(el)]
        clean = _suppress_wrapper_groups(clean)
        shown = clean[:max_elements]
        parts.append(f"Elements ({len(clean)}):")
        for el in shown:
            parts.append(f"  {_format_element(el)}")
        remaining = len(clean) - len(shown)
        if remaining > 0:
            parts.append(f"  ... and {remaining} more (use see() for full tree)")

    return "\n".join(parts)


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

    # Populate spatial cache so compact_state() gets a free hit
    try:
        from nexus.mind.session import spatial_put
        spatial_put(pid, elements)
    except Exception:
        pass

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
    from nexus.mind.session import compute_layout_hash
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
        "layout_hash": compute_layout_hash(elements),
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
# Structured data formatting
# ---------------------------------------------------------------------------

def _format_table(tbl):
    """Format a table dict as compact ASCII table."""
    title = tbl.get("title", "")
    headers = tbl.get("headers", [])
    rows = tbl.get("rows", [])
    num_rows = tbl.get("num_rows", 0)
    num_cols = tbl.get("num_cols", 0)

    title_part = f' "{title}"' if title else ""
    lines = [f"Table{title_part} ({num_cols} cols x {num_rows} rows):"]

    if not rows:
        lines.append("  (empty)")
        return "\n".join(lines)

    # Calculate column widths (cap at 30 chars per column)
    max_col_width = 30
    col_widths = []
    for c in range(num_cols):
        w = len(headers[c]) if c < len(headers) else 4
        for row in rows[:20]:  # Sample first 20 rows
            if c < len(row):
                w = max(w, len(str(row[c])[:max_col_width]))
        col_widths.append(min(w, max_col_width))

    def _fmt_row(cells):
        parts = []
        for c in range(num_cols):
            val = str(cells[c])[:max_col_width] if c < len(cells) else ""
            parts.append(val.ljust(col_widths[c]))
        return "  | " + " | ".join(parts) + " |"

    # Header
    if headers:
        lines.append(_fmt_row(headers))
        lines.append("  |" + "|".join("-" * (w + 2) for w in col_widths) + "|")

    # Data rows (cap at 20 for token efficiency)
    for row in rows[:20]:
        lines.append(_fmt_row(row))
    if num_rows > 20:
        lines.append(f"  ... and {num_rows - 20} more rows")

    return "\n".join(lines)


def _format_list(lst):
    """Format a list dict as numbered items."""
    title = lst.get("title", "")
    items = lst.get("items", [])
    count = lst.get("count", 0)
    list_type = lst.get("type", "list")

    title_part = f' "{title}"' if title else ""
    type_name = "Outline" if list_type == "outline" else "List"
    lines = [f"{type_name}{title_part} ({count} items):"]

    if not items:
        lines.append("  (empty)")
        return "\n".join(lines)

    for item in items[:30]:
        idx = item["index"] + 1
        label = item.get("label", "")
        value = item.get("value", "")
        selected = " *selected*" if item.get("selected") else ""
        val_part = f" = {value}" if value else ""
        lines.append(f"  {idx}. {label}{val_part}{selected}")

    if count > 30:
        lines.append(f"  ... and {count - 30} more items")

    return "\n".join(lines)


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


# ---------------------------------------------------------------------------
# System dialog detection
# ---------------------------------------------------------------------------

def _detect_system_dialogs():
    """Check for system dialogs (Gatekeeper, SecurityAgent, etc.).

    Returns formatted text for see() output, or empty string.
    """
    try:
        from nexus.sense.system import detect_system_dialogs, classify_dialog, format_system_dialogs
        dialogs = detect_system_dialogs()
        if not dialogs:
            return ""

        # Try to OCR and classify each dialog
        classifications = []
        for d in dialogs:
            ocr_results = _ocr_dialog_region(d)
            classification = classify_dialog(d, ocr_results)
            classifications.append(classification)

        return format_system_dialogs(dialogs, classifications)
    except Exception:
        return ""


def _ocr_dialog_region(dialog):
    """OCR a system dialog's region. Returns OCR results or empty list."""
    try:
        from nexus.sense.ocr import ocr_region
        b = dialog.get("bounds", {})
        x, y, w, h = b.get("x", 0), b.get("y", 0), b.get("w", 0), b.get("h", 0)
        if w > 0 and h > 0:
            return ocr_region(x, y, w, h)
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# OCR fallback for sparse AX trees
# ---------------------------------------------------------------------------

def _ocr_fallback(pid, app_info):
    """Run OCR when the AX tree has too few labeled elements.

    Captures the app's window region and runs Apple Vision OCR.
    Returns list of element dicts compatible with see() format.
    """
    try:
        from nexus.sense.ocr import ocr_region, ocr_to_elements

        # Get window bounds for the target app
        bounds = _app_window_bounds(pid)
        if not bounds:
            return []

        x, y, w, h = bounds
        if w <= 0 or h <= 0:
            return []

        ocr_results = ocr_region(x, y, w, h)
        if not ocr_results:
            return []

        return ocr_to_elements(ocr_results)
    except Exception:
        return []


def _app_window_bounds(pid):
    """Get the main window bounds for a PID. Returns (x, y, w, h) or None."""
    try:
        from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        if not windows:
            return None

        for w in windows:
            if w.get("kCGWindowOwnerPID") == pid:
                b = w.get("kCGWindowBounds", {})
                width = b.get("Width", 0)
                height = b.get("Height", 0)
                if width > 50 and height > 50:
                    return (b.get("X", 0), b.get("Y", 0), width, height)
    except Exception:
        pass
    return None
