"""Cortex Summarize — smart result summarization for Nexus commands.

Generates concise summaries from describe/web-ax results:
  - Element counts by type
  - Focused element
  - Error/dialog detection
  - Spatial grouping (top bar, sidebar, main content, bottom)

Pure functions. No LLM calls — all rule-based.
"""


# ---------------------------------------------------------------------------
# UIA Summarization
# ---------------------------------------------------------------------------

# Element types grouped by category
_UIA_CATEGORIES = {
    "button": {"ButtonControl", "SplitButtonControl"},
    "input": {"EditControl", "ComboBoxControl", "SpinnerControl", "SliderControl"},
    "checkbox": {"CheckBoxControl", "RadioButtonControl"},
    "link": {"HyperlinkControl"},
    "tab": {"TabItemControl", "TabControl"},
    "menu": {"MenuItemControl", "MenuBarControl"},
    "tree": {"TreeItemControl"},
    "list": {"ListItemControl"},
    "text": {"TextControl", "DocumentControl"},
}


def summarize_uia(result: dict) -> dict:
    """Generate a summary from a UIA describe result.

    Returns a summary dict that can be used as-is or prepended to full output.
    """
    elements = result.get("elements", [])
    win = result.get("window", {})
    focused = result.get("focused_element")

    # Count by category
    counts = {}
    for el in elements:
        el_type = el.get("type", "")
        for cat, types in _UIA_CATEGORIES.items():
            if el_type in types:
                counts[cat] = counts.get(cat, 0) + 1
                break

    # Detect errors/warnings
    errors = []
    for el in elements:
        name_lower = el.get("name", "").lower()
        if any(kw in name_lower for kw in ("error", "warning", "alert", "fail", "invalid")):
            errors.append(el.get("name", ""))

    # Detect dialogs (top-level panes/windows within the main window)
    dialogs = []
    for el in elements:
        if el.get("type", "") in {"WindowControl", "PaneControl"}:
            name = el.get("name", "").strip()
            if name and name != win.get("title", ""):
                dialogs.append(name)

    # Spatial groups
    groups = _spatial_groups_uia(elements, win)

    # Build summary line
    parts = [win.get("title", "?")]
    count_parts = []
    for cat in ("button", "input", "checkbox", "link", "tab", "menu", "tree", "list"):
        n = counts.get(cat, 0)
        if n > 0:
            count_parts.append("%d %s%s" % (n, cat, "s" if n > 1 else ""))
    if count_parts:
        parts.append(" | ".join(count_parts))

    if focused:
        parts.append("Focus: %s" % focused.get("name", "?"))
    if errors:
        parts.append("ERRORS: %s" % ", ".join(errors[:3]))
    if dialogs:
        parts.append("Dialogs: %s" % ", ".join(dialogs[:3]))

    return {
        "app": win.get("title", ""),
        "element_counts": counts,
        "total_elements": len(elements),
        "focused": focused.get("name", "") if focused else None,
        "errors": errors,
        "dialogs": dialogs,
        "groups": groups,
        "summary_line": " | ".join(parts),
    }


def _spatial_groups_uia(elements: list[dict], win: dict) -> dict:
    """Group elements by screen region based on y-coordinate.

    Returns: {"top": [...], "main": [...], "bottom": [...]}
    Names only, not full element dicts.
    """
    bounds = win.get("bounds", {})
    win_top = bounds.get("top", 0)
    win_bottom = bounds.get("bottom", 1080)
    win_height = win_bottom - win_top
    if win_height <= 0:
        return {}

    top_cutoff = win_top + win_height * 0.12
    bottom_cutoff = win_bottom - win_height * 0.12

    groups = {"top": [], "main": [], "bottom": []}
    for el in elements:
        el_bounds = el.get("bounds", {})
        cy = el_bounds.get("center_y", 0)
        name = el.get("name", "").strip()
        if not name:
            continue

        # Truncate long names
        display = name[:60] + "..." if len(name) > 60 else name

        if cy < top_cutoff:
            groups["top"].append(display)
        elif cy > bottom_cutoff:
            groups["bottom"].append(display)
        else:
            groups["main"].append(display)

    # Remove empty groups
    return {k: v for k, v in groups.items() if v}


# ---------------------------------------------------------------------------
# Web AXTree Summarization
# ---------------------------------------------------------------------------

_WEB_CATEGORIES = {
    "button": {"button"},
    "input": {"textbox", "combobox", "spinbutton", "slider", "searchbox"},
    "checkbox": {"checkbox", "radio", "switch"},
    "link": {"link"},
    "heading": {"heading"},
    "tab": {"tab"},
    "menu": {"menuitem"},
    "navigation": {"navigation"},
    "form": {"form"},
}


def summarize_web(result: dict) -> dict:
    """Generate a summary from a web-ax result."""
    nodes = result.get("nodes", [])
    title = result.get("title", "")
    url = result.get("url", "")

    counts = {}
    for node in nodes:
        role = node.get("role", "")
        for cat, roles in _WEB_CATEGORIES.items():
            if role in roles:
                counts[cat] = counts.get(cat, 0) + 1
                break

    # Find focused element
    focused_node = None
    for node in nodes:
        if node.get("focused"):
            focused_node = node
            break

    # Detect errors/alerts
    errors = []
    for node in nodes:
        if node.get("role") in ("alert", "status"):
            name = node.get("name", "").strip()
            if name:
                errors.append(name)
        elif any(kw in node.get("name", "").lower() for kw in ("error", "warning", "fail")):
            errors.append(node.get("name", ""))

    # Detect dialogs
    dialogs = [n.get("name", "") for n in nodes
               if n.get("role") in ("dialog", "alertdialog") and n.get("name", "").strip()]

    # Detect page type
    page_type = _detect_page_type(nodes, url)

    # Build summary line
    parts = [title or url]
    count_parts = []
    for cat in ("button", "input", "checkbox", "link", "heading", "tab", "menu"):
        n = counts.get(cat, 0)
        if n > 0:
            count_parts.append("%d %s%s" % (n, cat, "s" if n > 1 else ""))
    if count_parts:
        parts.append(" | ".join(count_parts))
    if focused_node:
        parts.append("Focus: [%s] %s" % (focused_node.get("role", "?"), focused_node.get("name", "?")))
    if page_type:
        parts.append("Type: %s" % page_type)
    if errors:
        parts.append("ERRORS: %s" % ", ".join(errors[:3]))
    if dialogs:
        parts.append("Dialogs: %s" % ", ".join(dialogs[:3]))

    return {
        "app": title,
        "url": url,
        "page_type": page_type,
        "element_counts": counts,
        "total_elements": len(nodes),
        "focused": {"role": focused_node.get("role", ""), "name": focused_node.get("name", "")} if focused_node else None,
        "errors": errors,
        "dialogs": dialogs,
        "summary_line": " | ".join(parts),
    }


def _detect_page_type(nodes: list[dict], url: str) -> str | None:
    """Heuristic page type detection."""
    roles = {n.get("role", "") for n in nodes}
    names = " ".join(n.get("name", "").lower() for n in nodes)

    # Login/auth page
    if "password" in names or "sign in" in names or "log in" in names:
        return "login"

    # Search results
    if "search" in url.lower() or ("searchbox" in roles and "link" in roles):
        link_count = sum(1 for n in nodes if n.get("role") == "link")
        if link_count > 5:
            return "search-results"

    # Form-heavy page
    input_count = sum(1 for n in nodes if n.get("role") in ("textbox", "combobox", "checkbox", "radio"))
    if input_count >= 3:
        return "form"

    # Article/content page
    heading_count = sum(1 for n in nodes if n.get("role") == "heading")
    if heading_count >= 2 and input_count <= 1:
        return "article"

    # Dashboard
    if "tab" in roles and "button" in roles:
        tab_count = sum(1 for n in nodes if n.get("role") == "tab")
        if tab_count >= 3:
            return "dashboard"

    return None


# ---------------------------------------------------------------------------
# Format summary for output
# ---------------------------------------------------------------------------

def format_summary(summary: dict, include_groups: bool = True) -> str:
    """Format a summary dict as compact text."""
    lines = [summary.get("summary_line", "")]

    if summary.get("url"):
        lines.append("URL: %s" % summary["url"])

    if summary.get("page_type"):
        lines.append("Page type: %s" % summary["page_type"])

    if include_groups:
        groups = summary.get("groups", {})
        if groups.get("top"):
            lines.append("TOP: %s" % ", ".join(groups["top"][:8]))
        if groups.get("main"):
            main_items = groups["main"]
            if len(main_items) > 10:
                lines.append("MAIN: %s... (+%d more)" % (
                    ", ".join(main_items[:8]), len(main_items) - 8))
            else:
                lines.append("MAIN: %s" % ", ".join(main_items))
        if groups.get("bottom"):
            lines.append("BOTTOM: %s" % ", ".join(groups["bottom"][:5]))

    return "\n".join(lines)
