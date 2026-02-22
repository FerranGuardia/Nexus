# Nexus — Three Tools for AI to See and Control Your Mac

Nexus is a Python MCP server that gives AI agents (Claude Code, Cursor, etc.) the ability to see and control a macOS desktop through just three tools.

## Architecture

```
nexus/
  __init__.py           # Package, version
  __main__.py           # python -m nexus → starts MCP server
  server.py             # MCP server: see, do, memory
  sense/                # PERCEPTION
    access.py           # macOS accessibility tree (AXUIElement via pyobjc)
    screen.py           # Screenshots (Quartz/CoreGraphics)
    fusion.py           # Unified see() — merges all senses
  act/                  # ACTION
    resolve.py          # Intent parsing: "click Save" → best action
    native.py           # macOS: accessibility actions + AppleScript
    input.py            # pyautogui fallback (mouse/keyboard)
  mind/                 # MEMORY
    store.py            # Persistent JSON key-value store (~/.nexus/)
```

## The Three Tools

| Tool | Purpose | Example |
|------|---------|---------|
| `see` | What's on screen (accessibility tree, windows, focus, screenshot, diff) | `see()`, `see(query="Save")`, `see(diff=True)` |
| `do` | Execute an intent (supports ordinals, app targeting) | `do("click Save")`, `do("click the 2nd button")`, `do("click OK", app="Safari")` |
| `memory` | Persistent key-value store | `memory(op="set", key="x", value="y")` |

### `see` parameters
- `app` — which app to look at (name or PID, default: frontmost)
- `query` — search for specific elements instead of full tree
- `screenshot` — include a base64 JPEG screenshot
- `menus` — include the app's full menu bar (every command + shortcuts)
- `diff` — compare with previous snapshot, show what changed

### `do` parameters
- `action` — intent string like "click Save", "type hello in search"
- `app` — target a specific app by name (default: frontmost). Lets you act on background apps without switching focus.

### `do` intents
```
click <target>              click File > Save As        type <text>
click the 2nd <role>        click the last button       click <role> 3
type <text> in <target>     press cmd+s                 open <app>
fill Name=value, Email=val  fill form Name=x, Age=y     (multi-field)
wait for <element>          wait 2s                     wait until X disappears
switch to <app>             scroll down/up              focus <target>
close                       copy / paste / undo / redo  select all
get clipboard               get url                     get tabs
tile <app> and <app>        move window left/right      maximize
menu <path>                 notify <message>            say <text>
```

### `memory` operations
- `set` / `get` / `list` / `delete` / `clear`

## Coding Philosophy

- **Functional programming** — pure functions, explicit params, return dicts
- **Three tools, not forty** — the AI doesn't pick APIs, it sees and does
- **Intent over implementation** — "click Save" not "AXPress on AXButton"
- **Token efficiency** — compact text output, screenshots only on request
- **No OOP unless framework requires it**

## Running

```bash
# MCP Server (main way to use Nexus)
source .venv/bin/activate
python -m nexus

# Quick test
python -c "from nexus.sense.fusion import see; print(see()['text'])"

# Test do tool
python -c "from nexus.act.resolve import do; print(do('get url'))"
```

## Python

Uses venv at `.venv/` (Python 3.12 via Homebrew):
```bash
source /Users/ferran/repos/Nexus/.venv/bin/activate
```

## Key Deps

pyobjc (ApplicationServices, Quartz, Cocoa), pyautogui, pillow, mcp (FastMCP)

## Accessibility Permission

macOS requires accessibility permission for the terminal/app running Nexus.
Go to: System Settings > Privacy & Security > Accessibility

## Project Direction

See `VISION.md` for the full roadmap and design philosophy.
