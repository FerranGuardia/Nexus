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

## What's Built

**15,000+ LOC across 26 source files + 15 test files. 1084 tests, all passing.**
**Skills system with 17 bundled skills, exposed as MCP resources.**
**OCR fallback, system dialog detection, and dialog templates integrated into see().**
**Merged do()+see() responses, keyboard shortcut preference, path navigation, and action bundles.**
**Session state with spatial caching, action journal, and layout hash change detection.**
**Hook pipeline with 7 built-in hooks for composable extensibility.**
**Perception plugins: pluggable fallback stack (AX → OCR → templates), perception-aware do().**

### Perception (`see`)
- macOS accessibility tree via AXUIElement (pyobjc)
- Window list with titles and bounds
- Focused element detection
- Fuzzy element search (`see(query="save button")`)
- Menu bar traversal (`see(menus=True)`) — shows every command + shortcuts
- Screenshots via Quartz/CoreGraphics
- Change detection (`see(diff=True)`) — compares with previous snapshot
- Content reading (`see(content=True)`) — reads text from documents, text areas, fields
- Background observation (`see(observe=True)`) — AXObserver monitors for UI changes
- Auto-detects AXTable and AXList/AXOutline, renders as ASCII tables
- Hierarchical grouping — elements shown under container headings (Toolbar, Dialog, Tabs)
- Smart truncation — 80 elements max, filters noise, "use query=" hint
- Tree cache with 1s TTL — 6x speedup on typical `do()` cycles
- Single-pass tree walk — elements, tables, and lists collected in one traversal
- Wrapper group suppression — AXGroup "X" + AXButton "X" → only button shown
- CDP auto-enrichment — when Chrome is focused, `see()` includes web page content

### Action (`do`)
- Intent-based: `do("click Save")`, not `click_at(340, 220)`
- **75+ intent patterns** — click, type, press, scroll, fill, wait, navigate, drag, hover, bundles, and more
- Verb synonym expansion: tap/hit/select → click, enter/input → type, visit/browse → navigate
- Action chains: `do("open Safari; navigate google.com; wait 1s")` — semicolon-separated, fail-fast
- Ordinal references: `do("click the 2nd button")`, `do("last checkbox")`, `do("link 3")`
- Spatial references: `do("click button near search")`, `do("field below Username")`
- Region-based: `do("click button in top-right")` — 7 screen regions
- Container scoping: `do("click delete in the row with Alice")`, `do("click delete in row 3")`
- App targeting: `do("click OK", app="Safari")` — acts on background apps
- Modifier-click: shift-click, cmd-click, option-click, ctrl-click
- Double-click, right-click, triple-click
- Hover — move mouse to element without clicking
- Form filling: `do("fill Name=Ferran, Email=f@x.com")`
- Wait conditions: `do("wait for Save dialog")`, `do("wait 2s")`, `do("wait until X disappears")`
- Element-based drag: `do("drag file.txt to Trash")`
- Scroll targeting: `do("scroll down in sidebar")`, `do("scroll until Save appears")`
- Structured data: `do("read table")`, `do("read list")`, `do("list windows")`
- **Window management**: minimize, restore, resize (WxH or %), grid positions (halves, quarters, thirds), coordinate moves, true fullscreen toggle, window info query
- Menu paths: `do("click File > Save As")`
- Keyboard: `do("press cmd+s")`
- CDP: `do("navigate url")`, `do("js expression")`, tab management
- Observation: `do("observe start/stop/status/clear")`
- Clipboard, Safari URL/tabs, Finder selection, notifications, text-to-speech
- **Error recovery**: fuzzy "Did you mean?" suggestions + role counts
- **Action verification**: auto-snapshots before/after, reports what changed + post-action state
- **Self-improving memory**: auto-learns label translations (e.g., "Save" → "Guardar") from fail→succeed correlation
- **Keyboard shortcut preference**: auto-caches menu shortcuts, uses them instead of tree walking (~50ms vs ~300ms)
- **Path navigation**: `do("navigate General > About")` — clicks through UI hierarchies in one call
- **Action bundles**: `do("save as draft.md")`, `do("find and replace foo with bar")`, `do("zoom in")`, `do("new document")`, `do("print")`

### Memory (`memory`)
- Persistent JSON store at `~/.nexus/memory.json`
- Survives across sessions, conversations, and restarts
- Simple CRUD: set, get, list, delete, clear
- Stats: show learning stats (label mappings, action history)

### Electron App Support
- Auto-detects Electron apps (VS Code, Slack, Discord, Figma, etc.)
- Sets `AXManualAccessibility` to unlock full accessibility tree (~5 → 59+ elements)
- Walks to depth 20 for Electron apps (content nests deep in Chromium DOM)

### Chrome Deep Integration (CDP)
- Auto-enriches `see()` with web page content when Chrome is focused
- `ensure_cdp()` auto-launches Chrome with debugging port if not running
- Multi-tab management: switch tab, new tab, close tab
- JS execution and URL navigation

### Test Suite
- **1084 tests**: ~579 resolve + 43 phase3 + 41 phase4 + 56 hooks + 76 plugins + 55 smoke + 47 skills + 39 learn + 27 state + 26 observe + 36 system + 37 templates + 22 ocr + 14 capture + 124 intents
- Unit tests mock all OS APIs — run anywhere, fast
- Smoke tests exercise real code paths on macOS

## Known Issues & Hard Truths

### 1. The "Why Not Just Use the CLI?" Problem
Nexus automates GUI apps — but most power users already live in the terminal. The killer use case: automating apps with no CLI (Figma, Keynote, System Settings), testing GUI apps, accessibility for users who can't use a mouse, and orchestrating multi-app workflows that span CLI and GUI.

### 2. Locale Dependency
macOS AXRoleDescription is localized — on a Spanish system, buttons are "botón", links are "enlace". The code uses AXRole (locale-independent) for matching and the self-improving memory auto-learns label translations. But fuzzy matching across locales could still struggle. Partially handled, not robustly tested.

### 3. VS Code Focus-Stealing
VS Code hosts the MCP server, so it steals focus during actions. Mitigated with `_schedule_focus_restore()` which re-activates the target app after a 0.4s delay. Works well but isn't perfect for rapid-fire actions. The `see(app=)` empty-string bug (FastMCP passing `""` instead of `None`) has been fixed — string app names now resolve correctly.

## What's Left to Build

**See `ROADMAP.md` for the full phased plan.** Summary of the 8 phases:

1. ~~**More skills**~~ — ✅ 16 bundled skills
2. ~~**See better**~~ — ✅ OCR fallback, system dialog detection, dialog templates
3. ~~**Act smarter**~~ — ✅ merged responses, shortcut preference, path nav, bundles
4. ~~**Remember**~~ — ✅ session state, spatial caching, action journal
5. ~~**Hook pipeline**~~ — ✅ 7 built-in hooks, composable extensibility
6. ~~**Perception plugins**~~ — ✅ pluggable fallback stack (AX → OCR → templates), perception-aware do()
7. **Polish** — ✅ 7a: app param fix, paste timing, type focus | remaining: typo tolerance, error recovery, CDP depth, multi-monitor
8. **Long game** — workflow recording, navigation graphs, continual learning, skill marketplace

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
- Read `ROADMAP.md` for the phased implementation plan
- Read `~/Desktop/research/nexus/` for 12 deep research documents (limitations, optimization, competitive landscape)
- Read `FIELD_TEST_DOCKER_INSTALL.md` to see exactly where Nexus fails today
- The codebase is ~12,000 LOC across 20 files. Start with `server.py` → `fusion.py` → `resolve.py`
- Test with real apps: Safari has the richest accessibility tree, Finder is good too
- VS Code (Electron) needs `AXManualAccessibility` — Nexus handles this automatically
- macOS accessibility permission must be granted to the parent app (Terminal, VS Code, etc.)
- The `.venv` uses Python 3.12 via Homebrew at `/Users/ferran/repos/Nexus/.venv/`
- Always run tests: `source .venv/bin/activate && python -m pytest tests/ -q`
- Quick test: `python -c "from nexus.sense.fusion import see; print(see()['text'])"`

Read `ROADMAP.md` — that's where the real work is. And if you think this project is done, go try the Docker install test.
