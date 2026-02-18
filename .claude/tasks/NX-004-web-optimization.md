# NX-004: Web Command Optimization

**Branch:** `task/NX-004-web-optimization`
**Status:** PENDING
**Depends on:** None
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** Every web command opens and closes a CDP connection to Chrome.
> Make connections persistent, add tab targeting, and add verbosity tiers so web-describe
> isn't always a massive dump.

---

## What

- Persistent CDP connection: connect once, reuse across web commands within a session
- Connection pool with auto-reconnect if Chrome restarts or tab changes
- Add `--tab N` flag to target a specific tab (currently always first tab)
- Tiered verbosity for `web-describe`:
  - Default: title, URL, focused element, visible form fields, main CTA buttons
  - `--full`: current behavior (all headings, all links, all inputs)
- Replace DOM `querySelectorAll` scraping with CDP AXTree in `web-describe` (leverage existing `web-ax`)

## Why

Web commands are the most-used Nexus feature. Connection overhead per call adds up fast. The full `web-describe` dump wastes tokens when Claude just needs to know what page it's on.

## Where

- **Read:** `nexus/cdp.py`, `nexus/oculus/web.py`, `nexus/digitus/web.py`
- **Write:**
  - `nexus/cdp.py` — add persistent connection mode, reconnect logic, tab targeting
  - `nexus/oculus/web.py` — tiered `web-describe`, integrate AXTree as default
  - `nexus/run.py` — add `--tab` and `--full` args to web subparsers
  - `nexus/tests/test_web_opt.py` (new) — tests for connection reuse and tab targeting

## Validation

- [ ] Sequential web commands reuse the same CDP session (no reconnect per call)
- [ ] `--tab 2` targets the second browser tab
- [ ] Default `web-describe` returns concise output (title, URL, focus, key elements)
- [ ] `web-describe --full` returns current verbose output (no regression)
- [ ] Connection auto-recovers if Chrome restarts
- [ ] All existing web E2E tests pass
- [ ] Benchmark: 3 sequential web commands are faster with persistent connection

---

## Not in scope

- Daemon mode integration (that's NX-003 — this works in single-shot mode too)
- Electron app CDP (that's NX-008)
