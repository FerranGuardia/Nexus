"""Tests for nexus.via — Via route recording, replay, and management."""

import json
import shutil
import tempfile
import time
from collections import deque
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest


# ---------------------------------------------------------------------------
# DB helpers — each test class gets a fresh temp DB
# ---------------------------------------------------------------------------

def _reset_db():
    import nexus.mind.db as db
    tmpdir = tempfile.mkdtemp()
    db.close()
    db.DB_DIR = Path(tmpdir)
    db.DB_PATH = Path(tmpdir) / "nexus.db"
    db._conn = None
    return tmpdir


def _teardown_db(tmpdir):
    import nexus.mind.db as db
    db.close()
    db.DB_DIR = Path.home() / ".nexus"
    db.DB_PATH = db.DB_DIR / "nexus.db"
    db._conn = None
    shutil.rmtree(tmpdir, ignore_errors=True)


def _reset_recording():
    """Clear Via recording state."""
    import nexus.via.recorder as rec
    rec._recording = None
    import nexus.via.tap as tap
    tap._event_buffer.clear()
    tap._recording_start = None
    tap._thread = None
    tap._runloop = None
    tap._stop_flag.clear()


# ===========================================================================
# tap.py — Key code mapping + helpers
# ===========================================================================

class TestKeyNames:

    def test_basic_letters(self):
        from nexus.via.tap import _KEY_NAMES
        assert _KEY_NAMES[0] == "a"
        assert _KEY_NAMES[1] == "s"
        assert _KEY_NAMES[6] == "z"

    def test_special_keys(self):
        from nexus.via.tap import _KEY_NAMES
        assert _KEY_NAMES[36] == "return"
        assert _KEY_NAMES[48] == "tab"
        assert _KEY_NAMES[49] == "space"
        assert _KEY_NAMES[51] == "delete"
        assert _KEY_NAMES[53] == "escape"

    def test_arrow_keys(self):
        from nexus.via.tap import _KEY_NAMES
        assert _KEY_NAMES[123] == "left"
        assert _KEY_NAMES[124] == "right"
        assert _KEY_NAMES[125] == "down"
        assert _KEY_NAMES[126] == "up"


class TestModifiers:

    def test_no_modifiers(self):
        from nexus.via.tap import _get_modifiers
        result = _get_modifiers(0)
        assert result == {"cmd": False, "shift": False, "ctrl": False, "opt": False}

    def test_cmd_modifier(self):
        from nexus.via.tap import _get_modifiers, kCGEventFlagMaskCommand
        result = _get_modifiers(kCGEventFlagMaskCommand)
        assert result["cmd"] is True
        assert result["shift"] is False

    def test_shift_modifier(self):
        from nexus.via.tap import _get_modifiers, kCGEventFlagMaskShift
        result = _get_modifiers(kCGEventFlagMaskShift)
        assert result["shift"] is True

    def test_combined_modifiers(self):
        from nexus.via.tap import (
            _get_modifiers, kCGEventFlagMaskCommand, kCGEventFlagMaskShift,
        )
        result = _get_modifiers(kCGEventFlagMaskCommand | kCGEventFlagMaskShift)
        assert result["cmd"] is True
        assert result["shift"] is True
        assert result["ctrl"] is False
        assert result["opt"] is False


class TestKeyChar:

    def test_simple_key(self):
        from nexus.via.tap import _key_char
        assert _key_char(0, {"cmd": False, "shift": False, "ctrl": False, "opt": False}) == "a"

    def test_cmd_key(self):
        from nexus.via.tap import _key_char
        assert _key_char(1, {"cmd": True, "shift": False, "ctrl": False, "opt": False}) == "cmd+s"

    def test_cmd_shift_key(self):
        from nexus.via.tap import _key_char
        assert _key_char(1, {"cmd": True, "shift": True, "ctrl": False, "opt": False}) == "cmd+shift+s"

    def test_unknown_key(self):
        from nexus.via.tap import _key_char
        result = _key_char(999, {"cmd": False, "shift": False, "ctrl": False, "opt": False})
        assert result == "key999"


class TestFindWindowAt:

    @patch("nexus.via.tap.CGWindowListCopyWindowInfo")
    def test_finds_matching_window(self, mock_wl):
        from nexus.via.tap import _find_window_at
        mock_wl.return_value = [
            {
                "kCGWindowOwnerPID": 100,
                "kCGWindowBounds": {"X": 100, "Y": 50, "Width": 800, "Height": 600},
            }
        ]
        result = _find_window_at(400, 300, pid=100)
        assert result == {"x": 100, "y": 50, "w": 800, "h": 600}

    @patch("nexus.via.tap.CGWindowListCopyWindowInfo")
    def test_no_matching_pid(self, mock_wl):
        from nexus.via.tap import _find_window_at
        mock_wl.return_value = [
            {
                "kCGWindowOwnerPID": 200,
                "kCGWindowBounds": {"X": 100, "Y": 50, "Width": 800, "Height": 600},
            }
        ]
        result = _find_window_at(400, 300, pid=100)
        assert result is None

    @patch("nexus.via.tap.CGWindowListCopyWindowInfo")
    def test_point_outside_window(self, mock_wl):
        from nexus.via.tap import _find_window_at
        mock_wl.return_value = [
            {
                "kCGWindowOwnerPID": 100,
                "kCGWindowBounds": {"X": 100, "Y": 50, "Width": 800, "Height": 600},
            }
        ]
        result = _find_window_at(50, 50, pid=100)  # outside
        assert result is None

    @patch("nexus.via.tap.CGWindowListCopyWindowInfo")
    def test_no_windows(self, mock_wl):
        from nexus.via.tap import _find_window_at
        mock_wl.return_value = []
        result = _find_window_at(400, 300)
        assert result is None


class TestHitTestAX:

    @patch("nexus.sense.access.element_at_position")
    def test_returns_role_label(self, mock_eap):
        from nexus.via.tap import _hit_test_ax
        mock_eap.return_value = {"_ax_role": "AXButton", "label": "Save"}
        role, label = _hit_test_ax(100, 200, pid=42)
        assert role == "AXButton"
        assert label == "Save"

    @patch("nexus.sense.access.element_at_position")
    def test_returns_none_on_miss(self, mock_eap):
        from nexus.via.tap import _hit_test_ax
        mock_eap.return_value = None
        role, label = _hit_test_ax(100, 200)
        assert role is None
        assert label is None


class TestTapLifecycle:

    def test_not_tapping_initially(self):
        _reset_recording()
        from nexus.via.tap import is_tapping
        assert not is_tapping()

    def test_drain_empty(self):
        _reset_recording()
        from nexus.via.tap import drain_events
        assert drain_events() == []

    @patch("nexus.via.tap.CGEventTapCreate", return_value=None)
    def test_start_tap_fails_gracefully(self, mock_create):
        _reset_recording()
        from nexus.via.tap import start_tap, is_tapping
        result = start_tap()
        assert result is False
        assert not is_tapping()


# ===========================================================================
# recorder.py — Recording orchestration
# ===========================================================================

class TestSlugify:

    def test_basic_slug(self):
        from nexus.via.recorder import _slugify
        assert _slugify("Login to Gmail") == "login-to-gmail"

    def test_special_chars(self):
        from nexus.via.recorder import _slugify
        assert _slugify("File: Open & Save!") == "file-open-save"

    def test_empty(self):
        from nexus.via.recorder import _slugify
        assert _slugify("") == "unnamed"


class TestRecordingStartStop:

    def setup_method(self):
        self.tmpdir = _reset_db()
        _reset_recording()

    def teardown_method(self):
        _teardown_db(self.tmpdir)
        _reset_recording()

    @patch("nexus.via.tap.start_tap", return_value=True)
    def test_start_recording(self, mock_start):
        from nexus.via.recorder import start_recording, is_recording
        result = start_recording("test route")
        assert result["ok"] is True
        assert result["id"] == "test-route"
        assert is_recording()

    @patch("nexus.via.tap.start_tap", return_value=True)
    def test_double_start_fails(self, mock_start):
        from nexus.via.recorder import start_recording
        start_recording("first")
        result = start_recording("second")
        assert result["ok"] is False
        assert "Already recording" in result["error"]

    @patch("nexus.via.tap.start_tap", return_value=False)
    def test_start_fails_without_tap(self, mock_start):
        from nexus.via.recorder import start_recording, is_recording
        result = start_recording("test")
        assert result["ok"] is False
        assert "CGEventTap" in result["error"]
        assert not is_recording()

    @patch("nexus.via.tap.stop_tap", return_value=[])
    @patch("nexus.via.tap.start_tap", return_value=True)
    def test_stop_recording_empty(self, mock_start, mock_stop):
        from nexus.via.recorder import start_recording, stop_recording, is_recording
        start_recording("empty")
        result = stop_recording()
        assert result["ok"] is True
        assert result["steps"] == 0
        assert not is_recording()

    @patch("nexus.via.tap.stop_tap")
    @patch("nexus.via.tap.start_tap", return_value=True)
    def test_stop_recording_with_events(self, mock_start, mock_stop):
        mock_stop.return_value = [
            {
                "event_type": "click", "ts_offset_ms": 0,
                "x": 400, "y": 300, "button": "left",
                "rel_x": 0.5, "rel_y": 0.4,
                "ax_role": "AXButton", "ax_label": "Sign In",
                "pid": 100, "app_name": "Chrome",
            },
            {
                "event_type": "key", "ts_offset_ms": 1000,
                "key_code": 36, "key_char": "return",
                "pid": 100, "app_name": "Chrome",
            },
        ]
        from nexus.via.recorder import start_recording, stop_recording
        start_recording("login")
        result = stop_recording()
        assert result["ok"] is True
        assert result["steps"] == 2
        assert "1 clicks" in result.get("summary", "")
        assert "1 keys" in result.get("summary", "")

    def test_stop_without_start(self):
        from nexus.via.recorder import stop_recording
        result = stop_recording()
        assert result["ok"] is False
        assert "Not recording" in result["error"]


class TestRecordingStorage:

    def setup_method(self):
        self.tmpdir = _reset_db()
        _reset_recording()

    def teardown_method(self):
        _teardown_db(self.tmpdir)
        _reset_recording()

    @patch("nexus.via.tap.stop_tap")
    @patch("nexus.via.tap.start_tap", return_value=True)
    def test_events_stored_in_db(self, mock_start, mock_stop):
        mock_stop.return_value = [
            {
                "event_type": "click", "ts_offset_ms": 0,
                "x": 400, "y": 300, "button": "left",
                "rel_x": 0.5, "rel_y": 0.4,
                "window_x": 100, "window_y": 50, "window_w": 800, "window_h": 600,
                "ax_role": "AXButton", "ax_label": "OK",
                "modifiers": {"cmd": False, "shift": False, "ctrl": False, "opt": False},
                "pid": 100, "app_name": "Finder",
            },
        ]
        from nexus.via.recorder import start_recording, stop_recording, get_recording
        start_recording("store-test")
        stop_recording()

        route = get_recording("store-test")
        assert route is not None
        assert route["step_count"] == 1
        steps = route["steps"]
        assert len(steps) == 1
        assert steps[0]["event_type"] == "click"
        assert steps[0]["ax_label"] == "OK"
        assert steps[0]["rel_x"] == 0.5
        assert steps[0]["modifiers"] == {"cmd": False, "shift": False, "ctrl": False, "opt": False}

    @patch("nexus.via.tap.stop_tap", return_value=[])
    @patch("nexus.via.tap.start_tap", return_value=True)
    def test_list_recordings(self, mock_start, mock_stop):
        from nexus.via.recorder import start_recording, stop_recording, list_recordings
        start_recording("route-one")
        stop_recording()
        _reset_recording()  # clear state for next recording
        start_recording("route-two")
        stop_recording()

        routes = list_recordings()
        assert len(routes) == 2
        ids = [r["id"] for r in routes]
        assert "route-one" in ids
        assert "route-two" in ids

    @patch("nexus.via.tap.stop_tap", return_value=[])
    @patch("nexus.via.tap.start_tap", return_value=True)
    def test_delete_recording(self, mock_start, mock_stop):
        from nexus.via.recorder import (
            start_recording, stop_recording, delete_recording,
            list_recordings, get_recording,
        )
        start_recording("to-delete")
        stop_recording()

        assert delete_recording("to-delete") is True
        assert get_recording("to-delete") is None
        assert len(list_recordings()) == 0

    def test_delete_nonexistent(self):
        from nexus.via.recorder import delete_recording
        assert delete_recording("no-such-route") is False

    @patch("nexus.via.tap.stop_tap", return_value=[])
    @patch("nexus.via.tap.start_tap", return_value=True)
    def test_unique_slug(self, mock_start, mock_stop):
        from nexus.via.recorder import start_recording, stop_recording
        start_recording("test")
        stop_recording()
        _reset_recording()
        result = start_recording("test")
        assert result["ok"] is True
        assert result["id"] == "test-2"
        stop_recording()


# ===========================================================================
# player.py — Route replay
# ===========================================================================

class TestReplayClick:

    def test_tier1_ax_locator(self):
        """AX locator finds element → click at current position."""
        from nexus.via.player import _replay_click

        step = {
            "ax_role": "AXButton", "ax_label": "Save",
            "rel_x": 0.5, "rel_y": 0.4,
            "x": 400, "y": 300,
            "button": "left", "modifiers": None,
            "pid": 100, "app_name": "TextEdit",
        }

        with patch("nexus.via.player._find_element_position", return_value=(500, 350)), \
             patch("nexus.via.player._do_click") as mock_click:
            result = _replay_click(step)
            assert result["ok"] is True
            assert result["method"] == "ax_locator"
            mock_click.assert_called_once_with(500, 350, "left", None)

    def test_tier2_relative_coords(self):
        """AX locator fails → use relative coordinates."""
        from nexus.via.player import _replay_click

        step = {
            "ax_role": "AXButton", "ax_label": "Save",
            "rel_x": 0.5, "rel_y": 0.4,
            "x": 400, "y": 300,
            "window_x": 100, "window_y": 50, "window_w": 800, "window_h": 600,
            "button": "left", "modifiers": None,
            "pid": 100, "app_name": "TextEdit",
        }

        with patch("nexus.via.player._find_element_position", return_value=None), \
             patch("nexus.via.player._relative_to_absolute", return_value=(500, 290)), \
             patch("nexus.via.player._do_click") as mock_click:
            result = _replay_click(step)
            assert result["ok"] is True
            assert result["method"] == "relative_coords"
            mock_click.assert_called_once_with(500, 290, "left", None)

    def test_tier3_absolute_coords(self):
        """Both AX and relative fail → use absolute coordinates."""
        from nexus.via.player import _replay_click

        step = {
            "ax_role": None, "ax_label": None,
            "rel_x": None, "rel_y": None,
            "x": 400, "y": 300,
            "button": "left", "modifiers": None,
            "pid": 100, "app_name": "TextEdit",
        }

        with patch("nexus.via.player._find_element_position", return_value=None), \
             patch("nexus.via.player._do_click") as mock_click:
            result = _replay_click(step)
            assert result["ok"] is True
            assert result["method"] == "absolute_coords"
            mock_click.assert_called_once_with(400, 300, "left", None)

    def test_no_position_data(self):
        """No position data at all → error."""
        from nexus.via.player import _replay_click
        step = {
            "ax_role": None, "ax_label": None,
            "rel_x": None, "rel_y": None,
            "x": None, "y": None,
            "button": "left", "modifiers": None,
        }
        with patch("nexus.via.player._find_element_position", return_value=None):
            result = _replay_click(step)
            assert result["ok"] is False


class TestReplayKey:

    def test_regular_key(self):
        from nexus.via.player import _replay_key
        step = {"key_char": "a", "key_code": 0, "modifiers": {}}
        with patch("nexus.via.player.raw_input") as mock_input:
            result = _replay_key(step)
            assert result["ok"] is True
            mock_input.type_text.assert_called_once_with("a")

    def test_shortcut_key(self):
        from nexus.via.player import _replay_key
        step = {"key_char": "cmd+s", "key_code": 1, "modifiers": {"cmd": True, "shift": False, "ctrl": False, "opt": False}}
        with patch("nexus.via.player.raw_input") as mock_input:
            result = _replay_key(step)
            assert result["ok"] is True
            assert result["method"] == "hotkey"
            mock_input.hotkey.assert_called_once_with("command", "s")

    def test_special_key(self):
        from nexus.via.player import _replay_key
        step = {"key_char": "return", "key_code": 36, "modifiers": {}}
        with patch("nexus.via.player.raw_input") as mock_input:
            result = _replay_key(step)
            assert result["ok"] is True
            mock_input.press_key.assert_called_once_with("return")

    def test_no_key_data(self):
        from nexus.via.player import _replay_key
        result = _replay_key({"key_char": "", "key_code": None, "modifiers": {}})
        assert result["ok"] is False


class TestReplayScroll:

    def test_scroll_down(self):
        from nexus.via.player import _replay_scroll
        step = {"x": 400, "y": 300, "button": "down"}
        with patch("nexus.via.player.raw_input") as mock_input:
            result = _replay_scroll(step)
            assert result["ok"] is True
            mock_input.scroll.assert_called_once_with(3, x=400, y=300)

    def test_scroll_up(self):
        from nexus.via.player import _replay_scroll
        step = {"x": 400, "y": 300, "button": "up"}
        with patch("nexus.via.player.raw_input") as mock_input:
            result = _replay_scroll(step)
            assert result["ok"] is True
            mock_input.scroll.assert_called_once_with(-3, x=400, y=300)


class TestRelativeToAbsolute:

    def test_with_current_window(self):
        from nexus.via import player
        orig = player.CGWindowListCopyWindowInfo
        try:
            player.CGWindowListCopyWindowInfo = lambda *a, **kw: [
                {
                    "kCGWindowOwnerPID": 100,
                    "kCGWindowOwnerName": "Finder",
                    "kCGWindowBounds": {"X": 200, "Y": 100, "Width": 1000, "Height": 700},
                }
            ]
            step = {
                "rel_x": 0.5, "rel_y": 0.4,
                "pid": 100, "app_name": "Finder",
                "window_x": 100, "window_y": 50, "window_w": 800, "window_h": 600,
            }
            result = player._relative_to_absolute(step, pid=100)
            assert result == (700, 380)  # 200 + 1000*0.5, 100 + 700*0.4
        finally:
            player.CGWindowListCopyWindowInfo = orig

    def test_fallback_to_original_bounds(self):
        """When no current window found, use recorded bounds."""
        from nexus.via import player
        orig = player.CGWindowListCopyWindowInfo
        try:
            player.CGWindowListCopyWindowInfo = lambda *a, **kw: []
            step = {
                "rel_x": 0.5, "rel_y": 0.4,
                "pid": None, "app_name": None,
                "window_x": 100, "window_y": 50, "window_w": 800, "window_h": 600,
            }
            result = player._relative_to_absolute(step)
            assert result == (500, 290)  # 100 + 800*0.5, 50 + 600*0.4
        finally:
            player.CGWindowListCopyWindowInfo = orig


class TestFindElementPosition:

    def test_finds_element(self):
        from nexus.via import player
        orig = player.describe_app
        try:
            player.describe_app = lambda pid=None, max_elements=150: [
                {"_ax_role": "AXButton", "label": "Save", "pos": (400, 300), "size": (80, 30)},
                {"_ax_role": "AXButton", "label": "Cancel", "pos": (300, 300), "size": (80, 30)},
            ]
            result = player._find_element_position("AXButton", "Save", pid=100)
            assert result == (440, 315)  # center: 400+80/2, 300+30/2
        finally:
            player.describe_app = orig

    def test_element_not_found(self):
        from nexus.via import player
        orig = player.describe_app
        try:
            player.describe_app = lambda pid=None, max_elements=150: [
                {"_ax_role": "AXButton", "label": "Cancel", "pos": (300, 300), "size": (80, 30)},
            ]
            result = player._find_element_position("AXButton", "Save", pid=100)
            assert result is None
        finally:
            player.describe_app = orig


class TestFullReplay:

    def setup_method(self):
        self.tmpdir = _reset_db()
        _reset_recording()

    def teardown_method(self):
        _teardown_db(self.tmpdir)
        _reset_recording()

    def test_replay_nonexistent_route(self):
        from nexus.via.player import replay
        result = replay("no-such-route")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_replay_empty_route(self):
        from nexus.mind import db
        db.via_route_create("empty", "Empty Route")
        from nexus.via.player import replay
        result = replay("empty")
        assert result["ok"] is False
        assert "no steps" in result["error"]

    def test_replay_success(self):
        from nexus.mind import db
        db.via_route_create("test", "Test Route")
        db.via_step_insert(
            "test", 1, 0.0, "click",
            x=400, y=300, rel_x=0.5, rel_y=0.4,
            button="left", ax_role="AXButton", ax_label="OK",
            pid=100, app_name="Finder",
        )
        db.via_step_insert(
            "test", 2, 500.0, "key",
            key_code=36, key_char="return",
            pid=100, app_name="Finder",
        )

        from nexus.via.player import replay
        with patch("nexus.via.player._replay_click", return_value={"ok": True, "method": "ax_locator"}), \
             patch("nexus.via.player._replay_key", return_value={"ok": True, "method": "keypress"}), \
             patch("nexus.via.player._handle_system_dialog"), \
             patch("nexus.via.player.time") as mock_time:
            mock_time.sleep = MagicMock()
            mock_time.time = time.time
            result = replay("test", speed=0)

        assert result["ok"] is True
        assert result["completed"] == 2
        assert len(result["steps"]) == 2

    def test_replay_stops_on_failure(self):
        from nexus.mind import db
        db.via_route_create("fail", "Fail Route")
        db.via_step_insert("fail", 1, 0.0, "click", x=100, y=100, button="left")
        db.via_step_insert("fail", 2, 500.0, "click", x=200, y=200, button="left")

        from nexus.via.player import replay
        with patch("nexus.via.player._replay_click", side_effect=[
            {"ok": True, "method": "absolute_coords"},
            {"ok": False, "error": "Element not found"},
        ]), \
             patch("nexus.via.player._handle_system_dialog"), \
             patch("nexus.via.player.time") as mock_time:
            mock_time.sleep = MagicMock()
            mock_time.time = time.time
            result = replay("fail", speed=0)

        assert result["ok"] is False
        assert result["completed"] == 1
        assert result["total"] == 2


# ===========================================================================
# resolve.py — Via intent routing
# ===========================================================================

class TestViaIntentRouting:

    def test_via_record_routes(self):
        from nexus.act.parse import _normalize_action
        # Via intents should NOT be normalized away
        assert "via record test" == "via record test"

    @patch("nexus.via.recorder.start_recording")
    def test_via_record_intent(self, mock_start):
        mock_start.return_value = {"ok": True, "id": "test", "name": "test"}
        from nexus.act.resolve import _handle_via
        result = _handle_via("via record test")
        assert result["ok"] is True
        mock_start.assert_called_once_with("test")

    @patch("nexus.via.recorder.stop_recording")
    def test_via_stop_intent(self, mock_stop):
        mock_stop.return_value = {"ok": True, "id": "test", "steps": 5}
        from nexus.act.resolve import _handle_via
        result = _handle_via("via stop")
        assert result["ok"] is True

    @patch("nexus.via.player.replay")
    def test_via_replay_intent(self, mock_replay):
        mock_replay.return_value = {"ok": True, "completed": 5}
        from nexus.act.resolve import _handle_via
        result = _handle_via("via replay gmail-login")
        assert result["ok"] is True
        mock_replay.assert_called_once_with("gmail-login", pid=None)

    @patch("nexus.via.recorder.list_recordings")
    def test_via_list_intent(self, mock_list):
        mock_list.return_value = []
        from nexus.act.resolve import _handle_via
        result = _handle_via("via list")
        assert result["ok"] is True
        assert "No Via routes" in result["text"]

    @patch("nexus.via.recorder.list_recordings")
    def test_via_list_with_routes(self, mock_list):
        mock_list.return_value = [
            {"id": "test", "name": "Test", "step_count": 5, "duration_ms": 3000},
        ]
        from nexus.act.resolve import _handle_via
        result = _handle_via("via list")
        assert "test" in result["text"]
        assert "5 steps" in result["text"]

    @patch("nexus.via.recorder.delete_recording")
    def test_via_delete_intent(self, mock_delete):
        mock_delete.return_value = True
        from nexus.act.resolve import _handle_via
        result = _handle_via("via delete test")
        assert result["ok"] is True

    @patch("nexus.via.recorder.delete_recording")
    def test_via_delete_not_found(self, mock_delete):
        mock_delete.return_value = False
        from nexus.act.resolve import _handle_via
        result = _handle_via("via delete nonexistent")
        assert result["ok"] is False

    def test_unknown_via_command(self):
        from nexus.act.resolve import _handle_via
        result = _handle_via("via something weird")
        assert result["ok"] is False
        assert "Unknown Via command" in result["error"]


# ===========================================================================
# DB — Via tables
# ===========================================================================

class TestViaDB:

    def setup_method(self):
        self.tmpdir = _reset_db()

    def teardown_method(self):
        _teardown_db(self.tmpdir)

    def test_route_create_and_get(self):
        from nexus.mind import db
        db.via_route_create("test-1", "Test Route", "Chrome")
        route = db.via_route_get("test-1")
        assert route is not None
        assert route["name"] == "Test Route"
        assert route["app"] == "Chrome"

    def test_route_list(self):
        from nexus.mind import db
        db.via_route_create("a", "Route A")
        db.via_route_create("b", "Route B")
        routes = db.via_route_list()
        assert len(routes) == 2

    def test_route_delete(self):
        from nexus.mind import db
        db.via_route_create("del", "To Delete")
        assert db.via_route_delete("del") is True
        assert db.via_route_get("del") is None
        assert db.via_route_delete("del") is False

    def test_route_update(self):
        from nexus.mind import db
        db.via_route_create("upd", "Update Test")
        db.via_route_update("upd", duration_ms=5000, step_count=10)
        route = db.via_route_get("upd")
        assert route["duration_ms"] == 5000
        assert route["step_count"] == 10

    def test_step_insert_and_retrieve(self):
        from nexus.mind import db
        db.via_route_create("steps", "Steps Test")
        db.via_step_insert(
            "steps", 1, 0.0, "click",
            x=400, y=300, rel_x=0.5, rel_y=0.4,
            window_x=100, window_y=50, window_w=800, window_h=600,
            button="left",
            modifiers={"cmd": False, "shift": True},
            ax_role="AXButton", ax_label="OK",
            pid=100, app_name="Finder",
        )
        db.via_step_insert(
            "steps", 2, 1000.0, "key",
            key_code=36, key_char="return",
            pid=100, app_name="Finder",
        )

        steps = db.via_steps_for_route("steps")
        assert len(steps) == 2
        assert steps[0]["event_type"] == "click"
        assert steps[0]["ax_label"] == "OK"
        assert steps[0]["rel_x"] == 0.5
        assert steps[0]["modifiers"] == {"cmd": False, "shift": True}
        assert steps[1]["event_type"] == "key"
        assert steps[1]["key_char"] == "return"

    def test_cascade_delete(self):
        from nexus.mind import db
        db.via_route_create("cascade", "Cascade Test")
        db.via_step_insert("cascade", 1, 0.0, "click", x=100, y=100)
        db.via_step_insert("cascade", 2, 100.0, "key", key_code=36, key_char="return")
        db.via_route_delete("cascade")
        steps = db.via_steps_for_route("cascade")
        assert len(steps) == 0


# ===========================================================================
# access.py — element_at_position
# ===========================================================================

class TestElementAtPosition:

    def test_hit_test_system_wide(self):
        from nexus.sense import access
        mock_el = MagicMock()
        with patch.object(access.pyax, "get_element_at_position", return_value=mock_el), \
             patch.object(access, "_system_wide", return_value=MagicMock()), \
             patch.object(access, "_element_to_dict", return_value={"role": "button", "label": "OK"}):
            result = access.element_at_position(400, 300)
            assert result is not None
            assert result["label"] == "OK"

    def test_hit_test_with_pid(self):
        from nexus.sense import access
        mock_el = MagicMock()
        mock_app = MagicMock()
        with patch.object(access.pyax, "get_element_at_position", return_value=mock_el), \
             patch.object(access.pyax, "get_application_from_pid", return_value=mock_app) as mock_create, \
             patch.object(access, "_element_to_dict", return_value={"role": "button", "label": "Save"}):
            result = access.element_at_position(400, 300, pid=100)
            assert result is not None
            mock_create.assert_called_once_with(100)

    def test_hit_test_miss(self):
        from nexus.sense import access
        with patch.object(access.pyax, "get_element_at_position", return_value=None), \
             patch.object(access, "_system_wide", return_value=MagicMock()):
            result = access.element_at_position(400, 300)
            assert result is None
