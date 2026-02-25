"""Tests for nexus.act.intents — type, press, scroll, hover, drag, fill, wait, CDP, data."""

import sys
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, "/Users/ferran/repos/Nexus")

from nexus.act.intents import (
    _handle_type, _handle_press, _handle_scroll,
    _scroll_in_element, _scroll_until,
    _handle_hover, _handle_drag, _handle_fill,
    _handle_read_table, _handle_read_list,
    _handle_navigate, _handle_run_js,
    _handle_switch_tab, _handle_new_tab, _handle_close_tab,
)
from nexus.act.parse import KEY_ALIASES
from nexus.act.resolve import do


# ===========================================================================
# TestHandlePress
# ===========================================================================


@patch("nexus.act.intents.raw_input")
class TestHandlePress:
    """Tests for _handle_press — keyboard shortcut routing."""

    def test_single_key_return(self, mock_raw_input):
        result = _handle_press("return")
        mock_raw_input.press.assert_called_once_with("return")
        assert result["keys"] == ["return"]

    def test_single_key_enter_alias(self, mock_raw_input):
        result = _handle_press("enter")
        mock_raw_input.press.assert_called_once_with("return")
        assert result["keys"] == ["return"]

    def test_single_key_esc(self, mock_raw_input):
        _handle_press("esc")
        mock_raw_input.press.assert_called_once_with("escape")

    def test_single_key_tab(self, mock_raw_input):
        _handle_press("tab")
        mock_raw_input.press.assert_called_once_with("tab")

    def test_single_key_space(self, mock_raw_input):
        _handle_press("space")
        mock_raw_input.press.assert_called_once_with("space")

    def test_single_key_delete(self, mock_raw_input):
        _handle_press("delete")
        mock_raw_input.press.assert_called_once_with("delete")

    def test_single_key_backspace_alias(self, mock_raw_input):
        _handle_press("backspace")
        mock_raw_input.press.assert_called_once_with("delete")

    def test_combo_cmd_plus_s(self, mock_raw_input):
        result = _handle_press("cmd+s")
        mock_raw_input.hotkey.assert_called_once_with("command", "s")
        assert result["keys"] == ["command", "s"]

    def test_combo_ctrl_plus_c(self, mock_raw_input):
        _handle_press("ctrl+c")
        mock_raw_input.hotkey.assert_called_once_with("control", "c")

    def test_combo_alt_plus_f4(self, mock_raw_input):
        _handle_press("alt+f4")
        mock_raw_input.hotkey.assert_called_once_with("option", "f4")

    def test_combo_cmd_shift_p(self, mock_raw_input):
        _handle_press("cmd+shift+p")
        mock_raw_input.hotkey.assert_called_once_with("command", "shift", "p")

    def test_combo_with_spaces(self, mock_raw_input):
        # "cmd s" — space-separated also works (split on + or space)
        _handle_press("cmd s")
        mock_raw_input.hotkey.assert_called_once_with("command", "s")

    def test_function_key(self, mock_raw_input):
        _handle_press("f12")
        mock_raw_input.press.assert_called_once_with("f12")

    def test_arrow_key(self, mock_raw_input):
        _handle_press("up")
        mock_raw_input.press.assert_called_once_with("up")

    def test_empty_keys(self, mock_raw_input):
        result = _handle_press("")
        assert result["ok"] is False
        assert "No key specified" in result["error"]

    def test_unknown_key_passed_through(self, mock_raw_input):
        # Unknown keys are passed through as-is (lowercased)
        _handle_press("volumeup")
        mock_raw_input.press.assert_called_once_with("volumeup")

    def test_case_insensitive(self, mock_raw_input):
        _handle_press("CMD+S")
        mock_raw_input.hotkey.assert_called_once_with("command", "s")


# ===========================================================================
# TestHandleScroll
# ===========================================================================


@patch("nexus.act.intents.raw_input")
class TestHandleScroll:
    """Tests for _handle_scroll — scroll direction and amount."""

    def test_scroll_down_default(self, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        _handle_scroll("down")
        mock_raw_input.scroll.assert_called_once_with(-3)

    def test_scroll_up_default(self, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        _handle_scroll("up")
        mock_raw_input.scroll.assert_called_once_with(3)

    def test_scroll_down_with_amount(self, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        _handle_scroll("down 5")
        mock_raw_input.scroll.assert_called_once_with(-5)

    def test_scroll_up_with_amount(self, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        _handle_scroll("up 10")
        mock_raw_input.scroll.assert_called_once_with(10)

    def test_scroll_down_alias_d(self, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        _handle_scroll("d")
        mock_raw_input.scroll.assert_called_once_with(-3)

    def test_scroll_up_alias_u(self, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        _handle_scroll("u")
        mock_raw_input.scroll.assert_called_once_with(3)

    def test_scroll_left(self, mock_raw_input):
        result = _handle_scroll("left")
        assert result["action"] == "scroll_left"

    def test_scroll_right(self, mock_raw_input):
        result = _handle_scroll("right")
        assert result["action"] == "scroll_right"

    def test_scroll_left_alias(self, mock_raw_input):
        result = _handle_scroll("l")
        assert result["action"] == "scroll_left"

    def test_scroll_right_alias(self, mock_raw_input):
        result = _handle_scroll("r")
        assert result["action"] == "scroll_right"

    def test_scroll_unknown_defaults_down(self, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        _handle_scroll("blah")
        mock_raw_input.scroll.assert_called_once_with(-3)

    def test_scroll_down_1(self, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        _handle_scroll("down 1")
        mock_raw_input.scroll.assert_called_once_with(-1)


# ===========================================================================
# TestHandleDrag
# ===========================================================================


@patch("nexus.act.intents.raw_input")
class TestHandleDrag:
    """Tests for _handle_drag — coordinate-based drag."""

    def test_valid_drag_comma(self, mock_raw_input):
        mock_raw_input.drag.return_value = {"ok": True}
        result = _handle_drag("100,200 to 300,400")
        mock_raw_input.drag.assert_called_once_with(100, 200, 300, 400)

    def test_valid_drag_space(self, mock_raw_input):
        mock_raw_input.drag.return_value = {"ok": True}
        result = _handle_drag("100 200 to 300 400")
        mock_raw_input.drag.assert_called_once_with(100, 200, 300, 400)

    def test_invalid_drag_no_to(self, mock_raw_input):
        result = _handle_drag("100,200 300,400")
        assert result["ok"] is False
        assert "Drag format" in result["error"]

    def test_invalid_drag_missing_coords(self, mock_raw_input):
        # "100 to 300" is now treated as element-based drag: drag "100" to "300"
        # Elements won't be found (mocked), so it returns source not found
        result = _handle_drag("100 to 300")
        assert result["ok"] is False

    def test_invalid_drag_text(self, mock_raw_input):
        result = _handle_drag("from here to there")
        assert result["ok"] is False

    def test_invalid_drag_empty(self, mock_raw_input):
        result = _handle_drag("")
        assert result["ok"] is False

    def test_valid_drag_large_coords(self, mock_raw_input):
        mock_raw_input.drag.return_value = {"ok": True}
        _handle_drag("0,0 to 1920,1080")
        mock_raw_input.drag.assert_called_once_with(0, 0, 1920, 1080)


# ===========================================================================
# TestHandleType
# ===========================================================================


@patch("nexus.act.intents.raw_input")
@patch("nexus.act.intents.native")
class TestHandleType:
    """Tests for _handle_type — type text, optionally into a target field."""

    def test_type_simple_text(self, mock_native, mock_raw_input):
        result = _handle_type("hello")
        mock_raw_input.type_text.assert_called_once_with("hello")
        assert result["ok"] is True
        assert result["text"] == "hello"

    def test_type_quoted_text(self, mock_native, mock_raw_input):
        result = _handle_type('"hello world"')
        mock_raw_input.type_text.assert_called_once_with("hello world")
        assert result["text"] == "hello world"

    def test_type_single_quoted(self, mock_native, mock_raw_input):
        result = _handle_type("'hello world'")
        mock_raw_input.type_text.assert_called_once_with("hello world")
        assert result["text"] == "hello world"

    def test_type_in_target(self, mock_native, mock_raw_input):
        mock_native.set_value.return_value = {"ok": True}
        _handle_type("hello in search")
        mock_native.set_value.assert_called_once_with("search", "hello", pid=None)

    def test_type_quoted_in_target(self, mock_native, mock_raw_input):
        mock_native.set_value.return_value = {"ok": True}
        _handle_type('"hello world" in search')
        mock_native.set_value.assert_called_once_with("search", "hello world", pid=None)

    def test_type_in_target_with_pid(self, mock_native, mock_raw_input):
        mock_native.set_value.return_value = {"ok": True}
        _handle_type("hello in search", pid=555)
        mock_native.set_value.assert_called_once_with("search", "hello", pid=555)

    def test_type_empty_returns_error(self, mock_native, mock_raw_input):
        result = _handle_type("")
        assert result["ok"] is False
        assert "Nothing to type" in result["error"]

    def test_type_multiword(self, mock_native, mock_raw_input):
        result = _handle_type("hello world")
        # "hello world" contains "in" nowhere, so it's treated as simple type
        # Actually wait — let's check if the regex matches "hello world" with "in"
        # re.match(r"(.+?)\s+in\s+(.+)$", "hello world") — no "in" so no match
        mock_raw_input.type_text.assert_called_once_with("hello world")


# ===========================================================================
# TestKeyAliases
# ===========================================================================


class TestKeyAliases:
    """Tests that KEY_ALIASES maps are correct and complete."""

    def test_cmd_aliases(self):
        assert KEY_ALIASES["cmd"] == "command"
        assert KEY_ALIASES["command"] == "command"

    def test_ctrl_aliases(self):
        assert KEY_ALIASES["ctrl"] == "control"
        assert KEY_ALIASES["control"] == "control"

    def test_alt_option_aliases(self):
        assert KEY_ALIASES["alt"] == "option"
        assert KEY_ALIASES["opt"] == "option"
        assert KEY_ALIASES["option"] == "option"

    def test_enter_return_aliases(self):
        assert KEY_ALIASES["enter"] == "return"
        assert KEY_ALIASES["return"] == "return"

    def test_esc_alias(self):
        assert KEY_ALIASES["esc"] == "escape"
        assert KEY_ALIASES["escape"] == "escape"

    def test_backspace_alias(self):
        assert KEY_ALIASES["backspace"] == "delete"
        assert KEY_ALIASES["delete"] == "delete"

    def test_arrow_keys(self):
        assert KEY_ALIASES["up"] == "up"
        assert KEY_ALIASES["down"] == "down"
        assert KEY_ALIASES["left"] == "left"
        assert KEY_ALIASES["right"] == "right"

    def test_function_keys(self):
        for i in range(1, 13):
            key = f"f{i}"
            assert KEY_ALIASES[key] == key


# ===========================================================================
# TestNavigateUrlHandling
# ===========================================================================


class TestNavigateUrlHandling:
    """Tests for _handle_navigate — URL normalization."""

    @patch("nexus.act.intents.native")
    def test_strips_to_prefix(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.intents import _handle_navigate
        _handle_navigate("to google.com")
        # Should call with https://google.com
        mock_native.run_applescript.assert_called_once()
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://google.com" in call_arg

    @patch("nexus.act.intents.native")
    def test_adds_https_scheme(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.intents import _handle_navigate
        _handle_navigate("example.com")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://example.com" in call_arg

    @patch("nexus.act.intents.native")
    def test_preserves_http_scheme(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.intents import _handle_navigate
        _handle_navigate("http://example.com")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "http://example.com" in call_arg
        assert "https://http://" not in call_arg

    @patch("nexus.act.intents.native")
    def test_preserves_https_scheme(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.intents import _handle_navigate
        _handle_navigate("https://example.com")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://example.com" in call_arg

    def test_empty_url_returns_error(self):
        from nexus.act.intents import _handle_navigate
        result = _handle_navigate("")
        assert result["ok"] is False
        assert "No URL" in result["error"]

    @patch("nexus.act.intents.native")
    def test_just_to_becomes_url(self, mock_native):
        # "to " stripped → "to" (doesn't match "to " prefix), treated as URL "https://to"
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.intents import _handle_navigate
        result = _handle_navigate("to ")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://to" in call_arg

    @patch("nexus.act.intents.native")
    def test_strips_quotes_from_url(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.intents import _handle_navigate
        _handle_navigate('"google.com"')
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://google.com" in call_arg

    @patch("nexus.act.intents.native")
    def test_file_scheme_preserved(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.intents import _handle_navigate
        _handle_navigate("file:///Users/ferran/index.html")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "file:///Users/ferran/index.html" in call_arg


# ===========================================================================
# TestRunJs
# ===========================================================================


class TestRunJs:
    """Tests for _handle_run_js — JavaScript execution."""

    def test_empty_expression(self):
        from nexus.act.intents import _handle_run_js
        result = _handle_run_js("")
        assert result["ok"] is False
        assert "No JavaScript" in result["error"]

    def test_whitespace_only(self):
        from nexus.act.intents import _handle_run_js
        result = _handle_run_js("   ")
        assert result["ok"] is False
        assert "No JavaScript" in result["error"]


# ===========================================================================
# TestTabManagement — CDP tab management intents
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestTabManagement:
    """Tests for tab management intents via do()."""

    @patch("nexus.act.resolve._handle_switch_tab")
    def test_switch_tab_number(self, mock_switch, mock_native, mock_raw):
        mock_switch.return_value = {"ok": True}
        do("switch tab 2")
        mock_switch.assert_called_once_with("2")

    @patch("nexus.act.resolve._handle_switch_tab")
    def test_switch_to_tab_name(self, mock_switch, mock_native, mock_raw):
        mock_switch.return_value = {"ok": True}
        do("switch to tab Google")
        mock_switch.assert_called_once_with("Google")

    @patch("nexus.act.resolve._handle_new_tab")
    def test_new_tab_empty(self, mock_new, mock_native, mock_raw):
        mock_new.return_value = {"ok": True}
        do("new tab")
        mock_new.assert_called_once_with("")

    @patch("nexus.act.resolve._handle_new_tab")
    def test_new_tab_with_url(self, mock_new, mock_native, mock_raw):
        mock_new.return_value = {"ok": True}
        do("new tab google.com")
        mock_new.assert_called_once_with("google.com")

    @patch("nexus.act.resolve._handle_close_tab")
    def test_close_tab_current(self, mock_close, mock_native, mock_raw):
        mock_close.return_value = {"ok": True}
        do("close tab")
        mock_close.assert_called_once_with("")

    @patch("nexus.act.resolve._handle_close_tab")
    def test_close_tab_number(self, mock_close, mock_native, mock_raw):
        mock_close.return_value = {"ok": True}
        do("close tab 3")
        mock_close.assert_called_once_with("3")

    @patch("nexus.act.resolve._handle_close_tab")
    def test_close_tab_by_name(self, mock_close, mock_native, mock_raw):
        mock_close.return_value = {"ok": True}
        do("close tab Google")
        mock_close.assert_called_once_with("Google")


# ===========================================================================
# TestScrollTargeting
# ===========================================================================


@patch("nexus.act.intents.raw_input")
class TestScrollTargeting:
    """Tests for scroll-in-element and scroll-until patterns."""

    def test_scroll_down_in_element(self, mock_raw):
        """'scroll down in file list' scrolls at element center."""
        mock_raw.scroll.return_value = {"ok": True}
        with patch("nexus.sense.access.find_elements") as mock_find:
            mock_find.return_value = [
                {"label": "file list", "pos": (100, 200), "size": (300, 400)}
            ]
            result = _handle_scroll("down in file list")
            mock_raw.scroll.assert_called_once_with(-3, x=250, y=400)

    def test_scroll_up_5_in_element(self, mock_raw):
        mock_raw.scroll.return_value = {"ok": True}
        with patch("nexus.sense.access.find_elements") as mock_find:
            mock_find.return_value = [
                {"label": "sidebar", "pos": (0, 0), "size": (200, 600)}
            ]
            result = _handle_scroll("up 5 in sidebar")
            mock_raw.scroll.assert_called_once_with(5, x=100, y=300)

    def test_scroll_in_element_not_found(self, mock_raw):
        with patch("nexus.sense.access.find_elements") as mock_find:
            mock_find.return_value = []
            result = _handle_scroll("down in nonexistent")
            assert result["ok"] is False
            assert "not found" in result["error"]

    def test_scroll_until_found_immediately(self, mock_raw):
        """If element is already visible, no scrolling needed."""
        mock_raw.scroll.return_value = {"ok": True}
        with patch("nexus.sense.access.find_elements") as mock_find:
            mock_find.return_value = [
                {"label": "Save", "role": "button", "pos": (100, 200), "size": (80, 30)}
            ]
            result = _handle_scroll("until Save appears")
            assert result["ok"] is True
            assert result["action"] == "scroll_until"
            assert result["scrolls"] == 0
            mock_raw.scroll.assert_not_called()

    def test_scroll_until_found_after_scrolls(self, mock_raw):
        mock_raw.scroll.return_value = {"ok": True}
        call_count = [0]
        def mock_find_fn(target, pid=None):
            call_count[0] += 1
            if call_count[0] >= 3:
                return [{"label": "Submit", "role": "button", "pos": (100, 200), "size": (80, 30)}]
            return []
        with patch("nexus.sense.access.find_elements", side_effect=mock_find_fn):
            with patch("time.sleep"):
                result = _handle_scroll("until Submit")
                assert result["ok"] is True
                assert result["scrolls"] == 2
                assert mock_raw.scroll.call_count == 2

    def test_scroll_until_timeout(self, mock_raw):
        mock_raw.scroll.return_value = {"ok": True}
        with patch("nexus.sense.access.find_elements") as mock_find:
            mock_find.return_value = []
            with patch("time.sleep"):
                result = _handle_scroll("until NonExistent")
                assert result["ok"] is False
                assert "not found after" in result["error"]

    def test_scroll_until_with_appears_suffix(self, mock_raw):
        """'scroll until Save appears' should work same as 'scroll until Save'."""
        mock_raw.scroll.return_value = {"ok": True}
        with patch("nexus.sense.access.find_elements") as mock_find:
            mock_find.return_value = [
                {"label": "Save", "role": "button", "pos": (10, 20), "size": (50, 30)}
            ]
            result = _handle_scroll("until Save appears")
            assert result["ok"] is True

    def test_scroll_down_still_works(self, mock_raw):
        """Normal scroll still works after adding new patterns."""
        mock_raw.scroll.return_value = {"ok": True}
        _handle_scroll("down")
        mock_raw.scroll.assert_called_once_with(-3)

    def test_scroll_up_10_still_works(self, mock_raw):
        mock_raw.scroll.return_value = {"ok": True}
        _handle_scroll("up 10")
        mock_raw.scroll.assert_called_once_with(10)

    def test_do_scroll_until_routing(self, mock_raw):
        """do('scroll until Save') routes correctly."""
        mock_raw.scroll.return_value = {"ok": True}
        with patch("nexus.sense.access.find_elements") as mock_find:
            mock_find.return_value = [
                {"label": "Save", "role": "button", "pos": (10, 20), "size": (50, 30)}
            ]
            result = do("scroll until Save")
            assert result["ok"] is True

    def test_do_scroll_down_in_routing(self, mock_raw):
        """do('scroll down in sidebar') routes correctly."""
        mock_raw.scroll.return_value = {"ok": True}
        with patch("nexus.sense.access.find_elements") as mock_find:
            mock_find.return_value = [
                {"label": "sidebar", "pos": (0, 0), "size": (200, 600)}
            ]
            result = do("scroll down in sidebar")
            assert result["ok"] is True


# ===========================================================================
# TestElementDrag — drag <element> to <element>
# ===========================================================================


class TestElementDrag:
    """Tests for element-based drag — 'drag X to Y'."""

    @patch("nexus.act.intents.raw_input")
    def test_coordinate_drag(self, mock_input):
        mock_input.drag.return_value = {"ok": True, "action": "drag"}
        result = _handle_drag("100,200 to 300,400")
        mock_input.drag.assert_called_once_with(100, 200, 300, 400)
        assert result["ok"] is True

    @patch("nexus.act.intents.raw_input")
    @patch("nexus.sense.access.find_elements")
    def test_element_drag(self, mock_find, mock_input):
        def find_side_effect(name, pid=None):
            if "file" in name.lower():
                return [{"label": "file.txt", "pos": (50, 100), "size": (80, 20)}]
            if "trash" in name.lower():
                return [{"label": "Trash", "pos": (400, 500), "size": (60, 60)}]
            return []
        mock_find.side_effect = find_side_effect
        mock_input.drag.return_value = {"ok": True}
        result = _handle_drag("file.txt to Trash")
        mock_input.drag.assert_called_once_with(90, 110, 430, 530)
        assert result["ok"] is True
        assert result["from_element"] == "file.txt"
        assert result["to_element"] == "Trash"

    @patch("nexus.sense.access.find_elements")
    def test_element_drag_source_not_found(self, mock_find):
        mock_find.return_value = []
        result = _handle_drag("missing to Trash")
        assert result["ok"] is False
        assert "source" in result["error"].lower()

    @patch("nexus.sense.access.find_elements")
    def test_element_drag_target_not_found(self, mock_find):
        def find_side_effect(name, pid=None):
            if "file" in name.lower():
                return [{"label": "file.txt", "pos": (50, 100), "size": (80, 20)}]
            return []
        mock_find.side_effect = find_side_effect
        result = _handle_drag("file.txt to missing")
        assert result["ok"] is False
        assert "target" in result["error"].lower()

    def test_drag_bad_format(self):
        result = _handle_drag("something random")
        assert result["ok"] is False
        assert "format" in result["error"].lower()

    @patch("nexus.act.intents.raw_input")
    def test_drag_via_do(self, mock_input):
        mock_input.drag.return_value = {"ok": True, "action": "drag"}
        result = do("drag 10,20 to 30,40")
        mock_input.drag.assert_called_once_with(10, 20, 30, 40)


# ===========================================================================
# TestDragAbsolute
# ===========================================================================


class TestDragAbsolute:
    """Tests that drag uses absolute coordinates (mouseDown/moveTo/mouseUp)."""

    @patch("pyautogui.mouseUp")
    @patch("pyautogui.moveTo")
    @patch("pyautogui.mouseDown")
    def test_drag_uses_absolute_positioning(self, mock_down, mock_move, mock_up):
        from nexus.act.input import drag
        result = drag(100, 200, 300, 400, duration=0.5)
        # First moveTo positions mouse at start
        assert mock_move.call_count == 2
        mock_move.assert_any_call(100, 200)
        mock_move.assert_any_call(300, 400, duration=0.5)
        mock_down.assert_called_once()
        mock_up.assert_called_once()
        assert result["ok"] is True
        assert result["from"] == [100, 200]
        assert result["to"] == [300, 400]


# ===========================================================================
# TestReadTable — structured table extraction
# ===========================================================================


class TestReadTable:
    """Tests for read table getter intent."""

    @patch("nexus.sense.access.find_tables")
    def test_read_table_no_tables(self, mock_find):
        mock_find.return_value = []
        result = _handle_read_table()
        assert result["ok"] is True
        assert "No tables" in result["text"]

    @patch("nexus.sense.access.find_tables")
    def test_read_table_with_data(self, mock_find):
        mock_find.return_value = [{
            "title": "Users",
            "headers": ["Name", "Email"],
            "rows": [["Alice", "alice@x.com"], ["Bob", "bob@x.com"]],
            "num_rows": 2,
            "num_cols": 2,
        }]
        result = _handle_read_table()
        assert result["ok"] is True
        assert "Users" in result["text"]
        assert "Alice" in result["text"]
        assert "Bob" in result["text"]

    @patch("nexus.sense.access.find_tables")
    def test_read_table_via_do(self, mock_find):
        mock_find.return_value = []
        result = do("read table")
        assert result["ok"] is True

    @patch("nexus.sense.access.find_tables")
    def test_get_table_via_do(self, mock_find):
        mock_find.return_value = []
        result = do("get table")
        assert result["ok"] is True


# ===========================================================================
# TestReadList — structured list extraction
# ===========================================================================


class TestReadList:
    """Tests for read list getter intent."""

    @patch("nexus.sense.access.find_lists")
    def test_read_list_no_lists(self, mock_find):
        mock_find.return_value = []
        result = _handle_read_list()
        assert result["ok"] is True
        assert "No lists" in result["text"]

    @patch("nexus.sense.access.find_lists")
    def test_read_list_with_items(self, mock_find):
        mock_find.return_value = [{
            "title": "Files",
            "type": "list",
            "items": [
                {"index": 0, "label": "document.pdf"},
                {"index": 1, "label": "photo.jpg"},
                {"index": 2, "label": "notes.txt", "selected": True},
            ],
            "count": 3,
        }]
        result = _handle_read_list()
        assert result["ok"] is True
        assert "Files" in result["text"]
        assert "document.pdf" in result["text"]
        assert "selected" in result["text"]

    @patch("nexus.sense.access.find_lists")
    def test_read_list_via_do(self, mock_find):
        mock_find.return_value = []
        result = do("read list")
        assert result["ok"] is True

    @patch("nexus.sense.access.find_lists")
    def test_get_list_via_do(self, mock_find):
        mock_find.return_value = []
        result = do("get list")
        assert result["ok"] is True


# ===========================================================================
# TestTableFormatting — _format_table and _format_list in fusion.py
# ===========================================================================


class TestTableFormatting:
    """Tests for table/list ASCII formatting in fusion.py."""

    def test_format_table_basic(self):
        from nexus.sense.fusion import _format_table
        tbl = {
            "title": "Scores",
            "headers": ["Name", "Score"],
            "rows": [["Alice", "95"], ["Bob", "87"]],
            "num_rows": 2,
            "num_cols": 2,
        }
        text = _format_table(tbl)
        assert "Scores" in text
        assert "2 cols x 2 rows" in text
        assert "Alice" in text
        assert "Bob" in text
        assert "|" in text  # Table borders

    def test_format_table_empty(self):
        from nexus.sense.fusion import _format_table
        tbl = {
            "title": "",
            "headers": [],
            "rows": [],
            "num_rows": 0,
            "num_cols": 0,
        }
        text = _format_table(tbl)
        assert "empty" in text

    def test_format_table_truncation(self):
        from nexus.sense.fusion import _format_table
        tbl = {
            "title": "Big",
            "headers": ["ID"],
            "rows": [[str(i)] for i in range(25)],
            "num_rows": 25,
            "num_cols": 1,
        }
        text = _format_table(tbl)
        assert "5 more rows" in text

    def test_format_list_basic(self):
        from nexus.sense.fusion import _format_list
        lst = {
            "title": "Recent",
            "type": "list",
            "items": [
                {"index": 0, "label": "item1"},
                {"index": 1, "label": "item2"},
            ],
            "count": 2,
        }
        text = _format_list(lst)
        assert "Recent" in text
        assert "2 items" in text
        assert "1. item1" in text
        assert "2. item2" in text

    def test_format_list_selected_items(self):
        from nexus.sense.fusion import _format_list
        lst = {
            "title": "",
            "type": "list",
            "items": [
                {"index": 0, "label": "a", "selected": True},
                {"index": 1, "label": "b"},
            ],
            "count": 2,
        }
        text = _format_list(lst)
        assert "*selected*" in text

    def test_format_list_outline_type(self):
        from nexus.sense.fusion import _format_list
        lst = {
            "title": "Tree",
            "type": "outline",
            "items": [{"index": 0, "label": "root"}],
            "count": 1,
        }
        text = _format_list(lst)
        assert "Outline" in text


# ===========================================================================
# TestAccessTableList — table/list parsing in access.py
# ===========================================================================


class TestAccessTableList:
    """Tests for read_table and read_list in access.py with mocked AX elements."""

    @patch("nexus.sense.access.ax_attr")
    def test_read_table_non_table_role(self, mock_attr):
        from nexus.sense.access import read_table
        mock_attr.return_value = "AXButton"
        result = read_table(MagicMock())
        assert result is None

    @patch("nexus.sense.access.ax_attr")
    def test_read_list_non_list_role(self, mock_attr):
        from nexus.sense.access import read_list
        mock_attr.return_value = "AXButton"
        result = read_list(MagicMock())
        assert result is None

    def test_cell_text_extraction(self):
        from nexus.sense.access import _cell_text
        mock_cell = MagicMock()
        with patch("nexus.sense.access.ax_attr") as mock_attr:
            mock_attr.side_effect = lambda el, attr: {
                "AXValue": "hello",
            }.get(attr)
            text = _cell_text(mock_cell)
            assert text == "hello"

    def test_cell_text_falls_back_to_title(self):
        from nexus.sense.access import _cell_text
        mock_cell = MagicMock()
        with patch("nexus.sense.access.ax_attr") as mock_attr:
            mock_attr.side_effect = lambda el, attr: {
                "AXValue": None,
                "AXTitle": "Title Text",
            }.get(attr)
            text = _cell_text(mock_cell)
            assert text == "Title Text"


# ===========================================================================
# TestHover — hover intent (moves mouse without clicking)
# ===========================================================================


class TestHover:
    """Tests for hover intent — moves mouse without clicking."""

    @patch("nexus.act.intents.raw_input")
    def test_hover_coordinates(self, mock_input):
        mock_input.hover.return_value = {"ok": True, "action": "hover", "x": 100, "y": 200}
        result = _handle_hover("100,200")
        mock_input.hover.assert_called_once_with(100, 200)
        assert result["ok"] is True

    @patch("nexus.act.intents.raw_input")
    def test_hover_coordinates_at_prefix(self, mock_input):
        mock_input.hover.return_value = {"ok": True, "action": "hover", "x": 300, "y": 400}
        result = _handle_hover("at 300,400")
        mock_input.hover.assert_called_once_with(300, 400)

    @patch("nexus.act.intents.raw_input")
    @patch("nexus.sense.access.find_elements")
    def test_hover_element_by_name(self, mock_find, mock_input):
        mock_find.return_value = [
            {"label": "Save", "role": "button", "pos": (100, 200), "size": (80, 30)}
        ]
        mock_input.hover.return_value = {"ok": True}
        result = _handle_hover("Save")
        mock_input.hover.assert_called_once_with(140, 215)
        assert result["ok"] is True
        assert result["at"] == [140, 215]

    @patch("nexus.act.intents.raw_input")
    @patch("nexus.sense.access.find_elements")
    def test_hover_strips_over_prefix(self, mock_find, mock_input):
        mock_find.return_value = [
            {"label": "Search", "role": "field", "pos": (50, 50), "size": (200, 30)}
        ]
        mock_input.hover.return_value = {"ok": True}
        result = _handle_hover("over Search")
        mock_find.assert_called_with("Search", None)

    @patch("nexus.act.intents.raw_input")
    @patch("nexus.sense.access.find_elements")
    def test_hover_strips_the_prefix(self, mock_find, mock_input):
        mock_find.return_value = [
            {"label": "Menu", "role": "button", "pos": (10, 10), "size": (60, 20)}
        ]
        mock_input.hover.return_value = {"ok": True}
        _handle_hover("over the Menu")
        mock_find.assert_called_with("Menu", None)

    @patch("nexus.sense.access.find_elements")
    def test_hover_element_not_found(self, mock_find):
        mock_find.return_value = []
        result = _handle_hover("Nonexistent")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_hover_empty_target(self):
        result = _handle_hover("")
        assert result["ok"] is False
        assert "Hover over what" in result["error"]

    @patch("nexus.act.intents.raw_input")
    @patch("nexus.sense.access.find_elements")
    def test_hover_no_position(self, mock_find, mock_input):
        mock_find.return_value = [
            {"label": "Ghost", "role": "button"}
        ]
        result = _handle_hover("Ghost")
        assert result["ok"] is False
        assert "no position" in result["error"]

    @patch("nexus.act.intents.raw_input")
    def test_hover_via_do(self, mock_input):
        """Test hover through the main do() dispatcher."""
        mock_input.hover.return_value = {"ok": True, "action": "hover", "x": 50, "y": 60}
        result = do("hover 50,60")
        mock_input.hover.assert_called_once_with(50, 60)
        assert result["ok"] is True

    @patch("nexus.act.intents.raw_input")
    def test_mouseover_synonym(self, mock_input):
        """Test 'mouseover' verb synonym maps to hover."""
        mock_input.hover.return_value = {"ok": True, "action": "hover", "x": 10, "y": 20}
        result = do("mouseover 10,20")
        mock_input.hover.assert_called_once_with(10, 20)


# ===========================================================================
# TestInputHover — low-level hover in input.py
# ===========================================================================


class TestInputHover:
    """Tests for hover and modifier_click in input.py."""

    @patch("pyautogui.moveTo")
    def test_hover_moves_mouse(self, mock_move):
        from nexus.act.input import hover
        result = hover(100, 200)
        mock_move.assert_called_once_with(100, 200)
        assert result["ok"] is True
        assert result["action"] == "hover"

    @patch("pyautogui.keyDown")
    @patch("pyautogui.click")
    @patch("pyautogui.keyUp")
    def test_modifier_click_shift(self, mock_up, mock_click, mock_down):
        from nexus.act.input import modifier_click
        result = modifier_click(100, 200, ["shift"])
        mock_down.assert_called_with("shift")
        mock_click.assert_called_with(100, 200)
        mock_up.assert_called_with("shift")
        assert result["ok"] is True
        assert result["modifiers"] == ["shift"]

    @patch("pyautogui.keyDown")
    @patch("pyautogui.click")
    @patch("pyautogui.keyUp")
    def test_modifier_click_multi(self, mock_up, mock_click, mock_down):
        from nexus.act.input import modifier_click
        result = modifier_click(50, 60, ["command", "shift"])
        assert mock_down.call_count == 2
        assert mock_up.call_count == 2
        # keyDown called in order: command, shift
        mock_down.assert_any_call("command")
        mock_down.assert_any_call("shift")
        # keyUp called in reverse: shift, command
        assert mock_up.call_args_list[0] == call("shift")
        assert mock_up.call_args_list[1] == call("command")


# ===========================================================================
# TestTripleClick
# ===========================================================================


class TestTripleClick:
    """Tests for triple-click support."""

    @patch("pyautogui.click")
    def test_triple_click_input(self, mock_click):
        from nexus.act.input import triple_click
        result = triple_click(100, 200)
        mock_click.assert_called_once_with(100, 200, clicks=3)
        assert result["ok"] is True
        assert result["action"] == "triple_click"

    @patch("nexus.act.click.native")
    @patch("nexus.act.click.raw_input")
    def test_triple_click_routing(self, mock_raw, mock_native):
        """do('triple-click Save') routes to _handle_click with triple=True."""
        mock_native.click_element.return_value = {"ok": True, "at": [100, 200]}
        mock_raw.triple_click.return_value = {"ok": True}
        result = do("triple-click Save")
        mock_raw.triple_click.assert_called_once_with(100, 200)

    @patch("nexus.act.click.native")
    @patch("nexus.act.click.raw_input")
    def test_tripleclick_variant(self, mock_raw, mock_native):
        mock_native.click_element.return_value = {"ok": True, "at": [50, 60]}
        mock_raw.triple_click.return_value = {"ok": True}
        result = do("tripleclick Save")
        mock_raw.triple_click.assert_called_once()

    @patch("nexus.act.click.native")
    @patch("nexus.act.click.raw_input")
    def test_tclick_variant(self, mock_raw, mock_native):
        mock_native.click_element.return_value = {"ok": True, "at": [50, 60]}
        mock_raw.triple_click.return_value = {"ok": True}
        result = do("tclick Save")
        mock_raw.triple_click.assert_called_once()

    @patch("nexus.act.click.raw_input")
    def test_triple_click_coordinates(self, mock_raw):
        mock_raw.triple_click.return_value = {"ok": True}
        result = do("triple-click 100,200")
        mock_raw.triple_click.assert_called_once_with(100, 200)

    @patch("nexus.act.click.raw_input")
    def test_triple_click_no_target(self, mock_raw):
        """Triple-click with no target clicks at mouse position."""
        mock_raw.mouse_position.return_value = {"x": 50, "y": 60}
        mock_raw.triple_click.return_value = {"ok": True}
        result = do("triple-click")
        mock_raw.triple_click.assert_called_once_with(50, 60)
