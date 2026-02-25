"""Tests for nexus.act.parse — parsing utilities and constants."""

import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/Users/ferran/repos/Nexus")

from nexus.act.parse import (
    _parse_ordinal, _word_to_ordinal, _strip_quotes, _parse_fields,
    _normalize_action, _parse_spatial, _parse_container, _resolve_modifiers,
    _filter_by_search,
    ORDINAL_WORDS, VERB_SYNONYMS, PHRASE_SYNONYMS,
    SPATIAL_RELATIONS, REGION_PATTERNS, ROLE_MAP, ROLE_WORDS,
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
# TestSpatialDicts
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
# TestTypoTolerance — fuzzy verb matching (Phase 7b)
# ===========================================================================


class TestTypoTolerance:
    """Tests for typo tolerance in _normalize_action."""

    # --- Common typos should be corrected ---

    def test_clikc_becomes_click(self):
        assert _normalize_action("clikc Save") == "click Save"

    def test_clickk_becomes_click(self):
        assert _normalize_action("clickk Save") == "click Save"

    def test_clck_becomes_click(self):
        assert _normalize_action("clck Save") == "click Save"

    def test_tpye_becomes_type(self):
        assert _normalize_action("tpye hello") == "type hello"

    def test_tyep_becomes_type(self):
        assert _normalize_action("tyep hello") == "type hello"

    def test_pres_becomes_press(self):
        assert _normalize_action("pres cmd+s") == "press cmd+s"

    def test_scrol_becomes_scroll(self):
        assert _normalize_action("scrol down") == "scroll down"

    def test_scrool_becomes_scroll(self):
        assert _normalize_action("scrool down") == "scroll down"

    def test_opne_becomes_open(self):
        assert _normalize_action("opne Safari") == "open Safari"

    def test_hovr_becomes_hover(self):
        assert _normalize_action("hovr button") == "hover button"

    def test_focsu_becomes_focus(self):
        assert _normalize_action("focsu field") == "focus field"

    # --- Typo in a synonym should resolve to the canonical verb ---

    def test_tapp_becomes_click(self):
        # "tapp" is close to "tap" which is a synonym for "click"
        assert _normalize_action("tapp Save") == "click Save"

    # --- Correct verbs should be unchanged ---

    def test_click_unchanged(self):
        assert _normalize_action("click Save") == "click Save"

    def test_type_unchanged(self):
        assert _normalize_action("type hello") == "type hello"

    def test_press_unchanged(self):
        assert _normalize_action("press cmd+s") == "press cmd+s"

    def test_scroll_unchanged(self):
        assert _normalize_action("scroll down") == "scroll down"

    # --- Short words (< 3 chars) should NOT fuzzy match ---

    def test_short_word_no_false_positive(self):
        assert _normalize_action("xy Save") == "xy Save"

    def test_two_char_no_match(self):
        assert _normalize_action("ab test") == "ab test"

    # --- Completely wrong words should not match ---

    def test_completely_wrong_no_match(self):
        assert _normalize_action("zzzzz Save") == "zzzzz Save"

    def test_random_word_no_match(self):
        assert _normalize_action("frobnicate widget") == "frobnicate widget"

    # --- Verb-only typos (no rest) ---

    def test_verb_only_typo(self):
        result = _normalize_action("clikc")
        assert result == "click"

    # --- Case insensitivity ---

    def test_typo_case_insensitive(self):
        assert _normalize_action("CLIKC Save") == "click Save"

    def test_typo_mixed_case(self):
        assert _normalize_action("Clikc Save") == "click Save"

    # --- Menu paths should NOT be typo-corrected ---

    def test_menu_path_not_corrected(self):
        # "Edit > Paste" — "Edit" should not fuzzy-match to "exit"
        assert _normalize_action("Edit > Paste") == "Edit > Paste"

    def test_menu_path_with_file(self):
        assert _normalize_action("File > Save As") == "File > Save As"
