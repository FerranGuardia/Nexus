# NX-013: Event-Driven Watch Mode

**Branch:** `task/NX-013-watch-mode`
**Status:** PENDING
**Depends on:** NX-003 (daemon mode — event stream needs persistent process)
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** Claude has to keep calling `describe` to detect changes — wasteful and misses
> transient events like dialogs, toasts, and error popups. Add a watch mode that streams UI events
> in real-time.

---

## What

- Add `watch` command that starts a background event listener in daemon mode
- Use `IUIAutomation.AddAutomationEventHandler` to subscribe to:
  - Focus changes (which element/window gained focus)
  - Window open/close events
  - Property changes (name, enabled state)
  - Structure changes (child added/removed — detects dialogs appearing)
- Emit JSON-line events to stdout as they occur
- Event format: `{"event": "focus_changed", "window": "...", "element": "...", "timestamp": ...}`
- Filter noisy events (cursor blink, tooltip flicker, etc.)
- `watch --stop` to stop the event listener
- Integrate with caching (NX-005): events invalidate cache proactively

## Why

Event-driven awareness enables UC6 (Claude as second pair of eyes). Instead of polling, Claude knows immediately when something changes — a dialog appears, focus moves, a new window opens. This is the foundation for proactive assistance.

## Where

- **Read:** `nexus/uia.py`, `nexus/serve.py` (NX-003 daemon)
- **Write:**
  - `nexus/watcher.py` (new) — UIA event handlers, event filtering, JSON-line emitter
  - `nexus/serve.py` — integrate watch as a background task in daemon mode
  - `nexus/run.py` — add `watch` and `watch --stop` subcommands
  - `nexus/tests/test_watcher.py` (new) — tests for event filtering logic

## Validation

- [ ] `watch` starts streaming events in daemon mode
- [ ] Focus change events are emitted when switching windows
- [ ] Window open/close events are emitted
- [ ] Dialog appearance triggers a structure-changed event
- [ ] Noisy events (cursor blink, tooltips) are filtered out
- [ ] `watch --stop` stops the event stream
- [ ] Events are valid JSON-lines format
- [ ] Unit tests for event filtering logic

---

## Not in scope

- Web/CDP event subscriptions (future — this is UIA events only)
- AT-SPI2 Linux support (future cross-platform)
