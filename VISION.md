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

### Electron App Support
- Auto-detects Electron apps (VS Code, Slack, Discord, Figma, etc.)
- Sets `AXManualAccessibility` to unlock full accessibility tree (~5 → 59+ elements)
- Walks to depth 20 for Electron apps (content nests deep in Chromium DOM)
- Sidebar tabs, toolbar buttons, status bar, panel toggles — all visible and clickable

### Browser Deep Integration
- CDP integration via `nexus/sense/web.py` — connects to Chrome's debugging port
- `see()` auto-enriches with web page content when Chrome is focused
- `do("navigate <url>")` and `do("js <expression>")` for direct web control
- `ensure_cdp()` auto-launches Chrome with debugging port if not running

## Known Issues & Hard Truths

Honest assessment of where Nexus falls short, written so we can fix it.

### 1. The "Why Not Just Use the CLI?" Problem
Nexus automates GUI apps — but most power users (the exact audience who'd install an MCP server) already live in the terminal. The killer use case isn't clear yet. When does clicking buttons through accessibility APIs beat a shell command? Possible answers: testing GUI apps, automating apps with no CLI (Figma, Keynote), accessibility for users who can't use a mouse. But we haven't proven any of these compellingly.

### ~~2. Electron Blindness~~ → SOLVED
~~VS Code gives ~5 elements~~ → **59+ elements** after enabling `AXManualAccessibility`. Nexus now auto-detects Electron apps (VS Code, Slack, Discord, Figma, etc.) and sets this attribute, which tells Chromium to build the full native accessibility tree. Sidebar tabs, toolbar buttons, status bar, panel toggles — all visible and clickable. The fix waits up to 2s for the tree to build (Chromium does it async) and walks to depth 20 (Electron nests content deep). See `access.py`: `_ensure_electron_accessibility()`. For even richer access, VS Code can be launched with `--remote-debugging-port=9222` for full CDP integration.

### 3. Fragile Intent Parser
`resolve.py` is a ~770-line chain of `if/elif` regex matches. It works for the exact phrasings we've coded, but:
- "click on the Save button" works, "hit Save" doesn't
- "type hello in search" works, "enter hello into search" doesn't
- Typos, synonyms, and slight rephrasing silently fall through to the wrong handler or fail
- Every new intent means another regex and another branch

This needs to become either a proper grammar/parser, or lean on the LLM to normalize intents before they reach Nexus. The current approach doesn't scale.

### ~~4. Zero Test Suite~~ → SOLVED
264 tests for intent parsing in `tests/test_resolve.py`. Covers ordinal parsing, intent routing, keyboard handling, scroll/drag/tile/move/type, URL normalization. All mocked — no real UI needed. Still needed: integration smoke tests for see/do/memory round-trip.

### ~~5. CDP Requires Manual Setup~~ → MOSTLY SOLVED
`ensure_cdp()` auto-launches Chrome with `--remote-debugging-port=9222` if Chrome isn't running. If Chrome IS running without the flag, gives a clear restart message. Only auto-launches on explicit actions (navigate, js), not passive see(). Remaining: auto-detect and offer to restart Chrome.

### ~~6. Token Cost of `see()`~~ → SOLVED
`see()` now caps at 80 elements (configurable), filters noise (unlabeled static text/images), and shows `... and N more (use query= to search)`. Menu bar capped to 150 items (depth ≤ 2).

### 7. Locale Dependency
macOS AXRoleDescription is localized — on a Spanish system, buttons are "botón", links are "enlace". The code uses AXRole (locale-independent) for matching, but user-facing output still shows localized strings. If someone writes `do("click the button")` on a Japanese system, fuzzy matching may struggle. This is partially handled but not robustly tested across locales.

### ~~8. No Error Recovery~~ → PARTIALLY SOLVED
Click failures now include fuzzy "Did you mean?" suggestions. Ordinal failures show role counts on screen. Both surfaced in do() output. Remaining: retry logic, "wrong app focused" detection.

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

Read the "Known Issues & Hard Truths" section — that's where the real work is.

The most impactful things you could build next:
1. Test suite for intent parsing — highest ROI, prevents regressions
2. Electron/VS Code workaround — solve the blindness problem
3. Intent normalization — make the parser less fragile
4. Auto-launch Chrome with debugging port — remove CDP friction
5. Smart tree truncation — reduce token cost of see()
