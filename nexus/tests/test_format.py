"""Unit tests for nexus.format — compact/minimal output formatters."""

import json
import subprocess

from nexus.format import format_compact, format_minimal
from nexus.tests.conftest import run_nexus, PYTHON, NEXUS_ROOT


# ═══════════════════════════════════════════════════════════════════════════
# Pure unit tests — no UIA needed, just dict → string
# ═══════════════════════════════════════════════════════════════════════════

FAKE_ELEMENT = {
    "name": "Save",
    "type": "ButtonControl",
    "class": "Button",
    "automation_id": "btnSave",
    "bounds": {"left": 100, "top": 300, "right": 180, "bottom": 330,
               "width": 80, "height": 30, "center_x": 140, "center_y": 315},
    "is_visible": True,
}

FAKE_DESCRIBE = {
    "command": "describe",
    "window": {"title": "Notepad", "type": "WindowControl",
               "bounds": {"left": 0, "top": 0, "right": 800, "bottom": 600,
                          "width": 800, "height": 600, "center_x": 400, "center_y": 300}},
    "cursor": {"x": 200, "y": 150, "over_element": None},
    "focused_element": FAKE_ELEMENT,
    "elements": [FAKE_ELEMENT, {
        "name": "Search...",
        "type": "EditControl",
        "class": "TextBox",
        "automation_id": "txtSearch",
        "bounds": {"left": 200, "top": 50, "right": 500, "bottom": 74,
                   "width": 300, "height": 24, "center_x": 350, "center_y": 62},
        "is_visible": True,
    }],
    "element_count": 2,
}

FAKE_WINDOWS = {
    "command": "windows",
    "windows": [
        {"title": "Notepad", "type": "WindowControl", "is_visible": True,
         "is_foreground": True, "bounds": {"width": 800, "height": 600,
                                            "center_x": 400, "center_y": 300}},
        {"title": "Chrome", "type": "WindowControl", "is_visible": True,
         "is_foreground": False, "bounds": {"width": 1920, "height": 1080,
                                             "center_x": 960, "center_y": 540}},
    ],
    "count": 2,
}

FAKE_FIND = {
    "command": "find",
    "query": "Save",
    "window": "Notepad",
    "matches": [FAKE_ELEMENT],
    "count": 1,
}

FAKE_FOCUSED = {
    "command": "focused",
    "element": FAKE_ELEMENT,
    "parent_chain": [
        {"name": "Toolbar", "type": "ToolBarControl"},
        {"name": "Notepad", "type": "WindowControl"},
    ],
}

FAKE_WEB_AX = {
    "command": "web-ax",
    "title": "Example",
    "url": "https://example.com",
    "nodes": [
        {"role": "button", "name": "Submit", "focused": True,
         "disabled": False, "expanded": None, "checked": None, "level": None},
        {"role": "link", "name": "Home", "focused": False,
         "disabled": False, "expanded": None, "checked": None, "level": None},
    ],
    "count": 2,
}

FAKE_WEB_FIND = {
    "command": "web-find",
    "query": "Submit",
    "url": "https://example.com",
    "matches": [
        {"tag": "button", "text": "Submit", "href": None,
         "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
    ],
    "count": 1,
}

FAKE_WEB_TABS = {
    "command": "web-tabs",
    "tabs": [
        {"title": "Google", "url": "https://google.com", "is_active": True},
        {"title": "GitHub", "url": "https://github.com", "is_active": False},
    ],
    "count": 2,
}


class TestCompactFormat:
    def test_describe_compact(self):
        text = format_compact(FAKE_DESCRIBE)
        assert "# Notepad" in text
        assert "Cursor: (200,150)" in text
        assert "[Btn] Save" in text
        assert "[Edit] Search..." in text
        assert "(2 elements)" in text

    def test_windows_compact(self):
        text = format_compact(FAKE_WINDOWS)
        assert "[Win] Notepad" in text
        assert "*fg*" in text
        assert "[Win] Chrome" in text
        assert "(2 windows)" in text

    def test_find_compact(self):
        text = format_compact(FAKE_FIND)
        assert "[Btn] Save" in text
        assert "(1 matches)" in text

    def test_focused_compact(self):
        text = format_compact(FAKE_FOCUSED)
        assert "[Btn] Save" in text
        assert "Chain:" in text
        assert "Toolbar(Toolbar)" in text

    def test_web_ax_compact(self):
        text = format_compact(FAKE_WEB_AX)
        assert "[Btn] Submit" in text
        assert "*focused*" in text
        assert "[Link] Home" in text

    def test_web_find_compact(self):
        text = format_compact(FAKE_WEB_FIND)
        assert "[button] Submit" in text
        assert "(1 matches)" in text

    def test_web_tabs_compact(self):
        text = format_compact(FAKE_WEB_TABS)
        assert "Google" in text
        assert "*active*" in text
        assert "GitHub" in text

    def test_unknown_command_returns_empty(self):
        text = format_compact({"command": "screenshot", "path": "/tmp/x.png"})
        assert text == ""

    def test_compact_much_shorter_than_json(self):
        json_str = json.dumps(FAKE_DESCRIBE, indent=2)
        compact_str = format_compact(FAKE_DESCRIBE)
        ratio = len(compact_str) / len(json_str)
        assert ratio < 0.6, "Compact should be <60%% of JSON size, got %.1f%%" % (ratio * 100)


class TestMinimalFormat:
    def test_describe_minimal(self):
        text = format_minimal(FAKE_DESCRIBE)
        assert "[Btn] Save" in text
        assert "[Edit] Search..." in text
        # No coordinates in minimal
        assert "(140," not in text

    def test_windows_minimal(self):
        text = format_minimal(FAKE_WINDOWS)
        assert "Notepad" in text
        assert "*fg*" in text

    def test_find_minimal(self):
        text = format_minimal(FAKE_FIND)
        assert "[Btn] Save" in text

    def test_web_ax_minimal(self):
        text = format_minimal(FAKE_WEB_AX)
        assert "[Btn] Submit" in text
        assert "[Link] Home" in text


# ═══════════════════════════════════════════════════════════════════════════
# E2E: --format flag via CLI
# ═══════════════════════════════════════════════════════════════════════════

class TestFormatFlagCLI:
    def test_format_json_is_default(self):
        """Default format should be valid JSON."""
        data = run_nexus("info")
        assert data["command"] == "info"

    def test_format_json_explicit(self):
        data = run_nexus("--format", "json", "info")
        assert data["command"] == "info"

    def test_format_compact_describe(self):
        result = subprocess.run(
            [PYTHON, "-m", "nexus", "--format", "compact", "describe"],
            capture_output=True, text=True, timeout=15, cwd=NEXUS_ROOT, encoding="utf-8",
        )
        assert result.returncode == 0
        output = result.stdout.strip()
        # Compact output should NOT be valid JSON
        assert output.startswith("#")
        assert "elements)" in output

    def test_format_compact_windows(self):
        result = subprocess.run(
            [PYTHON, "-m", "nexus", "--format", "compact", "windows"],
            capture_output=True, text=True, timeout=15, cwd=NEXUS_ROOT, encoding="utf-8",
        )
        assert result.returncode == 0
        assert "[Win]" in result.stdout

    def test_format_minimal_describe(self):
        result = subprocess.run(
            [PYTHON, "-m", "nexus", "--format", "minimal", "describe"],
            capture_output=True, text=True, timeout=15, cwd=NEXUS_ROOT, encoding="utf-8",
        )
        assert result.returncode == 0
        output = result.stdout.strip()
        assert output.startswith("#")

    def test_format_compact_action_falls_back_to_json(self):
        """Action commands (screenshot, click etc) fall back to JSON in compact mode."""
        data = run_nexus("--format", "compact", "info")
        # info is an action command → compact returns empty → falls back to JSON
        assert data["command"] == "info"
