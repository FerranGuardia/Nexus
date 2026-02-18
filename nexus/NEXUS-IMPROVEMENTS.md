# Nexus Improvements — Complete Task Breakdown

## Architecture: Eye / Brain / Hand

Nexus has three layers. Each is a separate research track and module boundary.

```
┌──────────────────────────────────────────────────────────┐
│                    CLAUDE (orchestrator)                  │
│  Decides WHAT to do. Receives pre-processed data.        │
│  Only burns tokens on decisions, not data wrangling.     │
└──────────────┬───────────────────────────┬───────────────┘
               │ reads                     │ commands
┌──────────────▼──────────────┐ ┌──────────▼──────────────┐
│     BRAIN (local compute)   │ │     HAND (actions)      │
│  Zero LLM calls. Processes  │ │  Executes actions.      │
│  raw eye data into concise, │ │  Picks best method:     │
│  actionable information.    │ │  API > CLI > shortcut   │
│                             │ │  > UIA > coordinate     │
│  • Compact formatter        │ │                         │
│  • Layout diff (M3)         │ │  • click, type, key     │
│  • Cache / "no change"      │ │  • web-click, navigate  │
│  • Readability.js strip     │ │  • COM Office calls     │
│  • Set-of-Mark annotate     │ │  • PowerShell runner    │
│  • OmniParser → elements    │ │  • Win32 SendMessage    │
│  • OCR → text               │ │  • keyboard shortcuts   │
└──────────────▲──────────────┘ └──────────▲──────────────┘
               │ raw data                  │ needs context
┌──────────────┴───────────────────────────┘──────────────┐
│                    EYE (data acquisition)                │
│  Read-only. Zero side effects. Gets raw data from:      │
│  • UIA tree (native apps)                               │
│  • CDP AXTree (web + Electron)                          │
│  • getComputedStyle / getBoundingClientRect (web)       │
│  • Screenshots (fallback)                               │
│  • COM Shell.Application (file system)                  │
│  • PowerShell queries (processes, registry)             │
└─────────────────────────────────────────────────────────┘
```

**Why this split matters**:
- **Eye** can run freely — read-only, no side effects, auto-approve everything
- **Brain** saves money — every computation done locally is a token Claude doesn't process. Layout diffs, element filtering, format compression, OCR all happen before Claude sees anything
- **Hand** needs confirmation — has side effects, different trust level, picks the best action method per app type
- **Module structure**: `nexus/eye.py`, `nexus/brain.py`, `nexus/hand.py`, `nexus/core.py` (shared infra: daemon, connections, caching)

**Subtask mapping**:

| Track | Subtasks | What it does |
|---|---|---|
| Eye | B (smart traversal), F (CDP AXTree), M1 (web-measure), M2 (measure-image), L (watch/events), J (Electron CDP) | Acquires raw data from screens, apps, pages |
| Brain | C (compact format), D (caching/diff), M3 (layout diff), K1 (OmniParser), K2 (Set-of-Mark), K3 (OCR), G1 (Readability), G2 (API capture) | Processes raw data locally, reduces tokens |
| Hand | H (COM automation), I (PowerShell runner), hand_router (method selection) | Executes actions via best available method |
| Infra | A (daemon mode), E (web optimization) | Shared infrastructure for all three |

### Brain Evolution: From Processing to Learning

The brain has three maturity levels. Don't design for level 1 only — keep the architecture open so levels 2 and 3 can grow naturally.

**Level 1 — Static processing** (what the subtasks above describe)
Hardcoded transformations: compact formatting, OCR, Readability extraction, layout diff math. No memory. Same input always produces same output. This is where we start.

**Level 2 — Persistent knowledge** (decision cache + trajectory store)
The brain records Claude's decisions and successful action sequences. Next time a similar situation occurs, the brain handles it without calling Claude. Not ML — just a lookup table that grows over time.

Examples:
- **Navigation cache**: Claude navigates Vercel settings once → brain stores `{app: "vercel", intent: "edge config", path: ["Storage", "Edge Config"]}` → next time, brain returns the path instantly, Claude never gets called
- **Action shortcuts DB**: Claude uses `click-element "Save"` → brain learns `key("ctrl+s")` works for any app with a Save function → builds a per-app shortcuts database from Claude's choices
- **Element relevance filter**: Claude consistently ignores decorative elements from `describe` output → brain learns to pre-filter them → 60% fewer elements hit Claude's context
- **Layout pattern memory**: Claude corrects padding from 120px to 24px → brain records the correction → detects similar inflation patterns in future layout diffs

Storage: `~/.nexus/knowledge/` — persists across sessions, projects, machine migrations.

**Level 3 — Learned models** (ML, not LLM)
Small, fast, local models trained on accumulated Level 2 data. Claude becomes the teacher — its judgments are the training signal, the brain's models are the students.

Examples:
- **Element classifier**: trained on which elements Claude clicks vs ignores → filters `describe` output to only actionable items (decision tree or small embedding model)
- **Action router**: trained on `{app_type, intent, successful_method}` tuples → predicts best action method (COM vs shortcut vs click) without asking Claude
- **Layout anomaly detector**: trained on design-vs-implementation diffs Claude has corrected → flags issues before Claude sees them
- **Navigation predictor**: similarity search over stored trajectories (vector store) → "this task is similar to one Claude solved before, here's the path it took" (this is what Microsoft UFO2 does with its execution history RAG)

The key principle: **Claude is expensive per-call but has perfect judgment. Local ML is cheap per-call but needs training data. The brain accumulates Claude's judgment as training data, gradually handling more situations locally.** Every LLM call today is a training sample for tomorrow's local model.

**Design constraints to not block this evolution**:
- Brain must have persistent storage (`~/.nexus/knowledge/`) — not just in-memory state
- Every brain decision should be logged with input/output/context — these logs become training data
- The brain's interface to Claude should be swappable — today it returns processed data, tomorrow it might return "I already know the answer" for cached patterns
- Don't hardcode the brain's processing pipeline — make it pluggable so new processors (ML models, vector stores) can slot in alongside static ones

---

## Current Pain Points
- **Slow**: cold-start per command (~300-500ms Python startup before work begins)
- **Heavy on context**: `describe` dumps up to 120 elements x 8 fields = massive JSON blob Claude has to parse
- **Brute-force tree walking**: recursive COM calls across entire window, no smart filtering
- **No state**: every call is stateless, rediscovers everything from scratch
- **Web commands**: Playwright connect/disconnect cycle on every single call
- **Blind to Electron apps**: VS Code, Discord, Slack expose almost no UIA tree — Nexus can't see their contents
- **No vision fallback**: when UIA fails, `screenshot` returns a raw file path with zero structure
- **Web scraping is shallow**: DOM `querySelectorAll` misses ARIA roles, states, shadow DOM, SPAs
- **No information gathering**: Playwright is only used to control the browser, not to research or extract docs
- **UI-only navigation**: file browsing, process management, and Office tasks all go through slow UI automation instead of direct APIs
- **No brain layer**: all raw data goes straight to Claude unprocessed — wastes tokens on parsing, not deciding

---

## Phase 1 — Core Engine (Subtasks A–E)

Performance and architecture improvements to the existing Nexus engine. Each subtask is **fully independent** — an agent can research + implement each one in isolation.

---

### SUBTASK A — Daemon Mode (Persistent Process)
**Goal**: Eliminate cold-start by running Nexus as a long-lived process.

**Scope**:
- Add a `serve` command that starts a stdin/stdout JSON-line REPL (read line → parse command → execute → print JSON → loop)
- Alternative: local HTTP server on a fixed port (e.g. `localhost:7827`)
- Keep the existing CLI mode working (backward compat) — detect if `serve` or single-shot
- Playwright CDP connection stays open across web commands
- UI Automation COM initialization happens once

**Key decisions to research**:
- stdin/stdout REPL vs HTTP server vs Unix socket — which is simplest for Claude Code to call?
- How to handle graceful shutdown, health check
- How to handle the watchdog timer in daemon mode (per-command timeout vs global)

**Files**: `nexus/nexus.py` (add `cmd_serve`), possibly `nexus/server.py` if separated

---

### SUBTASK B — Smart Tree Traversal (COM Conditions)
**Goal**: Replace recursive Python `GetChildren()` with native COM `FindAll()` conditions.

**Scope**:
- Research `uiautomation` library's `FindAll()`, `CreatePropertyCondition`, `AndCondition`, `OrCondition`
- Replace `_collect_named_elements` with condition-based queries (e.g. "all Buttons + EditBoxes + Links in this window")
- Replace `_find_elements` with `FindFirst`/`FindAll` using NameContains condition
- Benchmark before/after on a heavy app (VS Code, Chrome, File Explorer)
- Add `--depth` flag to `describe` (default: 3, current: 6)
- Filter invisible elements (zero-rect) at the COM level if possible, not Python level
- Add `is_enabled()` check and `is_interactable` flag (from UFO2) to filter to actionable controls only

**Files**: `nexus/nexus.py` (rewrite `_collect_named_elements`, `_find_elements`)

---

### SUBTASK C — Compact Output Format
**Goal**: Reduce token count of Nexus output by 60-80%.

**Scope**:
- Design a compact text format for element lists, e.g.:
  ```
  [Btn] Save | (120,340) 80x30
  [Edit] Search... | (200,50) 300x24 *focused*
  [Link] Settings | (50,400) 60x18
  ```
- Add `--format compact|json|minimal` flag (default: compact)
- `json` = current behavior (backward compat)
- `compact` = human/LLM-readable one-liner per element
- `minimal` = just names and types, no coordinates
- Apply to `describe`, `find`, `windows`, all web commands
- Design the format to be **parseable back** if needed (so Claude can extract coords from compact output)

**Files**: `nexus/nexus.py` (add formatter layer between commands and `_output`)

---

### SUBTASK D — Caching & Diff Layer
**Goal**: Avoid redundant full scans when the screen hasn't changed.

**Scope**:
- Cache last `describe` result with timestamp
- On next `describe` within N seconds, return `{"changed": false}` or a diff
- Detect change via: focused element changed? window title changed? quick element count check?
- Could use a hash of (window_title + focused_name + element_count) as cheap "did anything change" signal
- Add `--force` flag to bypass cache
- Research: is there a Windows API for "window content changed" events (WinEventHook) that could trigger cache invalidation proactively?

**Files**: `nexus/nexus.py` or new `nexus/cache.py`

---

### SUBTASK E — Web Command Optimization
**Goal**: Make web commands fast and lightweight.

**Scope**:
- Persistent Playwright CDP connection (comes free if daemon mode lands, but design it independently)
- Connection pool: if Chrome restarts or tab changes, detect and reconnect
- Add `--tab N` flag to target a specific tab (currently always uses first tab)
- `web-describe` returns way too much — add tiered verbosity:
  - Default: title, URL, focused element, visible form fields, main CTA buttons
  - `--full`: current behavior (all headings, all links, all inputs)
- Replace DOM `querySelectorAll` scraping with CDP Accessibility Tree (see Subtask F for details)

**Files**: `nexus/nexus.py` (web commands section), possibly `nexus/web.py` if extracted

---

## Phase 2 — New Capability Layers (Subtasks F–L)

New capabilities that expand what Nexus can see and do. Discovered through research into UFO2, OmniParser, SeeAct, Browser-Use, OpenClaw, Playwright MCP, and Anthropic's computer-use reference implementation.

---

### SUBTASK F — CDP Accessibility Tree for Web
**Goal**: Replace DOM scraping with Chrome's native accessibility tree for richer, more accurate web page understanding.

**The problem**: Current `web-describe` uses `page.evaluate()` with `querySelectorAll('h1,h2,h3')` etc. This misses:
- ARIA roles, states (`aria-expanded`, `aria-checked`, `aria-selected`)
- Shadow DOM content
- Semantic reading order
- Virtual/rendered-only elements in React/Vue SPAs

**The solution**: Chrome's CDP has `Accessibility.getFullAXTree` — returns the exact tree screen readers see. Playwright can call it directly via `CDPSession`.

**Scope**:
- Add `web-ax` command that fetches the CDP accessibility tree and returns structured JSON
- Each node includes: role, name, description, value, properties (checked, expanded, focused, disabled), childIds, backendDOMNodeId
- Design output to work with the compact formatter (Subtask C)
- Research acting on nodes via `backendDOMNodeId` (focus, click) without coordinate math
- This is what Microsoft's official Playwright MCP server uses by default (ARIA tree as YAML)
- Browser-Use team found raw CDP is 2-3x faster than Playwright's locator system

**Implementation sketch**:
```python
def cmd_web_ax(_args):
    def action(page, _browser):
        client = page.context.new_cdp_session(page)
        client.send("Accessibility.enable")
        tree = client.send("Accessibility.getFullAXTree")
        client.send("Accessibility.disable")
        # Filter to interactive/named nodes, format compactly
        _output({"command": "web-ax", "nodes": tree["nodes"][:100]})
    _with_page(action)
```

**Reference projects**: Microsoft Playwright MCP, Browser-Use (migrated from Playwright to raw CDP for speed)

**Files**: `nexus/nexus.py` (web commands section)

---

### SUBTASK G — Playwright as Information Gatherer
**Goal**: Use Playwright not just to control the browser, but to extract documentation, capture API responses, and research topics autonomously.

**The problem**: Nexus's `web-text` does `page.inner_text("body")` — a raw text dump including nav, ads, footers. No clean extraction, no API interception, no research flows.

**Scope — three new commands**:

#### G1: `web-markdown` — Clean content extraction
- Inject Mozilla Readability.js via `page.add_script_tag()` before extraction
- Readability strips nav, ads, footers — returns article content only
- This is what Firefox Reader View, Firecrawl, Crawl4AI, and Jina Reader all use
- Returns: title, clean text content (capped at ~8000 chars), excerpt, byline
- Replaces `web-text` for documentation/article pages

#### G2: `web-capture-api` — Intercept JSON API responses
- `page.on("response")` filtered by `content-type: application/json`
- Navigate to a URL, let the page's JS make its API calls, capture the structured JSON
- Many SPAs (React docs sites, dashboards) load content via fetch — the API response is cleaner than the rendered DOM
- Also useful for: ad/tracker blocking via `page.route()` to speed up page loads

#### G3: `web-research "query"` — Automated research flow
- Navigate to search engine (Brave/DuckDuckGo), extract organic result links
- Visit top 3-5 results, extract content with Readability.js
- Return structured `{url, title, content}` per source
- Pattern from WebVoyager / Browser-Use — the "search, visit, extract" loop

**Reference projects**: Crawl4AI (Playwright + Readability + BM25 filtering), Firecrawl (Playwright microservice + Readability), Jina Reader (Puppeteer + ReaderLM-v2 1.5B model)

**Files**: `nexus/nexus.py` or new `nexus/web_research.py`

---

### SUBTASK H — COM Automation (Skip the UI Entirely)
**Goal**: For Office apps and File Explorer, bypass UIA and use direct COM object models.

**The problem**: Nexus walks the UIA tree and simulates clicks for apps that have rich programmatic APIs. This is slow, fragile, and unnecessary.

**Scope**:

#### H1: `com-shell` — File Explorer as an object
- `win32com.client.Dispatch("Shell.Application")` — list open Explorer windows, get folder contents, navigate
- `shell.Namespace(path).Items()` returns files with Name, Size, Type — no UI needed
- Replaces: opening File Explorer, walking UIA tree to read file list

#### H2: `com-excel` — Excel without clicking
- `win32com.client.Dispatch("Excel.Application")` — open workbooks, read/write cells, headless mode
- Can run with `Visible=False` — no window needed at all

#### H3: `com-word` — Word document access
- `win32com.client.Dispatch("Word.Application")` — open docs, read content, modify

#### H4: `com-outlook` — Email access
- `win32com.client.Dispatch("Outlook.Application")` — read inbox, send emails via MAPI namespace

**Prereqs**: pywin32 is already installed. Zero new dependencies.

**Files**: new `nexus/com_tools.py`, register commands in `nexus/nexus.py`

---

### SUBTASK I — PowerShell/CLI Navigation
**Goal**: Add a shell execution command for system tasks that don't need UI interaction.

**The problem**: File browsing, process management, registry reads, service control — all faster and more reliable via shell commands than UI automation.

**Scope**:
- Add `ps-run "script"` command that executes PowerShell and returns structured JSON
- Wrapper: `subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True)`
- Parse stdout as JSON when possible, return raw text otherwise
- Use cases: `Get-ChildItem`, `Get-Process`, `Stop-Process`, `Start-Process`, `Get-ItemProperty` (registry)
- Safety: same trust level as existing Python execution — Claude already has shell access, this just makes it structured

**Implementation sketch**:
```python
def cmd_ps_run(args):
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", args.script],
        capture_output=True, text=True, timeout=15
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = result.stdout
    _output({"command": "ps-run", "data": data, "stderr": result.stderr or None})
```

**Files**: `nexus/nexus.py`

---

### SUBTASK J — Electron App Automation via CDP
**Goal**: Connect to Electron apps (VS Code, Discord, Slack) via Playwright CDP for full DOM + accessibility tree access.

**The problem**: Electron apps are Chromium under the hood but Nexus treats them as native windows with poor UIA trees. VS Code is the most important target — Claude could read editor contents, navigate file trees, click sidebar buttons.

**Scope**:
- Add `electron-connect PORT` command that connects Playwright to an Electron app's CDP port
- Document setup: apps need `--remote-debugging-port=XXXX` flag at launch
- VS Code: add to `%APPDATA%\Code\User\argv.json` permanently
- Discord: launch shortcut with `--remote-debugging-port=9224`
- Once connected, all `web-*` commands work on the Electron app's renderer
- Add `electron-describe` that combines CDP AXTree (Subtask F) with Electron context
- Research: can we detect already-running Electron apps' debug ports without relaunch?

**Reference projects**: `electron-playwright-mcp`, `playwright-mcp-electron` (both open source MCP servers wrapping this pattern)

**Key limitation**: Cannot attach to already-running Electron apps without the debug port flag. One-time setup cost per app.

**Files**: `nexus/nexus.py` or new `nexus/electron.py`

---

### SUBTASK K — Vision Augmentation (OmniParser + Set-of-Mark + OCR)
**Goal**: When UIA fails (Electron apps, custom controls, visual-only content), fall back to structured vision.

**The problem**: `cmd_screenshot` returns only a file path. Claude gets an image but no structured element data for custom-rendered UIs.

**Scope — three layers**:

#### K1: OmniParser integration (highest impact, highest effort)
- Microsoft's OmniParser: YOLO-v8 (icon detection) + Florence-2 0.23B (functional captioning)
- Takes screenshot → returns `{element_id, description, bounding_box}` tuples
- Same structure as UIA output — slots directly into existing Nexus format
- UFO2 runs UIA + OmniParser simultaneously, deduplicates via IoU overlap
- Open source (MIT), models on HuggingFace, runs locally
- `pip install omniparser` + model download

#### K2: Set-of-Mark annotation (medium effort, high payoff)
- When taking a screenshot, overlay numbered red boxes on each detected element (from UIA or OmniParser)
- Return the annotated image alongside element metadata
- Claude says "click element 7" → Nexus looks up coordinates → clicks
- Eliminates coordinate hallucination entirely
- Pattern from SeeAct (ICML 2024) and WebVoyager — Browser-Use hit 89.1% accuracy with this
- Anthropic's own computer-use reference demos use this approach

#### K3: Windows OCR (`ocr-region`)
- `pip install winrt-Windows.Media.Ocr` — native Windows OCR, no GPU, no external deps
- Or use `screen-ocr` library which wraps WinRT + EasyOCR + Tesseract under unified API
- Add `ocr-region X Y W H` command: screenshot region → OCR → return text + word bounding boxes
- Use cases: charts, canvas elements, PDF viewers, game UIs — anything with zero accessibility tree

**Reference projects**: Microsoft OmniParser (GitHub), SeeAct/UGround (OSU-NLP), ShowUI (2B VLA model, CVPR 2025), Anthropic computer-use demo

**Files**: new `nexus/vision.py`, integrate with `nexus/nexus.py`

---

### SUBTASK L — Event-Driven Awareness (Watch Mode)
**Goal**: Stream real-time UI events instead of requiring Claude to poll.

**The problem**: Every Nexus call is a point-in-time snapshot. Claude must repeatedly call `describe` to detect changes. This is wasteful and misses transient events (dialogs, toasts, error popups).

**Scope**:
- Add `watch` command that starts a background event listener
- Use `IUIAutomation.AddAutomationEventHandler` to subscribe to:
  - Focus changes (which element/window gained focus)
  - Window open/close events
  - Property changes (name, enabled state)
  - Structure changes (child added/removed — detects dialogs appearing)
- Emit JSON-line events to stdout as they occur
- AT-SPI2 (Linux equivalent) has richer event subscriptions — borrow the event taxonomy:
  - `object:state-changed:focused`, `object:text-changed:insert`, `object:active-descendant-changed`
- Filter noisy events (e.g., ignore cursor blink in text fields)
- Works best with daemon mode (Subtask A) — the event stream runs in the persistent process

**Reference**: AT-SPI2 event model (freedesktop.org), Windows UIA event handlers (MSDN)

**Files**: `nexus/nexus.py` or new `nexus/watcher.py`

---

### SUBTASK M — Layout Measurement & Design-to-Code Diff
**Goal**: Give Claude exact pixel measurements instead of relying on approximate visual judgment for layout matching.

**The problem**: Claude's vision is approximate. When comparing a design reference (Krita mockup, Figma frame, screenshot) to a live website, Claude says "looks close" when there's actually 200px of extra whitespace. The user ends up manually measuring in Krita with a pixel ruler and feeding numbers back to Claude. This defeats the purpose of automation.

**The insight**: Claude doesn't need better *eyes* — it needs **numbers**. Computed CSS values are exact. Bounding box measurements are exact. The diff between a reference image and the live page can be computed numerically, not judged visually.

**Scope — three commands**:

#### M1: `web-measure` — Extract computed layout dimensions
```
python nexus.py web-measure ".hero, .hero h1, .hero p, .hero img"
```
- Runs `getComputedStyle()` + `getBoundingClientRect()` for each matched selector
- Returns exact pixel values: width, height, padding (top/right/bottom/left), margin, position, font-size, line-height, gap
- Compact output format:
  ```
  .hero        | 1200x847 | pad: 120 64 80 64 | margin: 0 0 0 0 | font: — | gap: —
  .hero h1     |  800x72  | pad: 0 0 0 0      | margin: 0 0 24 0 | font: 48px/56px | gap: —
  .hero p      |  600x48  | pad: 0 0 0 0      | margin: 0 0 32 0 | font: 18px/28px | gap: —
  .hero img    |  400x300 | pad: 0 0 0 0      | margin: 0 0 0 0 | font: — | gap: —
  ```
- Claude gets exact numbers, knows immediately what to adjust without visual guessing
- Add `--viewport WxH` flag to measure at a specific viewport size

#### M2: `measure-image` — Extract bounding boxes from a reference design
- Takes a screenshot/image file path (Krita export, Figma screenshot, any design reference)
- Uses OCR (K3) to detect text blocks with their bounding boxes
- Uses OmniParser (K1) or simple contour detection (OpenCV) to find element regions
- Returns: `{element, bounds: {x, y, w, h}}` for each detected region
- This gives Claude the reference measurements without the user opening a ruler

#### M3: `web-layout-diff` — Numerical comparison between reference and implementation
- Takes: reference image path + CSS selectors for the live page
- Measures both (M2 on the image, M1 on the page)
- Computes per-element deltas:
  ```
  hero section:  height diff +247px (847 vs 600 target)
  heading:       top-padding diff +96px
  image:         gap-to-heading diff +50px
  ```
- Claude reads the diff and generates exact CSS fixes — no visual comparison needed

**Real example that motivated this**:
User designed a hero section in Krita. Asked Claude to implement it as HTML/CSS. Claude used Playwright screenshots and said "looks almost equal position-wise." In reality, the implementation was much taller with extra whitespace. The user had to manually open Krita, enable pixel rulers, measure each element's height, and feed those numbers to Claude. With `web-measure` + `measure-image`, Claude would have caught the 247px height discrepancy immediately without any manual measurement.

**Implementation for M1** (simplest, highest value):
```python
def cmd_web_measure(args):
    def action(page, _browser):
        selectors = [s.strip() for s in args.selectors.split(",")]
        results = page.evaluate("""(selectors) => {
            return selectors.map(sel => {
                const el = document.querySelector(sel);
                if (!el) return { selector: sel, error: "not found" };
                const rect = el.getBoundingClientRect();
                const cs = getComputedStyle(el);
                return {
                    selector: sel,
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    padding: [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].map(v => parseInt(v)),
                    margin: [cs.marginTop, cs.marginRight, cs.marginBottom, cs.marginLeft].map(v => parseInt(v)),
                    font_size: cs.fontSize,
                    line_height: cs.lineHeight,
                    gap: cs.gap || null,
                    display: cs.display,
                    position: cs.position,
                };
            });
        }""", selectors)
        _output({"command": "web-measure", "elements": results})
    _with_page(action)
```

**Depends on**: K3 (OCR for M2), K1 (OmniParser for M2), Playwright (already present for M1)

**Files**: `nexus/nexus.py` (M1), `nexus/vision.py` (M2, M3)

---

## Phase 3 — Real-World Use Cases & Creative Angles

These are the actual scenarios that spawned Nexus. Phase 1+2 are the engine; Phase 3 is **why the engine exists**. Each use case maps back to which subtasks enable it.

---

### USE CASE 1: Design-to-Code & Visual Document Formatting

**The scenario**: You design a layout in Krita/Figma/any visual tool and want Claude to implement it as a website or PDF. Or you have a marketing PDF to format with proper styling, layout, content breaks, visual hierarchy. Code alone never gets the visual result right — Claude says "looks close" when it's not.

**The real problem (from experience)**: You designed a hero section in Krita. Claude implemented it as HTML/CSS and used Playwright screenshots to verify. Claude said "almost equal position-wise." In reality, the implementation was much taller with excess whitespace. You had to manually open Krita, enable pixel rulers, measure each element's top-to-bottom pixel distance, and feed those numbers back to Claude one by one. That manual measurement step is what Nexus should eliminate.

**What Nexus enables**:

#### The measurement path (Subtask M — the precision fix)
- `web-measure ".hero, .hero h1, .hero img"` → exact computed dimensions, padding, margins in pixels
- `measure-image reference.png` → bounding boxes extracted from the Krita/Figma design export
- `web-layout-diff reference.png ".hero, .hero h1, .hero img"` → per-element delta: "hero is 247px too tall, heading has 96px excess top padding"
- Claude reads numbers, not pixels. No visual guessing. Exact CSS fixes.

#### The visual judgment path (for design decisions code can't make)
- Claude controls Figma via Nexus (Electron CDP attach — Subtask J) or via Figma's plugin API
- Takes screenshots of the current layout (K2: Set-of-Mark for element identification)
- OCR reads the actual rendered text (K3: Windows OCR) to verify content didn't break
- Claude identifies where content breaks should go, whether the visual hierarchy reads correctly — judgments that require **seeing**, not just parsing code
- Iterative loop: make a change → `web-measure` for precision → screenshot for aesthetics → adjust

**Two kinds of "looks wrong"**:
1. **Measurable** — "the hero is 247px too tall" → `web-measure` catches this, no vision needed
2. **Subjective** — "the page doesn't feel balanced" → screenshot + Claude's visual judgment
Nexus should use numbers for #1 and vision for #2, not vision for both.

**Depends on**: M (layout measurement — the core fix), J (Electron CDP for Figma), K2 (Set-of-Mark), K3 (OCR), G1 (web-markdown for extracting source content)

---

### USE CASE 2: Live Navigation Guide ("Where is this feature actually?")

**The scenario**: Claude tells you "go to Vercel > Settings > Domains > Advanced" but the UI has changed, or the path was never quite right. You're staring at the screen and can't find it. You want Claude to **look at your actual screen** and guide you to the right place.

**What Nexus enables**:
- You say "Claude, I'm on Vercel and I need to find X"
- Claude runs `web-ax` (Subtask F) or `web-describe` to see the actual current page structure
- Claude reads the real navigation items, sidebar links, tab labels — not what it remembers from training data, but what's **actually there right now**
- Claude says "I can see a 'Storage' tab in the left sidebar, click that, then look for 'Edge Config' in the submenu"
- If the feature moved or was renamed, Claude finds it by scanning the real UI instead of guessing from stale knowledge

**The key insight**: Claude's training data about website layouts is always outdated. Nexus makes Claude's navigation advice **grounded in reality**. Claude doesn't do the clicking — it just looks and tells you where to go.

**Extends to**: Any web dashboard (AWS Console, GitHub settings, Stripe dashboard, Cloudflare). Any time Claude's instructions don't match what you see.

**Depends on**: F (CDP AXTree), E (web command optimization), G1 (web-markdown for reading docs)

---

### USE CASE 3: Visual Audits (UI, Accessibility, Design QA)

**The scenario**: You've built a UI (or are evaluating someone else's app) and want Claude to audit it — not the code, but the **actual rendered output**. Does the spacing look right? Are there alignment issues? Is the contrast sufficient? Does it look professional?

**What Nexus enables**:

#### UI/Design Audit
- Screenshot the app → Claude sees the actual pixels
- Set-of-Mark annotation (K2) labels every element so Claude can reference them precisely
- Claude identifies: misaligned elements, inconsistent spacing, text that's too small, color contrast issues, orphaned headings, broken layouts at different sizes
- For web apps: CDP AXTree (F) gives semantic structure + screenshot gives visual result — Claude cross-references both

#### Accessibility Audit
- CDP AXTree (F) is literally the accessibility tree — what screen readers see
- Claude checks: missing alt text, unlabeled buttons, focus order issues, ARIA misuse, missing landmarks
- Combines with OCR (K3) to verify that visually-presented text is also in the accessibility tree
- This is what Playwright *can't* do alone — Playwright tests DOM structure, but Nexus + Claude can evaluate whether the **visual presentation** matches the **semantic structure**

#### App Audit (Native Apps)
- UIA tree (current Nexus) + screenshot for native Windows apps
- Claude checks: are dialogs accessible? Do buttons have labels? Is the tab order logical?
- For Electron apps (J): full CDP audit same as web

**The key insight**: Playwright can test "does this button exist" but not "does this page look right." Nexus gives Claude the visual layer that pure code testing can't cover.

**Depends on**: K2 (Set-of-Mark), K3 (OCR), F (CDP AXTree), J (Electron CDP for native-looking apps)

---

### USE CASE 4: App That Code Can't Reach

**The scenario**: You need to do something in an app that has no API, no CLI, no scripting interface. A proprietary tool, a government form, an enterprise app, a game settings panel. The only interface is the GUI.

**What Nexus enables**:
- UIA tree walking for native apps (current)
- OmniParser (K1) for apps with custom-rendered controls that UIA can't see
- Win32 SendMessage for legacy Win32 dialogs
- COM automation (H) for Office apps — but as a fallback when COM doesn't cover it, the visual path works
- Claude sees the app, identifies the controls, and either guides you or operates them directly

**Depends on**: B (smart tree traversal), K1 (OmniParser), K3 (OCR)

---

### USE CASE 5: Figma / Design Tool Co-Piloting

**The scenario**: You want Claude to help you in Figma — not just generate code from designs, but actually work *inside* Figma. Move layers, adjust spacing, create frames, apply styles.

**What Nexus enables**:
- Figma is Electron → connect via CDP (Subtask J)
- Full access to Figma's DOM/AXTree for reading the canvas structure
- Claude can identify layers, frames, text elements by their names in the layers panel
- Screenshot + Set-of-Mark (K2) for visual reference of the canvas itself
- Figma also has a plugin API (JavaScript) that could be called via Playwright's `page.evaluate()` — but that requires a Figma plugin to be running
- Hybrid approach: use CDP for reading state, keyboard shortcuts for common operations (Ctrl+G to group, V for move tool, etc.), and targeted clicks for specific layer selections

**Alternative angle**: Figma's REST API can read file structure, but can't manipulate the canvas in real-time. The Electron CDP path gives real-time control.

**Depends on**: J (Electron CDP), K2 (Set-of-Mark), F (CDP AXTree)

---

### USE CASE 6: Claude as a Second Pair of Eyes on Your Screen

**The scenario**: You're working and want Claude to passively see what you're doing — not to control anything, just to be aware. So when you ask a question, Claude already has context about what app you're in, what file you're looking at, what error is on screen.

**What Nexus enables**:
- Event-driven watch mode (L) streams focus changes and window switches
- Periodic lightweight `describe` (with caching — D) keeps a running picture
- When you ask Claude something, it already knows: "you're in VS Code editing `app.tsx`, the terminal shows a TypeScript error on line 42, and Chrome is open to localhost:3000"
- No need to copy-paste error messages or describe your screen — Claude already saw it

**Depends on**: L (watch mode), D (caching), A (daemon mode for persistent process)

---

### Design Principles (Extracted from Use Cases)

These patterns emerge across all use cases:

#### 1. Look-Don't-Touch Mode
Most use cases start with Claude **looking** and **advising**, not acting. The default should be read-only awareness with action as opt-in. "Tell me where to click" before "click it for me."

#### 2. Code-First, UI-Fallback
The action hierarchy should be: API/COM > CLI/PowerShell > keyboard shortcuts > UIA Invoke > coordinate click. Visual UI automation is the last resort, not the default.

#### 3. Vision + Structure = Complete Picture
Neither UIA alone nor screenshots alone are sufficient. Every use case benefits from having **both** the semantic structure (what elements exist, their roles, their states) **and** the visual output (what it actually looks like rendered). Cross-referencing the two is where the real value is.

#### 4. Grounded in Reality, Not Training Data
The killer feature isn't that Claude can control apps — it's that Claude can **see what's actually on screen right now** instead of guessing from outdated training data. Navigation guidance, audits, and design feedback all depend on this.

#### 5. Iterative Visual Loop
Design/formatting tasks need a tight loop: change → screenshot → evaluate → adjust. Nexus needs to make this loop fast (daemon mode, caching, compact output) so it feels interactive, not batch.

---

## Execution Priority

Reordered by which use cases they unlock, not just engineering effort.

### Tier 1 — Foundation + Quick Wins
*Unlocks: Navigation Guide (UC2), basic Audits (UC3), Design-to-Code precision (UC1)*

| Subtask | Effort | Unlocks | Use Cases |
|---|---|---|---|
| F: CDP AXTree | ~5 lines | Semantic web understanding | UC2, UC3 |
| M1: web-measure | ~30 lines | Exact layout dimensions (no visual guessing) | UC1, UC3 |
| C: Compact output format | Medium | 60-80% token reduction | All |
| G1: web-markdown (Readability.js) | ~30 lines | Clean doc extraction | UC2 |
| I: PowerShell runner | ~15 lines | System tasks without UI | UC4 |
| H1: COM Shell.Application | ~10 lines | File browsing without UI | UC4 |

### Tier 2 — Performance + Visual Layer
*Unlocks: Visual Audits (UC3), iterative design loop for UC1/UC5*

| Subtask | Effort | Unlocks | Use Cases |
|---|---|---|---|
| A: Daemon mode | Medium | 10x faster (tight visual loop) | UC1, UC5 |
| K3: Windows OCR | Medium (new dep) | Read visual-only content | UC1, UC3, UC4 |
| K2: Set-of-Mark annotation | Medium | Precise element reference | UC1, UC3, UC5 |
| B: Smart tree traversal | Medium | Faster + lighter native scans | UC3, UC4 |
| E: Web command optimization | Medium | Persistent connection, tabs | UC2, UC3 |

### Tier 3 — Electron + Design Tools
*Unlocks: Figma co-pilot (UC5), VS Code awareness (UC6), design-to-code diff (UC1)*

| Subtask | Effort | Unlocks | Use Cases |
|---|---|---|---|
| J: Electron CDP attach | Medium + setup | Figma, VS Code, Discord, Slack | UC1, UC5, UC6 |
| M2: measure-image | Medium (needs K3/K1) | Extract dimensions from reference designs | UC1 |
| M3: web-layout-diff | Medium (needs M1+M2) | Numerical diff: reference vs implementation | UC1 |
| K1: OmniParser integration | High (model download) | Custom control detection | UC1, UC4, UC5 |
| L: Event-driven watch mode | Medium | Passive screen awareness | UC6 |
| D: Caching & diff layer | Medium | Fast re-scans in visual loops | UC1, UC5, UC6 |
| G2: web-capture-api | ~20 lines | SPA data extraction | UC2 |

### Tier 4 — Full Ecosystem
*Unlocks: Autonomous research (UC2 extended), Office document workflows (UC1)*

| Subtask | Effort | Unlocks | Use Cases |
|---|---|---|---|
| G3: web-research flow | Medium | Autonomous research loops | UC2 |
| H2-H4: COM Office tools | Low each | Direct Office document access | UC1 |

---

## How to Assign to Parallel Agents

Each subtask can be given to a separate agent with this prompt structure:

```
You are improving Nexus (nexus/nexus.py), a Python screen awareness tool.
Your subtask is: [SUBTASK LETTER] — [TITLE]
[paste the subtask scope section]
Read nexus/nexus.py first. Research the approach. Implement it.
Do not modify areas outside your scope.
```

**Parallelism rules**:
- Phase 1 (A–E): A+B+C can run simultaneously. D benefits from A. E can run independently.
- Phase 2 (F–L): F+G+H+I are all independent. J depends on F conceptually. K is independent. L benefits from A.
- Phase 3: requires creative-director decisions before implementation.

---

## Research Sources

Projects studied for this improvement plan:
- **Microsoft UFO2/UFO3** — Desktop AgentOS, hybrid UIA + OmniParser ([github.com/microsoft/UFO](https://github.com/microsoft/UFO))
- **Microsoft OmniParser V2** — pure-vision screen parser, YOLO + Florence-2 ([github.com/microsoft/OmniParser](https://github.com/microsoft/OmniParser))
- **SeeAct** — ICML 2024, Set-of-Mark grounding ([github.com/OSU-NLP-Group/SeeAct](https://github.com/OSU-NLP-Group/SeeAct))
- **Browser-Use** — Playwright + LLM reasoning loop, AXTree approach ([github.com/browser-use/browser-use](https://github.com/browser-use/browser-use))
- **OpenClaw** — Personal AI assistant, Skills system pattern ([github.com/openclaw/openclaw](https://github.com/openclaw/openclaw))
- **Microsoft Playwright MCP** — Official MCP server, ARIA tree as default ([github.com/microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp))
- **Anthropic Computer Use Demo** — Reference implementation, image context pruning ([github.com/anthropics/claude-quickstarts](https://github.com/anthropics/claude-quickstarts))
- **ShowUI** — 2B VLA model for local GUI grounding, CVPR 2025 ([github.com/showlab/ShowUI](https://github.com/showlab/ShowUI))
- **Crawl4AI** — Playwright + Readability + BM25 content filtering ([github.com/unclecode/crawl4ai](https://github.com/unclecode/crawl4ai))
- **Firecrawl** — Playwright microservice + Readability extraction ([github.com/firecrawl/firecrawl](https://github.com/firecrawl/firecrawl))
- **screen-ocr** — Unified OCR wrapper for WinRT/EasyOCR/Tesseract ([github.com/wolfmanstout/screen-ocr](https://github.com/wolfmanstout/screen-ocr))
- **electron-playwright-mcp** — Playwright MCP for Electron apps ([github.com/fracalo/electron-playwright-mcp](https://github.com/fracalo/electron-playwright-mcp))
