# Nexus Roadmap

*February 2026. Informed by 12 research documents, 2 field tests, and the experience of being the end user.*

This project is not done. An agent that can't click a button after 20 tries in a Docker install wizard is not done. An agent that goes blind every time a system dialog appears is not done. An agent that takes 26 seconds for a 4-step navigation that a human does in 2 is not done.

The foundation is solid — three tools, 70+ intents, 726 tests, real desktop control. What's missing is **fluency**. The gap between "can do it" and "does it well." This roadmap is the path from one to the other.

---

## Where We Are

**v2.4 — Phases 1–5 complete, Phase 7a field test fixes applied**

```
15,000+ LOC | 1008 tests | 25 source files | 17 skill files
see/do/memory working via MCP | 75+ intent patterns
Action verification | Self-improving label memory
Observation mode | Control panel | Chrome CDP
Skills system (16 bundled skills as MCP resources)
OCR fallback (Apple Vision) | System dialog detection
Dialog templates | Capture abstraction
Merged do()+see() responses | Shortcut preference cache
Path navigation | Action bundles (5 built-in)
Session state (spatial cache, action journal, layout hashing)
Hook pipeline (7 built-in hooks, composable extensibility)
```

**What works well:**
- see() returns a rich accessibility tree in ~200ms
- do() handles 75+ intent patterns with spatial, ordinal, and container resolution
- Caching gives 6x speedup on repeated tree walks
- Learning auto-translates labels across locales
- Skills guide agents to CLI when GUI isn't needed
- see() auto-detects system dialogs (Gatekeeper, SecurityAgent, permissions)
- see() falls back to OCR when AX tree is sparse (<5 labeled elements)
- 8 dialog templates provide instant button coordinates for known patterns
- 16 skills cover app navigation, system knowledge, and workflow patterns
- **[NEW] do() returns post-action state — no see() needed after acting**
- **[NEW] do() prefers keyboard shortcuts over tree walking (~50ms vs ~300ms)**
- **[NEW] do("navigate X > Y") clicks through UI hierarchies in one call**
- **[NEW] Action bundles: save as, find/replace, zoom, new doc, print**
- **[NEW] Session state persists across MCP calls (spatial cache, action journal)**
- **[NEW] Spatial cache (3s TTL) with layout hash change detection eliminates redundant tree walks**
- **[NEW] Action journal gives proprioception — "what did I just do?" in every do() response**
- **[NEW] Hook pipeline — register(event, fn, priority) makes all behaviors composable**
- **[NEW] 7 built-in hooks replace hardcoded behaviors (OCR, spatial cache, learning, journal, dialogs)**

**What still doesn't:**
- ~~System dialogs are invisible~~ → now detected + OCR'd + classified
- ~~Navigation takes 12x longer than a human~~ → shortcuts + merged responses cut round-trips
- ~~No session state — each tool call starts from zero~~ → spatial cache + action journal
- ~~Adding new behaviors requires editing core code~~ → hook pipeline makes everything composable
- Some Electron apps return empty trees (Docker Desktop) → OCR fallback helps but coordinate clicking is still imprecise
- ~~see(app=) via MCP falls back to VS Code too often~~ → fixed: normalize FastMCP empty string params

---

## Phase 1: More Skills (No Code Required) ✅ COMPLETE

**Completed Feb 24, 2026. 12 new skills added (16 total).**

Skills are the cheapest improvement with the biggest payoff. Each skill is a markdown file that teaches the agent shortcuts, common paths, and known quirks. The agent reads the skill, skips the see/do dance, acts faster.

### Navigation skills (per-app knowledge)

| Skill | What it teaches |
|-------|----------------|
| `safari` | Keyboard shortcuts (Cmd+L, Cmd+T, Cmd+W...), navigation paths, AX tree quirks (200+ elements, use query=) |
| `vscode` | Focus-stealing workaround, Cmd+Shift+P palette, Electron depth=20, all shortcuts |
| `finder` | Go To Folder (Cmd+Shift+G), Quick Look (Space), Get Info (Cmd+I), CLI alternatives |
| `system-settings` | Common deep paths (General > About, Network > Wi-Fi...), search field fastest, admin password panes |
| `terminal` | When to use Terminal vs Nexus GUI, iTerm2 patterns, tmux integration |
| `docker` | CLI-first (`docker ps`, `docker compose`), Docker Desktop Electron blindness, workarounds |

### System knowledge skills

| Skill | What it teaches |
|-------|----------------|
| `system-dialogs` | Prevention (xattr -cr, spctl), detection (list windows for CoreServicesUIAgent), common layouts, coordinate fallback strategy |
| `electron-apps` | Which apps work (VS Code, Slack), which don't (Docker, Spotify), AXManualAccessibility, CDP fallback |
| `keyboard-navigation` | Universal macOS shortcuts, Tab/Shift-Tab field navigation, Escape to dismiss, Space to activate |

### Workflow template skills

| Skill | What it teaches |
|-------|----------------|
| `file-save-as` | Menu path, dialog fields, common locations, keyboard shortcut |
| `screenshot` | screencapture flags, region capture, clipboard vs file, annotation tools |
| `notifications` | osascript display notification, terminal-notifier, notification center |

**Why this matters:** Each navigation skill eliminates 3-5 unnecessary see/do cycles per interaction. Across a 10-minute session, that's minutes saved and dozens of token-expensive inference cycles avoided.

---

## Phase 2: See Better (Fix the Blind Spots) ✅ COMPLETE

**Completed Feb 24, 2026. 4 new modules + fusion.py integration.**

The accessibility tree covers ~80% of macOS apps. The other 20% — system dialogs, canvas apps, blind Electron apps — is where Nexus goes from "capable" to "blind." This phase adds fallback perception layers.

### 2a. OCR via Apple Vision Framework

When the AX tree returns too few elements, fall back to on-device OCR.

```
New file: nexus/sense/ocr.py
- Wraps VNRecognizeTextRequest via pyobjc (zero new dependencies)
- Returns text + bounding boxes + confidence scores
- ~130ms for full screen, ~50ms for a region
- Languages: Spanish + English (configurable)

Integration: nexus/sense/fusion.py
- If describe_app() returns < 5 labeled elements → trigger OCR on window region
- Merge OCR text elements with AX elements (mark source="ocr")
- OCR elements are clickable via coordinate (center of bounding box)
```

**Immediate wins:** System dialog text becomes visible. Blind Electron apps show text content. Coordinate clicking becomes text-guided instead of purely blind.

### 2b. System Dialog Detection

Detect when a system dialog is blocking normal interaction.

```
In: nexus/sense/fusion.py (or new nexus/sense/system.py)
- Poll CGWindowListCopyWindowInfo for CoreServicesUIAgent/SecurityAgent windows
- On detection: auto-capture dialog region, run OCR, match templates
- Report in see() output: "SYSTEM DIALOG DETECTED: [Gatekeeper] Open / Cancel"
- Provide clickable coordinates for dialog buttons
```

### 2c. ScreenCaptureKit Migration

Replace deprecated CGWindowListCreateImage (triggers Sequoia security warnings).

```
New file: nexus/sense/capture.py
- SCScreenshotManager for macOS 14+ (ScreenCaptureKit)
- CGWindowListCreateImage as fallback for macOS < 14
- Key gain: capture windows WITHOUT stealing focus
- Region capture for efficient OCR (crop before processing)
```

### 2d. Known Dialog Templates

Pre-computed button positions for standard macOS dialogs.

```
New file: nexus/sense/templates.py (or JSON at nexus/data/templates.json)
- Gatekeeper dialog: "Open" at relative (0.75, 0.85), "Cancel" at (0.55, 0.85)
- Save dialog: filename field at (0.5, 0.3), Save at (0.85, 0.9)
- Password prompt: password field center, OK bottom-right
- Detection via OCR text matching against known phrases
- ~50ms lookup — near-instant for known patterns
```

**After Phase 2:** Nexus can see system dialogs, interact with text-based blind apps, and handle known dialog patterns automatically. The Docker field test scenario goes from "blind for the entire GUI portion" to "handled most dialogs autonomously."

---

## Phase 3: Act Smarter (Reduce the Round-Trip Tax) ✅ COMPLETE

**Completed Feb 25, 2026. 4 sub-features: merged responses, shortcut cache, path nav, bundles.**

The round-trip loop (see → think → do → think → see → think) is the dominant cost. LLM inference is 80% of navigation time. This phase attacks the loop from multiple angles.

### 3a. Merged do() + see() Responses

do() already takes before/after snapshots for verification. Return the post-action state in a compact format so the agent never needs a separate see() after acting.

```
Current: do("click Save") → "Clicked Save. Changes: 1 new dialog."
Wanted:  do("click Save") → "Clicked Save. Changes: 1 new dialog.
           New state: dialog 'Save As' with [filename field (focused)],
           [location: Desktop], [Save] [Cancel]"
```

One round-trip instead of two. Cuts navigation time by ~30%.

### 3b. Keyboard Shortcut Preference

When do() receives an intent, check if a keyboard shortcut exists before searching the tree.

```
In: nexus/act/resolve.py
- Build shortcut cache from see(menus=True) on first use per app
- Store in session (Phase 4) for reuse
- do("open preferences") → finds Cmd+, → press cmd+, → done
- Skips: tree walk, element search, AX action, coordinate fallback
- ~50ms instead of ~300ms, no tree walk needed
```

### 3c. Path Navigation

Navigate multi-step UI hierarchies in a single intent.

```
New intent: do("navigate General > About")
- Click "General", wait for content change, click "About"
- Each step: find element → click → wait for UI update → next
- Report final state (merged response from 3a)
- Menu paths already work: do("click File > Save As")
- Extend same pattern to sidebar items, tabs, tree outlines
```

One do() call replaces 3 see/do cycles. 3-4x faster for deep navigation.

### 3d. Action Bundles

Common multi-step workflows as single intents.

```
do("save file as draft.md")
  → Internally: press cmd+shift+s → wait for dialog → type "draft.md" → press enter

do("find and replace foo with bar")
  → Internally: press cmd+h → type "foo" in search → type "bar" in replace → click Replace All
```

Bundles are defined as functions in a new `nexus/act/bundles.py`, not as skills (skills are guidance, bundles are executable).

---

## Phase 4: Remember (Session State and Spatial Cache) ✅ COMPLETE

**Completed Feb 25, 2026. 1 new module + 4 modified files + 41 tests.**

Session-level memory across MCP calls within a single server lifetime.

### 4a. Session Object (`nexus/mind/session.py`)

In-memory state: spatial cache, action journal, layout hashes, session metadata.
Module-level dicts (same pattern as learn.py). No disk I/O, no persistence.

### 4b. Spatial Caching

3-second TTL element cache layered above the 1-second tree cache.
Layout hash (sorted role+label, MD5) detects structural changes.
Observer events mark cache dirty via `mark_dirty(pid)`.
`snap()` → `compact_state()` gets a free cache hit (same PID, same elements).
Eliminates redundant tree walks in multi-step interactions.

### 4c. Action Journal in do() Response

50-entry deque of recent actions with timing, errors, and change summaries.
Last 3 entries appended as `--- Recent ---` to every mutating `do()` response.
Format: `"3s ago: click File -> OK (TextEdit)"` — ~150 chars for 3 entries.
Gives the agent proprioception without a separate `see()` call.

---

## Phase 5: Hook Pipeline (Extensibility Foundation) ✅ COMPLETE

**Completed Feb 25, 2026. 1 new module + 2 modified files + 41 tests.**

Lightweight hook system that lets each component influence the pipeline without coupling. Each hook is a simple function registered with a priority. Fire sequentially, stop on `{"stop": True}`. No classes, no inheritance, no framework.

### `nexus/hooks.py` — Registry + 7 Built-in Hooks

```
Registry: register(event, fn, priority, name), fire(event, ctx), clear(), registered()
Thread-safe, error-isolated (hooks never break the pipeline)

Built-in hooks (migrated from inline code):
  before_see:
    spatial_cache_read  (pri 10) — check spatial cache, skip tree walk on hit
  after_see:
    spatial_cache_write (pri 10) — store elements in spatial cache
    ocr_fallback        (pri 50) — run OCR when AX tree is sparse (<5 labeled)
    system_dialog       (pri 60) — detect Gatekeeper/SecurityAgent dialogs
    learning_hints      (pri 70) — show learned labels for current app
  after_do:
    learning_record     (pri 10) — record action for label correlation
    journal_record      (pri 20) — record to session action journal
```

### Modified files
- `nexus/sense/fusion.py` — replaced inline spatial cache, OCR, system dialog, and learning hint blocks with `fire("before_see")` and `fire("after_see")` calls
- `nexus/server.py` — replaced inline learning recording and journal recording with `fire("after_do")` call

### Future events (defined, not yet wired)
- `before_do` — shortcut preference, label substitution
- `on_error` — retry with OCR fallback, suggest alternatives
- `on_app_switch` — pre-fetch tree, load navigation skill
- `on_system_dialog` — auto-handle dialogs

**Why this matters:** Adding a new behavior is now ~15 lines (write function + register) instead of ~50 lines of core edits. Every Phase 2-4 behavior is a hook. New perception layers, error recovery strategies, and app-specific optimizations plug in without touching core code.

---

## Phase 7a: Field Test Blocker Fixes ✅ COMPLETE

**Completed Feb 25, 2026. 3 fixes + 13 new tests (1008 total).**

Targeted fixes for the concrete bugs that blocked Field Tests 1 and 2. Practical polish before architectural work.

### Fix 1: `see(app=)` Empty String Normalization
FastMCP passes `""` instead of `None` for unspecified optional params. `if app` evaluates to `False` for empty strings, so `pid=None` → shows VS Code instead of the requested app. Fixed by normalizing at server entry: `app = app.strip() if isinstance(app, str) and app.strip() else None`.

### Fix 2: Clipboard Paste Timing
`paste_text()` waited only 0.1s after Cmd+V before restoring clipboard. Mail.app's async IMAP/SMTP fields didn't absorb the paste in time — 5 of 26 chars appeared. Increased to 0.3s.

### Fix 3: Simple `type X` Focus Verification
`do("type smtp.server.com")` (no `"in field"`) called `raw_input.type_text()` blindly without verifying focus. Now tries AX `set_value` on the focused element first (proper focus + value setting), falls back to raw input if AX fails.

---

## Phase 6: Perception Plugins (Pluggable Fallback Stack)

**Timeline: 2 weeks. Effort: High. Impact: Architectural.**

Make the perception pipeline pluggable. Each layer handles cases the previous layer can't.

```
New file: nexus/sense/plugins.py

Layer 1: AX tree (always, ~200ms, priority 10)
Layer 2: OCR (when AX sparse, ~130ms, priority 50)
Layer 3: Templates (when OCR finds known patterns, ~50ms, priority 60)
Layer 4: VLM (optional, for canvas/icons, ~500ms, priority 80)

register_perception_layer(name, handler, priority)
- Handler: fn(pid, region) → [elements]
- Elements merged with source tag (ax, ocr, template, vlm)
- do() uses source tag to choose action method (AX action vs coordinate click)
```

**Layer 4 (VLM) is optional and deferred.** OCR + templates handle 90% of blind spots. VLM is for the remaining 10% (canvas apps, icon-only toolbars, custom-rendered UIs). It can be added later without changing the architecture.

---

## Phase 7: Polish and Resilience

**Timeline: Ongoing. Effort: Variable.**

### Typo tolerance
```
"clikc Save" → fuzzy match → "click Save"
Implementation: difflib.SequenceMatcher on first word of intent
```

### Smarter error recovery
```
When element not found:
1. Try learned label substitution (already exists)
2. Try OCR-based search (Phase 2)
3. Try keyboard shortcut (Phase 3b)
4. Suggest closest matches with confidence scores
5. Suggest CLI alternative if skill exists
```

### Auto-retry on wrong app focused
```
If do() acts on VS Code when targeting Safari:
- Detect mismatch (expected app != actual app)
- Re-activate target app
- Retry action
```

### CDP depth
```
- Network request interception (watch API calls)
- Console log capture (catch JS errors in web apps)
- More Electron app bundle IDs (Docker, Spotify, etc.)
```

### Multi-monitor awareness
```
- Query display list (NSScreen.screens())
- Region-based resolution uses correct display bounds
- do("move window to display 2")
```

---

## Phase 8: The Long Game

These are larger bets that build on everything above.

### Workflow recording
"Watch what I do" → replay as action chain. Observe mode captures the human's actions, Nexus stores them as a reproducible sequence. The agent can replay, adapt, and improve the workflow over time.

### Navigation graphs
Build a map of every app's UI states and transitions. After a few sessions, Nexus knows that "from System Settings, clicking General leads to a pane with About, Software Update, Storage." Navigate by declaring the destination — Nexus finds the path.

### Continual learning (Agent S3 pattern)
Store successful action trajectories, not just label translations. "To install Docker: brew install, launch, handle Gatekeeper with xattr, accept agreement with Tab+Enter, skip analytics, finish." Next time, replay the known-good trajectory instead of exploring step by step.

### Skill marketplace
Community-contributed app navigation skills. Install `nexushub install figma` and Nexus instantly knows every Figma shortcut, panel layout, and accessibility quirk.

### Cross-platform (the distant horizon)
Linux via AT-SPI, Windows via UIA. The architecture is layered for it — `sense/access.py` is the only platform-specific perception file. Replace it, and Nexus works on a new OS. But this is a massive undertaking and macOS is the focus.

---

## Design Principles (Still Non-Negotiable)

1. **Three tools.** see, do, memory. Adding a fourth requires extraordinary justification.
2. **Functional, not OOP.** Pure functions, explicit params, return dicts.
3. **Token efficiency.** Every byte of output costs LLM inference time. Be compact.
4. **Intent over implementation.** The AI says what. Nexus figures out how.
5. **Fail helpfully.** When something breaks, show what IS available and suggest recovery.
6. **Minimal deps.** pyobjc + pyautogui + pillow + mcp + websocket-client. No bloat.
7. **Skills are knowledge, not code.** Skills teach. Tools execute. Don't mix them.
8. **Hooks over hardcoding.** New behaviors plug into the pipeline, not into core functions.

---

## Success Metrics

How we know each phase worked:

| Phase | Metric | Current | Target |
|-------|--------|---------|--------|
| 1 (Skills) | see/do calls per simple task | 8-12 | 3-5 |
| 2 (See Better) | % of apps where see() returns useful elements | ~80% | ~95% |
| 2 (See Better) | System dialog handling | 0% autonomous | >80% autonomous |
| 3 (Act Smarter) | Time for 4-step navigation | ~26s | ~8s |
| 3 (Act Smarter) | Round-trips per action | 2-3 | 1 |
| 4 (Remember) | Redundant tree walks per session | ~50% | ~10% |
| 5 (Hooks) | Lines of code to add new behavior | ~50 (edit core) | ~15 (register hook) |
| 6 (Plugins) | Effort to add new perception layer | Days (edit fusion.py) | Hours (write handler) |
| 7 (Resilience) | Actions requiring human intervention | ~20% | ~5% |

---

## For Future Agents

If you're an AI picking up this project:

1. Read CLAUDE.md (architecture), VISION.md (philosophy), this file (roadmap)
2. Read `~/Desktop/research/nexus/` for deep context — 12 documents covering limitations, optimization, competitive landscape, and philosophy
3. Read `~/Desktop/research/` (6 more documents) for macOS API deep dives
4. The field test at `FIELD_TEST_DOCKER_INSTALL.md` shows exactly where Nexus fails — start there
5. Phase 1 (skills) requires no code changes — lowest risk, highest immediate impact
6. Phase 2 (OCR) is the critical unlock — system dialogs are the #1 blocker
7. Run tests: `source .venv/bin/activate && python -m pytest tests/ -q`
8. The codebase is ~12,000 LOC. Start with `server.py` → `fusion.py` → `resolve.py`

And if you think this project is "done" — go try to install Docker Desktop using only Nexus. Then come back and read this roadmap again.

---

*Built by Ferran and Claude. Still building.*
