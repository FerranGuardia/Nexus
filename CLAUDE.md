# Nexus — Claude's Eyes & Hands on the Computer

Nexus is a Python toolkit that gives AI agents (Claude Code, Nova, Cursor, etc.) the ability to see and control a Windows desktop via MCP tools.

## Architecture

Three pillars (Latin naming):
- **Oculus** (the Eye) — read-only awareness: UIA tree, CDP, OCR, vision
- **Cortex** (the Brain) — output pruning, filtering, trajectory memory
- **Digitus** (the Hand) — actions: click, type, navigate, COM automation

## Package Layout

```
nexus/
  __main__.py          # python -m nexus → run.main()
  run.py               # CLI entry: argparse, dispatch, JSON output
  mcp_server.py        # MCP server (FastMCP, stdio transport)
  serve.py             # Daemon mode: JSON-line REPL over stdin/stdout
  tools_schema.py      # Tool definitions, descriptions, annotations
  batch.py             # Multi-step command execution with $var interpolation
  cache.py             # In-memory + file-based caching
  cdp.py               # cdp_page() and cdp_browser() context managers
  uia.py               # Pure UIA helpers
  recorder.py          # JSONL trajectory recording
  watcher.py           # UIA event monitoring
  mark.py              # Set-of-Mark screenshot annotation
  electron.py          # Electron app CDP detection
  format.py            # Output formatters (compact, minimal)
  watchdog.py          # Timeout kill thread
  oculus/              # THE EYE
    uia.py             # describe(), windows(), find(), focused()
    web.py             # web_describe(), web_ax(), web_text(), web_find(), etc.
    ocr.py             # ocr_region(), ocr_screen()
    image.py           # measure_image(), web_layout_diff()
  digitus/             # THE HAND
    input.py           # click(), move(), type_text(), key(), screenshot()
    element.py         # click_element() with fuzzy matching
    healing.py         # Self-healing click with diagnosis + recovery
    web.py             # web_click(), web_navigate(), web_input()
    system.py          # ps_run(), com_shell()
    office.py          # com_excel(), com_word(), com_outlook()
    vision.py          # vision_detect() via OmniParser server
  cortex/              # THE BRAIN
    filters.py         # Query-scoped element filtering
    summarize.py       # Smart result summarization
    pruning.py         # Per-command auto-reduction policies
    memory.py          # Trajectory compaction + recall
  tests/               # E2E + unit tests
```

## Coding Philosophy

- **Functional programming by default** — pure functions, explicit params, return dicts
- **No unnecessary abstraction** — inline and explicit beats "clean" indirection
- **Every command is a pure function**: typed params → returns dict
- **CDP uses context managers** (`cdp_page()`, `cdp_browser()`), not closures
- **No OOP unless framework requires it**

## Running

```bash
# CLI
python -m nexus describe
python -m nexus --format compact web-ax

# MCP Server (for Claude Code / Cursor / Nova)
python -m nexus.mcp_server

# Daemon (JSON-line REPL)
python -m nexus serve

# Tests
pytest nexus/tests/ -v -m "not action"
```

## Python

Must use: `C:\Users\Nitropc\AppData\Local\Programs\Python\Python312\python.exe`

## Key Deps

pyautogui, pillow, pywinauto, pywin32, mcp (FastMCP)

## Tool Annotations (MCP)

Every tool declares safety hints via `ToolAnnotations`:
- `readOnlyHint=True` — 22 observation tools
- `destructiveHint=True` — ps_run, web_pdf, com_outlook
- Tool descriptions prefixed with `[Source]` tag: `[UIA]`, `[CDP]`, `[Screen]`, `[Vision]`, `[COM]`, `[System]`, `[Electron]`, `[Meta]`

## OmniParser Vision Server

Separate sidecar at `omniparser-server/`. Own venv, own process on :8500.
Setup: `python setup.py` → `python download_models.py` → `python server.py`
