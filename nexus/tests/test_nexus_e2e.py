"""E2E + unit tests for Nexus.

CLI tests validate JSON output via subprocess.
Direct tests import functions and call them, validating return dicts.

Usage:
    pytest nexus/tests/ -v                      # Core tests only (safe)
    pytest nexus/tests/ -v -m web               # Web tests (needs Chrome CDP)
    pytest nexus/tests/ -v -m action            # Action tests (moves mouse)
    pytest nexus/tests/ -v -m "not action"      # Everything except mouse/keyboard
"""

import json
import os
import subprocess

import pytest

from nexus.tests.conftest import run_nexus, PYTHON, NEXUS_ROOT


# ═══════════════════════════════════════════════════════════════════════════
# OCULUS — UIA Awareness Tests (always work on Windows)
# ═══════════════════════════════════════════════════════════════════════════

class TestInfo:
    def test_returns_screen_dimensions(self):
        data = run_nexus("info")
        assert data["command"] == "info"
        assert data["screen"]["width"] >= 800
        assert data["screen"]["height"] >= 600

    def test_returns_cursor_position(self):
        data = run_nexus("info")
        assert isinstance(data["cursor"]["x"], int)
        assert isinstance(data["cursor"]["y"], int)

    def test_direct_call(self):
        from nexus.digitus.input import info
        result = info()
        assert result["command"] == "info"
        assert result["screen"]["width"] >= 800


class TestWindows:
    def test_lists_windows(self):
        data = run_nexus("windows")
        assert data["command"] == "windows"
        assert data["count"] > 0

    def test_window_fields(self):
        data = run_nexus("windows")
        for win in data["windows"]:
            assert "title" in win
            assert "type" in win
            assert "is_visible" in win
            assert "is_foreground" in win

    def test_visible_windows_have_bounds(self):
        data = run_nexus("windows")
        for win in data["windows"]:
            if win["is_visible"]:
                assert win["bounds"] is not None
                assert win["bounds"]["width"] > 0

    def test_direct_call(self):
        from nexus.oculus.uia import windows
        result = windows()
        assert result["command"] == "windows"
        assert result["count"] > 0


class TestDescribe:
    def test_describes_active_window(self):
        data = run_nexus("describe")
        assert data["command"] == "describe"
        assert "title" in data["window"]
        assert isinstance(data["elements"], list)
        assert data["element_count"] == len(data["elements"])

    def test_has_cursor_and_focus(self):
        data = run_nexus("describe")
        assert "x" in data["cursor"]
        assert "focused_element" in data

    def test_elements_have_structure(self):
        data = run_nexus("describe")
        for elem in data["elements"]:
            assert "name" in elem
            assert "type" in elem
            assert "bounds" in elem
            assert "is_visible" in elem

    def test_direct_call(self):
        from nexus.oculus.uia import describe
        result = describe()
        assert result["command"] == "describe"
        assert "window" in result


class TestFocused:
    def test_returns_focused_element(self):
        data = run_nexus("focused")
        assert data["command"] == "focused"
        assert "element" in data
        assert isinstance(data["parent_chain"], list)

    def test_focused_element_fields(self):
        data = run_nexus("focused")
        if data["element"]:
            assert "name" in data["element"]
            assert "type" in data["element"]
            assert "bounds" in data["element"]

    def test_direct_call(self):
        from nexus.oculus.uia import focused
        result = focused()
        assert result["command"] == "focused"


class TestFind:
    def test_find_nonexistent(self):
        data = run_nexus("find", "xyzzy_nonexistent_9999")
        assert data["count"] == 0
        assert data["matches"] == []

    def test_find_returns_structure(self):
        data = run_nexus("find", "Close")
        assert data["command"] == "find"
        assert "window" in data
        for match in data["matches"]:
            assert "name" in match
            assert "bounds" in match
            assert match["is_visible"] is True

    def test_find_special_chars(self):
        data = run_nexus("find", "!@#$%^&*()")
        assert data["command"] == "find"
        assert data["count"] == 0

    def test_find_unicode(self):
        data = run_nexus("find", "\u00e9\u00e8\u00ea")
        assert data["command"] == "find"

    def test_direct_call(self):
        from nexus.oculus.uia import find
        result = find("xyzzy_nonexistent_9999")
        assert result["command"] == "find"
        assert result["count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# DIGITUS — Input & System Tests (always work on Windows)
# ═══════════════════════════════════════════════════════════════════════════

class TestScreenshot:
    def test_creates_file(self):
        data = run_nexus("screenshot")
        assert data["command"] == "screenshot"
        assert os.path.isfile(data["path"])
        assert data["path"].endswith(".png")
        with open(data["path"], "rb") as f:
            assert f.read(4) == b"\x89PNG"
        os.remove(data["path"])

    def test_file_has_content(self):
        data = run_nexus("screenshot")
        assert os.path.getsize(data["path"]) > 1000
        os.remove(data["path"])

    def test_region_capture(self):
        data = run_nexus("screenshot", "--region", "0,0,200,200")
        assert os.path.isfile(data["path"])
        os.remove(data["path"])

    def test_direct_call(self):
        from nexus.digitus.input import screenshot
        result = screenshot()
        assert result["command"] == "screenshot"
        assert os.path.isfile(result["path"])
        os.remove(result["path"])


class TestPsRun:
    def test_simple_command(self):
        data = run_nexus("ps-run", "Get-Date -Format yyyy")
        assert data["command"] == "ps-run"
        assert data["success"] is True
        assert len(str(data["data"])) > 0

    def test_json_output(self):
        data = run_nexus("ps-run", "Get-Process | Select-Object -First 2 Name,Id | ConvertTo-Json")
        assert data["success"] is True
        assert isinstance(data["data"], (list, dict))

    def test_bad_command(self):
        data = run_nexus("ps-run", "Get-NonExistentCmdlet12345")
        assert data["command"] == "ps-run"
        assert data["success"] is False

    def test_direct_call(self):
        from nexus.digitus.system import ps_run
        result = ps_run("Get-Date -Format yyyy")
        assert result["command"] == "ps-run"
        assert result["success"] is True


class TestComShell:
    def test_lists_home_directory(self):
        data = run_nexus("com-shell")
        assert data["command"] == "com-shell"
        assert data["success"] is True
        assert data["count"] > 0

    def test_item_fields(self):
        data = run_nexus("com-shell")
        item = data["items"][0]
        assert "name" in item
        assert "path" in item
        assert "type" in item
        assert "is_folder" in item

    def test_bad_path(self):
        data = run_nexus("com-shell", "--path", "Z:\\nonexistent\\path\\12345")
        assert data["success"] is False

    def test_direct_call(self):
        from nexus.digitus.system import com_shell
        result = com_shell()
        assert result["command"] == "com-shell"
        assert result["success"] is True


# ═══════════════════════════════════════════════════════════════════════════
# OCULUS — Web Awareness Tests (need Chrome CDP)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.web
class TestWebDescribe:
    def test_page_info(self):
        data = run_nexus("web-describe")
        assert data["command"] == "web-describe"
        assert "title" in data
        assert "url" in data

    def test_structure_lists(self):
        data = run_nexus("web-describe")
        assert isinstance(data["headings"], list)
        assert isinstance(data["links"], list)
        assert isinstance(data["inputs"], list)
        assert isinstance(data["buttons"], list)
        assert data["link_count"] == len(data["links"])


@pytest.mark.web
class TestWebText:
    def test_extracts_text(self):
        data = run_nexus("web-text")
        assert data["command"] == "web-text"
        assert "text" in data
        assert isinstance(data["truncated"], bool)


@pytest.mark.web
class TestWebFind:
    def test_find_common_text(self):
        data = run_nexus("web-find", "a")
        assert data["command"] == "web-find"
        assert isinstance(data["matches"], list)

    def test_find_nonexistent(self):
        data = run_nexus("web-find", "xyzzy_impossible_999")
        assert data["count"] == 0


@pytest.mark.web
class TestWebLinks:
    def test_lists_links(self):
        data = run_nexus("web-links")
        assert data["command"] == "web-links"
        assert isinstance(data["links"], list)
        for link in data["links"]:
            assert "text" in link
            assert "href" in link


@pytest.mark.web
class TestWebTabs:
    def test_at_least_one_tab(self):
        data = run_nexus("web-tabs")
        assert data["count"] >= 1
        tab = data["tabs"][0]
        assert "title" in tab
        assert "url" in tab
        assert "is_active" in tab


@pytest.mark.web
class TestWebAx:
    def test_returns_accessibility_tree(self):
        data = run_nexus("web-ax")
        assert data["command"] == "web-ax"
        assert isinstance(data["nodes"], list)
        if data["count"] > 0:
            node = data["nodes"][0]
            assert "role" in node
            assert "name" in node


@pytest.mark.web
class TestWebMeasure:
    def test_measures_body(self):
        data = run_nexus("web-measure", "body")
        assert data["command"] == "web-measure"
        el = data["elements"][0]
        assert el["selector"] == "body"
        assert el["width"] > 0
        assert el["height"] > 0
        assert isinstance(el["padding"], list)
        assert isinstance(el["margin"], list)

    def test_not_found_selector(self):
        data = run_nexus("web-measure", "#nonexistent_12345")
        assert data["elements"][0].get("error") == "not found"


@pytest.mark.web
class TestWebMarkdown:
    def test_extracts_content(self):
        data = run_nexus("web-markdown")
        assert data["command"] == "web-markdown"
        assert "url" in data
        assert "content" in data


# ═══════════════════════════════════════════════════════════════════════════
# DIGITUS — Action Tests (move mouse/keyboard)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.action
class TestMove:
    def test_moves_cursor(self, save_cursor):
        run_nexus("move", "300", "300")
        info = run_nexus("info")
        assert abs(info["cursor"]["x"] - 300) <= 2
        assert abs(info["cursor"]["y"] - 300) <= 2


@pytest.mark.action
class TestScroll:
    def test_scroll_up(self):
        data = run_nexus("scroll", "3")
        assert data["direction"] == "up"

    def test_scroll_down(self):
        data = run_nexus("scroll", "-3")
        assert data["direction"] == "down"


@pytest.mark.action
class TestKey:
    def test_press_escape(self):
        data = run_nexus("key", "escape")
        assert data["command"] == "key"
        assert data["keys"] == "escape"


@pytest.mark.action
class TestClick:
    def test_click_returns_success(self, save_cursor):
        data = run_nexus("click", "500", "500")
        assert data["button"] == "left"
        assert data["double"] is False


# ═══════════════════════════════════════════════════════════════════════════
# ROBUSTNESS
# ═══════════════════════════════════════════════════════════════════════════

class TestRobustness:
    def test_unknown_command_fails(self):
        result = subprocess.run(
            [PYTHON, "-m", "nexus", "nonexistent-command"],
            capture_output=True, text=True, timeout=10, cwd=NEXUS_ROOT, encoding="utf-8",
        )
        assert result.returncode != 0

    def test_all_commands_output_valid_json(self):
        for cmd in ["info", "windows", "describe", "focused"]:
            result = subprocess.run(
                [PYTHON, "-m", "nexus", cmd],
                capture_output=True, text=True, timeout=15, cwd=NEXUS_ROOT, encoding="utf-8",
            )
            assert result.returncode == 0
            parsed = json.loads(result.stdout)
            assert "command" in parsed

    def test_timeout_flag_accepted(self):
        data = run_nexus("--timeout", "10", "info")
        assert data["command"] == "info"


# ═══════════════════════════════════════════════════════════════════════════
# UIA HELPERS — Direct unit tests
# ═══════════════════════════════════════════════════════════════════════════

class TestUiaHelpers:
    def test_rect_to_dict(self):
        from nexus.uia import rect_to_dict

        class FakeRect:
            left = 10
            top = 20
            right = 110
            bottom = 70

        result = rect_to_dict(FakeRect())
        assert result["width"] == 100
        assert result["height"] == 50
        assert result["center_x"] == 60
        assert result["center_y"] == 45

    def test_collect_named_elements_returns_list(self):
        import uiautomation as auto
        from nexus.uia import collect_named_elements
        win = auto.GetForegroundControl()
        elements = collect_named_elements(win, max_depth=2, max_elements=5)
        assert isinstance(elements, list)
        for el in elements:
            assert "name" in el
            assert "bounds" in el

    def test_find_elements_no_match(self):
        import uiautomation as auto
        from nexus.uia import find_elements
        win = auto.GetForegroundControl()
        results = find_elements(win, "xyzzy_impossible_99999")
        assert results == []
