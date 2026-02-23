"""Observation mode — AXObserver for proactive change detection.

Runs AXObservers on a background CFRunLoop thread to capture macOS
accessibility events (focus changes, new windows, value updates, etc.)
without polling. Events are debounced, buffered, and drained by see().

Usage:
    start_observing(pid, app_name)  — begin watching an app
    stop_observing(pid)             — stop watching (or all if pid=None)
    drain_events()                  — atomically drain the event buffer
    is_observing(pid)               — check if a PID is being observed
    status()                        — overview of all observers + buffer
"""

import os
import objc
import threading
import time
from collections import deque

from ApplicationServices import (
    AXObserverCreate,
    AXObserverAddNotification,
    AXObserverRemoveNotification,
    AXObserverGetRunLoopSource,
    AXUIElementCreateApplication,
)
from CoreFoundation import (
    CFRunLoopGetCurrent,
    CFRunLoopRunInMode,
    CFRunLoopStop,
    CFRunLoopAddSource,
    CFRunLoopRemoveSource,
    CFRunLoopWakeUp,
    kCFRunLoopDefaultMode,
)

from nexus.sense.access import ax_attr, invalidate_cache


# ---------------------------------------------------------------------------
# Monitored notifications (registered per observed app)
# ---------------------------------------------------------------------------

_NOTIFICATIONS = [
    "AXFocusedUIElementChanged",
    "AXWindowCreated",
    "AXUIElementDestroyed",
    "AXValueChanged",
    "AXSelectedChildrenChanged",
    "AXTitleChanged",
]

# Per-notification debounce overrides (seconds).
# Default is 0.5s; noisy ones get longer windows.
_DEBOUNCE = {
    "AXTitleChanged": 2.0,
    "AXValueChanged": 0.5,
}
_DEBOUNCE_DEFAULT = 0.5

_MAX_EVENTS = 200

# ---------------------------------------------------------------------------
# Module-level state (same pattern as web.py)
# ---------------------------------------------------------------------------

# pid → {"observer": AXObserverRef, "source": CFRunLoopSource,
#         "app_ref": AXUIElementRef, "app_name": str, "started": float}
_observers = {}

_event_buffer = deque(maxlen=_MAX_EVENTS)
_lock = threading.Lock()

_thread = None
_runloop = None          # set from within the observer thread
_runloop_ready = None    # threading.Event, signaled when runloop is set

# Debounce tracking: (pid, notification_type) → timestamp
_last_event = {}

# Reverse lookup: id(observer) → pid
_observer_to_pid = {}


# ---------------------------------------------------------------------------
# AXObserver callback
# ---------------------------------------------------------------------------

@objc.callbackFor(AXObserverCreate)
def _on_notification(observer, element, notification, refcon):
    """AXObserver callback — runs on the observer thread.

    Debounces by (pid, notification_type), extracts minimal info from
    the element (before it goes stale), and appends to the shared buffer.
    """
    now = time.time()
    notif = str(notification)

    pid = _observer_to_pid.get(id(observer))
    if pid is None:
        return

    # Debounce
    key = (pid, notif)
    window = _DEBOUNCE.get(notif, _DEBOUNCE_DEFAULT)
    with _lock:
        last = _last_event.get(key, 0)
        if now - last < window:
            return
        _last_event[key] = now

    # Extract role + label immediately (element may go stale after return)
    role = ax_attr(element, "AXRole") or ""
    title = ax_attr(element, "AXTitle") or ax_attr(element, "AXDescription") or ""

    with _lock:
        _event_buffer.append({
            "ts": now,
            "pid": pid,
            "type": notif,
            "role": role,
            "label": title,
        })

    # Invalidate tree cache so next see() gets fresh data
    invalidate_cache()


# ---------------------------------------------------------------------------
# Background thread
# ---------------------------------------------------------------------------

def _ensure_thread():
    """Start the observer background thread if not running."""
    global _thread, _runloop_ready

    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _stop_flag.clear()
        _runloop_ready = threading.Event()
        _thread = threading.Thread(
            target=_observer_loop, daemon=True, name="nexus-observer"
        )
        _thread.start()

    # Wait for the runloop to be ready (up to 2s)
    _runloop_ready.wait(timeout=2.0)


_stop_flag = threading.Event()


def _observer_loop():
    """Background thread: runs CFRunLoop for all AXObservers.

    Uses CFRunLoopRunInMode in a loop (1s intervals) instead of
    CFRunLoopRun, which exits immediately when no sources are registered.
    """
    global _runloop

    _runloop = CFRunLoopGetCurrent()
    _runloop_ready.set()

    while not _stop_flag.is_set():
        # Run the loop for 1 second — processes any pending AXObserver events,
        # then returns so we can check the stop flag.
        CFRunLoopRunInMode(kCFRunLoopDefaultMode, 1.0, False)

    _runloop = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_observing(pid, app_name=""):
    """Start observing an app for accessibility events.

    Creates an AXObserver, registers for key notifications, and adds
    its source to the background CFRunLoop thread.

    Returns dict with ok/error status.
    """
    with _lock:
        if pid in _observers:
            return {"ok": True, "already": True, "pid": pid, "app": _observers[pid]["app_name"]}

    _ensure_thread()

    if _runloop is None:
        return {"ok": False, "error": "Observer thread failed to start"}

    # Create observer
    err, observer = AXObserverCreate(pid, _on_notification, None)
    if err != 0:
        return {"ok": False, "error": f"AXObserverCreate failed (error {err})"}

    # Register for each notification
    app_ref = AXUIElementCreateApplication(pid)
    for notif in _NOTIFICATIONS:
        AXObserverAddNotification(observer, app_ref, notif, None)

    # Add to the background thread's runloop
    source = AXObserverGetRunLoopSource(observer)
    CFRunLoopAddSource(_runloop, source, kCFRunLoopDefaultMode)
    CFRunLoopWakeUp(_runloop)

    with _lock:
        _observers[pid] = {
            "observer": observer,
            "source": source,
            "app_ref": app_ref,
            "app_name": app_name,
            "started": time.time(),
        }
        _observer_to_pid[id(observer)] = pid

    return {"ok": True, "pid": pid, "app": app_name, "notifications": len(_NOTIFICATIONS)}


def stop_observing(pid=None):
    """Stop observing an app (or all apps if pid is None).

    Removes notifications, detaches from the runloop, cleans up state.
    """
    with _lock:
        pids = [pid] if pid is not None else list(_observers.keys())

    stopped = []
    for p in pids:
        with _lock:
            info = _observers.pop(p, None)
            if info:
                _observer_to_pid.pop(id(info["observer"]), None)

        if info and _runloop is not None:
            # Remove each notification
            for notif in _NOTIFICATIONS:
                try:
                    AXObserverRemoveNotification(info["observer"], info["app_ref"], notif)
                except Exception:
                    pass
            # Detach from runloop
            try:
                CFRunLoopRemoveSource(_runloop, info["source"], kCFRunLoopDefaultMode)
                CFRunLoopWakeUp(_runloop)
            except Exception:
                pass
            stopped.append(p)

    return {"ok": True, "stopped": stopped}


def drain_events():
    """Atomically drain all buffered events. Returns list of event dicts.

    Called by see() to include pending events in output.
    Also lazily cleans up observers for dead PIDs.
    """
    _check_stale_observers()

    with _lock:
        events = list(_event_buffer)
        _event_buffer.clear()
    return events


def is_observing(pid=None):
    """Check if a PID is being observed (or if anything is observed when pid=None)."""
    with _lock:
        if pid is not None:
            return pid in _observers
        return len(_observers) > 0


def status():
    """Return overview of all active observers and buffer state."""
    now = time.time()
    with _lock:
        apps = []
        for pid, info in _observers.items():
            apps.append({
                "pid": pid,
                "app": info["app_name"],
                "since": round(now - info["started"], 1),
            })
        buffered = len(_event_buffer)

    return {"ok": True, "observing": apps, "buffered": buffered}


# ---------------------------------------------------------------------------
# Event formatting (used by fusion.py)
# ---------------------------------------------------------------------------

def format_events(events):
    """Format observation events as compact text for see() output.

    Groups by notification type, collapses multiples.
    Returns empty string if no events.
    """
    if not events:
        return ""

    # Group by type
    by_type = {}
    for ev in events:
        t = ev["type"].replace("AX", "")
        by_type.setdefault(t, []).append(ev)

    lines = [f"Recent events ({len(events)}):"]
    for event_type, evts in by_type.items():
        if len(evts) == 1:
            ev = evts[0]
            role = ev["role"].replace("AX", "") if ev["role"] else ""
            label_part = f' "{ev["label"]}"' if ev["label"] else ""
            role_part = f"[{role}]" if role else ""
            lines.append(f"  {event_type}: {role_part}{label_part}".rstrip())
        else:
            labels = [e["label"] for e in evts if e["label"]]
            if labels:
                shown = ", ".join(labels[:5])
                lines.append(f"  {event_type} x{len(evts)}: {shown}")
            else:
                lines.append(f"  {event_type} x{len(evts)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_stale_observers():
    """Remove observers for PIDs that are no longer running."""
    with _lock:
        pids = list(_observers.keys())

    for pid in pids:
        try:
            os.kill(pid, 0)  # signal 0 = check existence
        except OSError:
            stop_observing(pid)


def shutdown():
    """Clean up all observers and stop the background thread.

    Called on server shutdown.
    """
    stop_observing()  # all

    global _thread
    _stop_flag.set()
    if _thread is not None:
        _thread.join(timeout=3.0)
        _thread = None
