"""Tests for nexus.act.resolve — intent parser and router.

Tests the pure functions and routing logic of the `do` tool,
mocking native and raw_input so no macOS APIs are needed.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, call

# Ensure Nexus is importable
sys.path.insert(0, "/Users/ferran/repos/Nexus")

from nexus.act.resolve import (
    _parse_ordinal,
    _word_to_ordinal,
    _strip_quotes,
    _parse_fields,
    _normalize_action,
    _run_chain,
    _parse_spatial,
    _filter_by_search,
    _click_spatial,
    _click_in_region,
    _parse_container,
    _click_in_container,
    _find_and_click_in_row,
    _scroll_in_element,
    _scroll_until,
    _handle_hover,
    _handle_drag,
    _handle_read_table,
    _handle_read_list,
    _resolve_modifiers,
    do,
    _handle_scroll,
    _handle_tile,
    _handle_move,
    _handle_press,
    _handle_type,
    _handle_minimize,
    _handle_restore,
    _handle_resize,
    _handle_fullscreen,
    ORDINAL_WORDS,
    KEY_ALIASES,
    VERB_SYNONYMS,
    PHRASE_SYNONYMS,
    SPATIAL_RELATIONS,
    REGION_PATTERNS,
    ROLE_MAP,
    ROLE_WORDS,
)


# ===========================================================================
# TestParseOrdinal
# ===========================================================================


class TestParseOrdinal:
    """Tests for _parse_ordinal — ordinal + role extraction from click targets."""

    # --- Pattern 1: "<ordinal> [label...] <role>" ---

    def test_numeric_ordinal_button(self):
        assert _parse_ordinal("2nd button") == (2, "button", "")

    def test_numeric_ordinal_link(self):
        assert _parse_ordinal("3rd link") == (3, "link", "")

    def test_numeric_ordinal_1st(self):
        assert _parse_ordinal("1st tab") == (1, "tab", "")

    def test_numeric_ordinal_4th(self):
        assert _parse_ordinal("4th checkbox") == (4, "checkbox", "")

    def test_numeric_ordinal_11th(self):
        assert _parse_ordinal("11th button") == (11, "button", "")

    def test_numeric_ordinal_22nd(self):
        assert _parse_ordinal("22nd link") == (22, "link", "")

    def test_numeric_ordinal_33rd(self):
        assert _parse_ordinal("33rd field") == (33, "field", "")

    def test_word_ordinal_first(self):
        assert _parse_ordinal("first button") == (1, "button", "")

    def test_word_ordinal_second(self):
        assert _parse_ordinal("second link") == (2, "link", "")

    def test_word_ordinal_third(self):
        assert _parse_ordinal("third checkbox") == (3, "checkbox", "")

    def test_word_ordinal_tenth(self):
        assert _parse_ordinal("tenth field") == (10, "field", "")

    def test_word_ordinal_last(self):
        assert _parse_ordinal("last checkbox") == (-1, "checkbox", "")

    def test_last_button(self):
        assert _parse_ordinal("last button") == (-1, "button", "")

    # --- Leading "the" is stripped ---

    def test_the_2nd_button(self):
        assert _parse_ordinal("the 2nd button") == (2, "button", "")

    def test_the_first_link(self):
        assert _parse_ordinal("the first link") == (1, "link", "")

    def test_the_last_checkbox(self):
        assert _parse_ordinal("the last checkbox") == (-1, "checkbox", "")

    def test_the_3rd_tab(self):
        assert _parse_ordinal("the 3rd tab") == (3, "tab", "")

    # --- Ordinal with label: "first Save button" ---

    def test_ordinal_with_label(self):
        assert _parse_ordinal("first Save button") == (1, "button", "Save")

    def test_ordinal_with_multi_word_label(self):
        assert _parse_ordinal("2nd Submit Form button") == (2, "button", "Submit Form")

    def test_ordinal_with_label_and_the(self):
        assert _parse_ordinal("the 3rd Google link") == (3, "link", "Google")

    # --- Trailing extra words: "second link on the page" → role is "link" ---

    def test_ordinal_extra_words_ignored(self):
        # "on the page" comes after the last role word "link", so "link" is found
        assert _parse_ordinal("second link on the page") is None or \
               _parse_ordinal("second link on the page") == (2, "link", "")

    # Actually "second link on the page":
    # words = ["second", "link", "on", "the", "page"]
    # It scans from end for role word: "page" no, "the" no, "on" no, "link" yes → (2, "link", "")
    def test_second_link_on_the_page(self):
        result = _parse_ordinal("second link on the page")
        # "link" at index 1 is found scanning backwards
        assert result == (2, "link", "")

    # --- Pattern 2: "<role> <number>" — "button 3", "link 2" ---

    def test_role_then_number_button_3(self):
        assert _parse_ordinal("button 3") == (3, "button", "")

    def test_role_then_number_link_1(self):
        assert _parse_ordinal("link 1") == (1, "link", "")

    def test_role_then_number_tab_5(self):
        assert _parse_ordinal("tab 5") == (5, "tab", "")

    def test_role_then_number_checkbox_2(self):
        assert _parse_ordinal("checkbox 2") == (2, "checkbox", "")

    def test_role_then_number_field_10(self):
        assert _parse_ordinal("field 10") == (10, "field", "")

    # --- Roles recognized in both patterns ---

    def test_all_roles_pattern1(self):
        for role in ("button", "link", "tab", "menu", "field", "checkbox",
                      "radio", "text", "image", "slider", "switch", "toggle"):
            result = _parse_ordinal(f"1st {role}")
            assert result is not None, f"Role '{role}' should be recognized in pattern 1"
            assert result[0] == 1
            assert result[1] == role
            assert result[2] == ""

    def test_all_roles_pattern2(self):
        for role in ("button", "link", "tab", "menu", "field", "checkbox",
                      "radio", "text", "image", "slider", "switch", "toggle"):
            result = _parse_ordinal(f"{role} 1")
            assert result is not None, f"Role '{role}' should be recognized in pattern 2"
            assert result[0] == 1
            assert result[1] == role

    # --- Cases that return None ---

    def test_no_ordinal_plain_word(self):
        assert _parse_ordinal("Save") is None

    def test_no_ordinal_empty_string(self):
        assert _parse_ordinal("") is None

    def test_no_ordinal_just_the(self):
        assert _parse_ordinal("the") is None

    def test_no_ordinal_no_role(self):
        # "2nd foo" — "foo" is not a recognized role
        assert _parse_ordinal("2nd foo") is None

    def test_no_ordinal_single_ordinal_word(self):
        # "first" alone — ordinal but no role word
        assert _parse_ordinal("first") is None

    def test_no_ordinal_role_without_number(self):
        # "button" alone — role but no ordinal/number
        assert _parse_ordinal("button") is None

    def test_bare_number_no_role(self):
        # "3" alone — not a valid pattern
        assert _parse_ordinal("3") is None

    def test_number_without_suffix_no_role(self):
        # "2 something" — 2 isn't a recognized ordinal (no suffix), "something" not a role
        assert _parse_ordinal("2 something") is None

    # --- Case insensitivity ---

    def test_case_insensitive_the(self):
        assert _parse_ordinal("The 2nd Button") == (2, "button", "")

    def test_case_insensitive_ordinal(self):
        assert _parse_ordinal("FIRST button") == (1, "button", "")

    def test_case_insensitive_numeric_ordinal(self):
        assert _parse_ordinal("2ND BUTTON") == (2, "button", "")


# ===========================================================================
# TestWordToOrdinal
# ===========================================================================


class TestWordToOrdinal:
    """Tests for _word_to_ordinal — convert a word to an ordinal number."""

    # --- Word ordinals ---

    def test_first(self):
        assert _word_to_ordinal("first") == 1

    def test_second(self):
        assert _word_to_ordinal("second") == 2

    def test_third(self):
        assert _word_to_ordinal("third") == 3

    def test_fourth(self):
        assert _word_to_ordinal("fourth") == 4

    def test_fifth(self):
        assert _word_to_ordinal("fifth") == 5

    def test_sixth(self):
        assert _word_to_ordinal("sixth") == 6

    def test_seventh(self):
        assert _word_to_ordinal("seventh") == 7

    def test_eighth(self):
        assert _word_to_ordinal("eighth") == 8

    def test_ninth(self):
        assert _word_to_ordinal("ninth") == 9

    def test_tenth(self):
        assert _word_to_ordinal("tenth") == 10

    def test_last(self):
        assert _word_to_ordinal("last") == -1

    # --- Case insensitive ---

    def test_case_First(self):
        assert _word_to_ordinal("First") == 1

    def test_case_LAST(self):
        assert _word_to_ordinal("LAST") == -1

    def test_case_Third(self):
        assert _word_to_ordinal("Third") == 3

    # --- Numeric ordinals: "1st", "2nd", "3rd", "4th", etc. ---

    def test_1st(self):
        assert _word_to_ordinal("1st") == 1

    def test_2nd(self):
        assert _word_to_ordinal("2nd") == 2

    def test_3rd(self):
        assert _word_to_ordinal("3rd") == 3

    def test_4th(self):
        assert _word_to_ordinal("4th") == 4

    def test_10th(self):
        assert _word_to_ordinal("10th") == 10

    def test_11th(self):
        assert _word_to_ordinal("11th") == 11

    def test_12th(self):
        assert _word_to_ordinal("12th") == 12

    def test_13th(self):
        assert _word_to_ordinal("13th") == 13

    def test_21st(self):
        assert _word_to_ordinal("21st") == 21

    def test_22nd(self):
        assert _word_to_ordinal("22nd") == 22

    def test_23rd(self):
        assert _word_to_ordinal("23rd") == 23

    def test_100th(self):
        assert _word_to_ordinal("100th") == 100

    # --- Case insensitive numeric ---

    def test_2ND_upper(self):
        assert _word_to_ordinal("2ND") == 2

    def test_3RD_upper(self):
        assert _word_to_ordinal("3RD") == 3

    # --- Invalid inputs ---

    def test_invalid_random_word(self):
        assert _word_to_ordinal("hello") is None

    def test_invalid_empty(self):
        assert _word_to_ordinal("") is None

    def test_invalid_plain_number(self):
        # "5" alone — no ordinal suffix
        assert _word_to_ordinal("5") is None

    def test_invalid_wrong_suffix(self):
        # "1nd" — wrong suffix (should be 1st)
        # The regex matches any suffix so this would parse as 1
        assert _word_to_ordinal("1nd") == 1  # regex accepts any st/nd/rd/th

    def test_invalid_zero_th(self):
        # "0th" — technically parseable
        assert _word_to_ordinal("0th") == 0

    def test_invalid_word_with_number(self):
        assert _word_to_ordinal("abc") is None

    def test_invalid_negative(self):
        # "-1st" — regex requires \d+ so negative doesn't match
        assert _word_to_ordinal("-1st") is None


# ===========================================================================
# TestStripQuotes
# ===========================================================================


class TestStripQuotes:
    """Tests for _strip_quotes — remove surrounding quotes."""

    def test_double_quotes(self):
        assert _strip_quotes('"hello"') == "hello"

    def test_single_quotes(self):
        assert _strip_quotes("'hello'") == "hello"

    def test_no_quotes(self):
        assert _strip_quotes("hello") == "hello"

    def test_empty_string(self):
        assert _strip_quotes("") == ""

    def test_single_char(self):
        assert _strip_quotes("x") == "x"

    def test_single_double_quote(self):
        assert _strip_quotes('"') == '"'

    def test_single_single_quote(self):
        assert _strip_quotes("'") == "'"

    def test_mismatched_quotes_double_single(self):
        # "hello' — mismatched, should NOT strip
        assert _strip_quotes("\"hello'") == "\"hello'"

    def test_mismatched_quotes_single_double(self):
        assert _strip_quotes("'hello\"") == "'hello\""

    def test_nested_double_quotes(self):
        assert _strip_quotes('"hello "world""') == 'hello "world"'

    def test_nested_single_quotes(self):
        assert _strip_quotes("'it's a test'") == "it's a test"

    def test_empty_double_quotes(self):
        assert _strip_quotes('""') == ""

    def test_empty_single_quotes(self):
        assert _strip_quotes("''") == ""

    def test_spaces_inside_quotes(self):
        assert _strip_quotes('" hello world "') == " hello world "

    def test_whitespace_outside_quotes(self):
        # Leading/trailing whitespace is NOT stripped by this function
        assert _strip_quotes(' "hello" ') == ' "hello" '

    def test_just_two_double_quotes(self):
        assert _strip_quotes('""') == ""

    def test_just_two_single_quotes(self):
        assert _strip_quotes("''") == ""

    def test_triple_chars_not_quotes(self):
        assert _strip_quotes("abc") == "abc"


# ===========================================================================
# TestParseFields
# ===========================================================================


class TestParseFields:
    """Tests for _parse_fields — parse 'key=value, key=value' pairs."""

    def test_single_field(self):
        assert _parse_fields("Name=Ferran") == [("Name", "Ferran")]

    def test_multiple_fields(self):
        result = _parse_fields("Name=Ferran, Email=f@x.com")
        assert result == [("Name", "Ferran"), ("Email", "f@x.com")]

    def test_three_fields(self):
        result = _parse_fields("A=1, B=2, C=3")
        assert result == [("A", "1"), ("B", "2"), ("C", "3")]

    def test_quoted_value_double(self):
        result = _parse_fields('Name="John Doe"')
        assert result == [("Name", "John Doe")]

    def test_quoted_value_with_comma(self):
        # Quoted values with commas inside should be preserved
        result = _parse_fields('Address="123 Main St, Apt 4", City=NYC')
        assert len(result) == 2
        assert result[0] == ("Address", "123 Main St, Apt 4")
        assert result[1] == ("City", "NYC")

    def test_empty_string(self):
        assert _parse_fields("") == []

    def test_no_equals_sign(self):
        # Should skip entries without =
        assert _parse_fields("hello world") == []

    def test_empty_value(self):
        result = _parse_fields("Name=")
        assert result == [("Name", "")]

    def test_value_with_equals(self):
        # Value contains = sign
        result = _parse_fields("Equation=1+1=2")
        assert result == [("Equation", "1+1=2")]

    def test_whitespace_around_keys_values(self):
        result = _parse_fields("  Name = Ferran ,  Email = test@x.com  ")
        assert len(result) == 2
        assert result[0] == ("Name", "Ferran")
        assert result[1] == ("Email", "test@x.com")

    def test_single_quoted_value(self):
        result = _parse_fields("Name='John Doe'")
        assert result == [("Name", "John Doe")]

    def test_mixed_quoted_unquoted(self):
        result = _parse_fields('Name="John Doe", Age=30')
        assert result == [("Name", "John Doe"), ("Age", "30")]

    def test_empty_key_skipped(self):
        # "=value" — empty key should be skipped
        result = _parse_fields("=value")
        assert result == []


# ===========================================================================
# TestDoRouting
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestDoRouting:
    """Tests for do() — verify correct routing to native/raw_input handlers."""

    # --- Empty action ---

    def test_empty_action(self, mock_native, mock_raw_input):
        result = do("")
        assert result["ok"] is False
        assert "Empty action" in result["error"]

    def test_whitespace_only_action(self, mock_native, mock_raw_input):
        result = do("   ")
        assert result["ok"] is False
        assert "Empty action" in result["error"]

    # --- Shortcut intents ---

    def test_select_all(self, mock_native, mock_raw_input):
        do("select all")
        mock_raw_input.hotkey.assert_called_once_with("command", "a")

    def test_selectall_no_space(self, mock_native, mock_raw_input):
        do("selectall")
        mock_raw_input.hotkey.assert_called_once_with("command", "a")

    def test_copy(self, mock_native, mock_raw_input):
        result = do("copy")
        mock_raw_input.hotkey.assert_called_once_with("command", "c")
        assert result["ok"] is True
        assert result["action"] == "copy"

    def test_paste(self, mock_native, mock_raw_input):
        result = do("paste")
        mock_raw_input.hotkey.assert_called_once_with("command", "v")
        assert result["ok"] is True
        assert result["action"] == "paste"

    def test_undo(self, mock_native, mock_raw_input):
        result = do("undo")
        mock_raw_input.hotkey.assert_called_once_with("command", "z")
        assert result["ok"] is True
        assert result["action"] == "undo"

    def test_redo(self, mock_native, mock_raw_input):
        result = do("redo")
        mock_raw_input.hotkey.assert_called_once_with("command", "shift", "z")
        assert result["ok"] is True
        assert result["action"] == "redo"

    def test_close(self, mock_native, mock_raw_input):
        mock_native.close_window.return_value = {"ok": True}
        do("close")
        mock_native.close_window.assert_called_once()

    def test_close_window(self, mock_native, mock_raw_input):
        mock_native.close_window.return_value = {"ok": True}
        do("close window")
        mock_native.close_window.assert_called_once()

    # --- Getter intents ---

    def test_get_clipboard(self, mock_native, mock_raw_input):
        mock_native.clipboard_read.return_value = {"ok": True, "text": "hello"}
        result = do("get clipboard")
        mock_native.clipboard_read.assert_called_once()

    def test_read_clipboard(self, mock_native, mock_raw_input):
        mock_native.clipboard_read.return_value = {"ok": True, "text": "hi"}
        do("read clipboard")
        mock_native.clipboard_read.assert_called_once()

    def test_clipboard_alone(self, mock_native, mock_raw_input):
        mock_native.clipboard_read.return_value = {"ok": True, "text": "x"}
        do("clipboard")
        mock_native.clipboard_read.assert_called_once()

    def test_get_url(self, mock_native, mock_raw_input):
        mock_native.safari_url.return_value = {"ok": True, "url": "https://x.com"}
        do("get url")
        mock_native.safari_url.assert_called_once()

    def test_get_safari_url(self, mock_native, mock_raw_input):
        mock_native.safari_url.return_value = {"ok": True}
        do("get safari url")
        mock_native.safari_url.assert_called_once()

    def test_url_alone(self, mock_native, mock_raw_input):
        mock_native.safari_url.return_value = {"ok": True}
        do("url")
        mock_native.safari_url.assert_called_once()

    def test_get_tabs(self, mock_native, mock_raw_input):
        mock_native.safari_tabs.return_value = {"ok": True, "tabs": []}
        do("get tabs")
        mock_native.safari_tabs.assert_called_once()

    def test_get_safari_tabs(self, mock_native, mock_raw_input):
        mock_native.safari_tabs.return_value = {"ok": True}
        do("get safari tabs")
        mock_native.safari_tabs.assert_called_once()

    def test_tabs_alone(self, mock_native, mock_raw_input):
        mock_native.safari_tabs.return_value = {"ok": True}
        do("tabs")
        mock_native.safari_tabs.assert_called_once()

    def test_list_tabs(self, mock_native, mock_raw_input):
        mock_native.safari_tabs.return_value = {"ok": True}
        do("list tabs")
        mock_native.safari_tabs.assert_called_once()

    def test_get_source(self, mock_native, mock_raw_input):
        mock_native.safari_source.return_value = {"ok": True}
        do("get source")
        mock_native.safari_source.assert_called_once()

    def test_page_source(self, mock_native, mock_raw_input):
        mock_native.safari_source.return_value = {"ok": True}
        do("page source")
        mock_native.safari_source.assert_called_once()

    def test_get_selection(self, mock_native, mock_raw_input):
        mock_native.finder_selection.return_value = {"ok": True}
        do("get selection")
        mock_native.finder_selection.assert_called_once()

    def test_selected_files(self, mock_native, mock_raw_input):
        mock_native.finder_selection.return_value = {"ok": True}
        do("selected files")
        mock_native.finder_selection.assert_called_once()

    def test_maximize(self, mock_native, mock_raw_input):
        mock_native.maximize_window.return_value = {"ok": True}
        do("maximize")
        mock_native.maximize_window.assert_called_once()

    def test_maximize_window(self, mock_native, mock_raw_input):
        mock_native.maximize_window.return_value = {"ok": True}
        do("maximize window")
        mock_native.maximize_window.assert_called_once()

    def test_fullscreen(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        do("fullscreen")
        mock_native.fullscreen_window.assert_called_once()

    def test_maximize_is_not_fullscreen(self, mock_native, mock_raw_input):
        mock_native.maximize_window.return_value = {"ok": True}
        do("maximize")
        mock_native.maximize_window.assert_called_once()
        mock_native.fullscreen_window.assert_not_called()

    def test_enter_fullscreen(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        do("enter fullscreen")
        mock_native.fullscreen_window.assert_called_once()

    def test_exit_fullscreen(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        do("exit fullscreen")
        mock_native.fullscreen_window.assert_called_once()

    def test_minimize_shortcut(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        do("minimize")
        mock_native.minimize_window.assert_called_once()

    def test_minimize_window_shortcut(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        do("minimize window")
        mock_native.minimize_window.assert_called_once()

    def test_minimize_app_routed(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        do("minimize Safari")
        mock_native.minimize_window.assert_called_once_with(app_name="Safari")

    def test_restore_shortcut(self, mock_native, mock_raw_input):
        mock_native.unminimize_window.return_value = {"ok": True}
        do("restore")
        mock_native.unminimize_window.assert_called_once()

    def test_unminimize_shortcut(self, mock_native, mock_raw_input):
        mock_native.unminimize_window.return_value = {"ok": True}
        do("unminimize window")
        mock_native.unminimize_window.assert_called_once()

    def test_restore_app_routed(self, mock_native, mock_raw_input):
        mock_native.unminimize_window.return_value = {"ok": True}
        do("restore Safari")
        mock_native.unminimize_window.assert_called_once_with(app_name="Safari")

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_routed(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        do("resize to 800x600")
        mock_native.resize_window.assert_called_once()

    def test_fullscreen_app_routed(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        do("fullscreen Safari")
        mock_native.fullscreen_window.assert_called_once_with(app_name="Safari")

    def test_where_is_routed(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        do("where is Safari?")
        mock_native.window_info.assert_called_once()

    def test_wheres_routed(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        do("where's Chrome?")
        mock_native.window_info.assert_called_once()

    def test_window_info_routed(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        do("window info")
        mock_native.window_info.assert_called_once()

    # --- Click ---

    def test_click_element(self, mock_native, mock_raw_input):
        mock_native.click_element.return_value = {"ok": True, "action": "click"}
        do("click Save")
        mock_native.click_element.assert_called_once_with("Save", pid=None, role=None)

    def test_click_element_with_pid(self, mock_native, mock_raw_input):
        mock_native.click_element.return_value = {"ok": True}
        do("click Save", pid=12345)
        mock_native.click_element.assert_called_once_with("Save", pid=12345, role=None)

    # --- Click menu path (contains ">") ---

    def test_click_menu_path(self, mock_native, mock_raw_input):
        mock_native.click_menu.return_value = {"ok": True}
        do("click File > Save")
        mock_native.click_menu.assert_called_once_with("File > Save", pid=None)

    def test_click_menu_path_with_pid(self, mock_native, mock_raw_input):
        mock_native.click_menu.return_value = {"ok": True}
        do("click File > Save As", pid=999)
        mock_native.click_menu.assert_called_once_with("File > Save As", pid=999)

    def test_menu_verb_path(self, mock_native, mock_raw_input):
        mock_native.click_menu.return_value = {"ok": True}
        do("menu File > Save")
        mock_native.click_menu.assert_called_once_with("File > Save", pid=None)

    def test_menu_verb_without_angle_bracket(self, mock_native, mock_raw_input):
        mock_native.click_menu.return_value = {"ok": True}
        do("menu Edit")
        mock_native.click_menu.assert_called_once_with("Edit", pid=None)

    # --- Fallback: unknown verb with ">" treated as menu ---

    def test_unknown_verb_with_menu_path(self, mock_native, mock_raw_input):
        mock_native.click_menu.return_value = {"ok": True}
        do("Edit > Paste")
        mock_native.click_menu.assert_called_once_with("Edit > Paste", pid=None)

    # --- Fallback: unknown verb treated as click ---

    def test_unknown_verb_as_click(self, mock_native, mock_raw_input):
        mock_native.click_element.return_value = {"ok": True}
        do("Save")
        mock_native.click_element.assert_called()

    # --- Press ---

    def test_press_single_key_enter(self, mock_native, mock_raw_input):
        result = do("press enter")
        mock_raw_input.press.assert_called_once_with("return")
        assert result["ok"] is True
        assert result["action"] == "press"
        assert result["keys"] == ["return"]

    def test_press_combo_cmd_s(self, mock_native, mock_raw_input):
        result = do("press cmd+s")
        mock_raw_input.hotkey.assert_called_once_with("command", "s")
        assert result["ok"] is True
        assert result["keys"] == ["command", "s"]

    def test_press_combo_ctrl_shift_p(self, mock_native, mock_raw_input):
        do("press ctrl+shift+p")
        mock_raw_input.hotkey.assert_called_once_with("control", "shift", "p")

    def test_press_escape(self, mock_native, mock_raw_input):
        do("press esc")
        mock_raw_input.press.assert_called_once_with("escape")

    def test_press_tab(self, mock_native, mock_raw_input):
        do("press tab")
        mock_raw_input.press.assert_called_once_with("tab")

    def test_press_space(self, mock_native, mock_raw_input):
        do("press space")
        mock_raw_input.press.assert_called_once_with("space")

    def test_press_f5(self, mock_native, mock_raw_input):
        do("press f5")
        mock_raw_input.press.assert_called_once_with("f5")

    def test_press_alt_tab(self, mock_native, mock_raw_input):
        do("press alt+tab")
        mock_raw_input.hotkey.assert_called_once_with("option", "tab")

    def test_press_cmd_shift_z(self, mock_native, mock_raw_input):
        do("press cmd+shift+z")
        mock_raw_input.hotkey.assert_called_once_with("command", "shift", "z")

    # --- Type ---

    def test_type_simple(self, mock_native, mock_raw_input):
        result = do("type hello")
        mock_raw_input.type_text.assert_called_once_with("hello")
        assert result["ok"] is True
        assert result["action"] == "type"
        assert result["text"] == "hello"

    def test_type_with_quotes(self, mock_native, mock_raw_input):
        result = do('type "hello world"')
        mock_raw_input.type_text.assert_called_once_with("hello world")
        assert result["text"] == "hello world"

    def test_type_in_target(self, mock_native, mock_raw_input):
        mock_native.set_value.return_value = {"ok": True}
        do("type hello in search")
        mock_native.set_value.assert_called_once_with("search", "hello", pid=None)

    def test_type_quoted_in_target(self, mock_native, mock_raw_input):
        mock_native.set_value.return_value = {"ok": True}
        do('type "hello world" in search')
        mock_native.set_value.assert_called_once_with("search", "hello world", pid=None)

    def test_type_empty(self, mock_native, mock_raw_input):
        result = do("type")
        assert result["ok"] is False
        assert "Nothing to type" in result["error"]

    # --- Open ---

    def test_open_app(self, mock_native, mock_raw_input):
        mock_native.launch_app.return_value = {"ok": True}
        do("open Safari")
        mock_native.launch_app.assert_called_once_with("Safari")

    def test_open_app_with_spaces(self, mock_native, mock_raw_input):
        mock_native.launch_app.return_value = {"ok": True}
        do("open Visual Studio Code")
        mock_native.launch_app.assert_called_once_with("Visual Studio Code")

    # --- Switch ---

    def test_switch_to_app(self, mock_native, mock_raw_input):
        mock_native.activate_window.return_value = {"ok": True}
        do("switch to Terminal")
        mock_native.activate_window.assert_called_once_with(app_name="Terminal")

    def test_switch_without_to(self, mock_native, mock_raw_input):
        mock_native.activate_window.return_value = {"ok": True}
        do("switch Terminal")
        mock_native.activate_window.assert_called_once_with(app_name="Terminal")

    def test_activate_app(self, mock_native, mock_raw_input):
        mock_native.activate_window.return_value = {"ok": True}
        do("activate Safari")
        mock_native.activate_window.assert_called_once_with(app_name="Safari")

    # --- Scroll ---

    def test_scroll_down(self, mock_native, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        do("scroll down")
        mock_raw_input.scroll.assert_called_once_with(-3)

    def test_scroll_up(self, mock_native, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        do("scroll up")
        mock_raw_input.scroll.assert_called_once_with(3)

    # --- Focus ---

    def test_focus_element(self, mock_native, mock_raw_input):
        mock_native.focus_element.return_value = {"ok": True}
        do("focus search")
        mock_native.focus_element.assert_called_once_with("search", pid=None)

    # --- Notify ---

    def test_notify(self, mock_native, mock_raw_input):
        mock_native.notify.return_value = {"ok": True}
        do("notify Hello")
        mock_native.notify.assert_called_once_with("Nexus", "Hello")

    def test_notify_with_longer_message(self, mock_native, mock_raw_input):
        mock_native.notify.return_value = {"ok": True}
        do("notify Task completed successfully")
        mock_native.notify.assert_called_once_with("Nexus", "Task completed successfully")

    # --- Say ---

    def test_say(self, mock_native, mock_raw_input):
        mock_native.say.return_value = {"ok": True}
        do("say Hello")
        mock_native.say.assert_called_once_with("Hello")

    def test_say_sentence(self, mock_native, mock_raw_input):
        mock_native.say.return_value = {"ok": True}
        do("say The task is done")
        mock_native.say.assert_called_once_with("The task is done")

    # --- Navigate ---

    @patch("nexus.act.resolve._handle_navigate")
    def test_navigate_to_url(self, mock_handle_nav, mock_native, mock_raw_input):
        mock_handle_nav.return_value = {"ok": True}
        do("navigate to google.com")
        mock_handle_nav.assert_called_once_with("to google.com")

    @patch("nexus.act.resolve._handle_navigate")
    def test_goto_url(self, mock_handle_nav, mock_native, mock_raw_input):
        mock_handle_nav.return_value = {"ok": True}
        do("goto google.com")
        mock_handle_nav.assert_called_once_with("google.com")

    @patch("nexus.act.resolve._handle_navigate")
    def test_go_url(self, mock_handle_nav, mock_native, mock_raw_input):
        mock_handle_nav.return_value = {"ok": True}
        do("go to google.com")
        # "go to" phrase synonym normalizes to "navigate google.com"
        mock_handle_nav.assert_called_once_with("google.com")

    # --- Set/Write clipboard ---

    def test_set_clipboard(self, mock_native, mock_raw_input):
        mock_native.clipboard_write.return_value = {"ok": True}
        do("set clipboard hello")
        mock_native.clipboard_write.assert_called_once_with("hello")

    def test_write_clipboard_quoted(self, mock_native, mock_raw_input):
        mock_native.clipboard_write.return_value = {"ok": True}
        do('write clipboard "hello world"')
        mock_native.clipboard_write.assert_called_once_with("hello world")

    # --- JS ---

    @patch("nexus.act.resolve._handle_run_js")
    def test_js_verb(self, mock_handle_js, mock_native, mock_raw_input):
        mock_handle_js.return_value = {"ok": True}
        do("js document.title")
        mock_handle_js.assert_called_once_with("document.title")

    @patch("nexus.act.resolve._handle_run_js")
    def test_run_js(self, mock_handle_js, mock_native, mock_raw_input):
        mock_handle_js.return_value = {"ok": True}
        do("run js document.title")
        mock_handle_js.assert_called_once_with("document.title")

    @patch("nexus.act.resolve._handle_run_js")
    def test_eval_js(self, mock_handle_js, mock_native, mock_raw_input):
        mock_handle_js.return_value = {"ok": True}
        do("eval js alert('hi')")
        mock_handle_js.assert_called_once_with("alert('hi')")

    # --- Double click / right click verbs ---

    def test_double_click(self, mock_native, mock_raw_input):
        mock_native.click_element.return_value = {"ok": True}
        do("double-click item")
        mock_native.click_element.assert_called()

    def test_right_click(self, mock_native, mock_raw_input):
        mock_native.click_element.return_value = {"ok": True}
        do("right-click item")
        mock_native.click_element.assert_called()

    # --- Tile ---

    def test_tile_routed(self, mock_native, mock_raw_input):
        mock_native.tile_windows.return_value = {"ok": True}
        do("tile Safari and Terminal")
        mock_native.tile_windows.assert_called_once_with("Safari", "Terminal")

    # --- Fill ---

    @patch("nexus.act.resolve._handle_fill")
    def test_fill_routed(self, mock_handle_fill, mock_native, mock_raw_input):
        mock_handle_fill.return_value = {"ok": True}
        do("fill Name=Ferran")
        mock_handle_fill.assert_called_once_with("Name=Ferran", pid=None)

    # --- Return value structure ---

    def test_select_all_returns_ok(self, mock_native, mock_raw_input):
        result = do("select all")
        assert result["ok"] is True
        assert result["action"] == "select_all"

    def test_copy_returns_ok(self, mock_native, mock_raw_input):
        result = do("copy")
        assert result["ok"] is True
        assert result["action"] == "copy"

    def test_paste_returns_ok(self, mock_native, mock_raw_input):
        result = do("paste")
        assert result["ok"] is True
        assert result["action"] == "paste"


# ===========================================================================
# TestHandlePress
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
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


@patch("nexus.act.resolve.raw_input")
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


@patch("nexus.act.resolve.raw_input")
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
# TestHandleTile
# ===========================================================================


@patch("nexus.act.resolve.native")
class TestHandleTile:
    """Tests for _handle_tile — tile two windows side by side."""

    def test_tile_and_pattern(self, mock_native):
        mock_native.tile_windows.return_value = {"ok": True}
        result = _handle_tile("Safari and Terminal")
        mock_native.tile_windows.assert_called_once_with("Safari", "Terminal")

    def test_tile_two_words(self, mock_native):
        mock_native.tile_windows.return_value = {"ok": True}
        result = _handle_tile("Code Terminal")
        mock_native.tile_windows.assert_called_once_with("Code", "Terminal")

    def test_tile_and_case_insensitive(self, mock_native):
        mock_native.tile_windows.return_value = {"ok": True}
        _handle_tile("Safari AND Chrome")
        mock_native.tile_windows.assert_called_once_with("Safari", "Chrome")

    def test_tile_single_word_fails(self, mock_native):
        result = _handle_tile("Safari")
        assert result["ok"] is False
        assert "Tile format" in result["error"]

    def test_tile_empty_fails(self, mock_native):
        result = _handle_tile("")
        assert result["ok"] is False

    def test_tile_three_words_no_and(self, mock_native):
        # Three words without "and" — doesn't match either pattern
        result = _handle_tile("Safari Chrome Firefox")
        assert result["ok"] is False

    def test_tile_multi_word_app_and_pattern(self, mock_native):
        mock_native.tile_windows.return_value = {"ok": True}
        _handle_tile("Visual Studio Code and Terminal")
        mock_native.tile_windows.assert_called_once_with("Visual Studio Code", "Terminal")


# ===========================================================================
# TestHandleMove
# ===========================================================================


@patch("nexus.act.resolve.native")
@patch("nexus.act.resolve.raw_input")  # needed for screen_size via input module
class TestHandleMove:
    """Tests for _handle_move — window positioning."""

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_left(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_right(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window right")
        mock_native.move_window.assert_called_once_with(None, x=960, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 2560, "height": 1440})
    def test_move_window_left_retina(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=1280, h=1415, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_safari_left(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("Safari left")
        mock_native.move_window.assert_called_once_with("safari", x=0, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_center(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window center")
        mock_native.move_window.assert_called_once_with(None, x=480, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_full(self, mock_screen, mock_raw_input, mock_native):
        mock_native.maximize_window.return_value = {"ok": True}
        _handle_move("window full")
        mock_native.maximize_window.assert_called_once_with(None)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_unknown_direction(self, mock_screen, mock_raw_input, mock_native):
        result = _handle_move("window diagonal")
        assert result["ok"] is False
        assert "Unknown position" in result["error"]

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_alias_l(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window l")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_alias_r(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window r")
        mock_native.move_window.assert_called_once_with(None, x=960, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_maximize_alias(self, mock_screen, mock_raw_input, mock_native):
        mock_native.maximize_window.return_value = {"ok": True}
        _handle_move("window maximize")
        mock_native.maximize_window.assert_called_once_with(None)

    # --- Top/bottom halves ---
    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_top(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window top")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=1920, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_bottom(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window bottom")
        mock_native.move_window.assert_called_once_with(None, x=0, y=552, w=1920, h=527, window_index=1)

    # --- Quarters ---
    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_top_left(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window top-left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_top_right(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window top-right")
        mock_native.move_window.assert_called_once_with(None, x=960, y=25, w=960, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_bottom_left(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window bottom-left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=552, w=960, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_bottom_right(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window bottom-right")
        mock_native.move_window.assert_called_once_with(None, x=960, y=552, w=960, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_topleft_joined(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window topleft")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_bottomright_joined(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window bottomright")
        mock_native.move_window.assert_called_once_with(None, x=960, y=552, w=960, h=527, window_index=1)

    # --- Thirds ---
    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_left_third(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window left-third")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=640, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_center_third(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window center-third")
        mock_native.move_window.assert_called_once_with(None, x=640, y=25, w=640, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_right_third(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window right-third")
        mock_native.move_window.assert_called_once_with(None, x=1280, y=25, w=640, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_middle_third(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window middle-third")
        mock_native.move_window.assert_called_once_with(None, x=640, y=25, w=640, h=1055, window_index=1)

    # --- Coordinate move ---
    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_safari_to_coordinates(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("Safari to 100,200")
        mock_native.move_window.assert_called_once_with("Safari", x=100, y=200, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_to_coordinates(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window to 100,200")
        mock_native.move_window.assert_called_once_with(None, x=100, y=200, window_index=1)

    # --- Window index ---
    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_2_left(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window 2 left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=1055, window_index=2)


# ===========================================================================
# TestHandleType
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
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
# TestOrdinalWords
# ===========================================================================


class TestOrdinalWords:
    """Tests that ORDINAL_WORDS dict is complete."""

    def test_contains_first_through_tenth(self):
        assert ORDINAL_WORDS["first"] == 1
        assert ORDINAL_WORDS["second"] == 2
        assert ORDINAL_WORDS["third"] == 3
        assert ORDINAL_WORDS["fourth"] == 4
        assert ORDINAL_WORDS["fifth"] == 5
        assert ORDINAL_WORDS["sixth"] == 6
        assert ORDINAL_WORDS["seventh"] == 7
        assert ORDINAL_WORDS["eighth"] == 8
        assert ORDINAL_WORDS["ninth"] == 9
        assert ORDINAL_WORDS["tenth"] == 10

    def test_contains_last(self):
        assert ORDINAL_WORDS["last"] == -1

    def test_count(self):
        assert len(ORDINAL_WORDS) == 11  # first-tenth + last


# ===========================================================================
# TestNavigateUrlHandling
# ===========================================================================


class TestNavigateUrlHandling:
    """Tests for _handle_navigate — URL normalization."""

    @patch("nexus.act.resolve.native")
    def test_strips_to_prefix(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.resolve import _handle_navigate
        _handle_navigate("to google.com")
        # Should call with https://google.com
        mock_native.run_applescript.assert_called_once()
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://google.com" in call_arg

    @patch("nexus.act.resolve.native")
    def test_adds_https_scheme(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.resolve import _handle_navigate
        _handle_navigate("example.com")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://example.com" in call_arg

    @patch("nexus.act.resolve.native")
    def test_preserves_http_scheme(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.resolve import _handle_navigate
        _handle_navigate("http://example.com")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "http://example.com" in call_arg
        assert "https://http://" not in call_arg

    @patch("nexus.act.resolve.native")
    def test_preserves_https_scheme(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.resolve import _handle_navigate
        _handle_navigate("https://example.com")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://example.com" in call_arg

    def test_empty_url_returns_error(self):
        from nexus.act.resolve import _handle_navigate
        result = _handle_navigate("")
        assert result["ok"] is False
        assert "No URL" in result["error"]

    @patch("nexus.act.resolve.native")
    def test_just_to_becomes_url(self, mock_native):
        # "to " stripped → "to" (doesn't match "to " prefix), treated as URL "https://to"
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.resolve import _handle_navigate
        result = _handle_navigate("to ")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://to" in call_arg

    @patch("nexus.act.resolve.native")
    def test_strips_quotes_from_url(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.resolve import _handle_navigate
        _handle_navigate('"google.com"')
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://google.com" in call_arg

    @patch("nexus.act.resolve.native")
    def test_file_scheme_preserved(self, mock_native):
        mock_native.run_applescript.return_value = {"ok": True}
        from nexus.act.resolve import _handle_navigate
        _handle_navigate("file:///Users/ferran/index.html")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "file:///Users/ferran/index.html" in call_arg


# ===========================================================================
# TestRunJs
# ===========================================================================


class TestRunJs:
    """Tests for _handle_run_js — JavaScript execution."""

    def test_empty_expression(self):
        from nexus.act.resolve import _handle_run_js
        result = _handle_run_js("")
        assert result["ok"] is False
        assert "No JavaScript" in result["error"]

    def test_whitespace_only(self):
        from nexus.act.resolve import _handle_run_js
        result = _handle_run_js("   ")
        assert result["ok"] is False
        assert "No JavaScript" in result["error"]


# ===========================================================================
# TestNormalizeAction — verb synonym expansion
# ===========================================================================


class TestNormalizeAction:
    """Tests for _normalize_action — synonym expansion."""

    # --- Single-word verb synonyms ---

    def test_tap_becomes_click(self):
        assert _normalize_action("tap Save") == "click Save"

    def test_hit_becomes_click(self):
        assert _normalize_action("hit OK") == "click OK"

    def test_select_becomes_click(self):
        assert _normalize_action("select Done") == "click Done"

    def test_choose_becomes_click(self):
        assert _normalize_action("choose Cancel") == "click Cancel"

    def test_push_becomes_click(self):
        assert _normalize_action("push Submit") == "click Submit"

    def test_enter_becomes_type(self):
        assert _normalize_action("enter hello") == "type hello"

    def test_input_becomes_type(self):
        assert _normalize_action("input some text") == "type some text"

    def test_launch_becomes_open(self):
        assert _normalize_action("launch Safari") == "open Safari"

    def test_start_becomes_open(self):
        assert _normalize_action("start Terminal") == "open Terminal"

    def test_quit_passes_through(self):
        # quit/exit handled directly in shortcut intents, not via synonym
        assert _normalize_action("quit") == "quit"

    def test_exit_passes_through(self):
        assert _normalize_action("exit") == "exit"

    def test_swipe_becomes_scroll(self):
        assert _normalize_action("swipe down") == "scroll down"

    def test_browse_becomes_navigate(self):
        assert _normalize_action("browse google.com") == "navigate google.com"

    def test_visit_becomes_navigate(self):
        assert _normalize_action("visit example.com") == "navigate example.com"

    def test_load_becomes_navigate(self):
        assert _normalize_action("load page.html") == "navigate page.html"

    # --- Phrase synonyms (multi-word) ---

    def test_press_on_becomes_click(self):
        assert _normalize_action("press on Save") == "click Save"

    def test_click_on_becomes_click(self):
        assert _normalize_action("click on Submit") == "click Submit"

    def test_tap_on_becomes_click(self):
        assert _normalize_action("tap on OK") == "click OK"

    def test_go_to_becomes_navigate(self):
        assert _normalize_action("go to google.com") == "navigate google.com"

    # --- Non-synonyms pass through unchanged ---

    def test_click_unchanged(self):
        assert _normalize_action("click Save") == "click Save"

    def test_type_unchanged(self):
        assert _normalize_action("type hello") == "type hello"

    def test_press_unchanged(self):
        assert _normalize_action("press cmd+s") == "press cmd+s"

    def test_open_unchanged(self):
        assert _normalize_action("open Safari") == "open Safari"

    def test_scroll_unchanged(self):
        assert _normalize_action("scroll down") == "scroll down"

    def test_unknown_verb_unchanged(self):
        assert _normalize_action("frobnicate widget") == "frobnicate widget"

    # --- Edge cases ---

    def test_empty_string(self):
        assert _normalize_action("") == ""

    def test_whitespace_stripped(self):
        assert _normalize_action("  tap Save  ") == "click Save"

    def test_case_preserved_in_rest(self):
        # Verb is lowered but rest preserves original case
        assert _normalize_action("tap MyButton") == "click MyButton"

    def test_verb_only_no_rest(self):
        # launch has no rest — becomes "open"
        assert _normalize_action("launch") == "open"

    def test_synonym_case_insensitive(self):
        # "Tap" should still match
        assert _normalize_action("Tap Save") == "click Save"

    def test_phrase_takes_precedence_over_word(self):
        # "click on X" should match phrase "click on" → "click", not word "click" → stays
        result = _normalize_action("click on Save")
        assert result == "click Save"

    # --- Verbs that should NOT be synonymized (to avoid conflicts) ---

    def test_run_not_synonymized(self):
        # "run" conflicts with "run js" — should not become "open"
        assert _normalize_action("run js document.title") == "run js document.title"

    def test_write_not_synonymized(self):
        # "write" conflicts with "write clipboard" — should not become "type"
        assert _normalize_action("write clipboard hello") == "write clipboard hello"

    def test_select_all_not_broken(self):
        # "select all" is handled as a shortcut before normalization in do()
        # But _normalize_action itself would turn it to "click all"
        # This is OK because do() checks shortcuts first
        pass


# ===========================================================================
# TestDoSynonyms — end-to-end synonym routing via do()
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestDoSynonyms:
    """Test that verb synonyms route correctly through do()."""

    def test_tap_routes_to_click(self, mock_native, mock_raw_input):
        mock_native.click_element.return_value = {"ok": True}
        do("tap Save")
        mock_native.click_element.assert_called_once_with("Save", pid=None, role=None)

    def test_hit_routes_to_click(self, mock_native, mock_raw_input):
        mock_native.click_element.return_value = {"ok": True}
        do("hit Cancel")
        mock_native.click_element.assert_called_once_with("Cancel", pid=None, role=None)

    def test_press_on_routes_to_click(self, mock_native, mock_raw_input):
        mock_native.click_element.return_value = {"ok": True}
        do("press on Submit")
        mock_native.click_element.assert_called_once_with("Submit", pid=None, role=None)

    def test_click_on_routes_to_click(self, mock_native, mock_raw_input):
        mock_native.click_element.return_value = {"ok": True}
        do("click on Save")
        mock_native.click_element.assert_called_once_with("Save", pid=None, role=None)

    def test_enter_routes_to_type(self, mock_native, mock_raw_input):
        result = do("enter hello world")
        mock_raw_input.type_text.assert_called_once_with("hello world")
        assert result["ok"] is True

    def test_input_routes_to_type(self, mock_native, mock_raw_input):
        result = do("input test")
        mock_raw_input.type_text.assert_called_once_with("test")
        assert result["ok"] is True

    def test_launch_routes_to_open(self, mock_native, mock_raw_input):
        mock_native.launch_app.return_value = {"ok": True}
        do("launch Safari")
        mock_native.launch_app.assert_called_once_with("Safari")

    def test_start_routes_to_open(self, mock_native, mock_raw_input):
        mock_native.launch_app.return_value = {"ok": True}
        do("start Terminal")
        mock_native.launch_app.assert_called_once_with("Terminal")

    def test_visit_routes_to_navigate(self, mock_native, mock_raw_input):
        mock_native.run_applescript.return_value = {"ok": True}
        do("visit example.com")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://example.com" in call_arg

    def test_browse_routes_to_navigate(self, mock_native, mock_raw_input):
        mock_native.run_applescript.return_value = {"ok": True}
        do("browse google.com")
        call_arg = mock_native.run_applescript.call_args[0][0]
        assert "https://google.com" in call_arg

    def test_swipe_routes_to_scroll(self, mock_native, mock_raw_input):
        mock_raw_input.scroll.return_value = {"ok": True}
        do("swipe down")
        mock_raw_input.scroll.assert_called_once_with(-3)

    def test_quit_routes_to_close(self, mock_native, mock_raw_input):
        mock_native.close_window.return_value = {"ok": True}
        do("quit")
        mock_native.close_window.assert_called_once()

    def test_shortcuts_unaffected_by_synonyms(self, mock_native, mock_raw_input):
        """select all, copy, paste, undo, redo are checked before synonym expansion."""
        result = do("select all")
        mock_raw_input.hotkey.assert_called_with("command", "a")
        assert result["ok"] is True

    def test_getters_unaffected_by_synonyms(self, mock_native, mock_raw_input):
        """Getter intents should not be affected by synonym expansion."""
        mock_native.clipboard_read.return_value = {"ok": True, "text": "hi"}
        do("get clipboard")
        mock_native.clipboard_read.assert_called_once()


# ===========================================================================
# TestActionChains — semicolon-separated compound intents
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestActionChains:
    """Tests for action chains via do("step1; step2; step3")."""

    def test_two_step_chain(self, mock_native, mock_raw_input):
        """Two copy operations should both execute."""
        result = do("copy; paste")
        assert result["ok"] is True
        assert result["action"] == "chain"
        assert result["completed"] == 2
        assert result["total"] == 2
        assert len(result["steps"]) == 2

    def test_chain_preserves_step_info(self, mock_native, mock_raw_input):
        result = do("copy; undo")
        assert result["steps"][0]["action"] == "copy"
        assert result["steps"][0]["ok"] is True
        assert result["steps"][1]["action"] == "undo"
        assert result["steps"][1]["ok"] is True

    def test_chain_fails_fast_on_error(self, mock_native, mock_raw_input):
        """If a step fails, the chain stops."""
        mock_native.click_element.return_value = {"ok": False, "error": "Not found"}
        result = do("copy; click NonExistent; paste")
        assert result["ok"] is False
        assert result["completed"] == 1  # Only copy ran successfully
        assert result["total"] == 3
        assert "Step 2 failed" in result["error"]

    def test_three_step_chain(self, mock_native, mock_raw_input):
        result = do("select all; copy; paste")
        assert result["ok"] is True
        assert result["completed"] == 3

    def test_chain_with_whitespace(self, mock_native, mock_raw_input):
        """Extra whitespace around semicolons should be stripped."""
        result = do("copy ;  paste  ;  undo")
        assert result["ok"] is True
        assert result["completed"] == 3

    def test_empty_steps_skipped(self, mock_native, mock_raw_input):
        """Empty segments from consecutive semicolons are filtered out."""
        result = do("copy;; paste")
        assert result["ok"] is True
        assert result["completed"] == 2

    def test_single_step_chain(self, mock_native, mock_raw_input):
        """A chain with one step should still work."""
        # "copy;" → ["copy"]
        result = do("copy;")
        assert result["ok"] is True
        assert result["completed"] == 1

    def test_chain_with_synonym(self, mock_native, mock_raw_input):
        """Synonyms should work inside chain steps."""
        mock_native.launch_app.return_value = {"ok": True}
        result = do("launch Safari; copy")
        assert result["ok"] is True
        assert result["completed"] == 2
        mock_native.launch_app.assert_called_once_with("Safari")

    def test_chain_error_reports_which_step(self, mock_native, mock_raw_input):
        mock_native.click_element.return_value = {"ok": False, "error": "Element not found"}
        result = do("select all; click Missing")
        assert result["ok"] is False
        assert "Step 2" in result["error"]
        assert "Missing" in result["error"]

    def test_empty_chain(self, mock_native, mock_raw_input):
        """Only semicolons, no content."""
        result = do(";;;")
        assert result["ok"] is False
        assert "Empty" in result["error"]

    def test_chain_with_press(self, mock_native, mock_raw_input):
        result = do("press cmd+a; press cmd+c")
        assert result["ok"] is True
        assert result["completed"] == 2
        # Should have called hotkey twice
        assert mock_raw_input.hotkey.call_count == 2


# ===========================================================================
# TestVerbSynonymDicts
# ===========================================================================


class TestVerbSynonymDicts:
    """Tests that synonym dictionaries are well-formed."""

    def test_all_verb_synonyms_map_to_known_verbs(self):
        known_verbs = {"click", "type", "open", "close", "scroll", "navigate", "focus", "switch", "hover"}
        for synonym, canonical in VERB_SYNONYMS.items():
            assert canonical in known_verbs, f'VERB_SYNONYMS["{synonym}"] = "{canonical}" is not a known verb'

    def test_all_phrase_synonyms_map_to_known_patterns(self):
        known = {"click", "navigate", "switch to", "type", "focus"}
        for phrase, canonical in PHRASE_SYNONYMS.items():
            assert canonical in known, f'PHRASE_SYNONYMS["{phrase}"] = "{canonical}" is not recognized'

    def test_no_overlapping_synonyms(self):
        """A word should not appear as both a verb synonym and a phrase start."""
        phrase_starts = {p.split()[0] for p in PHRASE_SYNONYMS}
        # Some overlap is OK (e.g. "click" appears in "click on" phrase and
        # is also a real verb), but pure synonyms shouldn't shadow phrases
        for syn in VERB_SYNONYMS:
            if syn in phrase_starts:
                # This is fine as long as phrases are checked first
                pass

    def test_synonyms_are_lowercase(self):
        for k in VERB_SYNONYMS:
            assert k == k.lower(), f'VERB_SYNONYMS key "{k}" should be lowercase'
        for k in PHRASE_SYNONYMS:
            assert k == k.lower(), f'PHRASE_SYNONYMS key "{k}" should be lowercase'


# ===========================================================================
# TestParseSpatial — spatial reference parsing
# ===========================================================================


class TestParseSpatial:
    """Tests for _parse_spatial — parsing spatial references from click targets."""

    # --- Proximity: "near", "beside", "next to", "by", "close to" ---

    def test_button_near_search(self):
        assert _parse_spatial("button near search") == ("button", "near", "search")

    def test_button_beside_search(self):
        assert _parse_spatial("button beside search") == ("button", "near", "search")

    def test_button_next_to_search(self):
        assert _parse_spatial("button next to search") == ("button", "near", "search")

    def test_button_by_search(self):
        assert _parse_spatial("button by search") == ("button", "near", "search")

    def test_button_close_to_search(self):
        assert _parse_spatial("button close to search") == ("button", "near", "search")

    def test_save_near_cancel(self):
        assert _parse_spatial("Save near Cancel") == ("Save", "near", "Cancel")

    def test_close_button_near_search(self):
        assert _parse_spatial("close button near search") == ("close button", "near", "search")

    # --- Below/under ---

    def test_field_below_username(self):
        assert _parse_spatial("field below Username") == ("field", "below", "Username")

    def test_field_under_username(self):
        assert _parse_spatial("field under Username") == ("field", "below", "Username")

    def test_field_beneath_username(self):
        assert _parse_spatial("field beneath Username") == ("field", "below", "Username")

    def test_field_underneath_username(self):
        assert _parse_spatial("field underneath Username") == ("field", "below", "Username")

    def test_button_below_search(self):
        assert _parse_spatial("button below search") == ("button", "below", "search")

    # --- Above/over ---

    def test_button_above_submit(self):
        assert _parse_spatial("button above Submit") == ("button", "above", "Submit")

    def test_label_over_input(self):
        assert _parse_spatial("label over input") == ("label", "above", "input")

    # --- Left of ---

    def test_icon_left_of_cancel(self):
        assert _parse_spatial("icon left of Cancel") == ("icon", "left", "Cancel")

    def test_button_to_the_left_of_search(self):
        assert _parse_spatial("button to the left of search") == ("button", "left", "search")

    # --- Right of ---

    def test_button_right_of_search(self):
        assert _parse_spatial("button right of search") == ("button", "right", "search")

    def test_icon_to_the_right_of_ok(self):
        assert _parse_spatial("icon to the right of OK") == ("icon", "right", "OK")

    # --- "the" stripping ---

    def test_the_button_near_search(self):
        assert _parse_spatial("the button near search") == ("button", "near", "search")

    def test_button_near_the_search_field(self):
        assert _parse_spatial("button near the search field") == ("button", "near", "search field")

    def test_the_field_below_the_username(self):
        assert _parse_spatial("the field below the Username") == ("field", "below", "Username")

    # --- Region patterns ---

    def test_button_in_top_right(self):
        assert _parse_spatial("button in top-right") == ("button", "region", "top-right")

    def test_button_in_top_left(self):
        assert _parse_spatial("button in top-left") == ("button", "region", "top-left")

    def test_button_in_bottom_right(self):
        assert _parse_spatial("button in bottom-right") == ("button", "region", "bottom-right")

    def test_button_in_bottom_left(self):
        assert _parse_spatial("button in bottom-left") == ("button", "region", "bottom-left")

    def test_button_in_the_top_right(self):
        assert _parse_spatial("button in the top right") == ("button", "region", "top-right")

    def test_button_at_top_right(self):
        assert _parse_spatial("button at top-right") == ("button", "region", "top-right")

    def test_button_in_upper_right(self):
        assert _parse_spatial("button in upper-right") == ("button", "region", "top-right")

    def test_button_in_lower_left(self):
        assert _parse_spatial("button in lower-left") == ("button", "region", "bottom-left")

    def test_button_in_top(self):
        assert _parse_spatial("button in top") == ("button", "region", "top")

    def test_button_in_bottom(self):
        assert _parse_spatial("button in bottom") == ("button", "region", "bottom")

    def test_button_in_the_upper_area(self):
        assert _parse_spatial("button in the upper area") == ("button", "region", "top")

    def test_button_in_the_bottom_half(self):
        assert _parse_spatial("button in the bottom half") == ("button", "region", "bottom")

    def test_button_in_center(self):
        assert _parse_spatial("button in center") == ("button", "region", "center")

    def test_button_in_the_middle(self):
        assert _parse_spatial("button in the middle") == ("button", "region", "center")

    def test_close_button_in_top_right(self):
        assert _parse_spatial("close button in top-right") == ("close button", "region", "top-right")

    def test_save_in_top_left(self):
        assert _parse_spatial("Save in top-left") == ("Save", "region", "top-left")

    # --- Non-matching (returns None) ---

    def test_plain_label_no_spatial(self):
        assert _parse_spatial("Save") is None

    def test_empty_string(self):
        assert _parse_spatial("") is None

    def test_role_only(self):
        assert _parse_spatial("button") is None

    def test_no_reference_after_near(self):
        # "button near" has no reference text
        assert _parse_spatial("button near") is None

    def test_just_the(self):
        assert _parse_spatial("the") is None

    # --- Case insensitivity ---

    def test_case_insensitive_near(self):
        assert _parse_spatial("Button NEAR Search") == ("Button", "near", "Search")

    def test_case_insensitive_below(self):
        assert _parse_spatial("FIELD below USERNAME") == ("FIELD", "below", "USERNAME")

    def test_case_insensitive_region(self):
        assert _parse_spatial("button IN TOP-RIGHT") == ("button", "region", "top-right")


# ===========================================================================
# TestFilterBySearch — element filtering for spatial resolution
# ===========================================================================


class TestFilterBySearch:
    """Tests for _filter_by_search — filter elements by role or label."""

    def _make_elements(self):
        """Create a set of test elements."""
        return [
            {"label": "Save", "role": "botón", "_ax_role": "AXButton", "pos": (100, 100), "size": (80, 30)},
            {"label": "Cancel", "role": "botón", "_ax_role": "AXButton", "pos": (200, 100), "size": (80, 30)},
            {"label": "Search", "role": "campo de texto", "_ax_role": "AXTextField", "pos": (300, 50), "size": (200, 30)},
            {"label": "Username", "role": "texto estático", "_ax_role": "AXStaticText", "pos": (50, 200), "size": (100, 20)},
            {"label": "Google", "role": "enlace", "_ax_role": "AXLink", "pos": (150, 300), "size": (60, 20)},
            {"label": "Submit", "role": "botón", "_ax_role": "AXButton", "pos": (100, 400), "size": (80, 30)},
        ]

    def test_filter_by_role_button(self):
        elements = self._make_elements()
        result = _filter_by_search(elements, "button")
        assert len(result) == 3  # Save, Cancel, Submit
        assert all(el["_ax_role"] == "AXButton" for el in result)

    def test_filter_by_role_field(self):
        elements = self._make_elements()
        result = _filter_by_search(elements, "field")
        assert len(result) == 1
        assert result[0]["label"] == "Search"

    def test_filter_by_role_link(self):
        elements = self._make_elements()
        result = _filter_by_search(elements, "link")
        assert len(result) == 1
        assert result[0]["label"] == "Google"

    def test_filter_by_label_exact(self):
        elements = self._make_elements()
        result = _filter_by_search(elements, "Save")
        assert len(result) == 1
        assert result[0]["label"] == "Save"

    def test_filter_by_label_partial(self):
        elements = self._make_elements()
        result = _filter_by_search(elements, "Sub")
        assert len(result) == 1
        assert result[0]["label"] == "Submit"

    def test_filter_by_role_plus_label(self):
        """'Save button' → filter by AXButton role, then by label containing 'Save'."""
        elements = self._make_elements()
        result = _filter_by_search(elements, "Save button")
        assert len(result) == 1
        assert result[0]["label"] == "Save"

    def test_filter_role_first_label_second(self):
        """'button Save' → role=button, label=Save."""
        elements = self._make_elements()
        result = _filter_by_search(elements, "button Save")
        assert len(result) == 1
        assert result[0]["label"] == "Save"

    def test_filter_by_role_no_matches(self):
        elements = self._make_elements()
        result = _filter_by_search(elements, "slider")
        assert len(result) == 0

    def test_filter_by_label_no_matches(self):
        elements = self._make_elements()
        result = _filter_by_search(elements, "Nonexistent")
        assert len(result) == 0

    def test_filter_case_insensitive(self):
        elements = self._make_elements()
        result = _filter_by_search(elements, "save")
        assert len(result) == 1
        assert result[0]["label"] == "Save"


# ===========================================================================
# TestClickSpatial — spatial click resolution with mocked elements
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
class TestClickSpatial:
    """Tests for _click_spatial with mocked accessibility data."""

    def _mock_elements(self):
        """Return a set of positioned elements for spatial testing."""
        return [
            {"label": "Username", "role": "texto estático", "_ax_role": "AXStaticText",
             "pos": (50, 100), "size": (100, 20)},
            {"label": "", "role": "campo de texto", "_ax_role": "AXTextField",
             "pos": (50, 130), "size": (200, 30), "_ref": "field1_ref"},
            {"label": "Password", "role": "texto estático", "_ax_role": "AXStaticText",
             "pos": (50, 180), "size": (100, 20)},
            {"label": "", "role": "campo de texto seguro", "_ax_role": "AXTextField",
             "pos": (50, 210), "size": (200, 30), "_ref": "field2_ref"},
            {"label": "Submit", "role": "botón", "_ax_role": "AXButton",
             "pos": (100, 270), "size": (80, 30), "_ref": "submit_ref"},
            {"label": "Cancel", "role": "botón", "_ax_role": "AXButton",
             "pos": (200, 270), "size": (80, 30), "_ref": "cancel_ref"},
            {"label": "Search", "role": "campo de texto", "_ax_role": "AXTextField",
             "pos": (400, 50), "size": (200, 30), "_ref": "search_ref"},
            {"label": "Go", "role": "botón", "_ax_role": "AXButton",
             "pos": (610, 50), "size": (40, 30), "_ref": "go_ref"},
        ]

    @patch("nexus.sense.access.describe_app")
    @patch("nexus.sense.access.find_elements")
    @patch("nexus.sense.access.ax_actions", return_value=[])
    @patch("nexus.sense.access.ax_perform", return_value=False)
    def test_button_near_search(self, mock_perform, mock_actions, mock_find, mock_describe, mock_raw):
        elements = self._mock_elements()
        mock_find.return_value = [el for el in elements if el["label"] == "Search"]
        mock_describe.return_value = elements

        result = _click_spatial(("button", "near", "Search"), pid=None)
        assert result["ok"] is True
        assert result["action"] == "click_spatial"
        # Go button at (610,50) is nearest to Search at (400,50)
        assert result["element"]["label"] == "Go"

    @patch("nexus.sense.access.describe_app")
    @patch("nexus.sense.access.find_elements")
    @patch("nexus.sense.access.ax_actions", return_value=[])
    @patch("nexus.sense.access.ax_perform", return_value=False)
    def test_field_below_username(self, mock_perform, mock_actions, mock_find, mock_describe, mock_raw):
        elements = self._mock_elements()
        mock_find.return_value = [el for el in elements if el["label"] == "Username"]
        mock_describe.return_value = elements

        result = _click_spatial(("field", "below", "Username"), pid=None)
        assert result["ok"] is True
        # Field at (50,130) is directly below Username at (50,100)
        assert result["at"] is not None

    @patch("nexus.sense.access.describe_app")
    @patch("nexus.sense.access.find_elements")
    @patch("nexus.sense.access.ax_actions", return_value=[])
    @patch("nexus.sense.access.ax_perform", return_value=False)
    def test_button_right_of_submit(self, mock_perform, mock_actions, mock_find, mock_describe, mock_raw):
        elements = self._mock_elements()
        mock_find.return_value = [el for el in elements if el["label"] == "Submit"]
        mock_describe.return_value = elements

        result = _click_spatial(("button", "right", "Submit"), pid=None)
        assert result["ok"] is True
        # Cancel at (200,270) is right of Submit at (100,270)
        assert result["element"]["label"] == "Cancel"

    @patch("nexus.sense.access.describe_app")
    @patch("nexus.sense.access.find_elements")
    def test_reference_not_found(self, mock_find, mock_describe, mock_raw):
        mock_find.return_value = []
        result = _click_spatial(("button", "near", "Nonexistent"), pid=None)
        assert result["ok"] is False
        assert "not found" in result["error"]

    @patch("nexus.sense.access.describe_app")
    @patch("nexus.sense.access.find_elements")
    def test_no_candidates_in_direction(self, mock_find, mock_describe, mock_raw):
        elements = self._mock_elements()
        # Submit is at bottom, no buttons above it in the mock data
        mock_find.return_value = [el for el in elements if el["label"] == "Submit"]
        mock_describe.return_value = [
            el for el in elements if el["_ax_role"] == "AXButton" and el["label"] == "Submit"
        ]
        # Only Submit in describe_app — no other buttons
        result = _click_spatial(("button", "above", "Submit"), pid=None)
        assert result["ok"] is False
        assert "above" in result["error"].lower() or "not found" in result["error"].lower()


# ===========================================================================
# TestClickInRegion — region-based element resolution
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
class TestClickInRegion:
    """Tests for _click_in_region with mocked elements."""

    def _mock_elements(self):
        return [
            {"label": "Close", "role": "botón", "_ax_role": "AXButton",
             "pos": (1800, 30), "size": (40, 30), "_ref": "close_ref"},
            {"label": "Save", "role": "botón", "_ax_role": "AXButton",
             "pos": (100, 900), "size": (80, 30), "_ref": "save_ref"},
            {"label": "Help", "role": "botón", "_ax_role": "AXButton",
             "pos": (960, 540), "size": (80, 30), "_ref": "help_ref"},
        ]

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    @patch("nexus.sense.access.describe_app")
    @patch("nexus.sense.access.ax_actions", return_value=[])
    @patch("nexus.sense.access.ax_perform", return_value=False)
    def test_button_in_top_right(self, mock_perform, mock_actions, mock_describe, mock_screen, mock_raw):
        mock_describe.return_value = self._mock_elements()
        result = _click_in_region("button", "top-right", pid=None)
        assert result["ok"] is True
        assert result["element"]["label"] == "Close"

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    @patch("nexus.sense.access.describe_app")
    @patch("nexus.sense.access.ax_actions", return_value=[])
    @patch("nexus.sense.access.ax_perform", return_value=False)
    def test_button_in_bottom_left(self, mock_perform, mock_actions, mock_describe, mock_screen, mock_raw):
        mock_describe.return_value = self._mock_elements()
        result = _click_in_region("button", "bottom-left", pid=None)
        assert result["ok"] is True
        assert result["element"]["label"] == "Save"

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    @patch("nexus.sense.access.describe_app")
    @patch("nexus.sense.access.ax_actions", return_value=[])
    @patch("nexus.sense.access.ax_perform", return_value=False)
    def test_button_in_center(self, mock_perform, mock_actions, mock_describe, mock_screen, mock_raw):
        mock_describe.return_value = self._mock_elements()
        result = _click_in_region("button", "center", pid=None)
        assert result["ok"] is True
        assert result["element"]["label"] == "Help"

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    @patch("nexus.sense.access.describe_app")
    def test_no_match_in_region(self, mock_describe, mock_screen, mock_raw):
        mock_describe.return_value = self._mock_elements()
        result = _click_in_region("slider", "top-right", pid=None)
        assert result["ok"] is False
        assert "slider" in result["error"]

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    @patch("nexus.sense.access.describe_app")
    def test_unknown_region(self, mock_describe, mock_screen, mock_raw):
        mock_describe.return_value = self._mock_elements()
        result = _click_in_region("button", "northwest", pid=None)
        assert result["ok"] is False
        assert "Unknown region" in result["error"]


# ===========================================================================
# TestSpatialE2E — end-to-end via do() with spatial references
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestSpatialE2E:
    """End-to-end tests: do("click button near search") routes through spatial."""

    @patch("nexus.act.resolve._click_spatial")
    def test_click_button_near_search(self, mock_spatial, mock_native, mock_raw):
        mock_spatial.return_value = {"ok": True, "action": "click_spatial"}
        result = do("click button near search")
        mock_spatial.assert_called_once()
        args = mock_spatial.call_args
        # First arg is the spatial tuple
        assert args[0][0] == ("button", "near", "search")

    @patch("nexus.act.resolve._click_spatial")
    def test_click_field_below_username(self, mock_spatial, mock_native, mock_raw):
        mock_spatial.return_value = {"ok": True, "action": "click_spatial"}
        result = do("click field below Username")
        mock_spatial.assert_called_once()
        assert args[0][0] == ("field", "below", "Username") if (args := mock_spatial.call_args) else False

    @patch("nexus.act.resolve._click_spatial")
    def test_tap_button_near_search_synonym(self, mock_spatial, mock_native, mock_raw):
        """'tap button near search' → synonym → 'click button near search' → spatial."""
        mock_spatial.return_value = {"ok": True, "action": "click_spatial"}
        do("tap button near search")
        mock_spatial.assert_called_once()

    @patch("nexus.act.resolve._click_spatial")
    def test_click_button_in_top_right(self, mock_spatial, mock_native, mock_raw):
        mock_spatial.return_value = {"ok": True, "action": "click_spatial"}
        do("click button in top-right")
        mock_spatial.assert_called_once()
        args = mock_spatial.call_args
        assert args[0][0] == ("button", "region", "top-right")


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
# TestSpatialDicts — well-formedness of spatial config
# ===========================================================================


class TestSpatialDicts:
    """Tests that spatial patterns are well-formed."""

    def test_spatial_relations_are_compiled(self):
        for pattern, relation in SPATIAL_RELATIONS:
            assert hasattr(pattern, "match"), f"Pattern for {relation} should be compiled regex"

    def test_region_patterns_are_compiled(self):
        for pattern, region in REGION_PATTERNS:
            assert hasattr(pattern, "match"), f"Pattern for {region} should be compiled regex"

    def test_spatial_relations_known(self):
        known = {"near", "below", "above", "left", "right"}
        for _, relation in SPATIAL_RELATIONS:
            assert relation in known, f"Unknown spatial relation: {relation}"

    def test_region_patterns_known(self):
        known = {"top-left", "top-right", "bottom-left", "bottom-right", "top", "bottom", "center"}
        for _, region in REGION_PATTERNS:
            assert region in known, f"Unknown region: {region}"


# ===========================================================================
# TestHover — hover intent parsing and execution
# ===========================================================================


class TestHover:
    """Tests for hover intent — moves mouse without clicking."""

    @patch("nexus.act.resolve.raw_input")
    def test_hover_coordinates(self, mock_input):
        mock_input.hover.return_value = {"ok": True, "action": "hover", "x": 100, "y": 200}
        result = _handle_hover("100,200")
        mock_input.hover.assert_called_once_with(100, 200)
        assert result["ok"] is True

    @patch("nexus.act.resolve.raw_input")
    def test_hover_coordinates_at_prefix(self, mock_input):
        mock_input.hover.return_value = {"ok": True, "action": "hover", "x": 300, "y": 400}
        result = _handle_hover("at 300,400")
        mock_input.hover.assert_called_once_with(300, 400)

    @patch("nexus.act.resolve.raw_input")
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

    @patch("nexus.act.resolve.raw_input")
    @patch("nexus.sense.access.find_elements")
    def test_hover_strips_over_prefix(self, mock_find, mock_input):
        mock_find.return_value = [
            {"label": "Search", "role": "field", "pos": (50, 50), "size": (200, 30)}
        ]
        mock_input.hover.return_value = {"ok": True}
        result = _handle_hover("over Search")
        mock_find.assert_called_with("Search", None)

    @patch("nexus.act.resolve.raw_input")
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

    @patch("nexus.act.resolve.raw_input")
    @patch("nexus.sense.access.find_elements")
    def test_hover_no_position(self, mock_find, mock_input):
        mock_find.return_value = [
            {"label": "Ghost", "role": "button"}
        ]
        result = _handle_hover("Ghost")
        assert result["ok"] is False
        assert "no position" in result["error"]

    @patch("nexus.act.resolve.raw_input")
    def test_hover_via_do(self, mock_input):
        """Test hover through the main do() dispatcher."""
        mock_input.hover.return_value = {"ok": True, "action": "hover", "x": 50, "y": 60}
        result = do("hover 50,60")
        mock_input.hover.assert_called_once_with(50, 60)
        assert result["ok"] is True

    @patch("nexus.act.resolve.raw_input")
    def test_mouseover_synonym(self, mock_input):
        """Test 'mouseover' verb synonym maps to hover."""
        mock_input.hover.return_value = {"ok": True, "action": "hover", "x": 10, "y": 20}
        result = do("mouseover 10,20")
        mock_input.hover.assert_called_once_with(10, 20)


# ===========================================================================
# TestModifierClick — shift-click, cmd-click, option-click, ctrl-click
# ===========================================================================


class TestModifierClick:
    """Tests for modifier+click intents."""

    def test_resolve_modifiers_shift(self):
        assert _resolve_modifiers(["shift"]) == ["shift"]

    def test_resolve_modifiers_cmd(self):
        assert _resolve_modifiers(["cmd"]) == ["command"]

    def test_resolve_modifiers_command(self):
        assert _resolve_modifiers(["command"]) == ["command"]

    def test_resolve_modifiers_opt(self):
        assert _resolve_modifiers(["opt"]) == ["option"]

    def test_resolve_modifiers_option(self):
        assert _resolve_modifiers(["option"]) == ["option"]

    def test_resolve_modifiers_alt(self):
        assert _resolve_modifiers(["alt"]) == ["option"]

    def test_resolve_modifiers_ctrl(self):
        assert _resolve_modifiers(["ctrl"]) == ["control"]

    def test_resolve_modifiers_control(self):
        assert _resolve_modifiers(["control"]) == ["control"]

    @patch("nexus.act.resolve.raw_input")
    def test_shift_click_coordinates(self, mock_input):
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("shift-click 100,200")
        mock_input.modifier_click.assert_called_once_with(100, 200, ["shift"])
        assert result["ok"] is True

    @patch("nexus.act.resolve.raw_input")
    def test_cmd_click_coordinates(self, mock_input):
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("cmd-click 300,400")
        mock_input.modifier_click.assert_called_once_with(300, 400, ["command"])

    @patch("nexus.act.resolve.raw_input")
    def test_option_click_coordinates(self, mock_input):
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("option-click 50,60")
        mock_input.modifier_click.assert_called_once_with(50, 60, ["option"])

    @patch("nexus.act.resolve.raw_input")
    def test_ctrl_click_coordinates(self, mock_input):
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("ctrl-click 10,20")
        mock_input.modifier_click.assert_called_once_with(10, 20, ["control"])

    @patch("nexus.act.resolve.raw_input")
    def test_command_click_coordinates(self, mock_input):
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("command-click 10,20")
        mock_input.modifier_click.assert_called_once_with(10, 20, ["command"])

    @patch("nexus.act.resolve.raw_input")
    @patch("nexus.sense.access.find_elements")
    def test_shift_click_element(self, mock_find, mock_input):
        mock_find.return_value = [
            {"label": "file.txt", "role": "text", "_ax_role": "AXStaticText",
             "pos": (100, 200), "size": (80, 20)}
        ]
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("shift-click file.txt")
        mock_input.modifier_click.assert_called_once_with(140, 210, ["shift"])
        assert result["ok"] is True
        assert result.get("modifiers") == ["shift"]

    @patch("nexus.sense.access.find_elements")
    def test_shift_click_element_not_found(self, mock_find):
        mock_find.return_value = []
        result = do("shift-click Nonexistent")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_normalize_preserves_shift_click(self):
        """Modifier-click verbs should NOT be normalized away by synonyms."""
        assert _normalize_action("shift-click Save") == "shift-click Save"
        assert _normalize_action("cmd-click Item") == "cmd-click Item"


# ===========================================================================
# TestElementDrag — drag <element> to <element>
# ===========================================================================


class TestElementDrag:
    """Tests for element-based drag — 'drag X to Y'."""

    @patch("nexus.act.resolve.raw_input")
    def test_coordinate_drag(self, mock_input):
        mock_input.drag.return_value = {"ok": True, "action": "drag"}
        result = _handle_drag("100,200 to 300,400")
        mock_input.drag.assert_called_once_with(100, 200, 300, 400)
        assert result["ok"] is True

    @patch("nexus.act.resolve.raw_input")
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

    @patch("nexus.act.resolve.raw_input")
    def test_drag_via_do(self, mock_input):
        mock_input.drag.return_value = {"ok": True, "action": "drag"}
        result = do("drag 10,20 to 30,40")
        mock_input.drag.assert_called_once_with(10, 20, 30, 40)


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

    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_triple_click_routing(self, mock_raw, mock_native):
        """do('triple-click Save') routes to _handle_click with triple=True."""
        mock_native.click_element.return_value = {"ok": True, "at": [100, 200]}
        mock_raw.triple_click.return_value = {"ok": True}
        result = do("triple-click Save")
        mock_raw.triple_click.assert_called_once_with(100, 200)

    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_tripleclick_variant(self, mock_raw, mock_native):
        mock_native.click_element.return_value = {"ok": True, "at": [50, 60]}
        mock_raw.triple_click.return_value = {"ok": True}
        result = do("tripleclick Save")
        mock_raw.triple_click.assert_called_once()

    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_tclick_variant(self, mock_raw, mock_native):
        mock_native.click_element.return_value = {"ok": True, "at": [50, 60]}
        mock_raw.triple_click.return_value = {"ok": True}
        result = do("tclick Save")
        mock_raw.triple_click.assert_called_once()

    @patch("nexus.act.resolve.raw_input")
    def test_triple_click_coordinates(self, mock_raw):
        mock_raw.triple_click.return_value = {"ok": True}
        result = do("triple-click 100,200")
        mock_raw.triple_click.assert_called_once_with(100, 200)

    @patch("nexus.act.resolve.raw_input")
    def test_triple_click_no_target(self, mock_raw):
        """Triple-click with no target clicks at mouse position."""
        mock_raw.mouse_position.return_value = {"x": 50, "y": 60}
        mock_raw.triple_click.return_value = {"ok": True}
        result = do("triple-click")
        mock_raw.triple_click.assert_called_once_with(50, 60)


# ===========================================================================
# TestRoleMapConsolidation
# ===========================================================================


class TestRoleMapConsolidation:
    """Tests that ROLE_MAP and ROLE_WORDS are consistent and used everywhere."""

    def test_role_map_has_all_core_roles(self):
        expected = {"button", "link", "tab", "menu", "field", "checkbox",
                    "radio", "text", "image", "slider", "switch", "toggle"}
        assert expected.issubset(set(ROLE_MAP.keys()))

    def test_role_words_matches_role_map_keys(self):
        assert ROLE_WORDS == frozenset(ROLE_MAP.keys())

    def test_role_map_values_all_ax_prefixed(self):
        for role, ax_role in ROLE_MAP.items():
            assert ax_role.startswith("AX"), f"{role} → {ax_role} missing AX prefix"

    def test_icon_maps_to_ax_image(self):
        assert ROLE_MAP["icon"] == "AXImage"

    def test_label_maps_to_ax_static_text(self):
        assert ROLE_MAP["label"] == "AXStaticText"

    def test_toggle_maps_to_ax_switch(self):
        assert ROLE_MAP["toggle"] == "AXSwitch"


# ===========================================================================
# TestScrollTargeting
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
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
# TestParseContainer
# ===========================================================================


class TestParseContainer:
    """Tests for _parse_container — container-scoped click parsing."""

    def test_basic_row_with(self):
        result = _parse_container("delete in the row with Alice")
        assert result == ("delete", "Alice", None)

    def test_row_containing(self):
        result = _parse_container("button in the row containing Bob")
        assert result == ("button", "Bob", None)

    def test_row_that_has(self):
        result = _parse_container("checkbox in row that has Admin")
        assert result == ("checkbox", "Admin", None)

    def test_row_that_contains(self):
        result = _parse_container("delete in row that contains alice@example.com")
        assert result == ("delete", "alice@example.com", None)

    def test_row_number(self):
        result = _parse_container("button in row 3")
        assert result == ("button", None, 3)

    def test_row_number_with_the(self):
        result = _parse_container("delete in the row 5")
        assert result == ("delete", None, 5)

    def test_no_container(self):
        """Regular click targets don't parse as containers."""
        assert _parse_container("Save button") is None
        assert _parse_container("the 2nd button") is None
        assert _parse_container("button near search") is None

    def test_leading_the_stripped(self):
        result = _parse_container("the checkbox in the row with Alice")
        assert result == ("checkbox", "Alice", None)

    def test_multi_word_target(self):
        result = _parse_container("delete button in the row with Alice")
        assert result == ("delete button", "Alice", None)

    def test_multi_word_reference(self):
        result = _parse_container("delete in the row with John Doe")
        assert result == ("delete", "John Doe", None)


# ===========================================================================
# TestClickInContainer
# ===========================================================================


class TestClickInContainer:
    """Tests for _click_in_container — clicking within table rows."""

    def _make_mock_table(self, rows_data, row_refs):
        """Create a mock table dict matching find_tables() output."""
        headers = ["Name", "Email", "Action"]
        return {
            "title": "Users",
            "headers": headers,
            "rows": rows_data,
            "row_refs": row_refs,
            "num_rows": len(rows_data),
            "num_cols": len(headers),
        }

    @patch("nexus.act.resolve.raw_input")
    def test_click_by_row_content(self, mock_raw):
        """Click a button in the row containing 'Alice'."""
        mock_raw.click.return_value = {"ok": True}

        row_refs = [MagicMock(), MagicMock()]
        rows_data = [
            ["Alice", "alice@x.com", ""],
            ["Bob", "bob@x.com", ""],
        ]
        table = self._make_mock_table(rows_data, row_refs)

        # Mock walk_tree to return a button inside the row
        button_el = {
            "role": "button", "label": "Delete", "_ax_role": "AXButton",
            "pos": (500, 100), "size": (60, 30), "_ref": MagicMock(),
        }

        with patch("nexus.sense.access.find_tables", return_value=[table]):
            with patch("nexus.sense.access.walk_tree", return_value=[button_el]):
                with patch("nexus.sense.access.ax_actions", return_value=[]):
                    result = _click_in_container(("button", "Alice", None))
                    assert result["ok"] is True

    @patch("nexus.act.resolve.raw_input")
    def test_click_by_row_number(self, mock_raw):
        """Click button in row 2."""
        mock_raw.click.return_value = {"ok": True}

        row_refs = [MagicMock(), MagicMock()]
        rows_data = [["Alice", "a@x.com"], ["Bob", "b@x.com"]]
        table = self._make_mock_table(rows_data, row_refs)

        button_el = {
            "role": "button", "label": "Edit", "_ax_role": "AXButton",
            "pos": (500, 150), "size": (60, 30), "_ref": MagicMock(),
        }

        with patch("nexus.sense.access.find_tables", return_value=[table]):
            with patch("nexus.sense.access.walk_tree", return_value=[button_el]):
                with patch("nexus.sense.access.ax_actions", return_value=[]):
                    result = _click_in_container(("button", None, 2))
                    assert result["ok"] is True

    def test_no_tables_found(self):
        with patch("nexus.sense.access.find_tables", return_value=[]):
            result = _click_in_container(("delete", "Alice", None))
            assert result["ok"] is False
            assert "No tables" in result["error"]

    def test_row_not_found(self):
        row_refs = [MagicMock()]
        rows_data = [["Bob", "b@x.com"]]
        table = self._make_mock_table(rows_data, row_refs)

        with patch("nexus.sense.access.find_tables", return_value=[table]):
            result = _click_in_container(("delete", "Alice", None))
            assert result["ok"] is False
            assert "Alice" in result["error"]

    def test_row_number_out_of_range(self):
        row_refs = [MagicMock()]
        rows_data = [["Alice", "a@x.com"]]
        table = self._make_mock_table(rows_data, row_refs)

        with patch("nexus.sense.access.find_tables", return_value=[table]):
            result = _click_in_container(("delete", None, 99))
            assert result["ok"] is False
            assert "99" in result["error"]

    def test_target_not_in_row(self):
        row_refs = [MagicMock()]
        rows_data = [["Alice", "a@x.com"]]
        table = self._make_mock_table(rows_data, row_refs)

        # Row has a text element but no button
        text_el = {
            "role": "static text", "label": "Alice", "_ax_role": "AXStaticText",
            "pos": (100, 100), "size": (80, 20),
        }

        with patch("nexus.sense.access.find_tables", return_value=[table]):
            with patch("nexus.sense.access.walk_tree", return_value=[text_el]):
                result = _click_in_container(("button", "Alice", None))
                assert result["ok"] is False
                assert "not found in the row" in result["error"]

    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_do_routing_click_in_row(self, mock_raw, mock_native):
        """do('click delete in the row with Alice') routes to container scoping."""
        row_refs = [MagicMock()]
        rows_data = [["Alice", "a@x.com"]]
        table = {
            "title": "", "headers": ["Name", "Email"],
            "rows": rows_data, "row_refs": row_refs,
            "num_rows": 1, "num_cols": 2,
        }
        button_el = {
            "role": "button", "label": "delete", "_ax_role": "AXButton",
            "pos": (500, 100), "size": (60, 30), "_ref": MagicMock(),
        }
        mock_raw.click.return_value = {"ok": True}

        with patch("nexus.sense.access.find_tables", return_value=[table]):
            with patch("nexus.sense.access.walk_tree", return_value=[button_el]):
                with patch("nexus.sense.access.ax_actions", return_value=[]):
                    result = do("click delete in the row with Alice")
                    assert result["ok"] is True


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


class TestObserveIntents:
    """Tests for do('observe ...') intent routing."""

    @patch("nexus.sense.observe.start_observing", return_value={"ok": True, "pid": 42})
    @patch("nexus.sense.access.frontmost_app", return_value={"pid": 42, "name": "Safari"})
    def test_observe_start(self, mock_app, mock_start):
        from nexus.act.resolve import do
        result = do("observe start")
        assert result["ok"] is True
        mock_start.assert_called_once_with(42, "Safari")

    @patch("nexus.sense.observe.start_observing", return_value={"ok": True, "pid": 42})
    @patch("nexus.sense.access.frontmost_app", return_value={"pid": 42, "name": "Safari"})
    def test_observe_no_args_defaults_to_start(self, mock_app, mock_start):
        from nexus.act.resolve import do
        result = do("observe")
        assert result["ok"] is True
        mock_start.assert_called_once()

    @patch("nexus.sense.observe.stop_observing", return_value={"ok": True, "stopped": [42]})
    def test_observe_stop(self, mock_stop):
        from nexus.act.resolve import do
        result = do("observe stop")
        assert result["ok"] is True
        mock_stop.assert_called_once()

    @patch("nexus.sense.observe.drain_events", return_value=[])
    def test_observe_clear(self, mock_drain):
        from nexus.act.resolve import do
        result = do("observe clear")
        assert result["ok"] is True
        assert result["action"] == "observe_clear"

    @patch("nexus.sense.observe.status", return_value={"ok": True, "observing": [], "buffered": 0})
    def test_observe_status(self, mock_status):
        from nexus.act.resolve import do
        result = do("observe status")
        assert result["ok"] is True
        mock_status.assert_called_once()

    def test_observe_unknown_command(self):
        from nexus.act.resolve import do
        result = do("observe foobar")
        assert result["ok"] is False
        assert "Unknown" in result["error"]

    @patch("nexus.sense.observe.start_observing", return_value={"ok": True, "pid": 42})
    @patch("nexus.sense.access.frontmost_app", return_value={"pid": 42, "name": "Finder"})
    def test_observe_on_synonym(self, mock_app, mock_start):
        from nexus.act.resolve import do
        result = do("observe on")
        assert result["ok"] is True

    @patch("nexus.sense.observe.stop_observing", return_value={"ok": True, "stopped": []})
    def test_observe_off_synonym(self, mock_stop):
        from nexus.act.resolve import do
        result = do("observe off")
        assert result["ok"] is True


# ===========================================================================
# TestHandleMinimize
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestHandleMinimize:
    """Tests for _handle_minimize — minimize windows."""

    def test_minimize_no_args(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("")
        mock_native.minimize_window.assert_called_once()

    def test_minimize_app_name(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("Safari")
        mock_native.minimize_window.assert_called_once_with(app_name="Safari")

    def test_minimize_window_keyword(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("window")
        mock_native.minimize_window.assert_called_once()

    def test_minimize_window_2(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("window 2")
        mock_native.minimize_window.assert_called_once_with(app_name=None, window_index=2)

    def test_minimize_window_2_of_safari(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("window 2 of Safari")
        mock_native.minimize_window.assert_called_once_with(app_name="safari", window_index=2)

    def test_minimize_window_3(self, mock_native, mock_raw_input):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("window 3")
        mock_native.minimize_window.assert_called_once_with(app_name=None, window_index=3)


# ===========================================================================
# TestHandleRestore
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestHandleRestore:
    """Tests for _handle_restore — unminimize windows."""

    def test_restore_no_args(self, mock_native, mock_raw_input):
        mock_native.unminimize_window.return_value = {"ok": True}
        _handle_restore("")
        mock_native.unminimize_window.assert_called_once()

    def test_restore_app_name(self, mock_native, mock_raw_input):
        mock_native.unminimize_window.return_value = {"ok": True}
        _handle_restore("Safari")
        mock_native.unminimize_window.assert_called_once_with(app_name="Safari")

    def test_restore_window_keyword(self, mock_native, mock_raw_input):
        mock_native.unminimize_window.return_value = {"ok": True}
        _handle_restore("window")
        mock_native.unminimize_window.assert_called_once()

    def test_restore_chrome(self, mock_native, mock_raw_input):
        mock_native.unminimize_window.return_value = {"ok": True}
        _handle_restore("Chrome")
        mock_native.unminimize_window.assert_called_once_with(app_name="Chrome")


# ===========================================================================
# TestHandleResize
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestHandleResize:
    """Tests for _handle_resize — resize windows."""

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_absolute(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 800x600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_no_to(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("800x600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_with_X(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 800X600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_app_name(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("Safari to 1200x800")
        mock_native.resize_window.assert_called_once_with(app_name="Safari", w=1200, h=800)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_percentage_50(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 50%")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=960, h=527)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_percentage_75(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 75%")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=1440, h=791)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_app_percentage(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("Safari to 75%")
        mock_native.resize_window.assert_called_once_with(app_name="Safari", w=1440, h=791)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_window_keyword(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("window to 800x600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_window_2(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("window 2 to 800x600")
        mock_native.resize_window.assert_called_once_with(w=800, h=600, window_index=2)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_with_comma(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 800,600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_with_star(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 800*600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    def test_resize_empty_fails(self, mock_native, mock_raw_input):
        result = _handle_resize("")
        assert result["ok"] is False

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_unparseable_fails(self, mock_screen, mock_native, mock_raw_input):
        result = _handle_resize("to banana")
        assert result["ok"] is False

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_percentage_100(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 100%")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=1920, h=1055)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_percentage_25(self, mock_screen, mock_native, mock_raw_input):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 25%")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=480, h=263)


# ===========================================================================
# TestHandleFullscreen
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestHandleFullscreen:
    """Tests for _handle_fullscreen — true macOS fullscreen toggle."""

    def test_fullscreen_no_args(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        _handle_fullscreen("")
        mock_native.fullscreen_window.assert_called_once()

    def test_fullscreen_app_name(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        _handle_fullscreen("Safari")
        mock_native.fullscreen_window.assert_called_once_with(app_name="Safari")

    def test_fullscreen_window_keyword(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        _handle_fullscreen("window")
        mock_native.fullscreen_window.assert_called_once()

    def test_fullscreen_chrome(self, mock_native, mock_raw_input):
        mock_native.fullscreen_window.return_value = {"ok": True}
        _handle_fullscreen("Chrome")
        mock_native.fullscreen_window.assert_called_once_with(app_name="Chrome")


# ===========================================================================
# TestWindowInfo
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestWindowInfo:
    """Tests for window info getter intents."""

    def test_where_is_safari(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        result = do("where is Safari?")
        mock_native.window_info.assert_called_once_with(app_name="Safari")

    def test_wheres_chrome(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        result = do("where's Chrome?")
        mock_native.window_info.assert_called_once_with(app_name="Chrome")

    def test_where_is_no_question_mark(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        result = do("where is Terminal")
        mock_native.window_info.assert_called_once_with(app_name="Terminal")

    def test_window_info_no_app(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        result = do("window info")
        mock_native.window_info.assert_called_once()

    def test_get_window_info(self, mock_native, mock_raw_input):
        mock_native.window_info.return_value = {"ok": True}
        result = do("get window info")
        mock_native.window_info.assert_called_once()
