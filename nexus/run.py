"""Nexus CLI — argparse, dispatch, JSON output. The single entry point.

No side effects on import. Signal handling and watchdog start in main() only.
"""

import argparse
import json
import signal
import sys

from nexus.watchdog import start_watchdog, DEFAULT_TIMEOUT
from nexus.format import format_compact, format_minimal


def _cmd_screenshot(region: str | None = None, full: bool = False, mark: bool = False) -> dict:
    """Screenshot with optional Set-of-Mark annotation."""
    if not mark:
        from nexus.digitus.input import screenshot
        return screenshot(region=region, full=full)

    # Mark mode: get elements from UIA, then annotate
    from nexus.oculus.uia import describe
    from nexus.mark import screenshot_with_marks, store_marks

    desc = describe()
    elements = desc.get("elements", [])
    result = screenshot_with_marks(elements, region=region, full=full)
    store_marks(result.get("marks", []))
    return result


def _cmd_click_mark(mark_id: int) -> dict:
    """Click the center of a previously marked element."""
    from nexus.mark import resolve_mark
    import pyautogui

    mark = resolve_mark(mark_id)
    if not mark:
        return {"command": "click-mark", "ok": False, "error": "Mark %d not found. Take a screenshot --mark first." % mark_id}

    x, y = mark["x"], mark["y"]
    pyautogui.click(x, y)
    return {
        "command": "click-mark",
        "ok": True,
        "mark_id": mark_id,
        "name": mark.get("name", ""),
        "role": mark.get("role", ""),
        "x": x,
        "y": y,
    }


def _handle_signal(signum, _frame):
    name = signal.Signals(signum).name
    print(json.dumps({"ok": False, "error": "Nexus interrupted by %s" % name}))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Dispatch table: command name → (function, arg extractor)
#
# Two extractors per command:
#   - CLI extractor: lambda argparse.Namespace -> dict_of_kwargs
#   - Daemon extractor: lambda dict -> dict_of_kwargs (for JSON-line protocol)
# ---------------------------------------------------------------------------

def _build_commands():
    """Lazy import to avoid loading all modules at startup."""
    from nexus.oculus.uia import describe, windows, find, focused
    from nexus.oculus.web import (
        web_describe, web_text, web_find, web_links, web_tabs,
        web_ax, web_measure, web_contrast, web_markdown, web_capture_api, web_research,
    )
    from nexus.oculus.ocr import ocr_region, ocr_screen
    from nexus.digitus.input import (
        screenshot, click, move, drag, type_text, key, scroll, info,
    )
    from nexus.digitus.element import click_element
    from nexus.digitus.web import web_click, web_navigate, web_input, web_pdf
    from nexus.digitus.system import ps_run, com_shell
    from nexus.digitus.office import com_excel, com_word, com_outlook
    from nexus.digitus.vision import vision_detect, vision_health
    from nexus.oculus.image import measure_image, web_layout_diff
    from nexus.electron import detect as electron_detect, connect as electron_connect, list_targets as electron_targets

    def _port(a):
        return getattr(a, "port", 9222)

    return {
        # Oculus — UIA
        "describe":     (describe,      lambda a: {"max_depth": a.depth, "focus": getattr(a, "focus", None), "match": getattr(a, "match", None), "region": getattr(a, "region", None)}),
        "windows":      (windows,       lambda a: {}),
        "find":         (find,          lambda a: {"query": a.query, "focus": getattr(a, "focus", None), "region": getattr(a, "region", None)}),
        "focused":      (focused,       lambda a: {}),
        # Oculus — Web
        "web-describe": (web_describe,  lambda a: {"tab": getattr(a, "tab", 0), "full": getattr(a, "full", False), "port": _port(a)}),
        "web-text":     (web_text,      lambda a: {"tab": getattr(a, "tab", 0), "port": _port(a)}),
        "web-find":     (web_find,      lambda a: {"query": a.query, "tab": getattr(a, "tab", 0), "port": _port(a)}),
        "web-links":    (web_links,     lambda a: {"tab": getattr(a, "tab", 0), "port": _port(a)}),
        "web-tabs":     (web_tabs,      lambda a: {"port": _port(a)}),
        "web-ax":       (web_ax,        lambda a: {"tab": getattr(a, "tab", 0), "port": _port(a), "focus": getattr(a, "focus", None), "match": getattr(a, "match", None)}),
        "web-measure":  (web_measure,   lambda a: {"selectors": a.selectors, "tab": getattr(a, "tab", 0), "port": _port(a)}),
        "web-contrast": (web_contrast,  lambda a: {"selectors": getattr(a, "selectors", "") or "", "tab": getattr(a, "tab", 0), "port": _port(a)}),
        "web-markdown": (web_markdown,  lambda a: {"tab": getattr(a, "tab", 0), "port": _port(a)}),
        "web-capture-api": (web_capture_api, lambda a: {"url": a.url, "filter_pattern": a.filter or "", "tab": getattr(a, "tab", 0), "port": _port(a)}),
        "web-research": (web_research,  lambda a: {"query": a.query, "max_results": a.max, "engine": a.engine, "port": _port(a)}),
        # Oculus — OCR
        "ocr-region":   (ocr_region,    lambda a: {"x": a.x, "y": a.y, "w": a.w, "h": a.h, "lang": a.lang}),
        "ocr-screen":   (ocr_screen,    lambda a: {"lang": a.lang}),
        # Digitus — Input
        "screenshot":   (_cmd_screenshot, lambda a: {"region": a.region, "full": a.full, "mark": getattr(a, "mark", False)}),
        "click":        (click,         lambda a: {"x": a.x, "y": a.y, "right": a.right, "double": a.double}),
        "move":         (move,          lambda a: {"x": a.x, "y": a.y}),
        "drag":         (drag,          lambda a: {"start": a.start, "end": a.end, "duration": a.duration}),
        "type":         (type_text,     lambda a: {"text": a.text}),
        "key":          (key,           lambda a: {"keyname": a.keyname}),
        "scroll":       (scroll,        lambda a: {"amount": a.amount}),
        "info":         (info,          lambda a: {}),
        # Digitus — Element
        "click-element": (click_element, lambda a: {"name": a.name, "right": a.right, "double": a.double, "role": getattr(a, "role", None), "index": getattr(a, "index", 0), "verify": getattr(a, "verify", False), "heal": getattr(a, "heal", False)}),
        # Digitus — Click-mark
        "click-mark":   (_cmd_click_mark, lambda a: {"mark_id": a.mark_id}),
        # Digitus — Web
        "web-click":    (web_click,     lambda a: {"text": a.text, "port": _port(a), "heal": getattr(a, "heal", False)}),
        "web-navigate": (web_navigate,  lambda a: {"url": a.url, "port": _port(a)}),
        "web-input":    (web_input,     lambda a: {"selector": a.selector, "value": a.value, "port": _port(a)}),
        "web-pdf":      (web_pdf,       lambda a: {"output": getattr(a, "output", None), "page_format": getattr(a, "page_format", "A4"), "landscape": getattr(a, "landscape", False), "port": _port(a)}),
        # Digitus — Vision (OmniParser)
        "vision-detect": (vision_detect, lambda a: {"image_path": getattr(a, "image", None), "region": getattr(a, "region", None), "box_threshold": getattr(a, "threshold", 0.05), "iou_threshold": getattr(a, "iou", 0.1), "annotated": getattr(a, "annotated", False)}),
        "vision-health": (vision_health, lambda a: {}),
        # Oculus — Image measurement
        "measure-image": (measure_image, lambda a: {"image_path": a.image_path, "box_threshold": getattr(a, "threshold", 0.05), "iou_threshold": getattr(a, "iou", 0.1), "lang": getattr(a, "lang", "en"), "scale": getattr(a, "scale", 1.0)}),
        "web-layout-diff": (web_layout_diff, lambda a: {"image_path": a.image_path, "selectors": a.selectors, "tab": getattr(a, "tab", 0), "port": _port(a), "box_threshold": getattr(a, "threshold", 0.05), "iou_threshold": getattr(a, "iou", 0.1), "lang": getattr(a, "lang", "en"), "scale": getattr(a, "scale", 1.0), "match_by": getattr(a, "match_by", "text")}),
        # Digitus — System
        "ps-run":       (ps_run,        lambda a: {"script": a.script}),
        "com-shell":    (com_shell,     lambda a: {"path": a.path}),
        "com-excel":    (com_excel,     lambda a: {"action": a.action, "path": getattr(a, "path", None), "range_": getattr(a, "range", None), "cell": getattr(a, "cell", None), "value": getattr(a, "value", None), "sheet": getattr(a, "sheet", None)}),
        "com-word":     (com_word,      lambda a: {"action": a.action, "path": getattr(a, "path", None), "start": getattr(a, "start", None), "end": getattr(a, "end", None)}),
        "com-outlook":  (com_outlook,   lambda a: {"action": a.action, "count": getattr(a, "count", 5), "item_id": getattr(a, "id", None), "to": getattr(a, "to", None), "subject": getattr(a, "subject", None), "body": getattr(a, "body", None)}),
        # Electron
        "electron-detect":  (electron_detect,  lambda a: {}),
        "electron-connect": (electron_connect, lambda a: {"port": a.port}),
        "electron-targets": (electron_targets, lambda a: {"port": a.port}),
    }


def _build_daemon_commands():
    """Daemon/batch dispatch: same functions as CLI, but extractors take a dict (JSON request).

    Built from _build_commands() — single source of truth for function references.
    Only the extractors differ (dict.get vs getattr on Namespace).
    """
    cli = _build_commands()

    def _port(d):
        return d.get("port", 9222)

    # Dict-based extractors keyed by command name
    daemon_extractors = {
        "describe":     lambda d: {"max_depth": d.get("depth"), "focus": d.get("focus"), "match": d.get("match"), "region": d.get("region")},
        "windows":      lambda d: {},
        "find":         lambda d: {"query": d["query"], "focus": d.get("focus"), "region": d.get("region")},
        "focused":      lambda d: {},
        "web-describe": lambda d: {"tab": d.get("tab", 0), "full": d.get("full", False), "port": _port(d)},
        "web-text":     lambda d: {"tab": d.get("tab", 0), "port": _port(d)},
        "web-find":     lambda d: {"query": d["query"], "tab": d.get("tab", 0), "port": _port(d)},
        "web-links":    lambda d: {"tab": d.get("tab", 0), "port": _port(d)},
        "web-tabs":     lambda d: {"port": _port(d)},
        "web-ax":       lambda d: {"tab": d.get("tab", 0), "port": _port(d), "focus": d.get("focus"), "match": d.get("match")},
        "web-measure":  lambda d: {"selectors": d["selectors"], "tab": d.get("tab", 0), "port": _port(d)},
        "web-contrast": lambda d: {"selectors": d.get("selectors", ""), "tab": d.get("tab", 0), "port": _port(d)},
        "web-markdown": lambda d: {"tab": d.get("tab", 0), "port": _port(d)},
        "web-capture-api": lambda d: {"url": d["url"], "filter_pattern": d.get("filter", ""), "tab": d.get("tab", 0), "port": _port(d)},
        "web-research": lambda d: {"query": d["query"], "max_results": d.get("max", 3), "engine": d.get("engine", "duckduckgo"), "port": _port(d)},
        "ocr-region":   lambda d: {"x": d["x"], "y": d["y"], "w": d["w"], "h": d["h"], "lang": d.get("lang", "en")},
        "ocr-screen":   lambda d: {"lang": d.get("lang", "en")},
        "screenshot":   lambda d: {"region": d.get("region"), "full": d.get("full", False), "mark": d.get("mark", False)},
        "click":        lambda d: {"x": d["x"], "y": d["y"], "right": d.get("right", False), "double": d.get("double", False)},
        "move":         lambda d: {"x": d["x"], "y": d["y"]},
        "drag":         lambda d: {"start": d["start"], "end": d["end"], "duration": d.get("duration", 0.5)},
        "type":         lambda d: {"text": d["text"]},
        "key":          lambda d: {"keyname": d["keyname"]},
        "scroll":       lambda d: {"amount": d["amount"]},
        "info":         lambda d: {},
        "click-element": lambda d: {"name": d["name"], "right": d.get("right", False), "double": d.get("double", False), "role": d.get("role"), "index": d.get("index", 0), "verify": d.get("verify", False), "heal": d.get("heal", False)},
        "click-mark":   lambda d: {"mark_id": d["mark_id"]},
        "web-click":    lambda d: {"text": d["text"], "port": _port(d), "heal": d.get("heal", False)},
        "web-navigate": lambda d: {"url": d["url"], "port": _port(d)},
        "web-input":    lambda d: {"selector": d["selector"], "value": d["value"], "port": _port(d)},
        "web-pdf":      lambda d: {"output": d.get("output"), "page_format": d.get("format", "A4"), "landscape": d.get("landscape", False), "port": _port(d)},
        "vision-detect": lambda d: {"image_path": d.get("image"), "region": d.get("region"), "box_threshold": d.get("threshold", 0.05), "iou_threshold": d.get("iou", 0.1), "annotated": d.get("annotated", False)},
        "vision-health": lambda d: {},
        "measure-image": lambda d: {"image_path": d["image_path"], "box_threshold": d.get("threshold", 0.05), "iou_threshold": d.get("iou", 0.1), "lang": d.get("lang", "en"), "scale": d.get("scale", 1.0)},
        "web-layout-diff": lambda d: {"image_path": d["image_path"], "selectors": d["selectors"], "tab": d.get("tab", 0), "port": _port(d), "box_threshold": d.get("threshold", 0.05), "iou_threshold": d.get("iou", 0.1), "lang": d.get("lang", "en"), "scale": d.get("scale", 1.0), "match_by": d.get("match_by", "text")},
        "ps-run":       lambda d: {"script": d["script"]},
        "com-shell":    lambda d: {"path": d.get("path")},
        "com-excel":    lambda d: {"action": d.get("action", "list"), "path": d.get("path"), "range_": d.get("range"), "cell": d.get("cell"), "value": d.get("value"), "sheet": d.get("sheet")},
        "com-word":     lambda d: {"action": d.get("action", "read"), "path": d.get("path"), "start": d.get("start"), "end": d.get("end")},
        "com-outlook":  lambda d: {"action": d.get("action", "inbox"), "count": d.get("count", 5), "item_id": d.get("id"), "to": d.get("to"), "subject": d.get("subject"), "body": d.get("body")},
        "electron-detect":  lambda d: {},
        "electron-connect": lambda d: {"port": d["port"]},
        "electron-targets": lambda d: {"port": d["port"]},
    }

    # Combine: functions from CLI table + extractors from daemon table
    return {name: (cli[name][0], daemon_extractors[name]) for name in cli if name in daemon_extractors}


def _build_parser():
    # Shared timeout flag inherited by every subcommand
    _common = argparse.ArgumentParser(add_help=False)
    _common.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                         help="Max seconds before auto-kill (default: %d)" % DEFAULT_TIMEOUT)

    parser = argparse.ArgumentParser(description="Nexus — Claude's eyes and hands on the computer", parents=[_common])
    # --format on main parser only — avoids subparser default overwriting the parsed value
    parser.add_argument("--format", choices=["json", "compact", "minimal"], default="json",
                        help="Output format: json (default), compact (one-liner), minimal (names only)")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-prune results based on per-command policies (default off in CLI)")
    sub = parser.add_subparsers(dest="command", required=True)

    def _sub(name, **kwargs):
        """Create a subparser that inherits --timeout."""
        return sub.add_parser(name, parents=[_common], **kwargs)

    # === Serve (daemon mode) ===
    _sub("serve", help="Start persistent JSON-line daemon on stdin/stdout")

    # === Batch execution ===
    p = _sub("batch", help="Execute multiple commands in sequence; only return final result")
    p.add_argument("steps", help="Semicolon-separated commands, e.g. 'describe --focus buttons; find Save'")
    p.add_argument("--verbose", action="store_true", help="Return all intermediate results")
    p.add_argument("--continue-on-error", action="store_true", dest="continue_on_error",
                   help="Continue executing after a failure")

    # === Oculus: UIA ===
    p = _sub("describe", help="Describe active window elements, cursor, focus")
    p.add_argument("--depth", type=int, default=None,
                   help="Max tree depth for fallback traversal (default: 6)")
    p.add_argument("--force", action="store_true", help="Bypass cache, force fresh scan")
    p.add_argument("--diff", action="store_true",
                   help="Return only changes since last describe (added/removed/changed elements)")
    p.add_argument("--summary", action="store_true",
                   help="Return only a concise summary (element counts, focus, errors, spatial groups)")
    p.add_argument("--focus", default=None,
                   help="Filter preset: buttons, inputs, interactive, errors, dialogs, navigation, or free text")
    p.add_argument("--match", default=None,
                   help="Glob or regex pattern to match element names")
    p.add_argument("--region", default=None,
                   help="Spatial filter: top, bottom, left, right, center, or X,Y,W,H")
    p = _sub("windows", help="List all open windows")
    p.add_argument("--force", action="store_true", help="Bypass cache")
    p = _sub("find", help="Search for UI elements by name")
    p.add_argument("query", help="Text to search for in element names")
    p.add_argument("--focus", default=None,
                   help="Filter preset to narrow results by type")
    p.add_argument("--region", default=None,
                   help="Spatial filter: top, bottom, left, right, center, or X,Y,W,H")
    _sub("focused", help="What element has keyboard focus")

    # === Oculus: Web ===
    # Helper to add common --tab and --port flags to web subparsers
    def _web(name, **kwargs):
        p = _sub(name, **kwargs)
        p.add_argument("--tab", type=int, default=0, help="Target tab index (default: 0)")
        p.add_argument("--port", type=int, default=9222, help="CDP port (default: 9222, use other ports for Electron apps)")
        return p

    p = _web("web-describe", help="Page title, URL, key elements (concise by default)")
    p.add_argument("--full", action="store_true", help="Full verbose output (all headings, links, inputs)")
    _web("web-text", help="Full visible text content of the page")
    p = _web("web-find", help="Find elements by text on the page")
    p.add_argument("query", help="Text to search for")
    _web("web-links", help="List all links on the page")
    p = _sub("web-tabs", help="List all open browser tabs")
    p.add_argument("--port", type=int, default=9222, help="CDP port (default: 9222)")
    p = _web("web-ax", help="Chrome accessibility tree via CDP")
    p.add_argument("--focus", default=None,
                   help="Filter preset: buttons, inputs, interactive, navigation, headings, forms, errors, dialogs, or free text")
    p.add_argument("--match", default=None,
                   help="Glob or regex pattern to match node names")
    p.add_argument("--summary", action="store_true",
                   help="Return only a concise summary")
    p = _web("web-measure", help="Computed CSS layout for selectors")
    p.add_argument("selectors", help="Comma-separated CSS selectors")
    p = _web("web-contrast", help="Scan elements for color contrast / readability issues")
    p.add_argument("selectors", nargs="?", default="", help="Comma-separated CSS selectors (empty = scan common UI elements)")
    _web("web-markdown", help="Extract clean article content (Readability.js)")
    p = _web("web-research", help="Search web, visit results, extract content")
    p.add_argument("query", help="Search query")
    p.add_argument("--max", type=int, default=3, help="Max results to visit (default: 3, max: 5)")
    p.add_argument("--engine", choices=["duckduckgo", "brave"], default="duckduckgo", help="Search engine")
    p = _web("web-capture-api", help="Intercept JSON API responses during page load")
    p.add_argument("url", help="URL to navigate to")
    p.add_argument("--filter", default="", help="Only capture responses matching this URL pattern")

    # === Oculus: OCR ===
    p = _sub("ocr-region", help="OCR a screen region")
    p.add_argument("x", type=int, help="Region X")
    p.add_argument("y", type=int, help="Region Y")
    p.add_argument("w", type=int, help="Region width")
    p.add_argument("h", type=int, help="Region height")
    p.add_argument("--lang", default="en", help="OCR language (default: en)")
    p = _sub("ocr-screen", help="OCR the entire active window")
    p.add_argument("--lang", default="en", help="OCR language (default: en)")

    # === Digitus: Element ===
    p = _sub("click-element", help="Find element by name and click it")
    p.add_argument("name", help="Element name to search for (fuzzy match)")
    p.add_argument("--right", action="store_true")
    p.add_argument("--double", action="store_true")
    p.add_argument("--role", default=None,
                   help="Filter by role: button, input, link, tab, menu, checkbox, radio, etc.")
    p.add_argument("--index", type=int, default=0,
                   help="Which match to click (0-based) when multiple match")
    p.add_argument("--verify", action="store_true",
                   help="Re-describe after click to confirm state changed")
    p.add_argument("--heal", action="store_true",
                   help="Auto-recover from common failures (element moved, window lost, dialog blocking)")

    p = _sub("click-mark", help="Click a numbered element from the last --mark screenshot")
    p.add_argument("mark_id", type=int, help="Element number from the marked screenshot")

    # === Digitus: Input ===
    p = _sub("screenshot")
    p.add_argument("--region", help="X,Y,W,H to capture a region")
    p.add_argument("--full", action="store_true", help="Native resolution (no downscale)")
    p.add_argument("--mark", action="store_true", help="Annotate with numbered element badges (Set-of-Mark)")

    p = _sub("click")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--right", action="store_true")
    p.add_argument("--double", action="store_true")

    p = _sub("move")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)

    p = _sub("drag")
    p.add_argument("start", help="X1,Y1")
    p.add_argument("end", help="X2,Y2")
    p.add_argument("--duration", type=float, default=0.5)

    p = _sub("type")
    p.add_argument("text")

    p = _sub("key")
    p.add_argument("keyname", help="Key name or combo like ctrl+s")

    p = _sub("scroll")
    p.add_argument("amount", type=int, help="Positive=up, negative=down")

    _sub("info", help="Screen size and cursor position")

    # === Digitus: Web ===
    p = _sub("web-click", help="Click element by visible text")
    p.add_argument("text", help="Visible text of element to click")
    p.add_argument("--port", type=int, default=9222, help="CDP port (default: 9222)")
    p.add_argument("--heal", action="store_true",
                   help="Auto-recover from failures (wait for load, try alternative locators)")

    p = _sub("web-navigate", help="Navigate to a URL")
    p.add_argument("url", help="URL to navigate to")
    p.add_argument("--port", type=int, default=9222, help="CDP port (default: 9222)")

    p = _sub("web-input", help="Fill an input by label/placeholder/selector")
    p.add_argument("selector", help="Label, placeholder, or CSS selector")
    p.add_argument("value", help="Value to fill")
    p.add_argument("--port", type=int, default=9222, help="CDP port (default: 9222)")

    p = _sub("web-pdf", help="Export current page to PDF via CDP")
    p.add_argument("--output", default=None, help="Output file path (default: return base64)")
    p.add_argument("--page-format", dest="page_format", choices=["A4", "Letter", "A3", "Legal"], default="A4", help="Page format (default: A4)")
    p.add_argument("--landscape", action="store_true", help="Landscape orientation")
    p.add_argument("--port", type=int, default=9222, help="CDP port (default: 9222)")

    # === Digitus: Vision (OmniParser) ===
    p = _sub("vision-detect", help="Detect UI elements via OmniParser vision model")
    p.add_argument("--image", default=None, help="Image path (default: take fresh screenshot)")
    p.add_argument("--region", default=None, help="Screenshot region as X,Y,W,H (when no --image)")
    p.add_argument("--threshold", type=float, default=0.05, help="Box confidence threshold (default: 0.05)")
    p.add_argument("--iou", type=float, default=0.1, help="IOU threshold for overlap removal (default: 0.1)")
    p.add_argument("--annotated", action="store_true", help="Also save annotated image with bounding boxes")

    _sub("vision-health", help="Check if OmniParser vision server is running")

    # === Image Measurement ===
    p = _sub("measure-image", help="Measure UI elements in a reference design image (OmniParser + OCR)")
    p.add_argument("image_path", help="Absolute path to PNG image (Figma/Krita export)")
    p.add_argument("--threshold", type=float, default=0.05, help="OmniParser box confidence threshold (default: 0.05)")
    p.add_argument("--iou", type=float, default=0.1, help="OmniParser IOU threshold (default: 0.1)")
    p.add_argument("--lang", default="en", help="OCR language (default: en)")
    p.add_argument("--scale", type=float, default=1.0, help="Scale factor for @2x exports, e.g. 0.5 (default: 1.0)")

    p = _web("web-layout-diff", help="Compare reference design image against live CSS measurements")
    p.add_argument("image_path", help="Absolute path to reference design PNG")
    p.add_argument("selectors", help="Comma-separated CSS selectors (same as web-measure)")
    p.add_argument("--threshold", type=float, default=0.05, help="OmniParser box confidence threshold (default: 0.05)")
    p.add_argument("--iou", type=float, default=0.1, help="IOU threshold (default: 0.1)")
    p.add_argument("--lang", default="en", help="OCR language (default: en)")
    p.add_argument("--scale", type=float, default=1.0, help="Scale factor for @2x image (default: 1.0)")
    p.add_argument("--match-by", dest="match_by", choices=["text", "position", "index"], default="text",
                   help="Matching strategy: text (default), position, index")

    # === Electron ===
    _sub("electron-detect", help="Scan for running Chromium/Electron apps with CDP")
    p = _sub("electron-connect", help="Verify connection to an Electron app's CDP port")
    p.add_argument("port", type=int, help="CDP port to connect to")
    p = _sub("electron-targets", help="List CDP targets (pages) on a port")
    p.add_argument("port", type=int, help="CDP port to query")

    # === Digitus: System ===
    p = _sub("ps-run", help="Execute a PowerShell command")
    p.add_argument("script", help="PowerShell command to execute")

    p = _sub("com-shell", help="Browse files via COM Shell.Application")
    p.add_argument("--path", default=None, help="Directory path (default: home dir)")

    # === Digitus: Office COM ===
    p = _sub("com-excel", help="Excel automation via COM")
    p.add_argument("action", choices=["list", "read", "write", "sheets"], help="Action to perform")
    p.add_argument("--path", default=None, help="Workbook path to open")
    p.add_argument("--range", default=None, help="Cell range for read (e.g. A1:D10)")
    p.add_argument("--cell", default=None, help="Cell for write (e.g. B2)")
    p.add_argument("--value", default=None, help="Value for write")
    p.add_argument("--sheet", default=None, help="Sheet name to target")

    p = _sub("com-word", help="Word document access via COM")
    p.add_argument("action", choices=["read", "info"], help="Action to perform")
    p.add_argument("--path", default=None, help="Document path to open")
    p.add_argument("--start", type=int, default=None, help="Start paragraph number")
    p.add_argument("--end", type=int, default=None, help="End paragraph number")

    p = _sub("com-outlook", help="Outlook email access via COM")
    p.add_argument("action", choices=["inbox", "read", "send"], help="Action to perform")
    p.add_argument("--count", type=int, default=5, help="Number of inbox items (default: 5)")
    p.add_argument("--id", default=None, help="EntryID for read action")
    p.add_argument("--to", default=None, help="Recipient for send")
    p.add_argument("--subject", default=None, help="Subject for send")
    p.add_argument("--body", default=None, help="Body for send")

    # === Watch (event-driven awareness) ===
    p = _sub("watch", help="Stream UIA events (focus, window, structure changes)")
    p.add_argument("--stop", action="store_true", help="Stop the event watcher")
    p.add_argument("--status", action="store_true", help="Check watcher status")
    p.add_argument("--events", nargs="*", choices=["focus", "window", "structure", "property"],
                   default=None, help="Which event types to subscribe (default: all)")
    p.add_argument("--duration", type=float, default=0,
                   help="How long to watch in seconds (0 = until Ctrl+C)")

    # === Describe tools (agent discoverability) ===
    p = _sub("describe-tools", help="Output tool definitions for agent consumption")
    p.add_argument("--fmt", choices=["openai", "markdown"], default="openai",
                   help="Output format: openai (JSON function calling), markdown (human-readable)")
    p.add_argument("--output", default=None, help="Write to file instead of stdout")

    # === Task lifecycle ===
    p = _sub("task", help="Task lifecycle: start, end, note, status")
    task_sub = p.add_subparsers(dest="action", required=True)
    ps = task_sub.add_parser("start", help="Start a new task")
    ps.add_argument("name", help="Task description")
    pe = task_sub.add_parser("end", help="End current task with outcome")
    pe.add_argument("outcome", choices=["success", "fail", "partial"], help="Task outcome")
    pe.add_argument("--notes", default=None, help="Optional notes")
    pn = task_sub.add_parser("note", help="Add feedback to current task")
    pn.add_argument("text", help="Feedback text")
    task_sub.add_parser("status", help="Check if a task is active")

    # === Recall (memory search) ===
    p = _sub("recall", help="Search past task memories")
    p.add_argument("--query", default=None, help="Search in task names (substring)")
    p.add_argument("--app", default=None, help="Filter by app context (substring)")
    p.add_argument("--tag", default=None, help="Filter by tag")
    p.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    p.add_argument("--stats", action="store_true", help="Show aggregate stats instead of search")

    return parser


def _format_result(result: dict, fmt: str) -> str:
    """Apply format to a result dict. Returns formatted text or empty string."""
    if fmt == "compact":
        return format_compact(result)
    elif fmt == "minimal":
        return format_minimal(result)
    return ""


def main():
    """Parse args, start watchdog, dispatch command, print JSON result."""
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Force UTF-8 stdout on Windows (prevents cp1252 UnicodeEncodeError with emoji/unicode)
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    # COM/UIA requires CoInitialize on the calling thread (needed when spawned as subprocess)
    import pythoncom
    pythoncom.CoInitialize()

    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05

    parser = _build_parser()
    args = parser.parse_args()

    # Daemon mode — no watchdog, persistent loop
    if args.command == "serve":
        from nexus.serve import serve_loop
        commands = _build_daemon_commands()
        serve_loop(commands, format_fn=_format_result, default_timeout=args.timeout)
        return

    # Task lifecycle — handled directly, not through dispatch
    if args.command == "task":
        from nexus.recorder import task_start, task_end, task_note, task_status
        if args.action == "start":
            result = task_start(args.name)
        elif args.action == "end":
            result = task_end(args.outcome, notes=getattr(args, "notes", None))
        elif args.action == "note":
            result = task_note(args.text)
        elif args.action == "status":
            result = task_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Recall — search task memories
    if args.command == "recall":
        from nexus.cortex.memory import recall, recall_stats
        if getattr(args, "stats", False):
            result = recall_stats()
        else:
            result = recall(query=args.query, app=args.app, tag=args.tag, limit=args.limit)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Describe-tools — output tool schemas for agent consumption
    if args.command == "describe-tools":
        from nexus.tools_schema import extract_tool_schemas, generate_markdown
        schemas = extract_tool_schemas(parser)
        if args.fmt == "markdown":
            output = generate_markdown(schemas)
        else:
            output = json.dumps({"tools": schemas, "count": len(schemas)}, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(json.dumps({"ok": True, "path": args.output, "tool_count": len(schemas)}))
        else:
            print(output)
        return

    # Batch mode — execute multiple commands in sequence
    if args.command == "batch":
        start_watchdog(args.timeout)
        from nexus.batch import execute_batch
        # Build daemon-style commands (dict extractors) for batch
        commands = _build_daemon_commands()
        result = execute_batch(
            args.steps, commands,
            verbose=args.verbose,
            continue_on_error=args.continue_on_error,
        )
        fmt = args.format
        text = _format_result(result, fmt)
        if text:
            print(text)
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Watch mode — stream UIA events as JSON lines
    if args.command == "watch":
        from nexus.watcher import start_watching, stop_watching, watch_status, poll_events
        if args.stop:
            result = stop_watching()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return
        if args.status:
            result = watch_status()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return
        # Start watching and stream events
        result = start_watching(events=args.events)
        if not result.get("ok"):
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return
        sys.stderr.write(json.dumps(result) + "\n")
        sys.stderr.flush()
        import time as _t
        start = _t.time()
        try:
            while True:
                if args.duration > 0 and (_t.time() - start) >= args.duration:
                    break
                events = poll_events(max_events=50, timeout=0.5)
                for evt in events:
                    print(json.dumps(evt, ensure_ascii=False))
                    sys.stdout.flush()
        except KeyboardInterrupt:
            pass
        finally:
            stop_watching()
        return

    # Single-shot mode — watchdog + dispatch
    start_watchdog(args.timeout)

    commands = _build_commands()
    func, extract = commands[args.command]
    kwargs = extract(args)

    import time as _time
    t0 = _time.perf_counter()

    try:
        result = func(**kwargs)
    except Exception as e:
        # Always return structured JSON — never dump raw tracebacks
        result = {"command": args.command, "ok": False, "error": str(e)}

    duration_ms = int((_time.perf_counter() - t0) * 1000)

    # Auto-prune: apply per-command policies (only if no explicit --summary/--diff)
    use_summary = getattr(args, "summary", False)
    use_diff = getattr(args, "diff", False)
    if getattr(args, "auto", False) and not use_summary and not use_diff:
        from nexus.cortex.pruning import apply_policy
        cache_kwargs_clean = {k: v for k, v in kwargs.items() if v is not None}
        result = apply_policy(args.command, result, cache_kwargs=cache_kwargs_clean)
        suggested = result.pop("_suggested_format", None)
        if suggested and args.format == "json":
            args.format = suggested

    # Summary mode: replace full result with concise summary
    if use_summary and args.command == "describe":
        from nexus.cortex.summarize import summarize_uia, format_summary
        summary = summarize_uia(result)
        result = {"command": "describe", "mode": "summary", **summary}
    elif use_summary and args.command == "web-ax":
        from nexus.cortex.summarize import summarize_web, format_summary
        summary = summarize_web(result)
        result = {"command": "web-ax", "mode": "summary", **summary}

    # Diff mode: compare with cached result, return only changes
    if use_diff and args.command in ("describe", "web-ax"):
        from nexus.cache import cache_get_for_diff, compute_diff, cache_put
        # Build cache kwargs (exclude diff/force/format flags)
        cache_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        old_result = cache_get_for_diff(args.command, cache_kwargs, use_file=True)
        # Always store fresh result for next diff
        cache_put(args.command, cache_kwargs, result, use_file=True)
        if old_result:
            result = compute_diff(old_result, result)

    from nexus.recorder import record
    record(args.command, kwargs, result, duration_ms)

    fmt = args.format
    text = _format_result(result, fmt)
    if text:
        print(text)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
