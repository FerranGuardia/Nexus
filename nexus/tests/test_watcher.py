"""Tests for Nexus watcher — event filtering, debouncing, noise detection.

These tests cover the pure-function parts of the watcher module.
The actual UIA event subscription requires a live Windows desktop
and is tested manually or via the 'action' marker.
"""

import time
import pytest

from nexus.watcher import (
    _is_noisy,
    _debounce,
    filter_events,
    _last_events,
)


# ---------------------------------------------------------------------------
# Noise filtering
# ---------------------------------------------------------------------------

class TestIsNoisy:
    def test_empty_name_is_noisy(self):
        assert _is_noisy("") is True

    def test_cursor_is_noisy(self):
        assert _is_noisy("cursor") is True
        assert _is_noisy("Cursor") is True

    def test_desktop_is_noisy(self):
        assert _is_noisy("Desktop") is True
        assert _is_noisy("Program Manager") is True

    def test_taskbar_classes_noisy(self):
        assert _is_noisy("Something", "Shell_TrayWnd") is True
        assert _is_noisy("Something", "Progman") is True

    def test_tooltip_name_noisy(self):
        assert _is_noisy("Some tooltip text", "") is True
        assert _is_noisy("Tooltip for button", "") is True

    def test_tooltip_class_noisy(self):
        assert _is_noisy("Help", "ToolTipControl") is True

    def test_normal_element_not_noisy(self):
        assert _is_noisy("Save", "Button") is False
        assert _is_noisy("File", "MenuItem") is False
        assert _is_noisy("Untitled - Notepad", "Notepad") is False


# ---------------------------------------------------------------------------
# Debounce
# ---------------------------------------------------------------------------

class TestDebounce:
    def setup_method(self):
        _last_events.clear()

    def test_first_event_not_debounced(self):
        assert _debounce("focus", "Save Button") is False

    def test_rapid_duplicate_debounced(self):
        _debounce("focus", "Save Button")
        assert _debounce("focus", "Save Button") is True

    def test_different_key_not_debounced(self):
        _debounce("focus", "Save Button")
        assert _debounce("focus", "Cancel Button") is False

    def test_different_type_not_debounced(self):
        _debounce("focus", "Save Button")
        assert _debounce("structure", "Save Button") is False

    def test_after_delay_not_debounced(self):
        _debounce("focus", "Save Button")
        # Manually push the timestamp back
        key = "focus|Save Button"
        _last_events[key] = _last_events[key] - 200  # 200ms ago
        assert _debounce("focus", "Save Button") is False


# ---------------------------------------------------------------------------
# Event filtering (pure function)
# ---------------------------------------------------------------------------

SAMPLE_EVENTS = [
    {"event": "focus_changed", "element": "Save Button", "class": "Button"},
    {"event": "window_opened", "element": "Untitled - Notepad", "class": "Notepad"},
    {"event": "structure_changed", "element": "Dialog", "class": "DialogWindow", "change": "child_added"},
    {"event": "focus_changed", "element": "Cancel", "class": "Button"},
    {"event": "property_changed", "element": "Status", "class": "StatusBar", "property": "name"},
    {"event": "window_closed", "element": "Settings", "class": "ApplicationFrameWindow"},
]


class TestFilterEvents:
    def test_no_filters_returns_all(self):
        result = filter_events(SAMPLE_EVENTS)
        assert len(result) == len(SAMPLE_EVENTS)

    def test_filter_by_event_type(self):
        result = filter_events(SAMPLE_EVENTS, event_types=["focus_changed"])
        assert len(result) == 2
        assert all(e["event"] == "focus_changed" for e in result)

    def test_filter_multiple_event_types(self):
        result = filter_events(SAMPLE_EVENTS, event_types=["window_opened", "window_closed"])
        assert len(result) == 2

    def test_filter_by_excluded_class(self):
        result = filter_events(SAMPLE_EVENTS, exclude_classes=["Button"])
        assert len(result) == 4
        assert all(e["class"] != "Button" for e in result)

    def test_filter_by_name_contains(self):
        result = filter_events(SAMPLE_EVENTS, name_contains="save")
        assert len(result) == 1
        assert result[0]["element"] == "Save Button"

    def test_combined_filters(self):
        result = filter_events(
            SAMPLE_EVENTS,
            event_types=["focus_changed"],
            name_contains="cancel",
        )
        assert len(result) == 1
        assert result[0]["element"] == "Cancel"

    def test_empty_result(self):
        result = filter_events(SAMPLE_EVENTS, event_types=["nonexistent_event"])
        assert len(result) == 0

    def test_empty_input(self):
        result = filter_events([])
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Watch lifecycle (integration — requires Windows UIA)
# ---------------------------------------------------------------------------

@pytest.mark.action
class TestWatchLifecycle:
    """These tests actually start/stop the watcher. Marked 'action' since
    they create background threads and interact with the UIA subsystem."""

    def test_start_and_stop(self):
        from nexus.watcher import start_watching, stop_watching, watch_status

        result = start_watching(events=["focus"])
        assert result.get("ok") is True

        status = watch_status()
        assert status["running"] is True

        result = stop_watching()
        assert result.get("ok") is True

        status = watch_status()
        assert status["running"] is False

    def test_double_start_fails(self):
        from nexus.watcher import start_watching, stop_watching

        start_watching(events=["focus"])
        result = start_watching(events=["focus"])
        assert result.get("ok") is False
        assert "already running" in result.get("error", "").lower()
        stop_watching()

    def test_stop_without_start_fails(self):
        from nexus.watcher import stop_watching
        result = stop_watching()
        assert result.get("ok") is False

    def test_poll_returns_list(self):
        from nexus.watcher import start_watching, stop_watching, poll_events
        import time

        start_watching(events=["focus"])
        time.sleep(0.5)
        events = poll_events(max_events=10, timeout=0.1)
        assert isinstance(events, list)
        stop_watching()
