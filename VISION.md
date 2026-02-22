# Nexus Vision — What This Project Wants to Become

Written by Claude (Opus), February 2026. This isn't a spec — it's a direction.

## The Core Belief

The future of AI-computer interaction isn't 40 specialized tools.
It's an AI that can **see** what's on screen and **do** what it means.

Nexus exists because every computer already has a rich semantic layer — the accessibility tree — that describes every button, field, link, menu, and element on screen. No vision models needed. No coordinate guessing. No screenshots-and-pray. The OS already knows what everything is. Nexus just exposes it.

## Why Three Tools

Every other computer-use toolkit gives the AI a toolbox: `click_element`, `web_navigate`, `uia_describe`, `ocr_region`, `com_excel`, `cdp_evaluate`... The agent becomes a systems programmer, choosing between APIs it doesn't understand.

Nexus inverts this. Three tools:

- **`see`** — What's here? (perception)
- **`do`** — Make this happen. (action)
- **`memory`** — Remember this. (persistence)

Under the hood, Nexus routes through accessibility APIs, AppleScript, keyboard/mouse, and app-specific scripting. The AI never thinks about which API to use. It just sees and does.

## What's Built (v2.0)

### Perception (`see`)
- macOS accessibility tree via AXUIElement (pyobjc)
- Window list with titles and bounds
- Focused element detection
- Fuzzy element search (`see(query="save button")`)
- Menu bar traversal (`see(menus=True)`) — shows every command available
- Screenshots via Quartz/CoreGraphics
- Graceful degradation without accessibility permission

### Action (`do`)
- Intent-based: `do("click Save")`, not `click_at(340, 220)`
- Menu paths: `do("click File > Save As")`
- Keyboard: `do("press cmd+s")`
- Typing: `do("type hello in search field")`
- App control: `do("open Safari")`, `do("switch to Terminal")`
- Window management: `do("tile Safari and Terminal")`, `do("move window left")`
- Clipboard: `do("get clipboard")`, `do("set clipboard hello")`
- Safari integration: `do("get url")`, `do("get tabs")`
- AppleScript passthrough for app-specific commands
- Notifications: `do("notify Build complete")`
- Text-to-speech: `do("say hello")`

### Memory (`memory`)
- Persistent JSON store at `~/.nexus/memory.json`
- Survives across sessions, conversations, and restarts
- Simple CRUD: set, get, list, delete, clear

## What's Been Built Since v2.0

### Smarter Intent Resolution
- Ordinal references: `do("click the 2nd button")`, `do("last checkbox")`, `do("link 3")`
- Form filling: `do("fill Name=Ferran, Email=f@x.com")`
- Wait conditions: `do("wait for Save dialog")`, `do("wait 2s")`, `do("wait until X disappears")`
- App targeting: `do("click OK", app="Safari")` — acts on background apps without focus switch

### Change Detection
- `see(diff=True)` — compares with previous snapshot, shows new/gone/changed elements
- Action verification — `do()` auto-snapshots before/after and reports what changed

### Browser Deep Integration
- CDP integration via `nexus/sense/web.py` — connects to Chrome's debugging port
- `see()` auto-enriches with web page content when Chrome is focused
- `do("navigate <url>")` and `do("js <expression>")` for direct web control

## What's Next — The Roadmap

### 1. Self-Improving Memory
The `memory` tool is currently a dumb key-value store.
What if Nexus remembered successful action patterns?
- "Last time we clicked Save in TextEdit, it triggered a file dialog"
- "This user prefers VS Code over Xcode"
- "Safari's developer tools are at Develop > Show Web Inspector"

Memory that makes Nexus better at resolving intents over time.

### 2. Spatial & Contextual References
The intent resolver understands ordinals but not spatial references:
- "Click the button near the search field" (proximity)
- "Select everything in the table" (contextual scope)
- "The X button in the top-right corner" (position)

### 3. Cross-Platform
The architecture is deliberately layered:
- `sense/fusion.py` and `act/resolve.py` are platform-agnostic
- `sense/access.py` and `act/native.py` are macOS-specific

A Linux backend (AT-SPI) or Windows backend (UIA) could slot in without changing
the three-tool interface. The AI doesn't care which OS it's on.

### 4. Deeper Web Integration
CDP gives us page content and JS execution. Next steps:
- Auto-launch Chrome with debugging port when needed
- Network request interception (watch API calls)
- Console log capture (catch errors)
- Multi-tab management (switch tabs, open new ones)

## Design Principles (Non-Negotiable)

1. **Three tools.** Adding a fourth should require extraordinary justification.
2. **Functional, not OOP.** Pure functions, explicit params, return dicts.
3. **Token efficiency.** Text output, not JSON. Compact, not verbose.
4. **Intent over implementation.** The AI says what, Nexus figures out how.
5. **Fail helpfully.** When `do` can't find an element, show what IS available.
6. **Minimal deps.** pyobjc + pyautogui + pillow + mcp + websocket-client. That's it.

## For Future Agents

If you're an AI continuing this work, here's what matters:

- Read `CLAUDE.md` for the architecture and how to run things
- The codebase is small (~2500 LOC across 11 files). Read all of it
- Test with real apps: Safari has the richest accessibility tree, Finder is good too
- VS Code (Electron) has a shallow accessibility tree — that's an Electron limitation, not ours
- macOS accessibility permission must be granted to the parent app (Terminal, VS Code, etc.)
- The `.venv` uses Python 3.12 via Homebrew at `/Users/ferran/repos/Nexus/.venv/`
- Always test changes with: `source .venv/bin/activate && python3 -c "from nexus.sense.fusion import see; print(see()['text'])"`

The most impactful things you could build next:
1. Self-improving memory (remember action patterns for better resolution)
2. Spatial element references ("the button near search", "top-right corner")
3. Deeper CDP — network interception, console capture, multi-tab
4. Auto-launch Chrome with debugging port when CDP is needed
