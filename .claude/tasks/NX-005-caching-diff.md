# NX-005: Caching & Diff Layer

**Branch:** `task/NX-005-caching-diff`
**Status:** PENDING
**Depends on:** NX-003 (benefits from daemon, but can work standalone with file cache)
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** Nexus rediscovers the entire screen from scratch every call.
> Cache the last result and return "nothing changed" or a diff when the screen hasn't moved.

---

## What

- Cache last `describe` / `web-describe` result with timestamp
- On next call within N seconds, return `{"changed": false}` or a diff of what changed
- Change detection via hash of (window_title + focused_name + element_count)
- Add `--force` flag to bypass cache
- In daemon mode: in-memory cache. In single-shot mode: temp file cache (`~/.nexus/cache/`)
- Research Windows `WinEventHook` for proactive cache invalidation

## Why

Most `describe` calls return the same data — Claude polls to check if anything changed. Caching eliminates redundant full scans and saves tokens by returning only deltas.

## Where

- **Read:** `nexus/oculus/uia.py`, `nexus/oculus/web.py`, `nexus/run.py`
- **Write:**
  - `nexus/cache.py` (new) — cache storage, hash computation, diff generation
  - `nexus/oculus/uia.py` — integrate cache check before full scan
  - `nexus/oculus/web.py` — integrate cache check for web commands
  - `nexus/run.py` — add `--force` flag
  - `nexus/tests/test_cache.py` (new) — unit tests for cache logic

## Validation

- [ ] Second `describe` within cache window returns `{"changed": false}`
- [ ] Changed screen returns a diff with only the modified elements
- [ ] `--force` bypasses cache and returns full result
- [ ] Cache hash correctly detects: focus change, window switch, element count change
- [ ] File-based cache works in single-shot mode
- [ ] In-memory cache works in daemon mode (NX-003)
- [ ] Unit tests for hash computation and diff generation
- [ ] No regressions in existing E2E tests

---

## Not in scope

- Event-driven cache invalidation via WinEventHook (that's NX-013 watch mode)
- Persistent knowledge store / brain level 2 (future)
