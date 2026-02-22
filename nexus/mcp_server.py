"""Nexus MCP Server — exposes all Nexus tools via Model Context Protocol (stdio transport).

Each tool corresponds to one Nexus command. Functions call the underlying
Nexus functions directly (in-process, no subprocess overhead).

Tool annotations (WebMCP-inspired): every tool declares readOnlyHint,
destructiveHint, idempotentHint so orchestrators can reason about safety.
Tool descriptions prefixed with [source] tag for LLM tool-list scanning.

Run: python -m nexus.mcp_server
Config: add to .mcp.json with type "stdio"
"""

import base64
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent, ToolAnnotations


# ── Tool Annotations ──────────────────────────────────────────────────────────
# Semantic hints that help orchestrators reason about tool safety.
# readOnlyHint=True  → tool only observes, no side effects
# destructiveHint=True → tool can cause irreversible changes
# idempotentHint=True → calling twice with same args = same result
# openWorldHint=True → tool interacts with external world (network, other apps)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
SAFE_ACTION = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)
OPEN_WORLD = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)


def _json(result: dict) -> str:
    """Serialize a Nexus result dict to JSON string for MCP text response."""
    return json.dumps(result, ensure_ascii=False, indent=2)


def _com_init():
    """Initialize COM on the current thread. Required for UIA/COM tools."""
    import pythoncom
    pythoncom.CoInitialize()


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    """Setup pyautogui and UTF-8 stdout on startup."""
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    import pyautogui
    pyautogui.FAILSAFE = False  # MCP is agent-driven, user kills process to abort
    pyautogui.PAUSE = 0.05
    yield


mcp = FastMCP("nexus", lifespan=_lifespan)


# ── UIA Awareness ──────────────────────────────────────────────────────────────

@mcp.tool(annotations=READ_ONLY)
def describe(
    focus: Optional[str] = None,
    match: Optional[str] = None,
    region: Optional[str] = None,
    max_depth: Optional[int] = None,
) -> str:
    """[UIA] Describe the active window's UI elements, cursor position, and focused element.

    Use this to understand what's on screen before clicking or interacting.
    Returns named interactive elements with types and screen coordinates.
    If you know the element name, use find() instead (faster).

    Args:
        focus: Filter preset — "buttons", "inputs", "interactive", "errors",
               "dialogs", "navigation" — or free text to match element names.
        match: Glob or regex pattern to match element names (e.g. "Save*").
        region: Spatial filter — "top", "bottom", "left", "right", "center",
                or "X,Y,W,H" pixel coordinates.
        max_depth: Max UIA tree depth (default 6). Lower = faster, higher = deeper.
    """
    _com_init()
    from nexus.oculus.uia import describe as _describe
    return _json(_describe(max_depth=max_depth, focus=focus, match=match, region=region))


@mcp.tool(annotations=READ_ONLY)
def windows() -> str:
    """[UIA] List all open windows with titles, positions, and process info.

    Use to identify which app is running or find a specific window.
    """
    _com_init()
    from nexus.oculus.uia import windows as _windows
    return _json(_windows())


@mcp.tool(annotations=READ_ONLY)
def find(query: str, focus: Optional[str] = None, region: Optional[str] = None) -> str:
    """[UIA] Search for a UI element by name in the active window.

    Faster than describe when you know what element you're looking for.

    Args:
        query: Text to search for in element names (fuzzy match).
        focus: Filter preset to narrow results by type.
        region: Spatial filter — "top", "bottom", etc. or "X,Y,W,H".
    """
    _com_init()
    from nexus.oculus.uia import find as _find
    return _json(_find(query=query, focus=focus, region=region))


@mcp.tool(annotations=READ_ONLY)
def focused() -> str:
    """[UIA] Report which UI element currently has keyboard focus."""
    _com_init()
    from nexus.oculus.uia import focused as _focused
    return _json(_focused())


# ── Web Awareness (Chrome/CDP) ─────────────────────────────────────────────────

@mcp.tool(annotations=READ_ONLY)
def web_describe(tab: int = 0, full: bool = False, port: int = 9222) -> str:
    """[CDP] Get page title, URL, and key interactive elements from Chrome.

    Use for a quick overview of the current browser page.
    For complex SPAs with dynamic content, prefer web_ax instead.

    Args:
        tab: Target tab index (default: active tab).
        full: If True, return all headings, links, and inputs (verbose).
        port: CDP port (default 9222, use other ports for Electron apps).
    """
    from nexus.oculus.web import web_describe as _web_describe
    return _json(_web_describe(tab=tab, full=full, port=port))


@mcp.tool(annotations=READ_ONLY)
def web_text(tab: int = 0, port: int = 9222) -> str:
    """[CDP] Get all visible text content from the current browser tab.

    Args:
        tab: Target tab index.
        port: CDP port.
    """
    from nexus.oculus.web import web_text as _web_text
    return _json(_web_text(tab=tab, port=port))


@mcp.tool(annotations=READ_ONLY)
def web_find(query: str, tab: int = 0, port: int = 9222) -> str:
    """[CDP] Find elements on the current browser page by visible text.

    Args:
        query: Text to search for on the page.
        tab: Target tab index.
        port: CDP port.
    """
    from nexus.oculus.web import web_find as _web_find
    return _json(_web_find(query=query, tab=tab, port=port))


@mcp.tool(annotations=READ_ONLY)
def web_links(tab: int = 0, port: int = 9222) -> str:
    """[CDP] List all hyperlinks on the current browser page.

    Args:
        tab: Target tab index.
        port: CDP port.
    """
    from nexus.oculus.web import web_links as _web_links
    return _json(_web_links(tab=tab, port=port))


@mcp.tool(annotations=READ_ONLY)
def web_tabs(port: int = 9222) -> str:
    """[CDP] List all open browser tabs with titles and URLs.

    Args:
        port: CDP port.
    """
    from nexus.oculus.web import web_tabs as _web_tabs
    return _json(_web_tabs(port=port))


@mcp.tool(annotations=READ_ONLY)
def web_ax(
    tab: int = 0,
    port: int = 9222,
    focus: Optional[str] = None,
    match: Optional[str] = None,
) -> str:
    """[CDP] Chrome accessibility tree via CDP. More reliable than web_describe for SPAs.

    Returns the semantic structure that screen readers see — roles, names,
    states (checked, expanded, focused, disabled).

    Args:
        tab: Target tab index.
        port: CDP port.
        focus: Filter preset — "buttons", "inputs", "interactive", "navigation",
               "headings", "forms", "errors", "dialogs", or free text.
        match: Glob or regex pattern to match node names.
    """
    from nexus.oculus.web import web_ax as _web_ax
    return _json(_web_ax(tab=tab, port=port, focus=focus, match=match))


@mcp.tool(annotations=READ_ONLY)
def web_measure(selectors: str, tab: int = 0, port: int = 9222) -> str:
    """[CDP] Get exact computed CSS dimensions, padding, and margins for elements.

    Use for layout debugging — returns pixel-precise measurements.

    Args:
        selectors: Comma-separated CSS selectors (e.g. ".hero, .hero h1, .hero img").
        tab: Target tab index.
        port: CDP port.
    """
    from nexus.oculus.web import web_measure as _web_measure
    return _json(_web_measure(selectors=selectors, tab=tab, port=port))


@mcp.tool(annotations=READ_ONLY)
def web_contrast(selectors: str = "", tab: int = 0, port: int = 9222) -> str:
    """[CDP] Scan page elements for color contrast and readability issues.

    Walks up the DOM to find effective background, computes luminance delta,
    flags elements as critical (delta < 40), warning (delta < 80), or ok.
    With no selectors, scans common UI elements (buttons, links, nav, tables, forms).

    Args:
        selectors: Optional comma-separated CSS selectors. Empty = scan defaults.
        tab: Target tab index.
        port: CDP port.
    """
    from nexus.oculus.web import web_contrast as _web_contrast
    return _json(_web_contrast(selectors=selectors, tab=tab, port=port))


@mcp.tool(annotations=READ_ONLY)
def web_markdown(tab: int = 0, port: int = 9222) -> str:
    """[CDP] Extract clean article content from page using Readability.js.

    Strips navigation, ads, footers — returns just the main content as markdown.
    Great for reading documentation or articles.

    Args:
        tab: Target tab index.
        port: CDP port.
    """
    from nexus.oculus.web import web_markdown as _web_markdown
    return _json(_web_markdown(tab=tab, port=port))


@mcp.tool(annotations=OPEN_WORLD)
def web_capture_api(url: str, filter_pattern: str = "", tab: int = 0, port: int = 9222) -> str:
    """[CDP] Navigate to URL and capture all JSON API responses during page load.

    Use for SPAs that load data via fetch — the API JSON is cleaner than the DOM.

    Args:
        url: URL to navigate to.
        filter_pattern: Only capture responses matching this URL pattern.
        tab: Target tab index.
        port: CDP port.
    """
    from nexus.oculus.web import web_capture_api as _web_capture_api
    return _json(_web_capture_api(url=url, filter_pattern=filter_pattern, tab=tab, port=port))


@mcp.tool(annotations=OPEN_WORLD)
def web_research(query: str, max_results: int = 3, engine: str = "duckduckgo", port: int = 9222) -> str:
    """[CDP] Search the web, visit top results, and extract content autonomously.

    Args:
        query: Search query.
        max_results: Max results to visit (default 3, max 5).
        engine: Search engine — "duckduckgo" or "brave".
        port: CDP port.
    """
    from nexus.oculus.web import web_research as _web_research
    return _json(_web_research(query=query, max_results=max_results, engine=engine, port=port))


# ── OCR ────────────────────────────────────────────────────────────────────────

@mcp.tool(annotations=READ_ONLY)
def ocr_region(x: int, y: int, w: int, h: int, lang: str = "en") -> str:
    """[OCR] OCR a screen region by pixel coordinates.

    Use for non-accessible UIs, images, canvas elements, or any visual-only content.

    Args:
        x: Region X coordinate.
        y: Region Y coordinate.
        w: Region width in pixels.
        h: Region height in pixels.
        lang: OCR language (default "en").
    """
    from nexus.oculus.ocr import ocr_region as _ocr_region
    return _json(_ocr_region(x=x, y=y, w=w, h=h, lang=lang))


@mcp.tool(annotations=READ_ONLY)
def ocr_screen(lang: str = "en") -> str:
    """[OCR] OCR the entire active window.

    Use when the UIA tree is empty or unreliable. Slower than describe but works on
    any visual content. Returns recognized text with word-level bounding boxes.

    Args:
        lang: OCR language (default "en").
    """
    from nexus.oculus.ocr import ocr_screen as _ocr_screen
    return _json(_ocr_screen(lang=lang))


# ── Screen Input ───────────────────────────────────────────────────────────────

@mcp.tool(annotations=READ_ONLY)
def screenshot(region: Optional[str] = None, full: bool = False, mark: bool = False) -> list:
    """[Screen] Take a screenshot of the screen. Returns the image for visual inspection.

    Args:
        region: Capture only a region as "X,Y,W,H" (e.g. "100,200,800,600").
        full: If True, native resolution (no downscale to 1920x1080).
        mark: If True, annotate elements with numbered badges (Set-of-Mark).
              Use click_mark() afterward to click a numbered element.
    """
    _com_init()
    if not mark:
        from nexus.digitus.input import screenshot as _screenshot
        result = _screenshot(region=region, full=full)
    else:
        from nexus.oculus.uia import describe as _describe
        from nexus.mark import screenshot_with_marks, store_marks
        desc = _describe()
        elements = desc.get("elements", [])
        result = screenshot_with_marks(elements, region=region, full=full)
        store_marks(result.get("marks", []))

    path = result.get("path", "")
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return [ImageContent(type="image", data=data, mimeType="image/png")]
    return _json(result)


@mcp.tool(annotations=SAFE_ACTION)
def click(x: int, y: int, right: bool = False, double: bool = False) -> str:
    """[Screen] Click at exact pixel coordinates on screen.

    Prefer click_element when possible (safer, survives window moves).
    Only use raw coordinates for canvas/game UIs where elements have no names.

    Args:
        x: X coordinate.
        y: Y coordinate.
        right: If True, right-click instead of left-click.
        double: If True, double-click.
    """
    from nexus.digitus.input import click as _click
    return _json(_click(x=x, y=y, right=right, double=double))


@mcp.tool(annotations=SAFE_ACTION)
def move(x: int, y: int) -> str:
    """[Screen] Move cursor to pixel coordinates without clicking.

    Args:
        x: X coordinate.
        y: Y coordinate.
    """
    from nexus.digitus.input import move as _move
    return _json(_move(x=x, y=y))


@mcp.tool(annotations=SAFE_ACTION)
def drag(start: str, end: str, duration: float = 0.5) -> str:
    """[Screen] Drag from one screen coordinate to another.

    Args:
        start: Start coordinates as "X1,Y1".
        end: End coordinates as "X2,Y2".
        duration: Drag duration in seconds (default 0.5).
    """
    from nexus.digitus.input import drag as _drag
    return _json(_drag(start=start, end=end, duration=duration))


@mcp.tool(annotations=SAFE_ACTION)
def type_text(text: str) -> str:
    """[Screen] Type text at the current cursor/focus position.

    The target input must already have focus — use click_element or web_input to focus first.

    Args:
        text: The text to type.
    """
    from nexus.digitus.input import type_text as _type_text
    return _json(_type_text(text=text))


@mcp.tool(annotations=SAFE_ACTION)
def key_press(keyname: str) -> str:
    """[Screen] Press a key or keyboard shortcut.

    Args:
        keyname: Key name or combo — e.g. "ctrl+s", "enter", "tab", "alt+f4", "shift+ctrl+p".
    """
    from nexus.digitus.input import key as _key
    return _json(_key(keyname=keyname))


@mcp.tool(annotations=SAFE_ACTION)
def scroll(amount: int) -> str:
    """[Screen] Scroll the mouse wheel. Positive = up, negative = down.

    Args:
        amount: Scroll amount. Positive scrolls up, negative scrolls down.
    """
    from nexus.digitus.input import scroll as _scroll
    return _json(_scroll(amount=amount))


@mcp.tool(annotations=READ_ONLY)
def screen_info() -> str:
    """[Screen] Get screen resolution and current cursor position."""
    from nexus.digitus.input import info as _info
    return _json(_info())


# ── Element Interaction ────────────────────────────────────────────────────────

@mcp.tool(annotations=SAFE_ACTION)
def click_element(
    name: str,
    right: bool = False,
    double: bool = False,
    role: Optional[str] = None,
    index: int = 0,
    verify: bool = False,
    heal: bool = False,
) -> str:
    """[UIA] Find a UI element by name and click it. Safer than pixel coordinates.

    Supports fuzzy name matching. Use role to disambiguate when multiple elements match.
    Set heal=True for auto-recovery from failures (element moved, dialog blocking).
    On failure, returns suggestions with similar element names.

    Args:
        name: Element name to search for (fuzzy match).
        right: If True, right-click.
        double: If True, double-click.
        role: Filter by role — "button", "input", "link", "tab", "menu",
              "checkbox", "radio", etc.
        index: Which match to click (0-based) when multiple elements match.
        verify: If True, re-describe after click to confirm state changed.
        heal: If True, auto-recover from failures (element moved, dialog blocking).
    """
    _com_init()
    from nexus.digitus.element import click_element as _click_element
    return _json(_click_element(
        name=name, right=right, double=double, role=role,
        index=index, verify=verify, heal=heal,
    ))


@mcp.tool(annotations=SAFE_ACTION)
def click_mark(mark_id: int) -> str:
    """[Screen] Click a numbered element from the last screenshot with mark=True.

    Take a screenshot with mark=True first, then use this to click by number.

    Args:
        mark_id: Element number from the marked screenshot.
    """
    from nexus.run import _cmd_click_mark
    return _json(_cmd_click_mark(mark_id=mark_id))


# ── Web Actions ────────────────────────────────────────────────────────────────

@mcp.tool(annotations=SAFE_ACTION)
def web_click(text: str, port: int = 9222, heal: bool = False) -> str:
    """[CDP] Click a browser element by its visible text.

    Uses exact visible text matching — the text must be rendered on the page (not aria-label).
    Set heal=True for auto-recovery. On failure, returns clickable alternatives from the page.

    Args:
        text: Visible text of the element to click.
        port: CDP port.
        heal: If True, auto-recover from failures (wait for load, try alternatives).
    """
    from nexus.digitus.web import web_click as _web_click
    return _json(_web_click(text=text, port=port, heal=heal))


@mcp.tool(annotations=OPEN_WORLD)
def web_navigate(url: str, port: int = 9222) -> str:
    """[CDP] Navigate Chrome to a URL.

    Args:
        url: URL to navigate to.
        port: CDP port.
    """
    from nexus.digitus.web import web_navigate as _web_navigate
    return _json(_web_navigate(url=url, port=port))


@mcp.tool(annotations=SAFE_ACTION)
def web_input(selector: str, value: str, port: int = 9222) -> str:
    """[CDP] Fill an input field in the browser by label, placeholder, or CSS selector.

    Tries matching by: 1) label text, 2) placeholder text, 3) CSS selector — in that order.
    On failure, returns available inputs on the page so you can retry with the right selector.

    Args:
        selector: Label text, placeholder text, or CSS selector of the input.
        value: Value to fill into the input.
        port: CDP port.
    """
    from nexus.digitus.web import web_input as _web_input
    return _json(_web_input(selector=selector, value=value, port=port))


@mcp.tool(annotations=DESTRUCTIVE)
def web_pdf(
    output: Optional[str] = None,
    page_format: str = "A4",
    landscape: bool = False,
    port: int = 9222,
) -> str:
    """[CDP] Export the current browser page to PDF.

    Args:
        output: Output file path. If not set, returns base64-encoded PDF data.
        page_format: Page size — "A4", "Letter", "A3", or "Legal".
        landscape: If True, landscape orientation.
        port: CDP port.
    """
    from nexus.digitus.web import web_pdf as _web_pdf
    return _json(_web_pdf(output=output, page_format=page_format, landscape=landscape, port=port))


# ── System ─────────────────────────────────────────────────────────────────────

@mcp.tool(annotations=DESTRUCTIVE)
def ps_run(script: str) -> str:
    """[System] Execute a PowerShell command and return structured output.

    Use for system tasks: file operations, process management, registry reads.
    Output is auto-parsed as JSON when possible.

    Args:
        script: PowerShell command to execute.
    """
    from nexus.digitus.system import ps_run as _ps_run
    return _json(_ps_run(script=script))


@mcp.tool(annotations=READ_ONLY)
def com_shell(path: Optional[str] = None) -> str:
    """[COM] Browse the filesystem via Windows Shell.Application COM. No UI needed.

    Args:
        path: Directory path to browse (default: user home directory).
    """
    _com_init()
    from nexus.digitus.system import com_shell as _com_shell
    return _json(_com_shell(path=path))


@mcp.tool(annotations=SAFE_ACTION)
def com_excel(
    action: str,
    path: Optional[str] = None,
    cell_range: Optional[str] = None,
    cell: Optional[str] = None,
    value: Optional[str] = None,
    sheet: Optional[str] = None,
) -> str:
    """[COM] Automate Excel: list open workbooks, read/write cell ranges, list sheets.

    Args:
        action: Action — "list" (open workbooks), "read" (cell range), "write" (cell), "sheets".
        path: Workbook file path to open.
        cell_range: Cell range for read (e.g. "A1:D10").
        cell: Cell address for write (e.g. "B2").
        value: Value to write.
        sheet: Target sheet name.
    """
    from nexus.digitus.office import com_excel as _com_excel
    return _json(_com_excel(action=action, path=path, range_=cell_range, cell=cell, value=value, sheet=sheet))


@mcp.tool(annotations=READ_ONLY)
def com_word(
    action: str,
    path: Optional[str] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> str:
    """[COM] Read Word documents via COM automation.

    Args:
        action: Action — "read" (document text) or "info" (metadata).
        path: Document file path to open.
        start: Start paragraph number (for partial read).
        end: End paragraph number (for partial read).
    """
    from nexus.digitus.office import com_word as _com_word
    return _json(_com_word(action=action, path=path, start=start, end=end))


@mcp.tool(annotations=DESTRUCTIVE)
def com_outlook(
    action: str,
    count: int = 5,
    item_id: Optional[str] = None,
    to: Optional[str] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
) -> str:
    """[COM] Access Outlook: read inbox, read individual emails, send emails.

    Args:
        action: Action — "inbox" (list recent), "read" (single email), "send".
        count: Number of inbox items to return (default 5).
        item_id: Outlook EntryID for reading a specific email.
        to: Recipient email address (for send).
        subject: Email subject (for send).
        body: Email body text (for send).
    """
    from nexus.digitus.office import com_outlook as _com_outlook
    return _json(_com_outlook(action=action, count=count, item_id=item_id, to=to, subject=subject, body=body))


# ── Electron Apps ──────────────────────────────────────────────────────────────

@mcp.tool(annotations=READ_ONLY)
def electron_detect() -> str:
    """[Electron] Scan for running Chromium/Electron apps with CDP debug ports enabled.

    Finds VS Code, Discord, Slack, and other Electron apps if launched with
    --remote-debugging-port flag.
    """
    from nexus.electron import detect as _detect
    return _json(_detect())


@mcp.tool(annotations=READ_ONLY)
def electron_connect(port: int) -> str:
    """[Electron] Verify CDP connection to an Electron app by port number.

    Args:
        port: CDP debug port of the Electron app.
    """
    from nexus.electron import connect as _connect
    return _json(_connect(port=port))


@mcp.tool(annotations=READ_ONLY)
def electron_targets(port: int) -> str:
    """[Electron] List CDP targets (pages/tabs) on an Electron app's debug port.

    Args:
        port: CDP debug port to query.
    """
    from nexus.electron import list_targets as _list_targets
    return _json(_list_targets(port=port))


# ── Vision (OmniParser) ────────────────────────────────────────────────────────

@mcp.tool(annotations=READ_ONLY)
def vision_detect(
    image_path: Optional[str] = None,
    region: Optional[str] = None,
    box_threshold: float = 0.05,
    iou_threshold: float = 0.1,
    annotated: bool = False,
) -> str | list:
    """[Vision] Detect UI elements using OmniParser vision model (screenshot-based).

    Works on any UI including games, canvas apps, and non-accessible applications.
    Slower than UIA describe (~26s) — only use when describe/find return nothing.
    Requires OmniParser server running (check with vision_health first).

    Args:
        image_path: Path to image file. If not set, takes a fresh screenshot.
        region: Screenshot region as "X,Y,W,H" (only when image_path is not set).
        box_threshold: Detection confidence threshold (default 0.05).
        iou_threshold: IOU threshold for non-max suppression (default 0.1).
        annotated: If True, also return the annotated image with bounding boxes.
    """
    from nexus.digitus.vision import vision_detect as _vision_detect
    result = _vision_detect(
        image_path=image_path, region=region,
        box_threshold=box_threshold, iou_threshold=iou_threshold,
        annotated=annotated,
    )
    # If annotated, return the image so Claude can see detected elements
    if annotated and result.get("annotated_path"):
        path = result["annotated_path"]
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            return [
                ImageContent(type="image", data=data, mimeType="image/png"),
                TextContent(type="text", text=_json(result)),
            ]
    return _json(result)


@mcp.tool(annotations=READ_ONLY)
def vision_health() -> str:
    """[Vision] Check if the OmniParser vision server is running."""
    from nexus.digitus.vision import vision_health as _vision_health
    return _json(_vision_health())


# ── Image Measurement ─────────────────────────────────────────────────────

@mcp.tool(annotations=READ_ONLY)
def measure_image(
    image_path: str,
    box_threshold: float = 0.05,
    iou_threshold: float = 0.1,
    lang: str = "en",
    scale: float = 1.0,
) -> str:
    """[Vision] Measure UI elements in a reference design image using OmniParser + OCR.

    Combines vision detection (for icons/elements) with text recognition
    to build a complete element map of a design PNG exported from Figma or Krita.

    Args:
        image_path: Absolute path to PNG image (Figma/Krita export).
        box_threshold: OmniParser confidence threshold (default 0.05).
        iou_threshold: OmniParser overlap threshold (default 0.1).
        lang: OCR language (default "en").
        scale: Scale factor for @2x exports — 0.5 halves all coordinates.
    """
    from nexus.oculus.image import measure_image as _measure_image
    return _json(_measure_image(
        image_path=image_path,
        box_threshold=box_threshold,
        iou_threshold=iou_threshold,
        lang=lang,
        scale=scale,
    ))


@mcp.tool(annotations=READ_ONLY)
def web_layout_diff(
    image_path: str,
    selectors: str,
    tab: int = 0,
    port: int = 9222,
    box_threshold: float = 0.05,
    iou_threshold: float = 0.1,
    lang: str = "en",
    scale: float = 1.0,
    match_by: str = "text",
) -> str:
    """[Vision] Compare a reference design image against live CSS measurements.

    Runs measure-image on the PNG, runs web-measure on the selectors,
    matches elements, and returns per-element pixel deltas.

    Args:
        image_path: Absolute path to reference design PNG.
        selectors: Comma-separated CSS selectors (e.g. ".hero, h1, .btn").
        tab: Target tab index.
        port: CDP port (default 9222).
        box_threshold: OmniParser confidence threshold.
        iou_threshold: OmniParser overlap threshold.
        lang: OCR language.
        scale: Scale factor for @2x exports.
        match_by: Matching strategy — "text" (default), "position", or "index".
    """
    from nexus.oculus.image import web_layout_diff as _web_layout_diff
    return _json(_web_layout_diff(
        image_path=image_path,
        selectors=selectors,
        tab=tab,
        port=port,
        box_threshold=box_threshold,
        iou_threshold=iou_threshold,
        lang=lang,
        scale=scale,
        match_by=match_by,
    ))


# ── Meta ───────────────────────────────────────────────────────────────────────

@mcp.tool(annotations=SAFE_ACTION)
def batch(steps: str, verbose: bool = False, continue_on_error: bool = False) -> str:
    """[Meta] Execute multiple Nexus commands in sequence with variable interpolation.

    Steps are semicolon-separated. Variables from previous steps are available
    via $name, $x, $y, ${key} syntax.

    Example: "describe --focus buttons; click-element Save --verify"

    Args:
        steps: Semicolon-separated commands (e.g. "describe --focus buttons; find Save").
        verbose: If True, return all intermediate results (not just the final one).
        continue_on_error: If True, keep going after a step fails.
    """
    _com_init()
    from nexus.batch import execute_batch
    from nexus.run import _build_daemon_commands
    commands = _build_daemon_commands()
    result = execute_batch(steps, commands, verbose=verbose, continue_on_error=continue_on_error)
    return _json(result)


# ── Watch (Event-Driven Awareness) ────────────────────────────────────────

@mcp.tool(annotations=SAFE_ACTION)
def watch_start(events: Optional[str] = None) -> str:
    """[UIA] Start watching for UIA events (focus changes, window open/close, dialogs).

    Events stream in the background. Use watch_poll() to retrieve them.
    Use watch_stop() to end the session.

    Args:
        events: Comma-separated event types to subscribe to.
                Options: "focus", "window", "structure", "property".
                Default: all types.
    """
    _com_init()
    from nexus.watcher import start_watching
    event_list = [e.strip() for e in events.split(",")] if events else None
    return _json(start_watching(events=event_list))


@mcp.tool(annotations=SAFE_ACTION)
def watch_stop() -> str:
    """[UIA] Stop the UIA event watcher."""
    from nexus.watcher import stop_watching
    return _json(stop_watching())


@mcp.tool(annotations=READ_ONLY)
def watch_poll(max_events: int = 50, timeout: float = 1.0) -> str:
    """[UIA] Retrieve pending UIA events from the watcher.

    Call watch_start() first. Returns events that occurred since last poll.

    Args:
        max_events: Maximum number of events to return.
        timeout: How long to wait for the first event in seconds (0 = non-blocking).
    """
    from nexus.watcher import poll_events
    events = poll_events(max_events=max_events, timeout=timeout)
    return _json({"command": "watch-poll", "ok": True, "events": events, "count": len(events)})


@mcp.tool(annotations=READ_ONLY)
def watch_status() -> str:
    """[UIA] Check if the UIA event watcher is currently running."""
    from nexus.watcher import watch_status as _watch_status
    return _json(_watch_status())


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
