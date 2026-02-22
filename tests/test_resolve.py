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
    do,
    _handle_scroll,
    _handle_drag,
    _handle_tile,
    _handle_move,
    _handle_press,
    _handle_type,
    ORDINAL_WORDS,
    KEY_ALIASES,
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
        mock_native.maximize_window.return_value = {"ok": True}
        do("fullscreen")
        mock_native.maximize_window.assert_called_once()

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
        mock_handle_nav.assert_called_once_with("to google.com")

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
        result = _handle_drag("100 to 300")
        assert result["ok"] is False
        assert "Drag format" in result["error"]

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
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=1055)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_right(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window right")
        mock_native.move_window.assert_called_once_with(None, x=960, y=25, w=960, h=1055)

    @patch("nexus.act.input.screen_size", return_value={"width": 2560, "height": 1440})
    def test_move_window_left_retina(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=1280, h=1415)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_safari_left(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("Safari left")
        mock_native.move_window.assert_called_once_with("safari", x=0, y=25, w=960, h=1055)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_center(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window center")
        mock_native.move_window.assert_called_once_with(None, x=480, y=25, w=960, h=1055)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_full(self, mock_screen, mock_raw_input, mock_native):
        mock_native.maximize_window.return_value = {"ok": True}
        _handle_move("window full")
        mock_native.maximize_window.assert_called_once_with(None)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_unknown_direction(self, mock_screen, mock_raw_input, mock_native):
        result = _handle_move("window diagonal")
        assert result["ok"] is False
        assert "Unknown direction" in result["error"]

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_alias_l(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window l")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=1055)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_alias_r(self, mock_screen, mock_raw_input, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window r")
        mock_native.move_window.assert_called_once_with(None, x=960, y=25, w=960, h=1055)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_maximize_alias(self, mock_screen, mock_raw_input, mock_native):
        mock_native.maximize_window.return_value = {"ok": True}
        _handle_move("window maximize")
        mock_native.maximize_window.assert_called_once_with(None)


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
