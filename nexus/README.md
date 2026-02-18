# Nexus — Claude's Eyes, Brain & Hands on the Computer

Nexus is a Python toolkit that gives AI agents structured access to the Windows desktop and browser. It bridges the gap between what an LLM can reason about and what it can actually see and do on a computer.

**39 commands** across 9 categories. Every command returns structured JSON. Usable via CLI, JSON-line daemon, or MCP server.

## Architecture

```
                    CLAUDE / ANY LLM AGENT
                         |
            ┌────────────┼────────────┐
            |            |            |
        ┌───▼───┐   ┌───▼───┐   ┌───▼───┐
        │  EYE  │   │ BRAIN │   │ HAND  │
        │oculus/│   │cortex/│   │digitus│
        └───────┘   └───────┘   └───────┘
        Read-only   Local       Actions
        awareness   compute     with side
        (UIA, CDP,  (filter,    effects
        OCR, COM)   summarize,  (click, type,
                    diff, cache) navigate)
```

- **Eye (oculus/)** — read-only data acquisition. UIA trees, CDP accessibility trees, OCR, web scraping. Zero side effects.
- **Brain (cortex/)** — local processing. Filters, summarizes, diffs, caches. Saves tokens by processing data before the LLM sees it.
- **Hand (digitus/)** — actions. Clicks, typing, keyboard shortcuts, web navigation, COM automation, PowerShell.

## Quick Start

### Prerequisites

- Python 3.12+ (`C:\Users\Nitropc\AppData\Local\Programs\Python\Python312\python.exe`)
- Dependencies: `pyautogui`, `pillow`, `uiautomation`, `pywinauto`, `playwright`, `pywin32`
- Browser commands need Chrome running with `--remote-debugging-port=9222`

### Three Ways to Use Nexus

**1. CLI (single-shot)**
```bash
python -m nexus describe                    # what's on screen
python -m nexus web-ax                      # browser accessibility tree
python -m nexus click-element "Save"        # click a button by name
python -m nexus screenshot --mark           # annotated screenshot
```

**2. Daemon (persistent process, JSON-line protocol)**
```bash
python -m nexus serve
# Then send JSON lines on stdin:
# {"command": "describe", "focus": "buttons"}
# {"command": "click-element", "name": "Save"}
```

**3. MCP Server (Model Context Protocol — auto-discovered by Claude Code)**

Configured in `.mcp.json`. Claude Code discovers all 39 tools with typed schemas and descriptions on startup. No manual setup needed — just restart Claude Code.

```bash
python -m nexus.mcp_server    # starts stdio MCP server
```

## Command Reference

### Eye — UIA (Native Apps)

| Command | Purpose |
|---------|---------|
| `describe` | Active window elements, cursor, focused element. Accepts `--focus`, `--match`, `--region` filters |
| `windows` | List all open windows with titles and positions |
| `find "query"` | Search for UI elements by name (fuzzy match) |
| `focused` | Which element has keyboard focus |

### Eye — Web (Chrome/CDP)

| Command | Purpose |
|---------|---------|
| `web-describe` | Page title, URL, key interactive elements. `--full` for everything |
| `web-text` | Full visible text of the page |
| `web-find "query"` | Find elements by visible text |
| `web-links` | All hyperlinks on the page |
| `web-tabs` | All open browser tabs |
| `web-ax` | Chrome accessibility tree (roles, names, states). `--focus`, `--match` filters |
| `web-measure "selectors"` | Exact CSS dimensions, padding, margins by selector |
| `web-markdown` | Clean article content via Readability.js |
| `web-capture-api "url"` | Navigate and capture JSON API responses |
| `web-research "query"` | Search, visit top results, extract content |

### Eye — OCR

| Command | Purpose |
|---------|---------|
| `ocr-screen` | OCR the entire active window |
| `ocr-region X Y W H` | OCR a specific screen region |

### Hand — Screen Input

| Command | Purpose |
|---------|---------|
| `screenshot` | Take screenshot. `--mark` for Set-of-Mark annotation, `--region X,Y,W,H` |
| `click X Y` | Click at coordinates. `--right`, `--double` |
| `click-element "name"` | Find element by name, click its center. `--role`, `--verify`, `--heal` |
| `click-mark N` | Click element #N from last `screenshot --mark` |
| `move X Y` | Move cursor |
| `drag X1,Y1 X2,Y2` | Drag between coordinates |
| `type "text"` | Type text at cursor |
| `key "combo"` | Press key/shortcut (e.g. `ctrl+s`, `enter`, `alt+f4`) |
| `scroll N` | Scroll wheel (positive=up, negative=down) |
| `info` | Screen resolution and cursor position |

### Hand — Web Actions

| Command | Purpose |
|---------|---------|
| `web-click "text"` | Click browser element by visible text. `--heal` |
| `web-navigate "url"` | Navigate to URL |
| `web-input "selector" "value"` | Fill input by label/placeholder/CSS |
| `web-pdf` | Export page to PDF. `--output`, `--page-format`, `--landscape` |

### Hand — System

| Command | Purpose |
|---------|---------|
| `ps-run "script"` | Execute PowerShell, return structured output |
| `com-shell --path "dir"` | Browse files via COM (no UI) |
| `com-excel action` | Excel: list, read, write, sheets |
| `com-word action` | Word: read, info |
| `com-outlook action` | Outlook: inbox, read, send |

### Hand — Electron Apps

| Command | Purpose |
|---------|---------|
| `electron-detect` | Find running Electron apps with CDP |
| `electron-connect PORT` | Connect to Electron app's CDP port |
| `electron-targets PORT` | List CDP targets on a port |

### Brain — Context Engineering

| Feature | Flag | Purpose |
|---------|------|---------|
| Compact output | `--format compact` | 70-80% token reduction on describe/find |
| Minimal output | `--format minimal` | Names and types only, no coordinates |
| Summary mode | `--summary` | Concise counts, focus, errors, spatial groups |
| Diff mode | `--diff` | Only changes since last call |
| Focus filter | `--focus buttons` | Only buttons/inputs/interactive/errors/dialogs/navigation |
| Name filter | `--match "Save*"` | Glob/regex on element names |
| Region filter | `--region top` | Spatial: top/bottom/left/right/center or X,Y,W,H |
| Self-healing | `--heal` | Auto-recover from click failures |
| Verification | `--verify` | Re-describe after click to confirm |
| Batch mode | `batch "cmd1; cmd2"` | Multiple commands, variable interpolation |

### Meta — Discoverability

| Command | Purpose |
|---------|---------|
| `describe-tools` | Dump all tool schemas. `--fmt openai` (JSON) or `--fmt markdown` |
| `serve` | Start persistent JSON-line daemon |
| `task start/end/note/status` | Task lifecycle for trajectory recording |

## Package Layout

```
nexus/
  __main__.py            # python -m nexus entry point
  run.py                 # CLI: argparse, dispatch, JSON output
  mcp_server.py          # MCP server: 39 tools via FastMCP (stdio)
  tools_schema.py        # Tool schema extraction + markdown generation
  serve.py               # JSON-line daemon mode
  batch.py               # Multi-command batch execution
  cache.py               # Result caching + diff computation
  format.py              # Compact/minimal output formatters
  cdp.py                 # CDP context managers (cdp_page, cdp_browser)
  uia.py                 # Pure UIA helpers (rect_to_dict, element_to_dict)
  mark.py                # Set-of-Mark annotation (numbered badges)
  watchdog.py            # Timeout kill thread
  recorder.py            # Trajectory recording to JSONL
  electron.py            # Electron app detection + CDP attach
  oculus/                # THE EYE (read-only)
    uia.py               # describe(), windows(), find(), focused()
    web.py               # web_describe(), web_ax(), web_find(), etc.
    ocr.py               # ocr_region(), ocr_screen()
  cortex/                # THE BRAIN (local compute)
    filters.py           # Focus/match/region filter presets
    summarize.py         # Smart summarization for describe/web-ax
  digitus/               # THE HAND (actions)
    input.py             # click(), move(), type_text(), key(), screenshot()
    element.py           # click_element() with fuzzy match
    web.py               # web_click(), web_navigate(), web_input()
    system.py            # ps_run(), com_shell()
    office.py            # com_excel(), com_word(), com_outlook()
    healing.py           # Self-healing action recovery
  tests/
    test_nexus_e2e.py    # 27 core + 11 web + action tests
    test_cache.py        # Cache unit tests
    test_format.py       # Format unit tests
    test_serve.py        # Daemon protocol tests
```

## MCP Integration

Nexus is configured as an MCP server in `.mcp.json`. When Claude Code starts, it discovers all 39 tools with their typed schemas and descriptions. The agent can then call any Nexus command without knowing the CLI syntax.

Tool names use underscores (`web_describe`, `click_element`, `type_text`) instead of the CLI's hyphens.

Screenshot returns inline images via MCP's `ImageContent` type — the agent sees the screen directly in context.

## Output Formats

```bash
python -m nexus describe                        # JSON (default, verbose)
python -m nexus describe --format compact       # One line per element, 70% smaller
python -m nexus describe --format minimal       # Names and types only
python -m nexus describe --summary              # Counts, focus, errors only
python -m nexus describe --diff                 # Changes since last call
```

**Always use `--format compact` for awareness commands** in CLI mode. Raw JSON can be 70KB+ for complex windows. Compact is ~5KB. MCP mode returns structured JSON always.

## Testing

```bash
# Safe tests (no mouse/keyboard movement)
pytest nexus/tests/ -v -m "not action"

# Web tests (needs Chrome with CDP on :9222)
pytest nexus/tests/ -v -m "web"

# Action tests (moves mouse and keyboard — don't touch anything!)
pytest nexus/tests/ -v -m "action"
```

## What's Done vs Pending

### Completed (NX-001 through NX-022)

All foundation, performance, vision, context engineering, and discoverability tasks:

- Compact output, smart traversal, daemon mode, web optimization, caching/diff (NX-001 to NX-005)
- Windows OCR, Set-of-Mark annotation, Electron CDP, web capture API (NX-006 to NX-009)
- Web research, COM Office tools (NX-014, NX-015)
- Element targeting, batch execution, diff mode, smart summarization, self-healing, query-scoped filtering (NX-016 to NX-021)
- MCP server + tool schema generation (NX-022)

### Pending

| Task | Title | Status | Notes |
|------|-------|--------|-------|
| NX-010 | OmniParser Integration | Blocked: model download | YOLO + Florence-2 for custom control detection |
| NX-011 | Measure Image | Blocked: NX-010 | Extract bounding boxes from reference designs |
| NX-012 | Web Layout Diff | Blocked: NX-011 | Numerical reference vs implementation comparison |
| NX-013 | Event-Driven Watch Mode | Ready | Stream UI events instead of polling |

## Trajectory Recording

Every command is logged to `E:\NexusData\trajectories/YYYY-MM-DD.jsonl`. Override with `NEXUS_DATA_DIR` env var. Use `task start/end/note` to tag trajectories with context.

## Design Principles

1. **Functional by default** — pure functions, typed params, return dicts. No classes.
2. **No unnecessary abstraction** — inline and explicit over clever indirection.
3. **Filter at source** — less data generated = less tokens burned = faster agent decisions.
4. **Code-first, UI-fallback** — API/COM > CLI/PowerShell > shortcuts > UIA > coordinates.
5. **Numbers over vision** — use `web-measure` for layout precision, screenshots for aesthetics.
