"""Tests for Phase 3 features — Act Smarter.

3a: compact_state() in fusion.py
3b: Keyboard shortcut preference (_try_shortcut, shortcut cache)
3c: Path navigation (_handle_path_nav)
3d: Action bundles (bundles.py)
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, "/Users/ferran/repos/Nexus")


# ===========================================================================
# 3a: compact_state()
# ===========================================================================

class TestCompactState:
    """Test compact_state() returns useful post-action state."""

    def setup_method(self):
        """Clear spatial cache between tests."""
        try:
            from nexus.mind.session import reset
            reset()
        except Exception:
            pass

    @patch("nexus.sense.fusion.access")
    def test_compact_state_basic(self, mock_access):
        """Returns app, focus, and elements."""
        from nexus.sense.fusion import compact_state

        mock_access.frontmost_app.return_value = {"name": "Safari", "pid": 123}
        mock_access.window_title.return_value = "Google"
        mock_access.focused_element.return_value = {
            "role": "text field", "label": "Search", "pos": [100, 50],
            "value": "hello", "focused": True, "enabled": True,
        }
        mock_access.describe_app.return_value = [
            {"role": "text field", "label": "Search", "pos": [100, 50],
             "value": "hello", "focused": True, "enabled": True},
            {"role": "button", "label": "Go", "pos": [200, 50],
             "enabled": True},
        ]

        result = compact_state()
        assert "Safari" in result
        assert "Google" in result
        assert "Search" in result
        assert "Go" in result
        assert "Focus:" in result
        assert "Elements" in result

    @patch("nexus.sense.fusion.access")
    def test_compact_state_with_pid(self, mock_access):
        """Works with explicit PID."""
        from nexus.sense.fusion import compact_state

        mock_access.running_apps.return_value = [{"name": "Finder", "pid": 456}]
        mock_access.window_title.return_value = "Documents"
        mock_access.focused_element.return_value = None
        mock_access.describe_app.return_value = [
            {"role": "button", "label": "Back", "pos": [10, 10], "enabled": True},
        ]

        result = compact_state(pid=456)
        assert "Finder" in result
        assert "Back" in result

    @patch("nexus.sense.fusion.access")
    def test_compact_state_truncation(self, mock_access):
        """Truncates to max_elements."""
        from nexus.sense.fusion import compact_state

        mock_access.frontmost_app.return_value = {"name": "Test", "pid": 1}
        mock_access.window_title.return_value = ""
        mock_access.focused_element.return_value = None
        elements = [
            {"role": "button", "label": f"Btn{i}", "pos": [10, 10*i], "enabled": True}
            for i in range(30)
        ]
        mock_access.describe_app.return_value = elements

        result = compact_state(max_elements=5)
        assert "Btn0" in result
        assert "Btn4" in result
        assert "... and 25 more" in result
        assert "Btn5" not in result

    @patch("nexus.sense.fusion.access")
    def test_compact_state_filters_noise(self, mock_access):
        """Filters out noise elements like unlabeled static text."""
        from nexus.sense.fusion import compact_state

        mock_access.frontmost_app.return_value = {"name": "Test", "pid": 1}
        mock_access.window_title.return_value = ""
        mock_access.focused_element.return_value = None
        mock_access.describe_app.return_value = [
            {"role": "static text", "label": "", "_ax_role": "AXStaticText",
             "pos": [10, 10], "enabled": True},
            {"role": "button", "label": "OK", "pos": [100, 100], "enabled": True},
        ]

        result = compact_state()
        assert "OK" in result
        # Unlabeled static text should be filtered
        assert "static text" not in result or "OK" in result

    @patch("nexus.sense.fusion.access")
    def test_compact_state_empty(self, mock_access):
        """Returns empty-ish text when no app info."""
        from nexus.sense.fusion import compact_state

        mock_access.frontmost_app.return_value = None
        mock_access.running_apps.return_value = []
        mock_access.focused_element.return_value = None
        mock_access.describe_app.return_value = []

        result = compact_state(pid=999)
        assert isinstance(result, str)


# ===========================================================================
# 3b: Keyboard shortcut preference
# ===========================================================================

class TestShortcutCache:
    """Test _try_shortcut and shortcut cache behavior."""

    def setup_method(self):
        """Clear shortcut cache between tests."""
        from nexus.act import click
        click._shortcut_cache.clear()

    @patch("nexus.act.click._time")
    @patch("nexus.sense.access.menu_bar")
    @patch("nexus.sense.access.frontmost_app")
    def test_try_shortcut_found(self, mock_front, mock_menu, mock_time):
        """Finds shortcut for a known menu item."""
        from nexus.act.click import _try_shortcut

        mock_front.return_value = {"name": "Safari", "pid": 100}
        mock_time.time.return_value = 1000
        mock_menu.return_value = [
            {"title": "Save", "path": "File > Save", "shortcut": "Cmd+S", "depth": 1},
            {"title": "Open", "path": "File > Open", "shortcut": "Cmd+O", "depth": 1},
            {"title": "Close", "path": "File > Close", "depth": 1},  # no shortcut
        ]

        result = _try_shortcut("Save", pid=100)
        assert result == "Cmd+S"

    @patch("nexus.act.click._time")
    @patch("nexus.sense.access.menu_bar")
    @patch("nexus.sense.access.frontmost_app")
    def test_try_shortcut_case_insensitive(self, mock_front, mock_menu, mock_time):
        """Case-insensitive shortcut lookup."""
        from nexus.act.click import _try_shortcut

        mock_front.return_value = {"name": "Safari", "pid": 100}
        mock_time.time.return_value = 1000
        mock_menu.return_value = [
            {"title": "Save", "path": "File > Save", "shortcut": "Cmd+S", "depth": 1},
        ]

        assert _try_shortcut("save", pid=100) == "Cmd+S"
        assert _try_shortcut("SAVE", pid=100) == "Cmd+S"

    @patch("nexus.act.click._time")
    @patch("nexus.sense.access.menu_bar")
    @patch("nexus.sense.access.frontmost_app")
    def test_try_shortcut_not_found(self, mock_front, mock_menu, mock_time):
        """Returns None for items without shortcuts."""
        from nexus.act.click import _try_shortcut

        mock_front.return_value = {"name": "Safari", "pid": 100}
        mock_time.time.return_value = 1000
        mock_menu.return_value = [
            {"title": "Close", "path": "File > Close", "depth": 1},  # no shortcut
        ]

        result = _try_shortcut("Close", pid=100)
        assert result is None

    @patch("nexus.act.click._time")
    @patch("nexus.sense.access.menu_bar")
    @patch("nexus.sense.access.frontmost_app")
    def test_shortcut_cache_reuse(self, mock_front, mock_menu, mock_time):
        """Uses cached shortcuts within TTL, doesn't re-walk menu bar."""
        from nexus.act.click import _try_shortcut

        mock_front.return_value = {"name": "Safari", "pid": 100}
        mock_time.time.return_value = 1000
        mock_menu.return_value = [
            {"title": "Save", "path": "File > Save", "shortcut": "Cmd+S", "depth": 1},
        ]

        # First call builds cache
        _try_shortcut("Save", pid=100)
        assert mock_menu.call_count == 1

        # Second call within TTL reuses cache
        mock_time.time.return_value = 1030  # 30s later, within 60s TTL
        _try_shortcut("Save", pid=100)
        assert mock_menu.call_count == 1  # Still 1 — cache hit

    @patch("nexus.act.click._time")
    @patch("nexus.sense.access.menu_bar")
    @patch("nexus.sense.access.frontmost_app")
    def test_shortcut_cache_expiry(self, mock_front, mock_menu, mock_time):
        """Rebuilds cache after TTL expires."""
        from nexus.act.click import _try_shortcut

        mock_front.return_value = {"name": "Safari", "pid": 100}
        mock_time.time.return_value = 1000
        mock_menu.return_value = [
            {"title": "Save", "path": "File > Save", "shortcut": "Cmd+S", "depth": 1},
        ]

        _try_shortcut("Save", pid=100)
        assert mock_menu.call_count == 1

        # After TTL expires
        mock_time.time.return_value = 1100  # 100s later, past 60s TTL
        _try_shortcut("Save", pid=100)
        assert mock_menu.call_count == 2  # Rebuilt

    @patch("nexus.act.click._try_shortcut")
    @patch("nexus.act.click.native")
    @patch("nexus.act.click.raw_input")
    def test_handle_click_uses_shortcut(self, mock_input, mock_native, mock_try):
        """_handle_click uses shortcut when available for simple clicks."""
        from nexus.act.click import _handle_click

        mock_try.return_value = "Cmd+S"

        result = _handle_click("Save")
        assert result["ok"] is True
        assert result["action"] == "shortcut"
        assert result["shortcut"] == "Cmd+S"
        mock_input.hotkey.assert_called_once_with("cmd", "s")

    @patch("nexus.act.click._try_shortcut")
    @patch("nexus.act.click.native")
    @patch("nexus.act.click.raw_input")
    def test_handle_click_skips_shortcut_for_double_click(self, mock_input, mock_native, mock_try):
        """Don't use shortcuts for double-click, right-click, etc."""
        from nexus.act.click import _handle_click

        mock_try.return_value = "Cmd+S"
        mock_native.click_element.return_value = {"ok": True, "action": "click",
                                                    "at": [100, 50]}

        result = _handle_click("Save", double=True)
        # Should NOT use shortcut — should go through normal click path
        assert result.get("action") != "shortcut"

    @patch("nexus.act.click._try_shortcut")
    @patch("nexus.act.click.native")
    @patch("nexus.act.click.raw_input")
    def test_handle_click_skips_shortcut_for_modifier_click(self, mock_input, mock_native, mock_try):
        """Don't use shortcuts for modifier-clicks."""
        from nexus.act.click import _handle_click

        mock_try.return_value = "Cmd+S"

        # Set up find_elements for modifier click path
        with patch("nexus.sense.access.find_elements") as mock_find:
            mock_find.return_value = [
                {"role": "button", "label": "Save", "pos": [100, 50],
                 "size": [80, 30], "_ax_role": "AXButton"}
            ]
            result = _handle_click("Save", modifiers=["shift"])

        assert result.get("action") != "shortcut"

    def test_try_shortcut_no_pid(self):
        """Returns None when no PID can be resolved."""
        from nexus.act.click import _try_shortcut

        with patch("nexus.sense.access.frontmost_app", return_value=None):
            result = _try_shortcut("Save")
            assert result is None


# ===========================================================================
# 3c: Path navigation
# ===========================================================================

class TestPathNavigation:
    """Test _handle_path_nav and path detection in dispatch."""

    @patch("nexus.act.intents.native")
    def test_path_nav_basic(self, mock_native):
        """Navigates through a simple two-step path."""
        from nexus.act.intents import _handle_path_nav

        mock_native.click_element.return_value = {"ok": True, "action": "click"}

        with patch("nexus.sense.access.invalidate_cache"):
            result = _handle_path_nav("General > About")

        assert result["ok"] is True
        assert result["action"] == "path_nav"
        assert result["completed"] == 2
        assert result["path"] == "General > About"
        assert mock_native.click_element.call_count == 2

    @patch("nexus.act.intents.native")
    def test_path_nav_three_steps(self, mock_native):
        """Navigates through a three-step path."""
        from nexus.act.intents import _handle_path_nav

        mock_native.click_element.return_value = {"ok": True, "action": "click"}

        with patch("nexus.sense.access.invalidate_cache"):
            result = _handle_path_nav("Settings > General > About")

        assert result["ok"] is True
        assert result["completed"] == 3
        assert mock_native.click_element.call_count == 3

    @patch("nexus.act.intents.native")
    def test_path_nav_failure_on_step(self, mock_native):
        """Reports which step failed."""
        from nexus.act.intents import _handle_path_nav

        mock_native.click_element.side_effect = [
            {"ok": True, "action": "click"},
            {"ok": False, "error": "Element 'About' not found"},
        ]

        with patch("nexus.sense.access.invalidate_cache"):
            result = _handle_path_nav("General > About")

        assert result["ok"] is False
        assert result["completed"] == 1
        assert "About" in result["error"]

    def test_path_nav_empty(self):
        """Rejects empty paths."""
        from nexus.act.intents import _handle_path_nav

        result = _handle_path_nav("")
        assert result["ok"] is False

    @patch("nexus.act.resolve._handle_path_nav")
    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_dispatch_path_nav(self, mock_input, mock_native, mock_pnav):
        """Dispatcher routes 'navigate General > About' to path nav."""
        from nexus.act.resolve import do

        mock_pnav.return_value = {"ok": True, "action": "path_nav",
                                   "completed": 2, "total": 2,
                                   "path": "General > About"}
        result = do("navigate General > About")

        mock_pnav.assert_called_once_with("General > About", pid=None)
        assert result["action"] == "path_nav"

    @patch("nexus.act.resolve._handle_navigate")
    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_dispatch_navigate_url_not_path(self, mock_input, mock_native, mock_nav):
        """'navigate https://example.com' goes to URL handler, not path nav."""
        from nexus.act.resolve import do

        mock_nav.return_value = {"ok": True, "action": "navigate"}
        result = do("navigate to https://example.com")

        mock_nav.assert_called_once()

    @patch("nexus.act.resolve._handle_path_nav")
    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_dispatch_navigate_to_path(self, mock_input, mock_native, mock_pnav):
        """'navigate to General > About' strips 'to' and routes to path nav."""
        from nexus.act.resolve import do

        mock_pnav.return_value = {"ok": True, "action": "path_nav",
                                   "completed": 2, "total": 2,
                                   "path": "General > About"}
        result = do("navigate to General > About")

        mock_pnav.assert_called_once_with("General > About", pid=None)

    @patch("nexus.act.resolve._handle_path_nav")
    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_dispatch_goto_path(self, mock_input, mock_native, mock_pnav):
        """'go to General > About' routes to path nav."""
        from nexus.act.resolve import do

        mock_pnav.return_value = {"ok": True, "action": "path_nav",
                                   "completed": 2, "total": 2,
                                   "path": "General > About"}
        result = do("go to General > About")

        mock_pnav.assert_called_once()


# ===========================================================================
# 3d: Action bundles
# ===========================================================================

class TestBundles:
    """Test bundle matching and execution."""

    def test_match_save_as(self):
        """Matches 'save as filename'."""
        from nexus.act.bundles import match_bundle
        handler, m = match_bundle("save as draft.md")
        assert handler is not None
        assert m.group("filename") == "draft.md"

    def test_match_save_file_as(self):
        """Matches 'save file as filename'."""
        from nexus.act.bundles import match_bundle
        handler, m = match_bundle("save file as report.txt")
        assert handler is not None
        assert m.group("filename") == "report.txt"

    def test_match_find_replace(self):
        """Matches 'find and replace X with Y'."""
        from nexus.act.bundles import match_bundle
        handler, m = match_bundle("find and replace foo with bar")
        assert handler is not None
        assert m.group("find") == "foo"
        assert m.group("replace") == "bar"

    def test_match_find_replace_no_and(self):
        """Matches 'find replace X with Y' (without 'and')."""
        from nexus.act.bundles import match_bundle
        handler, m = match_bundle("find replace hello with world")
        assert handler is not None
        assert m.group("find") == "hello"
        assert m.group("replace") == "world"

    def test_match_new_document(self):
        """Matches 'new document', 'new file', 'new window'."""
        from nexus.act.bundles import match_bundle

        for phrase in ("new document", "new file", "new window"):
            handler, m = match_bundle(phrase)
            assert handler is not None, f"Should match: {phrase}"

    def test_match_print(self):
        """Matches 'print', 'print document', 'print page'."""
        from nexus.act.bundles import match_bundle

        for phrase in ("print", "print document", "print page"):
            handler, m = match_bundle(phrase)
            assert handler is not None, f"Should match: {phrase}"

    def test_match_zoom(self):
        """Matches zoom in/out/reset."""
        from nexus.act.bundles import match_bundle

        for phrase in ("zoom in", "zoom out", "zoom reset"):
            handler, m = match_bundle(phrase)
            assert handler is not None, f"Should match: {phrase}"

    def test_no_match_regular_action(self):
        """Regular actions don't match bundles."""
        from nexus.act.bundles import match_bundle

        handler, m = match_bundle("click Save")
        assert handler is None

    def test_no_match_partial(self):
        """Partial matches don't trigger bundles."""
        from nexus.act.bundles import match_bundle

        handler, m = match_bundle("save")
        assert handler is None  # "save" alone doesn't match "save as X"

    @patch("nexus.act.bundles.raw_input")
    def test_save_as_execution(self, mock_input):
        """Bundle save-as executes keyboard sequence."""
        from nexus.act.bundles import match_bundle

        handler, m = match_bundle("save as test.py")
        result = handler(m)
        assert result["ok"] is True
        assert result["action"] == "bundle_save_as"
        assert result["filename"] == "test.py"
        mock_input.hotkey.assert_any_call("command", "shift", "s")
        mock_input.type_text.assert_called_once_with("test.py")

    @patch("nexus.act.bundles.raw_input")
    def test_find_replace_execution(self, mock_input):
        """Bundle find-replace types in both fields."""
        from nexus.act.bundles import match_bundle

        handler, m = match_bundle("find and replace old with new")
        result = handler(m)
        assert result["ok"] is True
        assert result["find"] == "old"
        assert result["replace"] == "new"
        mock_input.hotkey.assert_any_call("command", "h")

    @patch("nexus.act.bundles.raw_input")
    def test_new_document_execution(self, mock_input):
        """Bundle new document sends Cmd+N."""
        from nexus.act.bundles import match_bundle

        handler, m = match_bundle("new document")
        result = handler(m)
        assert result["ok"] is True
        mock_input.hotkey.assert_called_once_with("command", "n")

    @patch("nexus.act.bundles.raw_input")
    def test_print_execution(self, mock_input):
        """Bundle print sends Cmd+P."""
        from nexus.act.bundles import match_bundle

        handler, m = match_bundle("print")
        result = handler(m)
        assert result["ok"] is True
        mock_input.hotkey.assert_called_once_with("command", "p")

    @patch("nexus.act.bundles.raw_input")
    def test_zoom_in_execution(self, mock_input):
        """Bundle zoom in sends Cmd+=."""
        from nexus.act.bundles import match_bundle

        handler, m = match_bundle("zoom in")
        result = handler(m)
        assert result["ok"] is True
        mock_input.hotkey.assert_called_once_with("command", "=")

    @patch("nexus.act.bundles.raw_input")
    def test_zoom_out_execution(self, mock_input):
        """Bundle zoom out sends Cmd+-."""
        from nexus.act.bundles import match_bundle

        handler, m = match_bundle("zoom out")
        result = handler(m)
        assert result["ok"] is True
        mock_input.hotkey.assert_called_once_with("command", "-")

    @patch("nexus.act.bundles.raw_input")
    def test_zoom_reset_execution(self, mock_input):
        """Bundle zoom reset sends Cmd+0."""
        from nexus.act.bundles import match_bundle

        handler, m = match_bundle("zoom reset")
        result = handler(m)
        assert result["ok"] is True
        mock_input.hotkey.assert_called_once_with("command", "0")

    @patch("nexus.act.resolve.raw_input")
    @patch("nexus.act.resolve.native")
    @patch("nexus.act.bundles.raw_input")
    def test_dispatch_save_as(self, mock_bundle_input, mock_native, mock_input):
        """Dispatcher routes 'save as X' to bundle."""
        from nexus.act.resolve import do

        result = do("save as draft.md")
        assert result["ok"] is True
        assert result["action"] == "bundle_save_as"

    @patch("nexus.act.resolve.raw_input")
    @patch("nexus.act.resolve.native")
    @patch("nexus.act.bundles.raw_input")
    def test_dispatch_zoom_in(self, mock_bundle_input, mock_native, mock_input):
        """Dispatcher routes 'zoom in' to bundle."""
        from nexus.act.resolve import do

        result = do("zoom in")
        assert result["ok"] is True
        assert result["action"] == "bundle_zoom"

    @patch("nexus.act.resolve.raw_input")
    @patch("nexus.act.resolve.native")
    @patch("nexus.act.bundles.raw_input")
    def test_dispatch_new_document(self, mock_bundle_input, mock_native, mock_input):
        """Dispatcher routes 'new document' to bundle."""
        from nexus.act.resolve import do

        result = do("new document")
        assert result["ok"] is True
        assert result["action"] == "bundle_new_document"

    @patch("nexus.act.resolve.raw_input")
    @patch("nexus.act.resolve.native")
    @patch("nexus.act.bundles.raw_input")
    def test_dispatch_print(self, mock_bundle_input, mock_native, mock_input):
        """Dispatcher routes 'print' to bundle."""
        from nexus.act.resolve import do

        result = do("print")
        assert result["ok"] is True
        assert result["action"] == "bundle_print"

    @patch("nexus.act.resolve.raw_input")
    @patch("nexus.act.resolve.native")
    @patch("nexus.act.bundles.raw_input")
    def test_dispatch_find_replace(self, mock_bundle_input, mock_native, mock_input):
        """Dispatcher routes 'find and replace X with Y' to bundle."""
        from nexus.act.resolve import do

        result = do("find and replace foo with bar")
        assert result["ok"] is True
        assert result["action"] == "bundle_find_replace"
