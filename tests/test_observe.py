"""Unit tests for nexus.sense.observe — AXObserver-based observation mode.

All AXObserver and CFRunLoop calls are mocked. These tests verify the
debounce logic, buffer management, event formatting, state tracking,
and lifecycle without requiring real accessibility permission.
"""

import sys
import time
import threading
from collections import deque
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, "/Users/ferran/repos/Nexus")


# ---------------------------------------------------------------------------
# Helpers to reset module state between tests
# ---------------------------------------------------------------------------

def _reset_observe_state():
    """Reset all module-level state in observe.py."""
    from nexus.sense import observe
    with observe._lock:
        observe._observers.clear()
        observe._event_buffer.clear()
        observe._last_event.clear()
        observe._observer_to_pid.clear()
    observe._thread = None
    observe._runloop = None
    observe._runloop_ready = None


@pytest.fixture(autouse=True)
def clean_state():
    """Ensure each test starts with fresh observe state."""
    _reset_observe_state()
    yield
    _reset_observe_state()


# ===========================================================================
# Event buffer and drain
# ===========================================================================


class TestDrainEvents:
    """drain_events() atomically drains the buffer."""

    def test_empty_buffer_returns_empty_list(self):
        from nexus.sense.observe import drain_events
        assert drain_events() == []

    def test_drain_returns_all_events(self):
        from nexus.sense import observe
        with observe._lock:
            observe._event_buffer.append({"type": "AXWindowCreated", "pid": 1, "ts": 1.0, "role": "", "label": ""})
            observe._event_buffer.append({"type": "AXValueChanged", "pid": 1, "ts": 2.0, "role": "", "label": ""})
        events = observe.drain_events()
        assert len(events) == 2
        assert events[0]["type"] == "AXWindowCreated"
        assert events[1]["type"] == "AXValueChanged"

    def test_drain_clears_buffer(self):
        from nexus.sense import observe
        with observe._lock:
            observe._event_buffer.append({"type": "AXWindowCreated", "pid": 1, "ts": 1.0, "role": "", "label": ""})
        observe.drain_events()
        assert observe.drain_events() == []

    def test_buffer_overflow_drops_oldest(self):
        from nexus.sense import observe
        with observe._lock:
            for i in range(250):
                observe._event_buffer.append({"type": "AXValueChanged", "pid": 1, "ts": float(i), "role": "", "label": str(i)})
        events = observe.drain_events()
        assert len(events) == 200  # maxlen
        assert events[0]["label"] == "50"  # first 50 dropped


# ===========================================================================
# Debounce logic
# ===========================================================================


class TestDebounce:
    """Debounce collapses rapid same-type events within the time window."""

    def _fire_callback(self, observer_id, pid, notification, role="", title=""):
        """Simulate a notification callback with mocked ax_attr."""
        from nexus.sense import observe
        observe._observer_to_pid[observer_id] = pid

        mock_observer = MagicMock()
        mock_observer.__hash__ = lambda s: observer_id
        # Override id() lookup by directly setting the key
        observe._observer_to_pid[id(mock_observer)] = pid

        mock_element = MagicMock()
        with patch.object(observe, "ax_attr", side_effect=lambda el, attr: {
            "AXRole": role, "AXTitle": title, "AXDescription": ""
        }.get(attr, "")):
            with patch.object(observe, "invalidate_cache"):
                observe._on_notification(mock_observer, mock_element, notification, None)

    def test_first_event_passes_through(self):
        from nexus.sense import observe
        self._fire_callback(100, 42, "AXWindowCreated", "AXWindow", "Test")
        events = observe.drain_events()
        assert len(events) == 1
        assert events[0]["type"] == "AXWindowCreated"
        assert events[0]["label"] == "Test"

    def test_rapid_same_type_debounced(self):
        from nexus.sense import observe
        self._fire_callback(100, 42, "AXValueChanged", "AXTextField", "Field1")
        self._fire_callback(100, 42, "AXValueChanged", "AXTextField", "Field1")
        self._fire_callback(100, 42, "AXValueChanged", "AXTextField", "Field1")
        events = observe.drain_events()
        assert len(events) == 1  # only first passes

    def test_different_types_not_debounced(self):
        from nexus.sense import observe
        self._fire_callback(100, 42, "AXWindowCreated", "AXWindow", "Win")
        self._fire_callback(100, 42, "AXValueChanged", "AXTextField", "Field")
        self._fire_callback(100, 42, "AXFocusedUIElementChanged", "AXButton", "OK")
        events = observe.drain_events()
        assert len(events) == 3

    def test_different_pids_not_debounced(self):
        from nexus.sense import observe
        self._fire_callback(100, 42, "AXValueChanged", "AXTextField", "A")
        self._fire_callback(200, 99, "AXValueChanged", "AXTextField", "B")
        events = observe.drain_events()
        assert len(events) == 2

    def test_callback_invalidates_cache(self):
        from nexus.sense import observe
        mock_observer = MagicMock()
        observe._observer_to_pid[id(mock_observer)] = 42
        mock_element = MagicMock()

        with patch.object(observe, "ax_attr", return_value=""):
            with patch.object(observe, "invalidate_cache") as mock_invalidate:
                observe._on_notification(mock_observer, mock_element, "AXWindowCreated", None)
                mock_invalidate.assert_called_once()

    def test_unknown_observer_ignored(self):
        """Callback with unregistered observer ID is silently ignored."""
        from nexus.sense import observe
        mock_observer = MagicMock()
        # Don't register this observer
        mock_element = MagicMock()
        with patch.object(observe, "ax_attr", return_value=""):
            with patch.object(observe, "invalidate_cache") as mock_invalidate:
                observe._on_notification(mock_observer, mock_element, "AXWindowCreated", None)
                mock_invalidate.assert_not_called()
        assert observe.drain_events() == []


# ===========================================================================
# start_observing / stop_observing / is_observing / status
# ===========================================================================


class TestObserverLifecycle:
    """Observer creation, registration, and cleanup (mocked AX/CF)."""

    @patch("nexus.sense.observe.CFRunLoopWakeUp")
    @patch("nexus.sense.observe.CFRunLoopAddSource")
    @patch("nexus.sense.observe.AXObserverGetRunLoopSource", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverAddNotification")
    @patch("nexus.sense.observe.AXUIElementCreateApplication", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverCreate", return_value=(0, MagicMock()))
    def test_start_observing_success(self, mock_create, mock_app, mock_add, mock_source, mock_cf_add, mock_wake):
        from nexus.sense import observe
        # Simulate thread already running
        observe._runloop = MagicMock()
        observe._thread = MagicMock(is_alive=lambda: True)

        result = observe.start_observing(42, "Safari")
        assert result["ok"] is True
        assert result["pid"] == 42
        assert result["app"] == "Safari"
        assert result["notifications"] == len(observe._NOTIFICATIONS)
        assert observe.is_observing(42)

    @patch("nexus.sense.observe.CFRunLoopWakeUp")
    @patch("nexus.sense.observe.CFRunLoopAddSource")
    @patch("nexus.sense.observe.AXObserverGetRunLoopSource", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverAddNotification")
    @patch("nexus.sense.observe.AXUIElementCreateApplication", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverCreate", return_value=(0, MagicMock()))
    def test_start_already_observing(self, mock_create, mock_app, mock_add, mock_source, mock_cf_add, mock_wake):
        from nexus.sense import observe
        observe._runloop = MagicMock()
        observe._thread = MagicMock(is_alive=lambda: True)

        observe.start_observing(42, "Safari")
        result = observe.start_observing(42, "Safari")
        assert result["ok"] is True
        assert result.get("already") is True

    @patch("nexus.sense.observe.AXObserverCreate", return_value=(-25201, None))
    def test_start_observing_ax_error(self, mock_create):
        from nexus.sense import observe
        observe._runloop = MagicMock()
        observe._thread = MagicMock(is_alive=lambda: True)

        result = observe.start_observing(42, "Safari")
        assert result["ok"] is False
        assert "failed" in result["error"]

    def test_start_observing_no_thread(self):
        """Returns error if the observer thread can't start."""
        from nexus.sense import observe
        # _runloop stays None (thread didn't start)
        with patch.object(observe, "_ensure_thread"):
            result = observe.start_observing(42, "Safari")
            assert result["ok"] is False
            assert "thread" in result["error"].lower()

    @patch("nexus.sense.observe.CFRunLoopWakeUp")
    @patch("nexus.sense.observe.CFRunLoopRemoveSource")
    @patch("nexus.sense.observe.AXObserverRemoveNotification")
    @patch("nexus.sense.observe.CFRunLoopAddSource")
    @patch("nexus.sense.observe.AXObserverGetRunLoopSource", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverAddNotification")
    @patch("nexus.sense.observe.AXUIElementCreateApplication", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverCreate", return_value=(0, MagicMock()))
    def test_stop_observing_specific_pid(self, mock_create, mock_app, mock_add, mock_source,
                                          mock_cf_add, mock_rm_notif, mock_cf_rm, mock_wake):
        from nexus.sense import observe
        observe._runloop = MagicMock()
        observe._thread = MagicMock(is_alive=lambda: True)

        observe.start_observing(42, "Safari")
        observe.start_observing(99, "Chrome")

        result = observe.stop_observing(42)
        assert result["ok"] is True
        assert 42 in result["stopped"]
        assert not observe.is_observing(42)
        assert observe.is_observing(99)

    @patch("nexus.sense.observe.CFRunLoopWakeUp")
    @patch("nexus.sense.observe.CFRunLoopRemoveSource")
    @patch("nexus.sense.observe.AXObserverRemoveNotification")
    @patch("nexus.sense.observe.CFRunLoopAddSource")
    @patch("nexus.sense.observe.AXObserverGetRunLoopSource", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverAddNotification")
    @patch("nexus.sense.observe.AXUIElementCreateApplication", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverCreate", return_value=(0, MagicMock()))
    def test_stop_all(self, mock_create, mock_app, mock_add, mock_source,
                      mock_cf_add, mock_rm_notif, mock_cf_rm, mock_wake):
        from nexus.sense import observe
        observe._runloop = MagicMock()
        observe._thread = MagicMock(is_alive=lambda: True)

        observe.start_observing(42, "Safari")
        observe.start_observing(99, "Chrome")

        result = observe.stop_observing()  # all
        assert result["ok"] is True
        assert len(result["stopped"]) == 2
        assert not observe.is_observing()

    def test_is_observing_default_false(self):
        from nexus.sense.observe import is_observing
        assert is_observing() is False
        assert is_observing(42) is False

    def test_status_empty(self):
        from nexus.sense.observe import status
        s = status()
        assert s["ok"] is True
        assert s["observing"] == []
        assert s["buffered"] == 0

    @patch("nexus.sense.observe.CFRunLoopWakeUp")
    @patch("nexus.sense.observe.CFRunLoopAddSource")
    @patch("nexus.sense.observe.AXObserverGetRunLoopSource", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverAddNotification")
    @patch("nexus.sense.observe.AXUIElementCreateApplication", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverCreate", return_value=(0, MagicMock()))
    def test_status_with_observer(self, mock_create, mock_app, mock_add, mock_source, mock_cf_add, mock_wake):
        from nexus.sense import observe
        observe._runloop = MagicMock()
        observe._thread = MagicMock(is_alive=lambda: True)

        observe.start_observing(42, "Safari")
        s = observe.status()
        assert len(s["observing"]) == 1
        assert s["observing"][0]["pid"] == 42
        assert s["observing"][0]["app"] == "Safari"
        assert "since" in s["observing"][0]


# ===========================================================================
# Stale PID cleanup
# ===========================================================================


class TestStaleCleanup:
    """Dead PIDs are automatically cleaned up on drain_events()."""

    @patch("nexus.sense.observe.CFRunLoopWakeUp")
    @patch("nexus.sense.observe.CFRunLoopRemoveSource")
    @patch("nexus.sense.observe.AXObserverRemoveNotification")
    @patch("nexus.sense.observe.CFRunLoopAddSource")
    @patch("nexus.sense.observe.AXObserverGetRunLoopSource", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverAddNotification")
    @patch("nexus.sense.observe.AXUIElementCreateApplication", return_value=MagicMock())
    @patch("nexus.sense.observe.AXObserverCreate", return_value=(0, MagicMock()))
    def test_dead_pid_removed_on_drain(self, mock_create, mock_app, mock_add, mock_source,
                                        mock_cf_add, mock_rm_notif, mock_cf_rm, mock_wake):
        from nexus.sense import observe
        observe._runloop = MagicMock()
        observe._thread = MagicMock(is_alive=lambda: True)

        observe.start_observing(99999, "FakeApp")
        assert observe.is_observing(99999)

        # os.kill(99999, 0) will raise OSError for a non-existent PID
        observe.drain_events()
        assert not observe.is_observing(99999)


# ===========================================================================
# Event formatting
# ===========================================================================


class TestFormatEvents:
    """format_events() produces compact, grouped text output."""

    def test_empty_returns_empty_string(self):
        from nexus.sense.observe import format_events
        assert format_events([]) == ""

    def test_single_event(self):
        from nexus.sense.observe import format_events
        events = [{"type": "AXWindowCreated", "role": "AXWindow", "label": "New Window", "pid": 1, "ts": 1.0}]
        text = format_events(events)
        assert "Recent events (1):" in text
        assert "WindowCreated:" in text
        assert "[Window]" in text
        assert '"New Window"' in text

    def test_multiple_same_type_grouped(self):
        from nexus.sense.observe import format_events
        events = [
            {"type": "AXValueChanged", "role": "AXTextField", "label": "Name", "pid": 1, "ts": 1.0},
            {"type": "AXValueChanged", "role": "AXTextField", "label": "Email", "pid": 1, "ts": 2.0},
        ]
        text = format_events(events)
        assert "Recent events (2):" in text
        assert "ValueChanged x2:" in text
        assert "Name" in text
        assert "Email" in text

    def test_mixed_types(self):
        from nexus.sense.observe import format_events
        events = [
            {"type": "AXWindowCreated", "role": "AXWindow", "label": "Win", "pid": 1, "ts": 1.0},
            {"type": "AXValueChanged", "role": "AXTextField", "label": "Field", "pid": 1, "ts": 2.0},
        ]
        text = format_events(events)
        assert "Recent events (2):" in text
        assert "WindowCreated:" in text
        assert "ValueChanged:" in text

    def test_no_label_no_role(self):
        from nexus.sense.observe import format_events
        events = [{"type": "AXUIElementDestroyed", "role": "", "label": "", "pid": 1, "ts": 1.0}]
        text = format_events(events)
        assert "UIElementDestroyed:" in text

    def test_multiple_no_labels(self):
        from nexus.sense.observe import format_events
        events = [
            {"type": "AXValueChanged", "role": "", "label": "", "pid": 1, "ts": 1.0},
            {"type": "AXValueChanged", "role": "", "label": "", "pid": 1, "ts": 2.0},
        ]
        text = format_events(events)
        assert "ValueChanged x2" in text
