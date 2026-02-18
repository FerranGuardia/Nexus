"""Compact output formatters for Nexus commands.

Pure functions: take a command result dict, return a formatted string.
No side effects, no imports from other nexus modules.
"""

# Role abbreviation map — keep roles short but recognizable
ROLE_ABBREV = {
    "ButtonControl": "Btn",
    "EditControl": "Edit",
    "HyperlinkControl": "Link",
    "MenuItemControl": "Menu",
    "CheckBoxControl": "Check",
    "RadioButtonControl": "Radio",
    "ComboBoxControl": "Combo",
    "TabItemControl": "Tab",
    "ListItemControl": "Item",
    "TreeItemControl": "Tree",
    "TextControl": "Text",
    "ImageControl": "Img",
    "GroupControl": "Group",
    "PaneControl": "Pane",
    "WindowControl": "Win",
    "ToolBarControl": "Toolbar",
    "StatusBarControl": "Status",
    "MenuBarControl": "MenuBar",
    "HeaderControl": "Header",
    "DataItemControl": "Data",
    "DocumentControl": "Doc",
    "ScrollBarControl": "Scroll",
    "SliderControl": "Slider",
    "SpinnerControl": "Spin",
    "ProgressBarControl": "Progress",
    "TableControl": "Table",
    "ToolTipControl": "Tip",
    "CustomControl": "Custom",
    "SplitButtonControl": "SplitBtn",
    "ThumbControl": "Thumb",
    "TitleBarControl": "TitleBar",
    "AppBarControl": "AppBar",
    "SemanticZoomControl": "Zoom",
    "ListControl": "List",
    "TreeControl": "TreeView",
    "TabControl": "TabCtl",
    "MenuControl": "MenuCtl",
    "HeaderItemControl": "HeaderItem",
    "SeparatorControl": "Sep",
    "CalendarControl": "Cal",
    "DataGridControl": "Grid",
}

# Web role abbreviations
WEB_ROLE_ABBREV = {
    "button": "Btn",
    "link": "Link",
    "textbox": "Edit",
    "heading": "H",
    "checkbox": "Check",
    "radio": "Radio",
    "combobox": "Combo",
    "tab": "Tab",
    "menuitem": "Menu",
    "listitem": "Item",
    "img": "Img",
    "search": "Search",
    "navigation": "Nav",
    "banner": "Banner",
    "main": "Main",
    "region": "Region",
    "form": "Form",
    "list": "List",
    "table": "Table",
    "cell": "Cell",
    "row": "Row",
    "group": "Group",
    "tree": "Tree",
    "treeitem": "Tree",
    "slider": "Slider",
    "spinbutton": "Spin",
    "dialog": "Dialog",
    "alert": "Alert",
    "status": "Status",
    "progressbar": "Progress",
    "tooltip": "Tip",
    "separator": "Sep",
}


def _abbrev(control_type: str) -> str:
    """Abbreviate a UIA ControlTypeName."""
    return ROLE_ABBREV.get(control_type, control_type.replace("Control", ""))


def _web_abbrev(role: str) -> str:
    """Abbreviate a web accessibility role."""
    return WEB_ROLE_ABBREV.get(role, role.capitalize() if role else "?")


def _bounds_short(bounds: dict) -> str:
    """Format bounds as compact string: (cx,cy) WxH"""
    if not bounds:
        return ""
    cx = bounds.get("center_x", bounds.get("x", 0))
    cy = bounds.get("center_y", bounds.get("y", 0))
    w = bounds.get("width", 0)
    h = bounds.get("height", 0)
    return "(%d,%d) %dx%d" % (cx, cy, w, h)


# ---------------------------------------------------------------------------
# UIA element formatters
# ---------------------------------------------------------------------------

def _format_uia_element_compact(el: dict) -> str:
    """One-liner for a UIA element: [Type] Name | (cx,cy) WxH"""
    role = _abbrev(el.get("type", ""))
    name = el.get("name", "").strip()
    bounds = _bounds_short(el.get("bounds", {}))
    enabled = el.get("is_enabled")
    parts = ["[%s] %s" % (role, name)]
    if bounds:
        parts.append(bounds)
    if enabled is False:
        parts.append("*disabled*")
    return " | ".join(parts)


def _format_uia_element_minimal(el: dict) -> str:
    """Minimal: [Type] Name"""
    role = _abbrev(el.get("type", ""))
    name = el.get("name", "").strip()
    return "[%s] %s" % (role, name)


# ---------------------------------------------------------------------------
# Web element formatters
# ---------------------------------------------------------------------------

def _format_web_node_compact(node: dict) -> str:
    """One-liner for a web AX node: [Role] Name *flags*"""
    role = _web_abbrev(node.get("role", ""))
    name = node.get("name", "").strip()
    flags = []
    if node.get("focused"):
        flags.append("*focused*")
    if node.get("disabled"):
        flags.append("*disabled*")
    if node.get("checked") is True:
        flags.append("*checked*")
    if node.get("expanded") is True:
        flags.append("*expanded*")
    level = node.get("level")
    if level:
        role = "%s%s" % (role, level)
    line = "[%s] %s" % (role, name)
    if flags:
        line += " " + " ".join(flags)
    return line


def _format_web_element_compact(el: dict) -> str:
    """One-liner for web-find/web-describe elements: [tag] text | (x,y) WxH"""
    tag = el.get("tag", el.get("type", "?"))
    text = el.get("text", el.get("name", "")).strip()
    bounds = _bounds_short(el.get("bounds", {}))
    href = el.get("href")
    parts = ["[%s] %s" % (tag, text)]
    if href:
        parts.append(href)
    if bounds:
        parts.append(bounds)
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Command-level formatters
# ---------------------------------------------------------------------------

# Commands whose output contains element lists worth compacting
OCULUS_UIA_COMMANDS = {"describe", "windows", "find", "focused"}
OCULUS_WEB_COMMANDS = {"web-describe", "web-text", "web-find", "web-links",
                       "web-tabs", "web-ax", "web-measure", "web-markdown"}


def format_compact(result: dict) -> str:
    """Format a command result dict as compact one-liner-per-element text."""
    cmd = result.get("command", "")
    lines = []

    # Summary mode
    if result.get("mode") == "summary":
        lines.append("SUMMARY: %s" % result.get("summary_line", ""))
        if result.get("url"):
            lines.append("URL: %s" % result["url"])
        if result.get("page_type"):
            lines.append("Page type: %s" % result["page_type"])
        groups = result.get("groups", {})
        if groups.get("top"):
            lines.append("TOP: %s" % ", ".join(groups["top"][:8]))
        if groups.get("main"):
            main = groups["main"]
            if len(main) > 10:
                lines.append("MAIN: %s... (+%d more)" % (", ".join(main[:8]), len(main) - 8))
            else:
                lines.append("MAIN: %s" % ", ".join(main))
        if groups.get("bottom"):
            lines.append("BOTTOM: %s" % ", ".join(groups["bottom"][:5]))
        return "\n".join(lines)

    # Diff mode — works for both describe and web-ax diffs
    if result.get("mode") == "diff":
        win = result.get("window", "")
        if isinstance(win, dict):
            win = win.get("title", "?")
        lines.append("DIFF %s (%.1fs ago, %d unchanged)" % (
            win, result.get("since_seconds", 0), result.get("unchanged_count", 0)))
        lines.append(result.get("summary", ""))
        for el in result.get("added", []):
            if el.get("role"):
                lines.append("+ %s" % _format_web_node_compact(el))
            else:
                lines.append("+ %s" % _format_uia_element_compact(el))
        for el in result.get("removed", []):
            if el.get("role"):
                lines.append("- %s" % _format_web_node_compact(el))
            else:
                lines.append("- %s" % _format_uia_element_compact(el))
        for ch in result.get("changed", []):
            role = _abbrev(ch.get("type", "")) if "Control" in ch.get("type", "") else _web_abbrev(ch.get("type", ""))
            changes_str = ", ".join("%s: %s→%s" % (k, v[0], v[1]) for k, v in ch.get("changes", {}).items())
            lines.append("~ [%s] %s | %s" % (role, ch.get("name", ""), changes_str))
        return "\n".join(lines)

    if cmd == "describe":
        win = result.get("window", {})
        lines.append("# %s" % win.get("title", "?"))
        cursor = result.get("cursor", {})
        lines.append("Cursor: (%d,%d)" % (cursor.get("x", 0), cursor.get("y", 0)))
        focused_el = result.get("focused_element")
        if focused_el:
            lines.append("Focus: %s" % _format_uia_element_compact(focused_el))
        lines.append("---")
        for el in result.get("elements", []):
            lines.append(_format_uia_element_compact(el))
        lines.append("(%d elements)" % result.get("element_count", 0))

    elif cmd == "windows":
        for win in result.get("windows", []):
            fg = "*fg*" if win.get("is_foreground") else ""
            vis = "" if win.get("is_visible") else "*hidden*"
            bounds = _bounds_short(win.get("bounds")) if win.get("bounds") else ""
            parts = ["[Win] %s" % win.get("title", "?")]
            if bounds:
                parts.append(bounds)
            flags = " ".join(f for f in [fg, vis] if f)
            if flags:
                parts.append(flags)
            lines.append(" | ".join(parts))
        lines.append("(%d windows)" % result.get("count", 0))

    elif cmd == "find":
        lines.append("# find '%s' in %s" % (result.get("query", ""), result.get("window", "")))
        for el in result.get("matches", []):
            lines.append(_format_uia_element_compact(el))
        lines.append("(%d matches)" % result.get("count", 0))

    elif cmd == "focused":
        el = result.get("element")
        if el:
            lines.append(_format_uia_element_compact(el))
            chain = result.get("parent_chain", [])
            if chain:
                path = " > ".join("%s(%s)" % (p.get("name", ""), _abbrev(p.get("type", "")))
                                  for p in chain)
                lines.append("Chain: %s" % path)
        else:
            lines.append("(no focused element)")

    elif cmd == "web-describe":
        lines.append("# %s" % result.get("title", "?"))
        lines.append("URL: %s" % result.get("url", ""))
        # Concise mode fields
        if result.get("heading"):
            lines.append("H1: %s" % result["heading"])
        if result.get("focused"):
            f = result["focused"]
            lines.append("Focus: [%s] %s" % (f.get("tag", "?"), f.get("text", "")))
        # Full mode fields
        if result.get("headings"):
            lines.append("--- Headings ---")
            for h in result["headings"]:
                lines.append("[%s] %s" % (h.get("level", "?"), h.get("text", "")))
        if result.get("buttons"):
            lines.append("--- Buttons ---")
            for b in result["buttons"]:
                lines.append("[Btn] %s" % b.get("text", ""))
        if result.get("inputs"):
            lines.append("--- Inputs ---")
            for inp in result["inputs"]:
                label = inp.get("label") or inp.get("placeholder") or inp.get("name") or "?"
                val = inp.get("value", "")
                vstr = " = '%s'" % val if val else ""
                lines.append("[%s] %s%s" % (inp.get("type", "?"), label, vstr))
        if result.get("links"):
            lines.append("--- Links (%d) ---" % result.get("link_count", 0))
            for lnk in result["links"][:20]:
                lines.append("[Link] %s | %s" % (lnk.get("text", ""), lnk.get("href", "")))
            if len(result["links"]) > 20:
                lines.append("... +%d more" % (len(result["links"]) - 20))

    elif cmd == "web-text":
        lines.append("# %s" % result.get("title", "?"))
        lines.append("URL: %s" % result.get("url", ""))
        lines.append(result.get("text", ""))
        if result.get("truncated"):
            lines.append("... (truncated, %d lines total)" % result.get("line_count", 0))

    elif cmd == "web-find":
        lines.append("# web-find '%s'" % result.get("query", ""))
        for el in result.get("matches", []):
            lines.append(_format_web_element_compact(el))
        lines.append("(%d matches)" % result.get("count", 0))

    elif cmd == "web-links":
        lines.append("URL: %s" % result.get("url", ""))
        for lnk in result.get("links", []):
            lines.append("[Link] %s | %s" % (lnk.get("text", ""), lnk.get("href", "")))
        lines.append("(%d links)" % result.get("count", 0))

    elif cmd == "web-tabs":
        for tab in result.get("tabs", []):
            active = "*active*" if tab.get("is_active") else ""
            parts = [tab.get("title", "?"), tab.get("url", "")]
            if active:
                parts.append(active)
            lines.append(" | ".join(parts))
        lines.append("(%d tabs)" % result.get("count", 0))

    elif cmd == "web-ax":
        lines.append("# %s" % result.get("title", "?"))
        for node in result.get("nodes", []):
            lines.append(_format_web_node_compact(node))
        lines.append("(%d nodes)" % result.get("count", 0))

    elif cmd == "web-measure":
        for el in result.get("elements", []):
            if el.get("error"):
                lines.append("[%s] ERROR: %s" % (el.get("selector", "?"), el["error"]))
            else:
                lines.append("[%s] %dx%d @(%d,%d) pad:%s mar:%s %s %s" % (
                    el.get("selector", "?"),
                    el.get("width", 0), el.get("height", 0),
                    el.get("x", 0), el.get("y", 0),
                    el.get("padding", []),
                    el.get("margin", []),
                    el.get("display", ""),
                    el.get("font_size", ""),
                ))

    elif cmd == "web-markdown":
        if result.get("error"):
            lines.append("ERROR: %s" % result["error"])
        else:
            lines.append("# %s" % result.get("title", "?"))
            if result.get("byline"):
                lines.append("By: %s" % result["byline"])
            lines.append(result.get("content", ""))

    elif cmd == "measure-image":
        sz = result.get("image_size", {})
        lines.append("# measure-image: %dx%d (scale: %.1f)" % (
            sz.get("width", 0), sz.get("height", 0), result.get("scale", 1.0)))
        lines.append("Elements: %d (omniparser: %d, ocr: %d)" % (
            result.get("count", 0), result.get("omniparser_count", 0), result.get("ocr_word_count", 0)))
        lines.append("---")
        for el in result.get("elements", []):
            b = el.get("bounds", {})
            ocr = " '%s'" % el["ocr_text"] if el.get("ocr_text") else ""
            lines.append("[%s] %s%s | (%d,%d) %dx%d" % (
                el.get("type", "?"), el.get("name", ""), ocr,
                b.get("x", 0), b.get("y", 0), b.get("width", 0), b.get("height", 0)))

    elif cmd == "web-layout-diff":
        summ = result.get("summary", {})
        lines.append("# layout-diff: %d matched, %d issues" % (summ.get("matched", 0), summ.get("issues", 0)))
        lines.append("URL: %s | match_by: %s" % (result.get("url", "?"), result.get("match_by", "?")))
        lines.append("---")
        for m in result.get("matched", []):
            d = m.get("deltas", {})
            ok = "OK" if m.get("ok") else "MISMATCH"
            w_diff = d.get("width", {}).get("diff", 0)
            h_diff = d.get("height", {}).get("diff", 0)
            lines.append("[%s] %s → %s | w%+d h%+d" % (
                ok, m.get("selector", "?"),
                m.get("image_text", m.get("live_text", ""))[:40],
                w_diff, h_diff))
        if result.get("unmatched_selectors"):
            lines.append("Unmatched selectors: %s" % ", ".join(result["unmatched_selectors"]))
        if result.get("unmatched_image_elements"):
            lines.append("Unmatched image: %s" % ", ".join(str(x) for x in result["unmatched_image_elements"][:10]))

    else:
        # Unknown command or action commands — pass through as JSON
        return ""

    return "\n".join(lines)


def format_minimal(result: dict) -> str:
    """Minimal format — names and types only, no coordinates."""
    cmd = result.get("command", "")
    lines = []

    if cmd == "describe":
        lines.append("# %s" % result.get("window", {}).get("title", "?"))
        for el in result.get("elements", []):
            lines.append(_format_uia_element_minimal(el))
        lines.append("(%d elements)" % result.get("element_count", 0))

    elif cmd == "windows":
        for win in result.get("windows", []):
            fg = "*fg*" if win.get("is_foreground") else ""
            line = win.get("title", "?")
            if fg:
                line += " " + fg
            lines.append(line)

    elif cmd == "find":
        for el in result.get("matches", []):
            lines.append(_format_uia_element_minimal(el))
        lines.append("(%d matches)" % result.get("count", 0))

    elif cmd == "focused":
        el = result.get("element")
        if el:
            lines.append(_format_uia_element_minimal(el))
        else:
            lines.append("(none)")

    elif cmd == "web-ax":
        for node in result.get("nodes", []):
            role = _web_abbrev(node.get("role", ""))
            name = node.get("name", "").strip()
            lines.append("[%s] %s" % (role, name))
        lines.append("(%d nodes)" % result.get("count", 0))

    elif cmd == "web-describe":
        lines.append("# %s" % result.get("title", "?"))
        lines.append("URL: %s" % result.get("url", ""))
        for h in result.get("headings", []):
            lines.append("[%s] %s" % (h.get("level", "?"), h.get("text", "")))
        for b in result.get("buttons", []):
            lines.append("[Btn] %s" % b.get("text", ""))
        for inp in result.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name") or "?"
            lines.append("[%s] %s" % (inp.get("type", "?"), label))

    elif cmd == "web-find":
        for el in result.get("matches", []):
            tag = el.get("tag", "?")
            text = el.get("text", "").strip()
            lines.append("[%s] %s" % (tag, text))
        lines.append("(%d matches)" % result.get("count", 0))

    elif cmd == "web-links":
        for lnk in result.get("links", []):
            lines.append("%s | %s" % (lnk.get("text", ""), lnk.get("href", "")))

    elif cmd == "web-tabs":
        for tab in result.get("tabs", []):
            active = "*active*" if tab.get("is_active") else ""
            line = tab.get("title", "?")
            if active:
                line += " " + active
            lines.append(line)

    else:
        return ""

    return "\n".join(lines)
