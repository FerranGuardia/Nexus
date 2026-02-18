# NX-008: Electron App Automation via CDP

**Branch:** `task/NX-008-electron-cdp`
**Status:** PENDING
**Depends on:** None (enhanced by NX-004 web optimization)
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** VS Code, Discord, Slack, and Figma are Electron apps — Chromium under the hood.
> But Nexus treats them as native windows with terrible UIA trees. Connect via CDP to get full
> DOM + accessibility tree access, just like Chrome.

---

## What

- Add `electron-connect PORT` command that connects Playwright to an Electron app's CDP port
- Once connected, all `web-*` commands work on the Electron app's renderer
- Add `electron-describe` that combines CDP AXTree with Electron-specific context (app name, window title)
- Document per-app setup:
  - VS Code: add `"remote-debugging-port": 9222` to `%APPDATA%\Code\User\argv.json`
  - Discord: launch with `--remote-debugging-port=9224`
  - Figma: launch with `--remote-debugging-port=9225`
- Add `electron-detect` command: scan common CDP ports to find running Electron apps
- Store last-connected port for auto-reconnect

## Why

Electron apps are the biggest blind spot. VS Code is Claude's primary workspace — seeing the editor contents, file tree, terminal output, and sidebar directly would be transformative. Figma access enables design co-piloting (UC5).

## Where

- **Read:** `nexus/cdp.py`, `nexus/oculus/web.py`, `nexus/digitus/web.py`
- **Write:**
  - `nexus/electron.py` (new) — connection management, port scanning, app detection
  - `nexus/cdp.py` — extend to accept custom CDP ports (not just default Chrome)
  - `nexus/run.py` — add `electron-connect`, `electron-describe`, `electron-detect` subcommands
  - `nexus/tests/test_electron.py` (new) — tests for connection protocol
  - `docs/ELECTRON-SETUP.md` (new) — per-app setup instructions

## Key Limitation

Cannot attach to already-running Electron apps without the debug port flag. Requires one-time setup per app (add launch flag or config entry).

## Validation

- [ ] `electron-connect 9222` connects to VS Code's CDP port
- [ ] `web-describe` works on the connected Electron app
- [ ] `web-ax` returns the Electron app's accessibility tree
- [ ] `electron-detect` finds running Electron apps with open CDP ports
- [ ] `electron-describe` includes app name and window title
- [ ] All existing `web-*` commands work transparently on Electron targets
- [ ] Setup docs cover VS Code, Discord, and Figma
- [ ] E2E test: connect to an Electron app, run web-describe

---

## Not in scope

- Figma plugin API integration (future — this is just CDP-level access)
- Auto-launching apps with debug flags (user does one-time setup)
