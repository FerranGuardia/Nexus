"""Nexus Daemon — persistent JSON-line REPL over stdin/stdout.

Eliminates cold-start penalty by running Nexus as a long-lived process.
Protocol: read one JSON line → parse command + args → execute → print JSON result → loop.

No side effects on import. Call serve_loop() to start.
"""

import json
import os
import sys
import threading
import time

from nexus.cache import cache_get, cache_put, cache_clear

# Commands eligible for caching (read-only awareness commands)
CACHEABLE_COMMANDS = {"describe", "windows", "web-describe", "web-ax", "web-text", "web-links"}


def _make_response(data: dict, request_id=None) -> dict:
    """Wrap a command result with protocol metadata."""
    if request_id is not None:
        data["_id"] = request_id
    return data


def _error(msg: str, request_id=None) -> dict:
    return _make_response({"ok": False, "error": msg}, request_id)


def _run_with_timeout(func, kwargs, timeout_sec):
    """Run func(**kwargs) in a thread with a timeout. Returns (result, error)."""
    result_box = [None]
    error_box = [None]

    def _worker():
        try:
            # COM/UIA requires CoInitialize in each thread
            import pythoncom
            pythoncom.CoInitialize()
            try:
                result_box[0] = func(**kwargs)
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            error_box[0] = str(e)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=timeout_sec)

    if t.is_alive():
        return None, "Command timed out after %d seconds" % timeout_sec
    if error_box[0]:
        return None, error_box[0]
    return result_box[0], None


# ---------------------------------------------------------------------------
# Event streamer — background thread that pushes watch events to stdout
# ---------------------------------------------------------------------------

_event_streamer_active = threading.Event()
_event_streamer_thread = None

# Events that should invalidate the UIA cache
_CACHE_INVALIDATING_EVENTS = frozenset({
    "focus_changed", "window_opened", "window_closed",
    "structure_changed", "property_changed",
})


def _event_streamer_loop():
    """Background loop: poll watcher events and write them as JSON lines."""
    from nexus.watcher import poll_events, watch_status
    while _event_streamer_active.is_set():
        events = poll_events(max_events=20, timeout=0.5)
        for evt in events:
            # Invalidate cache on relevant events
            if evt.get("event") in _CACHE_INVALIDATING_EVENTS:
                cache_clear()
            _write({"_event": True, **evt})
        # Check if watcher died
        status = watch_status()
        if not status.get("running"):
            break
    _event_streamer_active.clear()


def _start_event_streamer(request_id=None):
    """Start the background event streamer thread."""
    global _event_streamer_thread
    _event_streamer_active.set()
    _event_streamer_thread = threading.Thread(
        target=_event_streamer_loop,
        daemon=True,
        name="nexus-event-streamer",
    )
    _event_streamer_thread.start()


def _stop_event_streamer():
    """Stop the background event streamer."""
    global _event_streamer_thread
    _event_streamer_active.clear()
    if _event_streamer_thread is not None:
        _event_streamer_thread.join(timeout=3.0)
        _event_streamer_thread = None


def _emit_status(status: str, **extra):
    """Write a daemon status line to stderr. Structured JSON for machine parsing."""
    msg = {"nexus": "daemon", "status": status, **extra}
    sys.stderr.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def _probe_capabilities() -> dict:
    """Detect which subsystems are available. Returns {name: bool}."""
    caps = {}

    # UIA / COM
    try:
        import pythoncom  # noqa: F401
        caps["uia"] = True
    except ImportError:
        caps["uia"] = False

    # CDP — just check if port 9222 is listening (fast TCP probe)
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        s.connect(("127.0.0.1", 9222))
        s.close()
        caps["cdp"] = True
    except Exception:
        caps["cdp"] = False

    # OmniParser vision server
    try:
        import urllib.request
        url = os.environ.get("NEXUS_VISION_URL", "http://127.0.0.1:8500") + "/health"
        req = urllib.request.urlopen(url, timeout=1)
        caps["vision"] = req.status == 200
    except Exception:
        caps["vision"] = False

    # pyautogui
    try:
        import pyautogui  # noqa: F401
        caps["screen"] = True
    except ImportError:
        caps["screen"] = False

    return caps


def serve_loop(commands: dict, format_fn=None, default_timeout: int = 30):
    """Main daemon loop. Reads JSON lines from stdin, dispatches, writes results to stdout.

    State machine: initializing → loading → ready → (running) → stopped
    On failure:    initializing → failed

    Args:
        commands: dict of {name: (func, arg_extractor_from_dict)} — same shape as _build_commands()
                  but extractors take a dict (not argparse Namespace).
        format_fn: optional function(result_dict, format_str) -> str. If None, always JSON.
        default_timeout: per-command timeout in seconds.
    """
    _emit_status("initializing")

    try:
        # Probe what's available
        _emit_status("loading")
        capabilities = _probe_capabilities()
    except Exception as e:
        _emit_status("failed", error=str(e))
        sys.exit(1)

    start_time = time.time()
    _emit_status("ready",
                 capabilities=capabilities,
                 tools=len(commands),
                 builtin=["ping", "quit", "commands", "task", "watch", "recall", "batch"])

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        # Parse the request
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _write(_error("Invalid JSON: %s" % str(e)))
            continue

        if not isinstance(req, dict):
            _write(_error("Request must be a JSON object"))
            continue

        cmd_name = req.get("command", "")
        request_id = req.get("_id")
        timeout = req.get("timeout", default_timeout)
        fmt = req.get("format", "json")

        # Built-in commands
        if cmd_name == "ping":
            _write(_make_response({
                "ok": True,
                "uptime": round(time.time() - start_time, 1),
            }, request_id))
            continue

        if cmd_name == "quit":
            _write(_make_response({"ok": True, "message": "Nexus daemon shutting down"}, request_id))
            break

        if cmd_name == "commands":
            _write(_make_response({
                "ok": True,
                "commands": sorted(commands.keys()) + ["ping", "quit", "commands", "task", "watch"],
            }, request_id))
            continue

        if cmd_name == "task":
            from nexus.recorder import task_start, task_end, task_note, task_status
            action = req.get("action", "")
            if action == "start":
                result = task_start(req.get("name", "unnamed"))
            elif action == "end":
                result = task_end(req.get("outcome", "partial"), notes=req.get("notes"))
            elif action == "note":
                result = task_note(req.get("text", ""))
            elif action == "status":
                result = task_status()
            else:
                _write(_error("task action must be: start, end, note, status", request_id))
                continue
            _write(_make_response(result, request_id))
            continue

        if cmd_name == "recall":
            from nexus.cortex.memory import recall, recall_stats
            if req.get("stats"):
                result = recall_stats()
            else:
                result = recall(query=req.get("query"), app=req.get("app"),
                               tag=req.get("tag"), limit=req.get("limit", 10))
            _write(_make_response(result, request_id))
            continue

        if cmd_name == "watch":
            from nexus.watcher import start_watching, stop_watching, poll_events, watch_status
            action = req.get("action", "start")
            if action == "start":
                events_filter = req.get("events")  # list of event types or None
                result = start_watching(events=events_filter)
                # Start background event streamer if not already running
                if result.get("ok") and not _event_streamer_active.is_set():
                    _start_event_streamer(request_id)
            elif action == "stop":
                _stop_event_streamer()
                result = stop_watching()
            elif action == "poll":
                max_events = req.get("max", 50)
                timeout = req.get("timeout", 0.0)
                events = poll_events(max_events=max_events, timeout=timeout)
                result = {"command": "watch-poll", "ok": True, "events": events, "count": len(events)}
            elif action == "status":
                result = watch_status()
            else:
                _write(_error("watch action must be: start, stop, poll, status", request_id))
                continue
            _write(_make_response(result, request_id))
            continue

        if cmd_name == "batch":
            from nexus.batch import execute_batch
            steps = req.get("steps", "")
            if not steps:
                _write(_error("batch requires 'steps' field", request_id))
                continue
            t0 = time.perf_counter()
            result, err = _run_with_timeout(
                execute_batch,
                {"batch_str": steps, "commands": commands,
                 "verbose": req.get("verbose", False),
                 "continue_on_error": req.get("continue_on_error", False)},
                timeout,
            )
            if err:
                _write(_error(err, request_id))
            else:
                _write(_make_response(result, request_id))
            continue

        # Look up command
        if cmd_name not in commands:
            _write(_error("Unknown command: '%s'" % cmd_name, request_id))
            continue

        func, extract = commands[cmd_name]

        # Extract kwargs from the request dict
        try:
            kwargs = extract(req)
        except Exception as e:
            _write(_error("Bad arguments for '%s': %s" % (cmd_name, str(e)), request_id))
            continue

        # Check cache (unless force=True)
        force = req.get("force", False)
        if not force and cmd_name in CACHEABLE_COMMANDS:
            cached = cache_get(cmd_name, kwargs, use_file=False)
            if cached is not None:
                _write(_make_response(cached, request_id))
                continue

        # Execute with timeout
        t0 = time.perf_counter()
        result, err = _run_with_timeout(func, kwargs, timeout)
        duration_ms = int((time.perf_counter() - t0) * 1000)

        if err:
            _write(_error(err, request_id))
            continue

        # Record trajectory
        from nexus.recorder import record
        record(cmd_name, kwargs, result, duration_ms)

        # Store in cache for cacheable commands
        if cmd_name in CACHEABLE_COMMANDS:
            cache_put(cmd_name, kwargs, result, use_file=False)

        # Auto-prune: apply per-command policies (default ON, opt-out with "auto": false)
        if not req.get("summary") and not req.get("diff") and req.get("auto", True):
            from nexus.cortex.pruning import apply_policy
            result = apply_policy(cmd_name, result, cache_kwargs=kwargs)
            suggested = result.pop("_suggested_format", None)
            if suggested and fmt == "json":
                fmt = suggested

        # Format output
        if fmt != "json" and format_fn:
            text = format_fn(result, fmt)
            if text:
                _write(_make_response({"ok": True, "text": text}, request_id))
                continue

        _write(_make_response(result, request_id))

    # Stop event streamer if running
    _stop_event_streamer()
    try:
        from nexus.watcher import stop_watching
        stop_watching()
    except Exception:
        pass

    _emit_status("stopped", uptime=round(time.time() - start_time, 1))


def _write(data: dict):
    """Write a single JSON line to stdout and flush."""
    try:
        sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        sys.exit(0)
