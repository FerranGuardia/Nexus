"""Via recorder — high-level recording orchestration.

Composes tap.py (CGEventTap capture) with db.py (SQLite storage).
One recording at a time. Events accumulate in memory during recording
and flush to the database on stop.

Usage:
    do("via record gmail-login")  → starts capturing user input
    do("via stop")                → stops, saves route to DB
    do("via list")                → shows saved routes
    do("via replay gmail-login")  → replays the route
    do("via delete gmail-login")  → removes from DB
"""

import re
import time

from nexus.mind import db
from nexus.via import tap


# ---------------------------------------------------------------------------
# Recording state (in-memory, one active recording at a time)
# ---------------------------------------------------------------------------

_recording = None  # {"id": str, "name": str, "app": str, "started": float}


def _slugify(name):
    """Convert 'Login to Gmail' to 'login-to-gmail'."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip()).strip('-')
    return slug or "unnamed"


def _unique_slug(base):
    """Ensure slug doesn't collide with existing route IDs."""
    slug = base
    n = 2
    while db.via_route_get(slug) is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


# ---------------------------------------------------------------------------
# Recording API
# ---------------------------------------------------------------------------

def start_recording(name, app=None):
    """Start recording a new Via route.

    Starts the CGEventTap and creates a DB entry.
    Returns {"ok": True, "id": slug, "name": name}.
    """
    global _recording
    if _recording is not None:
        return {
            "ok": False,
            "error": f'Already recording route "{_recording["id"]}". '
                     f'Use do("via stop") first.',
        }

    slug = _unique_slug(_slugify(name))
    db.via_route_create(slug, name, app)

    ok = tap.start_tap()
    if not ok:
        # Clean up the DB entry
        db.via_route_delete(slug)
        return {
            "ok": False,
            "error": "Failed to start CGEventTap. Check accessibility permissions.",
        }

    _recording = {"id": slug, "name": name, "app": app, "started": time.time()}
    return {"ok": True, "action": "via_record_start", "id": slug, "name": name}


def stop_recording():
    """Stop recording and flush events to database.

    Returns {"ok": True, "id": ..., "steps": count, "duration": elapsed}.
    """
    global _recording
    if _recording is None:
        return {"ok": False, "error": 'Not recording. Use do("via record <name>") first.'}

    route_id = _recording["id"]
    elapsed = time.time() - _recording["started"]

    # Stop tap and get raw events
    events = tap.stop_tap()

    # Filter noise: only keep click, key, scroll events that have event_type
    events = [e for e in events if e.get("event_type")]

    # Store events to DB
    for i, ev in enumerate(events):
        db.via_step_insert(
            route_id=route_id,
            step_num=i + 1,
            ts_offset_ms=ev.get("ts_offset_ms", 0),
            event_type=ev["event_type"],
            x=ev.get("x"),
            y=ev.get("y"),
            rel_x=ev.get("rel_x"),
            rel_y=ev.get("rel_y"),
            window_x=ev.get("window_x"),
            window_y=ev.get("window_y"),
            window_w=ev.get("window_w"),
            window_h=ev.get("window_h"),
            button=ev.get("button"),
            key_code=ev.get("key_code"),
            key_char=ev.get("key_char"),
            modifiers=ev.get("modifiers"),
            ax_role=ev.get("ax_role"),
            ax_label=ev.get("ax_label"),
            pid=ev.get("pid"),
            app_name=ev.get("app_name"),
        )

    # Update route metadata
    db.via_route_update(route_id, duration_ms=elapsed * 1000, step_count=len(events))

    result = {
        "ok": True,
        "action": "via_record_stop",
        "id": route_id,
        "name": _recording["name"],
        "steps": len(events),
        "duration_s": round(elapsed, 1),
    }

    # Summarize what was captured
    clicks = sum(1 for e in events if e.get("event_type") == "click")
    keys = sum(1 for e in events if e.get("event_type") == "key")
    scrolls = sum(1 for e in events if e.get("event_type") == "scroll")
    parts = []
    if clicks:
        parts.append(f"{clicks} clicks")
    if keys:
        parts.append(f"{keys} keys")
    if scrolls:
        parts.append(f"{scrolls} scrolls")
    if parts:
        result["summary"] = ", ".join(parts)

    # Show captured steps
    step_lines = []
    for i, ev in enumerate(events[:20]):  # Show first 20
        etype = ev["event_type"]
        if etype == "click":
            label = ev.get("ax_label", "")
            role = (ev.get("ax_role") or "").replace("AX", "")
            target = f' "{label}" ({role})' if label else f" at ({ev.get('x')}, {ev.get('y')})"
            rel = ""
            if ev.get("rel_x") is not None:
                rel = f" [rel {ev['rel_x']:.2f}, {ev['rel_y']:.2f}]"
            step_lines.append(f"  {i+1}. {ev.get('button', 'left')} click{target}{rel}")
        elif etype == "key":
            step_lines.append(f"  {i+1}. key: {ev.get('key_char', '?')}")
        elif etype == "scroll":
            step_lines.append(f"  {i+1}. scroll {ev.get('button', '?')}")
    if len(events) > 20:
        step_lines.append(f"  ... and {len(events) - 20} more")
    if step_lines:
        result["steps_preview"] = "\n".join(step_lines)

    _recording = None
    return result


def is_recording():
    """Check if a Via recording is active."""
    return _recording is not None


# ---------------------------------------------------------------------------
# Storage API
# ---------------------------------------------------------------------------

def list_recordings():
    """List all saved Via routes."""
    return db.via_route_list()


def get_recording(route_id):
    """Get route details including all steps."""
    route = db.via_route_get(route_id)
    if route is None:
        return None
    route["steps"] = db.via_steps_for_route(route_id)
    return route


def delete_recording(route_id):
    """Delete a Via route and its steps."""
    return db.via_route_delete(route_id)
