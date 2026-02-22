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

## What's Next — The Roadmap I Care About

### 1. Smarter Intent Resolution
The `do` tool currently uses keyword matching. It works for "click Save" but fails for:
- "Click the third link on the page" (ordinal references)
- "Select everything in the table" (contextual scope)
- "Move the download folder to the desktop" (Finder operations)
- "Reply to the last email" (app-specific workflows)

The intent resolver should understand ordinals, spatial references, and app context.
It shouldn't need an LLM — the AI calling Nexus IS the LLM. But it needs better parsing.

### 2. Workflow Chains
Right now each `do` call is independent. But real tasks are chains:
- "Fill out this form" = see fields → type in each → click submit
- "Download this PDF" = click link → wait → check Downloads

Nexus should support `do("fill form", fields={"name": "Ferran", "email": "..."})` — multi-step intents that Nexus executes as a sequence, verifying each step.

### 3. Change Detection
After `do("click Save")`, what changed? Did a dialog appear? Did the button disappear?
A `see(diff=True)` that compares before/after would let the AI verify its actions worked.

### 4. Browser Deep Integration
Safari's accessibility tree is good but not great for web content.
Chrome DevTools Protocol (CDP) gives richer access to web pages — DOM, network, console.
Adding CDP as a perception source (activated when Chrome/Safari is focused) would make
web automation much more powerful without adding new tools.

### 5. Cross-Platform
The architecture is deliberately layered:
- `sense/fusion.py` and `act/resolve.py` are platform-agnostic
- `sense/access.py` and `act/native.py` are macOS-specific

A Linux backend (AT-SPI) or Windows backend (UIA) could slot in without changing
the three-tool interface. The AI doesn't care which OS it's on.

### 6. Self-Improving Memory
The `memory` tool is currently a dumb key-value store.
What if Nexus remembered successful action patterns?
- "Last time we clicked Save in TextEdit, it triggered a file dialog"
- "This user prefers VS Code over Xcode"
- "Safari's developer tools are at Develop > Show Web Inspector"

Memory that makes Nexus better at resolving intents over time.

## Design Principles (Non-Negotiable)

1. **Three tools.** Adding a fourth should require extraordinary justification.
2. **Functional, not OOP.** Pure functions, explicit params, return dicts.
3. **Token efficiency.** Text output, not JSON. Compact, not verbose.
4. **Intent over implementation.** The AI says what, Nexus figures out how.
5. **Fail helpfully.** When `do` can't find an element, show what IS available.
6. **No unnecessary deps.** pyobjc + pyautogui + pillow + mcp. That's it.

## For Future Agents

If you're an AI continuing this work, here's what matters:

- Read `CLAUDE.md` for the architecture and how to run things
- The codebase is small (~1000 LOC across 10 files). Read all of it
- Test with real apps: Safari has the richest accessibility tree, Finder is good too
- VS Code (Electron) has a shallow accessibility tree — that's an Electron limitation, not ours
- macOS accessibility permission must be granted to the parent app (Terminal, VS Code, etc.)
- The `.venv` uses Python 3.12 via Homebrew at `/Users/ferran/repos/Nexus/.venv/`
- Always test changes with: `source .venv/bin/activate && python3 -c "from nexus.sense.fusion import see; print(see()['text'])"`

The most impactful things you could build next:
1. Ordinal references in `do` ("click the 2nd button")
2. `see(diff=True)` for change detection
3. CDP integration for richer web perception
4. Workflow chains in `do`
