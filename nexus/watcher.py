"""Nexus Watcher — event-driven UI awareness via Windows UIA event subscriptions.

Subscribes to UIA events (focus changes, window open/close, structure changes)
and streams JSON-line events. Runs on a dedicated MTA thread.

No side effects on import. Call start_watching() to begin, stop_watching() to end.
"""

import json
import queue
import threading
import time

# Event queue — handlers push events here, consumer reads them
_event_queue = queue.Queue(maxsize=500)

# Control
_stop_event = threading.Event()
_watcher_thread = None
_watcher_lock = threading.Lock()

# Noise filtering — debounce rapid-fire events
_last_events = {}  # event_type+key -> timestamp
DEBOUNCE_MS = 150  # ignore duplicate events within this window

# Names/patterns to ignore (cursor blink, tooltips, system noise)
NOISE_NAMES = frozenset({
    "", "cursor", "Cursor", "Desktop", "Program Manager",
    "Start", "Taskbar", "Task Switching",
})

NOISE_CLASSES = frozenset({
    "Progman", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "TopLevelWindowForOverflowXamlIsland",
})


def _is_noisy(name: str, class_name: str = "") -> bool:
    """Filter out noisy/irrelevant events."""
    if name in NOISE_NAMES:
        return True
    if class_name in NOISE_CLASSES:
        return True
    # Tooltip flicker
    if "tooltip" in name.lower() or "ToolTip" in class_name:
        return True
    return False


def _debounce(event_type: str, key: str) -> bool:
    """Return True if this event should be suppressed (too recent duplicate)."""
    now = time.monotonic() * 1000  # ms
    lookup = "%s|%s" % (event_type, key)
    last = _last_events.get(lookup, 0)
    if (now - last) < DEBOUNCE_MS:
        return True
    _last_events[lookup] = now
    return False


def _emit(event: dict):
    """Push an event to the queue (non-blocking, drops if full)."""
    event["timestamp"] = time.time()
    try:
        _event_queue.put_nowait(event)
    except queue.Full:
        pass  # drop oldest-style: queue is bounded


def _safe_name(element) -> str:
    """Safely extract CurrentName from a COM element."""
    try:
        return element.CurrentName or ""
    except Exception:
        return ""


def _safe_class(element) -> str:
    """Safely extract CurrentClassName from a COM element."""
    try:
        return element.CurrentClassName or ""
    except Exception:
        return ""


def _safe_rect(element) -> dict | None:
    """Safely extract bounding rect from a COM element."""
    try:
        r = element.CurrentBoundingRectangle
        return {
            "left": r.left, "top": r.top,
            "right": r.right, "bottom": r.bottom,
            "center_x": (r.left + r.right) // 2,
            "center_y": (r.top + r.bottom) // 2,
        }
    except Exception:
        return None


def _safe_control_type(element) -> int:
    """Safely extract CurrentControlType from a COM element."""
    try:
        return element.CurrentControlType
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# COM Event Sink — implements all four UIA handler interfaces
# ---------------------------------------------------------------------------

def _create_event_sink():
    """Create the COM event sink. Import comtypes lazily to avoid import-time side effects."""
    import comtypes
    import comtypes.client
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen.UIAutomationClient import (
        IUIAutomationFocusChangedEventHandler,
        IUIAutomationEventHandler,
        IUIAutomationPropertyChangedEventHandler,
        IUIAutomationStructureChangedEventHandler,
    )

    # Event IDs for decoding
    EVENT_NAMES = {
        20000: "tooltip_opened",
        20001: "tooltip_closed",
        20003: "menu_opened",
        20007: "menu_closed",
        20009: "invoked",
        20012: "item_selected",
        20016: "window_opened",
        20017: "window_closed",
        20018: "menu_mode_start",
        20019: "menu_mode_end",
        20024: "live_region_changed",
        20035: "notification",
    }

    STRUCTURE_TYPES = {
        0: "child_added",
        1: "child_removed",
        2: "children_invalidated",
        3: "children_bulk_added",
        4: "children_bulk_removed",
        5: "children_reordered",
    }

    PROPERTY_NAMES = {
        30005: "name",
        30010: "is_enabled",
        30045: "value",
    }

    class WatcherSink(comtypes.COMObject):
        _com_interfaces_ = [
            IUIAutomationFocusChangedEventHandler,
            IUIAutomationEventHandler,
            IUIAutomationPropertyChangedEventHandler,
            IUIAutomationStructureChangedEventHandler,
        ]

        def IUIAutomationFocusChangedEventHandler_HandleFocusChangedEvent(self, sender):
            try:
                name = _safe_name(sender)
                cls = _safe_class(sender)
                if _is_noisy(name, cls):
                    return
                if _debounce("focus", name):
                    return
                _emit({
                    "event": "focus_changed",
                    "element": name,
                    "class": cls,
                    "control_type": _safe_control_type(sender),
                    "bounds": _safe_rect(sender),
                })
            except Exception:
                pass

        def IUIAutomationEventHandler_HandleAutomationEvent(self, sender, eventId):
            try:
                event_name = EVENT_NAMES.get(eventId, "event_%d" % eventId)
                # Skip tooltips entirely
                if eventId in (20000, 20001):
                    return
                name = _safe_name(sender)
                cls = _safe_class(sender)
                if _is_noisy(name, cls):
                    return
                if _debounce(event_name, name):
                    return
                _emit({
                    "event": event_name,
                    "element": name,
                    "class": cls,
                    "event_id": eventId,
                    "bounds": _safe_rect(sender),
                })
            except Exception:
                pass

        def IUIAutomationPropertyChangedEventHandler_HandlePropertyChangedEvent(
            self, sender, propertyId, newValue
        ):
            try:
                prop_name = PROPERTY_NAMES.get(propertyId, "prop_%d" % propertyId)
                name = _safe_name(sender)
                cls = _safe_class(sender)
                if _is_noisy(name, cls):
                    return
                if _debounce("prop_%s" % prop_name, name):
                    return
                _emit({
                    "event": "property_changed",
                    "property": prop_name,
                    "property_id": propertyId,
                    "element": name,
                    "class": cls,
                    "new_value": str(newValue) if newValue is not None else None,
                })
            except Exception:
                pass

        def IUIAutomationStructureChangedEventHandler_HandleStructureChangedEvent(
            self, sender, changeType, runtimeId
        ):
            try:
                change_name = STRUCTURE_TYPES.get(changeType, "change_%d" % changeType)
                name = _safe_name(sender)
                cls = _safe_class(sender)
                if _is_noisy(name, cls):
                    return
                if _debounce("structure_%s" % change_name, name):
                    return
                _emit({
                    "event": "structure_changed",
                    "change": change_name,
                    "element": name,
                    "class": cls,
                    "bounds": _safe_rect(sender),
                })
            except Exception:
                pass

    return WatcherSink()


# ---------------------------------------------------------------------------
# Watcher thread — MTA thread that owns all event subscriptions
# ---------------------------------------------------------------------------

def _watcher_loop(events: list[str] | None = None):
    """Main watcher loop. Runs on a dedicated thread with COM initialized.

    Args:
        events: Which event types to subscribe to. None = all.
                Options: "focus", "window", "structure", "property"
    """
    # Initialize COM on this thread (STA is fine — UIA callbacks fire on
    # UIA's own worker threads regardless of apartment type)
    import pythoncom
    pythoncom.CoInitialize()

    try:
        import comtypes
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import (
            CUIAutomation,
            IUIAutomation,
        )

        automation = comtypes.client.CreateObject(
            CUIAutomation,
            interface=IUIAutomation,
        )
        root = automation.GetRootElement()
        sink = _create_event_sink()

        subscribe_all = events is None
        subscribed = []

        # Focus changes
        if subscribe_all or "focus" in events:
            try:
                automation.AddFocusChangedEventHandler(None, sink)
                subscribed.append("focus")
            except Exception as e:
                _emit({"event": "watch_error", "detail": "focus handler failed: %s" % e})

        # Window open/close
        if subscribe_all or "window" in events:
            try:
                automation.AddAutomationEventHandler(
                    20016,  # UIA_Window_WindowOpenedEventId
                    root, 7,  # TreeScope_Subtree
                    None, sink,
                )
                automation.AddAutomationEventHandler(
                    20017,  # UIA_Window_WindowClosedEventId
                    root, 7, None, sink,
                )
                subscribed.append("window")
            except Exception as e:
                _emit({"event": "watch_error", "detail": "window handler failed: %s" % e})

        # Structure changes (dialog appear, child added/removed)
        if subscribe_all or "structure" in events:
            try:
                automation.AddStructureChangedEventHandler(
                    root, 7, None, sink,
                )
                subscribed.append("structure")
            except Exception as e:
                _emit({"event": "watch_error", "detail": "structure handler failed: %s" % e})

        # Property changes (name, enabled)
        if subscribe_all or "property" in events:
            try:
                import ctypes
                prop_ids = (ctypes.c_long * 2)(30005, 30010)  # Name, IsEnabled
                automation.AddPropertyChangedEventHandlerNativeArray(
                    root, 7, None, sink, prop_ids, 2,
                )
                subscribed.append("property")
            except Exception as e:
                _emit({"event": "watch_error", "detail": "property handler failed: %s" % e})

        # Signal that we're ready
        _emit({
            "event": "watch_started",
            "subscriptions": subscribed,
        })

        # Block until stop is requested
        _stop_event.wait()

        # Clean up — remove all handlers (must be on this same MTA thread)
        try:
            automation.RemoveAllEventHandlers()
        except Exception:
            pass

        _emit({"event": "watch_stopped"})

    except Exception as e:
        _emit({"event": "watch_error", "detail": "watcher loop failed: %s" % e})
    finally:
        pythoncom.CoUninitialize()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_watching(events: list[str] | None = None) -> dict:
    """Start the UIA event watcher on a background thread.

    Args:
        events: Which event types to subscribe to. None = all.
                Options: "focus", "window", "structure", "property"

    Returns:
        {"ok": True/False, "message": str}
    """
    global _watcher_thread

    with _watcher_lock:
        if _watcher_thread is not None and _watcher_thread.is_alive():
            return {"command": "watch", "ok": False, "error": "Watcher already running"}

        _stop_event.clear()
        # Drain any stale events
        while not _event_queue.empty():
            try:
                _event_queue.get_nowait()
            except queue.Empty:
                break

        _watcher_thread = threading.Thread(
            target=_watcher_loop,
            args=(events,),
            daemon=True,
            name="nexus-watcher",
        )
        _watcher_thread.start()

        # Wait briefly for the watch_started event
        try:
            evt = _event_queue.get(timeout=5.0)
            if evt.get("event") == "watch_started":
                return {
                    "command": "watch",
                    "ok": True,
                    "subscriptions": evt.get("subscriptions", []),
                    "message": "Watcher started",
                }
            elif evt.get("event") == "watch_error":
                return {
                    "command": "watch",
                    "ok": False,
                    "error": evt.get("detail", "Unknown error"),
                }
        except queue.Empty:
            pass

        return {"command": "watch", "ok": True, "message": "Watcher starting (no confirmation yet)"}


def stop_watching() -> dict:
    """Stop the UIA event watcher.

    Returns:
        {"ok": True/False, "message": str}
    """
    global _watcher_thread

    with _watcher_lock:
        if _watcher_thread is None or not _watcher_thread.is_alive():
            return {"command": "watch", "ok": False, "error": "Watcher not running"}

        _stop_event.set()
        _watcher_thread.join(timeout=5.0)

        if _watcher_thread.is_alive():
            return {"command": "watch", "ok": False, "error": "Watcher thread did not stop"}

        _watcher_thread = None
        return {"command": "watch", "ok": True, "message": "Watcher stopped"}


def poll_events(max_events: int = 50, timeout: float = 0.0) -> list[dict]:
    """Drain pending events from the queue.

    Args:
        max_events: Maximum number of events to return.
        timeout: How long to wait for the first event (0 = non-blocking).

    Returns:
        List of event dicts.
    """
    events = []

    # Wait for first event if timeout > 0
    if timeout > 0 and _event_queue.empty():
        try:
            evt = _event_queue.get(timeout=timeout)
            events.append(evt)
        except queue.Empty:
            return events

    # Drain remaining without blocking
    while len(events) < max_events:
        try:
            events.append(_event_queue.get_nowait())
        except queue.Empty:
            break

    return events


def watch_status() -> dict:
    """Check if the watcher is currently running."""
    running = _watcher_thread is not None and _watcher_thread.is_alive()
    pending = _event_queue.qsize()
    return {
        "command": "watch",
        "running": running,
        "pending_events": pending,
    }


# ---------------------------------------------------------------------------
# Event filtering utilities (pure functions, testable)
# ---------------------------------------------------------------------------

def filter_events(events: list[dict],
                  event_types: list[str] | None = None,
                  exclude_classes: list[str] | None = None,
                  name_contains: str | None = None) -> list[dict]:
    """Filter a list of events by type, class, or name.

    Args:
        events: List of event dicts to filter.
        event_types: Only keep events with these event types.
        exclude_classes: Remove events from these window classes.
        name_contains: Only keep events where element name contains this string.

    Returns:
        Filtered list of events.
    """
    result = events

    if event_types is not None:
        type_set = set(event_types)
        result = [e for e in result if e.get("event") in type_set]

    if exclude_classes is not None:
        cls_set = set(exclude_classes)
        result = [e for e in result if e.get("class", "") not in cls_set]

    if name_contains is not None:
        name_lower = name_contains.lower()
        result = [e for e in result if name_lower in e.get("element", "").lower()]

    return result
