# NX-009: Web Capture API (Intercept JSON Responses)

**Branch:** `task/NX-009-web-capture-api`
**Status:** PENDING
**Depends on:** None
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** Many SPAs load content via fetch/XHR — the API response JSON is cleaner
> than scraping the rendered DOM. Add a command that intercepts these API responses as a page loads.

---

## What

- Add `web-capture-api URL` command that:
  1. Sets up `page.on("response")` listener filtered by `content-type: application/json`
  2. Navigates to the URL
  3. Waits for page load + a short settling period
  4. Returns all captured JSON API responses: `[{url, status, body}]`
- Optional: `--filter PATTERN` to only capture responses matching a URL pattern
- Optional: `--block PATTERNS` to block ad/tracker URLs via `page.route()` for faster loads
- Cap response body size (e.g., 10KB per response, 50KB total) to avoid context explosion

## Why

React docs sites, dashboards, SPAs — they all load content via fetch. The API response is structured data, cleaner than the rendered DOM. This is the "X-ray" view of what a page actually loaded.

## Where

- **Read:** `nexus/cdp.py`, `nexus/oculus/web.py`
- **Write:**
  - `nexus/oculus/web.py` — add `web_capture_api()` function
  - `nexus/run.py` — add `web-capture-api` subcommand with URL, --filter, --block args
  - `nexus/tests/test_web_capture.py` (new) — tests

## Validation

- [ ] `web-capture-api https://example.com` returns intercepted JSON responses
- [ ] `--filter /api/` only captures responses with `/api/` in the URL
- [ ] Response bodies are capped at configured size limit
- [ ] Works on a real SPA (test with a React app or public API-backed site)
- [ ] Non-JSON responses are ignored
- [ ] Returns empty list gracefully when no JSON responses are captured
- [ ] E2E test with a known SPA

---

## Not in scope

- WebSocket interception (future enhancement)
- Modifying requests (this is read-only capture)
