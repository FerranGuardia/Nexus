"""Nexus Tool Schema — extract tool definitions from argparse parser.

Two outputs:
  extract_tool_schemas(parser) -> list[dict]   # OpenAI function calling format
  generate_markdown(schemas) -> str            # Human/LLM-readable reference

Used by the 'describe-tools' CLI command and can be imported directly.
"""

import argparse


# One-sentence "when to use" descriptions — richer than argparse help strings.
# These are what an LLM reads to decide which tool to call.
# Prefixed with [Source] tag for instant subsystem identification.
TOOL_DESCRIPTIONS = {
    # UIA Awareness
    "describe": "[UIA] Describe the active window's UI elements, cursor position, and focused element. Use this to understand what's on screen before clicking or interacting. Returns named interactive elements with types and screen coordinates. Use focus/match/region params to narrow results. If you know the element name, use 'find' instead (faster).",
    "windows": "[UIA] List all open windows with titles, positions, and process info. Use to identify which app is running or find a specific window before switching to it.",
    "find": "[UIA] Search for a UI element by name in the active window. Faster than describe when you know what element you're looking for — returns only matches, not the full tree.",
    "focused": "[UIA] Report which UI element currently has keyboard focus. Use after typing or tabbing to confirm the right field is active.",
    # Web Awareness
    "web-describe": "[CDP] Get page title, URL, and key interactive elements from Chrome. Use for a quick overview of the current browser page. For complex SPAs with dynamic content, prefer web_ax instead.",
    "web-text": "[CDP] Get all visible text content from the current browser tab. Returns raw text, not DOM structure. Use when you need to read page content, not interact with it.",
    "web-find": "[CDP] Find elements on the current browser page by visible text. Returns matching elements with their roles and positions. Use before web_click to verify the element exists.",
    "web-links": "[CDP] List all hyperlinks on the current browser page with their URLs and text. Use when you need to find a link to click or extract URLs.",
    "web-tabs": "[CDP] List all open browser tabs with titles and URLs. Use to find which tab to target with the tab parameter.",
    "web-ax": "[CDP] Chrome accessibility tree via CDP. More reliable than web_describe for SPAs and dynamic pages — returns the semantic structure that screen readers see (roles, names, states like checked/expanded/focused/disabled). Use focus param to filter by type.",
    "web-measure": "[CDP] Get exact computed CSS dimensions, padding, and margins for elements by CSS selector. Returns pixel-precise measurements. Use for layout debugging — not for finding elements (use web_find or web_ax for that).",
    "web-contrast": "[CDP] Scan page elements for color contrast and readability issues. Walks up the DOM to find effective background color, computes luminance delta, and flags elements as critical (delta < 40), warning (delta < 80), or ok. With no selectors, scans common UI elements (buttons, links, nav, tables, forms, badges, footer). Use after CSS changes to verify readability.",
    "web-markdown": "[CDP] Extract clean article content from page using Readability.js. Strips navigation, ads, footers — returns just the main content as markdown. Great for reading documentation or articles.",
    "web-capture-api": "[CDP] Navigate to URL and capture all JSON API responses during page load. Use for SPAs that load data via fetch — the API JSON is cleaner than the DOM. Set filter_pattern to match specific API endpoints.",
    "web-research": "[CDP] Search the web, visit top results, and extract content autonomously. Use for research tasks that need multiple sources. Returns extracted content from each result page.",
    # OCR
    "ocr-region": "[OCR] OCR a screen region by pixel coordinates. Use for non-accessible UIs, images, canvas elements, or any visual-only content where UIA returns nothing.",
    "ocr-screen": "[OCR] OCR the entire active window. Use when the UIA tree is empty or unreliable for the target app. Slower than describe but works on any visual content.",
    # Screen Input
    "screenshot": "[Screen] Take a screenshot of the screen. Returns the image for visual inspection. Use mark=True to annotate elements with numbered badges, then click_mark to click by number.",
    "click": "[Screen] Click at exact pixel coordinates. Use click_element instead when possible (safer, survives window moves). Only use raw coordinates for canvas/game UIs where elements have no names.",
    "move": "[Screen] Move cursor to pixel coordinates without clicking. Use for hover effects or to position before drag operations.",
    "drag": "[Screen] Drag from one screen coordinate to another. Specify start and end as 'X,Y' strings.",
    "type": "[Screen] Type text at the current cursor/focus position. The target input must already have focus — use click_element or web_input to focus first.",
    "key": "[Screen] Press a key or keyboard shortcut. Use combo syntax: 'ctrl+s', 'alt+f4', 'shift+ctrl+p'. Single keys: 'enter', 'tab', 'escape', 'space'.",
    "scroll": "[Screen] Scroll the mouse wheel at current cursor position. Positive = up, negative = down. Typical values: 3 for a page, 1 for a few lines.",
    "info": "[Screen] Get screen resolution and current cursor position.",
    # Element Interaction
    "click-element": "[UIA] Find a UI element by name and click it. Safer than pixel coordinates — survives window moves. Uses fuzzy name matching. Set role to disambiguate ('button', 'link', 'tab', etc.). Set heal=True for auto-recovery from failures.",
    "click-mark": "[Screen] Click a numbered element from the last screenshot with mark=True. Take a screenshot with mark=True first, then use this to click by number. Useful when element names are ambiguous.",
    # Web Actions
    "web-click": "[CDP] Click a browser element by its visible text. Uses exact text matching — the text must be visible on the page. Set heal=True for auto-recovery. If it fails, check the error suggestions for clickable alternatives.",
    "web-navigate": "[CDP] Navigate Chrome to a URL. Waits for DOM content loaded. URLs without http:// get https:// prepended.",
    "web-input": "[CDP] Fill an input field in the browser. Tries matching by: 1) label text, 2) placeholder text, 3) CSS selector — in that order. If all fail, error includes available inputs on the page.",
    "web-pdf": "[CDP] Export the current browser page to PDF. Set output path to save to file, or omit for base64 data.",
    # System
    "ps-run": "[System] Execute a PowerShell command and return structured output. Output is auto-parsed as JSON when possible. Use for system tasks: file operations, process management, registry reads.",
    "com-shell": "[COM] Browse the filesystem via Windows Shell.Application COM. No UI needed. Returns file listings with sizes and dates. Use path with backslashes.",
    "com-excel": "[COM] Automate Excel via COM: list open workbooks, read/write cell ranges, list sheets. Requires Excel to be installed.",
    "com-word": "[COM] Read Word documents via COM. Actions: 'read' (get text), 'info' (get metadata). Use start/end to read specific paragraph ranges.",
    "com-outlook": "[COM] Access Outlook via COM: 'inbox' (list recent), 'read' (single email by ID), 'send' (compose and send).",
    # Vision
    "vision-detect": "[Vision] Detect UI elements using OmniParser vision model (screenshot-based). Works on any UI including games, canvas apps, and non-accessible applications. Slower than UIA (~26s) — use only when describe/find return nothing. Requires OmniParser server running.",
    "vision-health": "[Vision] Check if the OmniParser vision server is running on the expected port.",
    "measure-image": "[Vision] Measure UI elements in a reference design PNG (Figma/Krita export) using OmniParser + OCR. Returns element list with pixel-accurate bounds. Use scale=0.5 for @2x exports.",
    "web-layout-diff": "[Vision] Compare a reference design image against live CSS measurements. Matches elements by text/position/index and reports pixel deltas per element. Use to verify implementation matches design.",
    # Electron
    "electron-detect": "[Electron] Scan for running Chromium/Electron apps with CDP debug ports. Finds VS Code, Discord, Slack etc. if launched with --remote-debugging-port.",
    "electron-connect": "[Electron] Verify CDP connection to an Electron app by port number. Use after electron_detect to confirm a port is reachable.",
    "electron-targets": "[Electron] List CDP targets (pages/tabs) on an Electron app's debug port. Use to find the right tab index for web commands with a custom port.",
    # Meta
    "batch": "[Meta] Execute multiple Nexus commands in sequence with variable interpolation. Steps are semicolon-separated. Variables from previous steps available via $name, $x, $y syntax.",
}


# Tool annotations — semantic hints for orchestrators.
# Maps command name to (readOnlyHint, destructiveHint, idempotentHint).
TOOL_ANNOTATIONS = {
    # UIA Awareness — all read-only
    "describe": (True, False, True),
    "windows": (True, False, True),
    "find": (True, False, True),
    "focused": (True, False, True),
    # Web Awareness — all read-only
    "web-describe": (True, False, True),
    "web-text": (True, False, True),
    "web-find": (True, False, True),
    "web-links": (True, False, True),
    "web-tabs": (True, False, True),
    "web-ax": (True, False, True),
    "web-measure": (True, False, True),
    "web-contrast": (True, False, True),
    "web-markdown": (True, False, True),
    "web-capture-api": (False, False, False),  # navigates, side effect
    "web-research": (False, False, False),  # navigates, side effect
    # OCR — read-only
    "ocr-region": (True, False, True),
    "ocr-screen": (True, False, True),
    # Screen Input
    "screenshot": (True, False, True),
    "click": (False, False, False),
    "move": (False, False, False),
    "drag": (False, False, False),
    "type": (False, False, False),
    "key": (False, False, False),
    "scroll": (False, False, False),
    "info": (True, False, True),
    # Element Interaction
    "click-element": (False, False, False),
    "click-mark": (False, False, False),
    # Web Actions
    "web-click": (False, False, False),
    "web-navigate": (False, False, False),
    "web-input": (False, False, False),
    "web-pdf": (False, True, False),  # writes files = destructive
    # System
    "ps-run": (False, True, False),  # arbitrary commands = destructive
    "com-shell": (True, False, True),
    "com-excel": (False, False, False),  # write action is destructive, but read isn't
    "com-word": (True, False, True),
    "com-outlook": (False, True, False),  # send action is destructive
    # Vision
    "vision-detect": (True, False, True),
    "vision-health": (True, False, True),
    "measure-image": (True, False, True),
    "web-layout-diff": (True, False, True),
    # Electron
    "electron-detect": (True, False, True),
    "electron-connect": (True, False, True),
    "electron-targets": (True, False, True),
    # Meta
    "batch": (False, False, False),
}

TOOL_CATEGORIES = {
    "UIA Awareness (Native Apps)": ["describe", "windows", "find", "focused"],
    "Web Awareness (Chrome/CDP)": [
        "web-describe", "web-text", "web-find", "web-links", "web-tabs",
        "web-ax", "web-measure", "web-contrast", "web-markdown", "web-capture-api", "web-research",
    ],
    "OCR": ["ocr-region", "ocr-screen"],
    "Screen Input": ["screenshot", "click", "move", "drag", "type", "key", "scroll", "info"],
    "Element Interaction": ["click-element", "click-mark"],
    "Web Actions": ["web-click", "web-navigate", "web-input", "web-pdf"],
    "Vision (OmniParser)": ["vision-detect", "vision-health", "measure-image", "web-layout-diff"],
    "System": ["ps-run", "com-shell", "com-excel", "com-word", "com-outlook"],
    "Electron Apps": ["electron-detect", "electron-connect", "electron-targets"],
    "Meta": ["batch"],
}

# Commands to skip in schema output (infrastructure, not agent-facing)
_SKIP_COMMANDS = {"serve", "task", "describe-tools"}


def _action_to_param(action: argparse.Action) -> dict:
    """Convert one argparse action to a JSON Schema property."""
    param = {}

    if isinstance(action, argparse._StoreTrueAction):
        param["type"] = "boolean"
    elif action.type == int:
        param["type"] = "integer"
    elif action.type == float:
        param["type"] = "number"
    else:
        param["type"] = "string"

    if action.choices:
        param["enum"] = list(action.choices)
    if action.default is not None and action.default != argparse.SUPPRESS:
        param["default"] = action.default
    if action.help and action.help != argparse.SUPPRESS:
        param["description"] = action.help

    return param


def extract_tool_schemas(parser: argparse.ArgumentParser) -> list:
    """Extract OpenAI function-calling format tool definitions from argparse parser.

    Returns list of dicts: [{name, description, parameters: {type, properties, required}}]
    """
    schemas = []

    # Find the subparsers action
    subparsers_action = None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers_action = action
            break

    if not subparsers_action:
        return schemas

    for cmd_name, subparser in subparsers_action.choices.items():
        if cmd_name in _SKIP_COMMANDS:
            continue

        properties = {}
        required = []

        for action in subparser._actions:
            # Skip help and timeout (inherited, not tool-specific)
            if isinstance(action, argparse._HelpAction):
                continue
            if action.dest in ("help", "timeout"):
                continue

            prop = _action_to_param(action)
            properties[action.dest] = prop

            # Positional args (no --flag prefix) are required
            is_positional = not action.option_strings
            if is_positional and not isinstance(action, argparse._StoreTrueAction):
                required.append(action.dest)

        description = TOOL_DESCRIPTIONS.get(cmd_name, "")
        if not description:
            description = subparser.description or getattr(subparser, "_help", "") or cmd_name

        schema = {
            "name": cmd_name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

        # Add annotations if available
        annot = TOOL_ANNOTATIONS.get(cmd_name)
        if annot:
            read_only, destructive, idempotent = annot
            schema["annotations"] = {
                "readOnlyHint": read_only,
                "destructiveHint": destructive,
                "idempotentHint": idempotent,
            }

        schemas.append(schema)

    return schemas


def generate_markdown(schemas: list) -> str:
    """Generate a human/LLM-readable markdown reference from tool schemas."""
    lines = [
        "# Nexus Tool Reference",
        "",
        "Nexus gives AI agents eyes and hands on Windows. %d tools across %d categories." % (len(schemas), len(TOOL_CATEGORIES)),
        "Call via CLI (`python -m nexus <command>`) or MCP server (`nexus.mcp_server`).",
        "",
    ]

    by_name = {s["name"]: s for s in schemas}

    for category, commands in TOOL_CATEGORIES.items():
        lines.append("## %s" % category)
        lines.append("")
        for cmd in commands:
            if cmd not in by_name:
                continue
            schema = by_name[cmd]
            lines.append("### `%s`" % cmd)
            lines.append("")
            lines.append(schema["description"])
            lines.append("")

            params = schema["parameters"]["properties"]
            required_list = schema["parameters"].get("required", [])
            if params:
                for name, prop in params.items():
                    req = " **(required)**" if name in required_list else ""
                    typ = prop.get("type", "string")
                    desc = prop.get("description", "")
                    default = prop.get("default")
                    enum = prop.get("enum")

                    parts = ["- `%s` (%s)%s" % (name, typ, req)]
                    if desc:
                        parts.append(" — %s" % desc)
                    if enum:
                        parts.append(" Choices: %s." % ", ".join("`%s`" % e for e in enum))
                    if default is not None:
                        parts.append(" Default: `%s`." % default)
                    lines.append("".join(parts))
                lines.append("")

    return "\n".join(lines)
