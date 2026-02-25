"""Tests for nexus.act.window — window management intents."""

import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/Users/ferran/repos/Nexus")

from nexus.act.window import (
    _handle_tile, _handle_move, _handle_minimize, _handle_restore,
    _handle_resize, _handle_fullscreen, _list_windows,
)
from nexus.act.resolve import do


# ===========================================================================
# TestHandleTile
# ===========================================================================


@patch("nexus.act.window.native")
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


@patch("nexus.act.window.native")
class TestHandleMove:
    """Tests for _handle_move — window positioning."""

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_left(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_right(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window right")
        mock_native.move_window.assert_called_once_with(None, x=960, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 2560, "height": 1440})
    def test_move_window_left_retina(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=1280, h=1415, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_safari_left(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("Safari left")
        mock_native.move_window.assert_called_once_with("safari", x=0, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_center(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window center")
        mock_native.move_window.assert_called_once_with(None, x=480, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_full(self, mock_screen, mock_native):
        mock_native.maximize_window.return_value = {"ok": True}
        _handle_move("window full")
        mock_native.maximize_window.assert_called_once_with(None)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_unknown_direction(self, mock_screen, mock_native):
        result = _handle_move("window diagonal")
        assert result["ok"] is False
        assert "Unknown position" in result["error"]

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_alias_l(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window l")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_alias_r(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window r")
        mock_native.move_window.assert_called_once_with(None, x=960, y=25, w=960, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_maximize_alias(self, mock_screen, mock_native):
        mock_native.maximize_window.return_value = {"ok": True}
        _handle_move("window maximize")
        mock_native.maximize_window.assert_called_once_with(None)

    # --- Top/bottom halves ---
    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_top(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window top")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=1920, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_bottom(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window bottom")
        mock_native.move_window.assert_called_once_with(None, x=0, y=552, w=1920, h=527, window_index=1)

    # --- Quarters ---
    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_top_left(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window top-left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_top_right(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window top-right")
        mock_native.move_window.assert_called_once_with(None, x=960, y=25, w=960, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_bottom_left(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window bottom-left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=552, w=960, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_bottom_right(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window bottom-right")
        mock_native.move_window.assert_called_once_with(None, x=960, y=552, w=960, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_topleft_joined(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window topleft")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=527, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_bottomright_joined(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window bottomright")
        mock_native.move_window.assert_called_once_with(None, x=960, y=552, w=960, h=527, window_index=1)

    # --- Thirds ---
    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_left_third(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window left-third")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=640, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_center_third(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window center-third")
        mock_native.move_window.assert_called_once_with(None, x=640, y=25, w=640, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_right_third(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window right-third")
        mock_native.move_window.assert_called_once_with(None, x=1280, y=25, w=640, h=1055, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_middle_third(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window middle-third")
        mock_native.move_window.assert_called_once_with(None, x=640, y=25, w=640, h=1055, window_index=1)

    # --- Coordinate move ---
    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_safari_to_coordinates(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("Safari to 100,200")
        mock_native.move_window.assert_called_once_with("Safari", x=100, y=200, window_index=1)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_to_coordinates(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window to 100,200")
        mock_native.move_window.assert_called_once_with(None, x=100, y=200, window_index=1)

    # --- Window index ---
    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_move_window_2_left(self, mock_screen, mock_native):
        mock_native.move_window.return_value = {"ok": True}
        _handle_move("window 2 left")
        mock_native.move_window.assert_called_once_with(None, x=0, y=25, w=960, h=1055, window_index=2)


# ===========================================================================
# TestHandleMinimize
# ===========================================================================


@patch("nexus.act.window.native")
class TestHandleMinimize:
    """Tests for _handle_minimize — minimize windows."""

    def test_minimize_no_args(self, mock_native):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("")
        mock_native.minimize_window.assert_called_once()

    def test_minimize_app_name(self, mock_native):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("Safari")
        mock_native.minimize_window.assert_called_once_with(app_name="Safari")

    def test_minimize_window_keyword(self, mock_native):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("window")
        mock_native.minimize_window.assert_called_once()

    def test_minimize_window_2(self, mock_native):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("window 2")
        mock_native.minimize_window.assert_called_once_with(app_name=None, window_index=2)

    def test_minimize_window_2_of_safari(self, mock_native):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("window 2 of Safari")
        mock_native.minimize_window.assert_called_once_with(app_name="safari", window_index=2)

    def test_minimize_window_3(self, mock_native):
        mock_native.minimize_window.return_value = {"ok": True}
        _handle_minimize("window 3")
        mock_native.minimize_window.assert_called_once_with(app_name=None, window_index=3)


# ===========================================================================
# TestHandleRestore
# ===========================================================================


@patch("nexus.act.window.native")
class TestHandleRestore:
    """Tests for _handle_restore — unminimize windows."""

    def test_restore_no_args(self, mock_native):
        mock_native.unminimize_window.return_value = {"ok": True}
        _handle_restore("")
        mock_native.unminimize_window.assert_called_once()

    def test_restore_app_name(self, mock_native):
        mock_native.unminimize_window.return_value = {"ok": True}
        _handle_restore("Safari")
        mock_native.unminimize_window.assert_called_once_with(app_name="Safari")

    def test_restore_window_keyword(self, mock_native):
        mock_native.unminimize_window.return_value = {"ok": True}
        _handle_restore("window")
        mock_native.unminimize_window.assert_called_once()

    def test_restore_chrome(self, mock_native):
        mock_native.unminimize_window.return_value = {"ok": True}
        _handle_restore("Chrome")
        mock_native.unminimize_window.assert_called_once_with(app_name="Chrome")


# ===========================================================================
# TestHandleResize
# ===========================================================================


@patch("nexus.act.window.native")
class TestHandleResize:
    """Tests for _handle_resize — resize windows."""

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_absolute(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 800x600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_no_to(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("800x600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_with_X(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 800X600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_app_name(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("Safari to 1200x800")
        mock_native.resize_window.assert_called_once_with(app_name="Safari", w=1200, h=800)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_percentage_50(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 50%")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=960, h=527)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_percentage_75(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 75%")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=1440, h=791)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_app_percentage(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("Safari to 75%")
        mock_native.resize_window.assert_called_once_with(app_name="Safari", w=1440, h=791)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_window_keyword(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("window to 800x600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_window_2(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("window 2 to 800x600")
        mock_native.resize_window.assert_called_once_with(w=800, h=600, window_index=2)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_with_comma(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 800,600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_with_star(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 800*600")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=800, h=600)

    def test_resize_empty_fails(self, mock_native):
        result = _handle_resize("")
        assert result["ok"] is False

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_unparseable_fails(self, mock_screen, mock_native):
        result = _handle_resize("to banana")
        assert result["ok"] is False

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_percentage_100(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 100%")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=1920, h=1055)

    @patch("nexus.act.input.screen_size", return_value={"width": 1920, "height": 1080})
    def test_resize_percentage_25(self, mock_screen, mock_native):
        mock_native.resize_window.return_value = {"ok": True}
        _handle_resize("to 25%")
        mock_native.resize_window.assert_called_once_with(app_name=None, w=480, h=263)


# ===========================================================================
# TestHandleFullscreen
# ===========================================================================


@patch("nexus.act.window.native")
class TestHandleFullscreen:
    """Tests for _handle_fullscreen — true macOS fullscreen toggle."""

    def test_fullscreen_no_args(self, mock_native):
        mock_native.fullscreen_window.return_value = {"ok": True}
        _handle_fullscreen("")
        mock_native.fullscreen_window.assert_called_once()

    def test_fullscreen_app_name(self, mock_native):
        mock_native.fullscreen_window.return_value = {"ok": True}
        _handle_fullscreen("Safari")
        mock_native.fullscreen_window.assert_called_once_with(app_name="Safari")

    def test_fullscreen_window_keyword(self, mock_native):
        mock_native.fullscreen_window.return_value = {"ok": True}
        _handle_fullscreen("window")
        mock_native.fullscreen_window.assert_called_once()

    def test_fullscreen_chrome(self, mock_native):
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


# ===========================================================================
# TestListWindows
# ===========================================================================


class TestListWindows:
    """Tests for _list_windows and routing."""

    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_list_windows_routed(self, mock_raw_input, mock_native):
        with patch("nexus.act.resolve._list_windows", return_value={"ok": True}) as mock_lw:
            do("list windows")
            mock_lw.assert_called_once()

    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_get_windows_routed(self, mock_raw_input, mock_native):
        with patch("nexus.act.resolve._list_windows", return_value={"ok": True}) as mock_lw:
            do("get windows")
            mock_lw.assert_called_once()

    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_windows_routed(self, mock_raw_input, mock_native):
        with patch("nexus.act.resolve._list_windows", return_value={"ok": True}) as mock_lw:
            do("windows")
            mock_lw.assert_called_once()

    @patch("nexus.act.resolve.native")
    @patch("nexus.act.resolve.raw_input")
    def test_show_windows_routed(self, mock_raw_input, mock_native):
        with patch("nexus.act.resolve._list_windows", return_value={"ok": True}) as mock_lw:
            do("show windows")
            mock_lw.assert_called_once()

    @patch("nexus.sense.access.windows", return_value=[])
    def test_list_windows_empty(self, mock_wins):
        result = _list_windows()
        assert result["ok"] is True
        assert "No windows" in result["text"]

    @patch("nexus.sense.access.windows", return_value=[
        {"app": "Safari", "title": "Google", "pid": 100, "bounds": {"x": 0, "y": 25, "w": 1920, "h": 1055}},
        {"app": "Terminal", "title": "zsh", "pid": 200, "bounds": {"x": 960, "y": 25, "w": 960, "h": 1055}},
    ])
    def test_list_windows_with_results(self, mock_wins):
        result = _list_windows()
        assert result["ok"] is True
        assert result["count"] == 2
        assert "Safari" in result["text"]
        assert "Terminal" in result["text"]
        assert "1920x1055" in result["text"]

    @patch("nexus.sense.access.windows", return_value=[
        {"app": "Finder", "title": "", "pid": 300, "bounds": {"x": 0, "y": 0, "w": 800, "h": 600}},
    ])
    def test_list_windows_no_title(self, mock_wins):
        result = _list_windows()
        assert result["ok"] is True
        assert "Finder" in result["text"]
        # No title → no dash
        assert '\u2014' not in result["text"]
