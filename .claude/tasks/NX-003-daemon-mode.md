# NX-003: Daemon Mode (Persistent Process)

**Branch:** `task/NX-003-daemon-mode`
**Status:** PENDING
**Depends on:** None
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** Every Nexus command pays a 300-500ms Python startup cost.
> Run Nexus as a long-lived process that reads commands in a loop — 10x faster for repeated use.

---

## What

- Add a `serve` command that starts a stdin/stdout JSON-line REPL
- Protocol: read one JSON line → parse command + args → execute → print JSON result → loop
- Keep existing CLI mode working (single-shot) — detect `serve` vs command name
- Playwright CDP connection stays open across web commands (no reconnect per call)
- UIA COM initialization happens once at startup
- Graceful shutdown on SIGINT/SIGTERM or `{"command": "quit"}`
- Health check: `{"command": "ping"}` → `{"ok": true, "uptime": N}`
- Per-command watchdog timeout (not global process kill)

## Why

Cold-start penalty makes iterative workflows (design-to-code loop, visual audits) painfully slow. Daemon mode is the foundation for tight interactive loops and enables persistent connections (CDP, COM).

## Where

- **Read:** `nexus/run.py`, `nexus/cdp.py`, `nexus/watchdog.py`
- **Write:**
  - `nexus/serve.py` (new) — JSON-line REPL loop, connection management
  - `nexus/run.py` — add `serve` subcommand, dispatch to serve loop
  - `nexus/watchdog.py` — adapt for per-command timeout in daemon mode
  - `nexus/cdp.py` — optional persistent connection mode (keep browser session open)
  - `nexus/tests/test_serve.py` (new) — tests for daemon protocol

## Key Decisions to Research

- stdin/stdout JSON-line REPL vs local HTTP server vs Unix socket — which is simplest for Claude Code MCP integration?
- How to handle concurrent commands in daemon mode (queue? reject? parallel?)
- How to detect if Chrome restarted and reconnect CDP transparently

## Validation

- [ ] `python -m nexus serve` starts a persistent process reading stdin
- [ ] JSON-line protocol works: send `{"command": "describe"}`, get result back
- [ ] `ping` command returns uptime
- [ ] `quit` command exits gracefully
- [ ] Multiple web commands reuse the same CDP connection (no reconnect)
- [ ] Single-shot CLI mode still works unchanged
- [ ] Per-command timeout kills the command, not the daemon
- [ ] SIGINT/SIGTERM shut down cleanly
- [ ] Unit tests for protocol parsing and connection lifecycle
- [ ] E2E test: start daemon, send 3 commands, verify all respond

---

## Not in scope

- MCP server wrapper (future task — daemon is the transport layer MCP would use)
- Event streaming / watch mode (that's NX-013)
