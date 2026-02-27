"""Tests for focus isolation — ensure_focus and _is_focus_exempt."""

import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/Users/ferran/repos/Nexus")


# ===========================================================================
# ensure_focus
# ===========================================================================


class TestEnsureFocus:
    """Tests for native.ensure_focus — pre-action focus guarantee."""

    def test_noop_when_pid_none(self):
        from nexus.act.native import ensure_focus
        assert ensure_focus(None) is True

    @patch("nexus.act.native.frontmost_app", return_value={"pid": 123, "name": "Safari"})
    def test_noop_when_already_focused(self, mock_front):
        from nexus.act.native import ensure_focus
        assert ensure_focus(123) is True
        # Should NOT import NSWorkspace — fast path
        mock_front.assert_called_once()

    @patch("nexus.act.native.invalidate_cache")
    @patch("nexus.act.native.frontmost_app", return_value={"pid": 999, "name": "Code"})
    def test_activates_when_wrong_app(self, mock_front, mock_invalidate):
        from nexus.act.native import ensure_focus

        mock_app = MagicMock()
        mock_app.processIdentifier.return_value = 123

        mock_ws = MagicMock()
        mock_ws.runningApplications.return_value = [mock_app]

        with patch("AppKit.NSWorkspace") as mock_NSWorkspace, \
             patch("nexus.act.native._time.sleep"):
            mock_NSWorkspace.sharedWorkspace.return_value = mock_ws
            result = ensure_focus(123)

        assert result is True
        mock_app.activateWithOptions_.assert_called_once()
        mock_invalidate.assert_called_once()

    @patch("nexus.act.native.frontmost_app", return_value={"pid": 999, "name": "Code"})
    def test_returns_false_when_app_not_found(self, mock_front):
        from nexus.act.native import ensure_focus

        mock_ws = MagicMock()
        mock_ws.runningApplications.return_value = []

        with patch("AppKit.NSWorkspace") as mock_NSWorkspace:
            mock_NSWorkspace.sharedWorkspace.return_value = mock_ws
            result = ensure_focus(99999)

        assert result is False

    @patch("nexus.act.native.frontmost_app", return_value=None)
    def test_activates_when_no_frontmost(self, mock_front):
        """If frontmost_app returns None, should try to activate."""
        from nexus.act.native import ensure_focus

        mock_app = MagicMock()
        mock_app.processIdentifier.return_value = 42

        mock_ws = MagicMock()
        mock_ws.runningApplications.return_value = [mock_app]

        with patch("AppKit.NSWorkspace") as mock_NSWorkspace, \
             patch("nexus.act.native._time.sleep"), \
             patch("nexus.act.native.invalidate_cache"):
            mock_NSWorkspace.sharedWorkspace.return_value = mock_ws
            result = ensure_focus(42)

        assert result is True
        mock_app.activateWithOptions_.assert_called_once()


# ===========================================================================
# _is_focus_exempt
# ===========================================================================


class TestIsFocusExempt:
    """Tests for _is_focus_exempt — skip focus for getters/navigators."""

    def test_getters_are_exempt(self):
        from nexus.act.resolve import _is_focus_exempt
        assert _is_focus_exempt("get clipboard") is True
        assert _is_focus_exempt("read table") is True
        assert _is_focus_exempt("get url") is True
        assert _is_focus_exempt("get tabs") is True

    def test_focus_managers_are_exempt(self):
        from nexus.act.resolve import _is_focus_exempt
        assert _is_focus_exempt("open safari") is True
        assert _is_focus_exempt("switch to mail") is True
        assert _is_focus_exempt("activate finder") is True

    def test_cdp_actions_are_exempt(self):
        from nexus.act.resolve import _is_focus_exempt
        assert _is_focus_exempt("navigate https://google.com") is True
        assert _is_focus_exempt("js document.title") is True
        assert _is_focus_exempt("new tab") is True
        assert _is_focus_exempt("close tab") is True
        assert _is_focus_exempt("switch tab 2") is True

    def test_observe_and_hover_are_exempt(self):
        from nexus.act.resolve import _is_focus_exempt
        assert _is_focus_exempt("hover save") is True
        assert _is_focus_exempt("observe start") is True

    def test_mutating_actions_are_not_exempt(self):
        from nexus.act.resolve import _is_focus_exempt
        assert _is_focus_exempt("click save") is False
        assert _is_focus_exempt("type hello") is False
        assert _is_focus_exempt("press cmd+s") is False
        assert _is_focus_exempt("select all") is False
        assert _is_focus_exempt("copy") is False
        assert _is_focus_exempt("paste") is False
        assert _is_focus_exempt("scroll down") is False
        assert _is_focus_exempt("fill name=john") is False
        assert _is_focus_exempt("drag icon to trash") is False


# ===========================================================================
# Integration: do() calls ensure_focus
# ===========================================================================


@patch("nexus.act.resolve.raw_input")
@patch("nexus.act.resolve.native")
class TestDoCallsEnsureFocus:
    """Integration: do() calls ensure_focus for raw-input actions with pid."""

    def test_calls_ensure_focus_for_copy(self, mock_native, mock_raw_input):
        from nexus.act.resolve import do
        do("copy", pid=123)
        mock_native.ensure_focus.assert_called_once_with(123)

    def test_calls_ensure_focus_for_press(self, mock_native, mock_raw_input):
        from nexus.act.resolve import do
        mock_native.ensure_focus.return_value = True
        # press goes through verb dispatch which calls _handle_press
        # but the mock native means it won't actually execute
        do("press cmd+s", pid=123)
        mock_native.ensure_focus.assert_called_once_with(123)

    def test_calls_ensure_focus_for_paste(self, mock_native, mock_raw_input):
        from nexus.act.resolve import do
        do("paste", pid=123)
        mock_native.ensure_focus.assert_called_once_with(123)

    def test_skips_ensure_focus_when_no_pid(self, mock_native, mock_raw_input):
        from nexus.act.resolve import do
        do("copy")
        mock_native.ensure_focus.assert_not_called()

    def test_skips_ensure_focus_for_getter(self, mock_native, mock_raw_input):
        from nexus.act.resolve import do
        mock_native.clipboard_read.return_value = {"ok": True, "text": "hi"}
        do("get clipboard", pid=123)
        mock_native.ensure_focus.assert_not_called()

    def test_skips_ensure_focus_for_open(self, mock_native, mock_raw_input):
        from nexus.act.resolve import do
        mock_native.launch_app.return_value = {"ok": True, "action": "launch"}
        do("open Safari", pid=123)
        mock_native.ensure_focus.assert_not_called()
