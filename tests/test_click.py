"""Tests for nexus.act.click — click resolution (spatial, ordinal, container)."""

import sys
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, "/Users/ferran/repos/Nexus")

from nexus.act.click import (
    _click_spatial, _click_in_region, _click_resolved,
    _click_in_container, _find_and_click_in_row,
    _handle_click,
)
from nexus.act.parse import (
    _filter_by_search, _resolve_modifiers,
    ROLE_MAP, ROLE_WORDS,
)
from nexus.act.resolve import do


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


@patch("nexus.act.click.raw_input")
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


@patch("nexus.act.click.raw_input")
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


@patch("nexus.act.click.raw_input")
@patch("nexus.act.click.native")
class TestSpatialE2E:
    """End-to-end tests: do("click button near search") routes through spatial."""

    @patch("nexus.act.click._click_spatial")
    def test_click_button_near_search(self, mock_spatial, mock_native, mock_raw):
        mock_spatial.return_value = {"ok": True, "action": "click_spatial"}
        result = do("click button near search")
        mock_spatial.assert_called_once()
        args = mock_spatial.call_args
        # First arg is the spatial tuple
        assert args[0][0] == ("button", "near", "search")

    @patch("nexus.act.click._click_spatial")
    def test_click_field_below_username(self, mock_spatial, mock_native, mock_raw):
        mock_spatial.return_value = {"ok": True, "action": "click_spatial"}
        result = do("click field below Username")
        mock_spatial.assert_called_once()
        assert args[0][0] == ("field", "below", "Username") if (args := mock_spatial.call_args) else False

    @patch("nexus.act.click._click_spatial")
    def test_tap_button_near_search_synonym(self, mock_spatial, mock_native, mock_raw):
        """'tap button near search' → synonym → 'click button near search' → spatial."""
        mock_spatial.return_value = {"ok": True, "action": "click_spatial"}
        do("tap button near search")
        mock_spatial.assert_called_once()

    @patch("nexus.act.click._click_spatial")
    def test_click_button_in_top_right(self, mock_spatial, mock_native, mock_raw):
        mock_spatial.return_value = {"ok": True, "action": "click_spatial"}
        do("click button in top-right")
        mock_spatial.assert_called_once()
        args = mock_spatial.call_args
        assert args[0][0] == ("button", "region", "top-right")


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

    @patch("nexus.act.click.raw_input")
    def test_shift_click_coordinates(self, mock_input):
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("shift-click 100,200")
        mock_input.modifier_click.assert_called_once_with(100, 200, ["shift"])
        assert result["ok"] is True

    @patch("nexus.act.click.raw_input")
    def test_cmd_click_coordinates(self, mock_input):
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("cmd-click 300,400")
        mock_input.modifier_click.assert_called_once_with(300, 400, ["command"])

    @patch("nexus.act.click.raw_input")
    def test_option_click_coordinates(self, mock_input):
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("option-click 50,60")
        mock_input.modifier_click.assert_called_once_with(50, 60, ["option"])

    @patch("nexus.act.click.raw_input")
    def test_ctrl_click_coordinates(self, mock_input):
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("ctrl-click 10,20")
        mock_input.modifier_click.assert_called_once_with(10, 20, ["control"])

    @patch("nexus.act.click.raw_input")
    def test_command_click_coordinates(self, mock_input):
        mock_input.modifier_click.return_value = {"ok": True}
        result = do("command-click 10,20")
        mock_input.modifier_click.assert_called_once_with(10, 20, ["command"])

    @patch("nexus.act.click.raw_input")
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
        from nexus.act.parse import _normalize_action
        assert _normalize_action("shift-click Save") == "shift-click Save"
        assert _normalize_action("cmd-click Item") == "cmd-click Item"


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

    @patch("nexus.act.click.raw_input")
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

    @patch("nexus.act.click.raw_input")
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

    @patch("nexus.act.click.native")
    @patch("nexus.act.click.raw_input")
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
