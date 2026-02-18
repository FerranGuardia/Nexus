# Nexus — Claude's Eyes & Hands on the Computer

Nexus is a CLI tool that lets you see and interact with the Windows desktop and browser. You run commands via `python -m nexus <command>` and get structured JSON back.

**Python**: `C:\Users\Nitropc\AppData\Local\Programs\Python\Python312\python.exe`

## Quick Reference — All Commands

### See (read-only, no side effects)

| Command | What it does | Example |
|---------|-------------|---------|
| `describe` | Active window: elements, cursor, focused element | `python -m nexus describe` |
| `describe --focus buttons` | Only button elements | `python -m nexus describe --focus interactive` |
| `describe --match "Save*"` | Elements matching a pattern | `python -m nexus describe --match "File*"` |
| `describe --region top` | Elements in a screen region | `python -m nexus describe --region top` |
| `describe --summary` | Concise summary (counts, focus, errors) | `python -m nexus describe --summary` |
| `describe --diff` | Only changes since last describe | `python -m nexus describe --diff` |
| `windows` | List all open windows | `python -m nexus windows` |
| `find "text"` | Search UI elements by name | `python -m nexus find "Save"` |
| `focused` | Which element has keyboard focus | `python -m nexus focused` |
| `screenshot` | Take screenshot (saves PNG, returns path) | `python -m nexus screenshot` |
| `screenshot --mark` | Screenshot with numbered badges on elements | `python -m nexus screenshot --mark` |
| `screenshot --region X,Y,W,H` | Capture a specific screen region | `python -m nexus screenshot --region 0,0,800,600` |
| `ocr-screen` | OCR the active window | `python -m nexus ocr-screen` |
| `ocr-region X Y W H` | OCR a specific screen region | `python -m nexus ocr-region 100 100 400 200` |
| `web-describe` | Page title, URL, inputs, buttons (concise) | `python -m nexus web-describe` |
| `web-describe --full` | All headings, links, inputs, buttons | `python -m nexus web-describe --full` |
| `web-text` | Full visible text of the page | `python -m nexus web-text` |
| `web-find "text"` | Find elements by visible text | `python -m nexus web-find "Submit"` |
| `web-links` | All links on the page | `python -m nexus web-links` |
| `web-tabs` | List all open browser tabs | `python -m nexus web-tabs` |
| `web-ax` | Chrome accessibility tree (interactive elements) | `python -m nexus web-ax` |
| `web-ax --focus forms` | Only form elements from AX tree | `python -m nexus web-ax --focus navigation` |
| `web-ax --summary` | Concise AX tree summary | `python -m nexus web-ax --summary` |
| `web-measure "sel1,sel2"` | Exact CSS dimensions, padding, margins | `python -m nexus web-measure ".header, h1"` |
| `web-markdown` | Clean article content via Readability.js | `python -m nexus web-markdown` |
| `web-capture-api "url"` | Navigate and capture JSON API responses | `python -m nexus web-capture-api "https://api.example.com"` |
| `web-research "query"` | Search web, visit results, extract content | `python -m nexus web-research "CSS grid layout"` |
| `info` | Screen size and cursor position | `python -m nexus info` |

### Act (has side effects)

| Command | What it does | Example |
|---------|-------------|---------|
| `click X Y` | Click at coordinates | `python -m nexus click 500 300` |
| `click X Y --right` | Right-click | `python -m nexus click 500 300 --right` |
| `click X Y --double` | Double-click | `python -m nexus click 500 300 --double` |
| `click-element "name"` | Find UI element by name, click its center | `python -m nexus click-element "Save"` |
| `click-element "name" --role button` | Filter by role to disambiguate | `python -m nexus click-element "OK" --role button` |
| `click-element "name" --verify` | Re-describe after click to confirm | `python -m nexus click-element "Save" --verify` |
| `click-element "name" --heal` | Auto-recover from failures | `python -m nexus click-element "Save" --heal` |
| `click-mark N` | Click element #N from last `screenshot --mark` | `python -m nexus click-mark 5` |
| `move X Y` | Move cursor | `python -m nexus move 500 300` |
| `drag X1,Y1 X2,Y2` | Drag from start to end | `python -m nexus drag 100,100 400,400` |
| `type "text"` | Type text | `python -m nexus type "Hello world"` |
| `key "combo"` | Press key or combo | `python -m nexus key "ctrl+s"` |
| `scroll N` | Scroll (positive=up, negative=down) | `python -m nexus scroll -3` |
| `web-click "text"` | Click web element by visible text | `python -m nexus web-click "Submit"` |
| `web-click "text" --heal` | With auto-recovery | `python -m nexus web-click "Login" --heal` |
| `web-navigate "url"` | Navigate browser to URL | `python -m nexus web-navigate "https://example.com"` |
| `web-input "selector" "value"` | Fill input by label/placeholder/CSS | `python -m nexus web-input "Email" "test@example.com"` |
| `web-pdf --output path.pdf` | Export current page to PDF | `python -m nexus web-pdf --output doc.pdf` |
| `ps-run "script"` | Execute PowerShell | `python -m nexus ps-run "Get-ChildItem"` |

### System / Office

| Command | What it does |
|---------|-------------|
| `com-shell --path "C:\dir"` | Browse files via COM (no UI needed) |
| `com-excel list/read/write/sheets` | Excel automation via COM |
| `com-word read/info` | Word document access via COM |
| `com-outlook inbox/read/send` | Outlook email via COM |

### Vision (OmniParser — for non-accessible UIs)

| Command | What it does | Example |
|---------|-------------|---------|
| `vision-detect` | Detect UI elements via screenshot + AI vision model | `python -m nexus vision-detect` |
| `vision-detect --image path.png` | Detect from existing image | `python -m nexus vision-detect --image shot.png` |
| `vision-detect --region X,Y,W,H` | Detect in a screen region only | `python -m nexus vision-detect --region 0,0,800,600` |
| `vision-detect --annotated` | Return annotated image with numbered bounding boxes | `python -m nexus vision-detect --annotated` |
| `vision-health` | Check if OmniParser vision server is running | `python -m nexus vision-health` |

**When to use vision-detect vs describe:**
- Use `describe` for normal apps — it's instant and uses the OS accessibility tree.
- Use `vision-detect` when `describe` returns nothing useful — games, canvas apps, custom-rendered UIs, remote desktops.
- `vision-detect` takes ~1-5s (GPU) or ~15-30s (CPU) — much slower than `describe`, so only use it when needed.
- **Requires**: OmniParser server running at `http://localhost:8500`. Check with `vision-health` first.

### Design-to-Code Measurement

| Command | What it does | Example |
|---------|-------------|---------|
| `measure-image path.png` | Measure all UI elements in a design PNG (OmniParser + OCR) | `python -m nexus measure-image C:\designs\hero.png` |
| `measure-image path.png --scale 0.5` | Same, for @2x Figma exports (halves all coordinates) | |
| `web-layout-diff path.png ".hero, h1"` | Compare design vs live CSS, report pixel deltas | `python -m nexus web-layout-diff design.png ".hero h1, .cta"` |
| `web-layout-diff ... --match-by position` | Use position-based matching (for icon-heavy layouts) | |
| `web-layout-diff ... --match-by index` | Match by order (1st selector = 1st image element) | |

**Design-to-code workflow:**
```
1. Export design:      Save PNG from Figma/Krita (@1x, or --scale 0.5 for @2x)
2. Measure reference:  python -m nexus --format compact measure-image C:\designs\hero.png
3. Implement HTML/CSS
4. Open in Chrome:     python -m nexus web-navigate "file:///C:/path/to/page.html"
5. Diff layout:        python -m nexus --format compact web-layout-diff C:\designs\hero.png ".hero, h1, .cta"
6. Read MISMATCH lines, fix CSS, repeat from step 4
```

- Both commands require the OmniParser server running. Check with `vision-health`.
- `measure-image` returns elements sorted in reading order (top-to-bottom, left-to-right) with ids `img_0`, `img_1`, ...
- `web-layout-diff` flags mismatches where width or height differs by more than 10%.

### Electron Apps

| Command | What it does |
|---------|-------------|
| `electron-detect` | Find running Electron apps with CDP debug ports |
| `electron-connect PORT` | Connect to an Electron app's CDP port |
| `electron-targets PORT` | List pages/tabs on an Electron CDP port |

### Batch & Meta

| Command | What it does | Example |
|---------|-------------|---------|
| `batch "cmd1; cmd2; cmd3"` | Execute multiple commands in sequence | `python -m nexus batch "describe --focus buttons; click-element Save"` |
| `describe-tools --fmt openai` | Dump all tool schemas as JSON | `python -m nexus describe-tools` |
| `describe-tools --fmt markdown` | Human-readable tool reference | `python -m nexus describe-tools --fmt markdown` |

## Tool Source Tags & Annotations

Every tool description is prefixed with a `[Source]` tag for instant identification:

| Tag | Subsystem | Example tools |
|-----|-----------|--------------|
| `[UIA]` | Native Windows UI automation | describe, find, click-element |
| `[CDP]` | Chrome DevTools Protocol | web-describe, web-ax, web-click |
| `[Screen]` | Pixel-level input/output | click, type, key, screenshot |
| `[OCR]` | Text recognition | ocr-region, ocr-screen |
| `[Vision]` | OmniParser AI detection | vision-detect, measure-image |
| `[COM]` | Office/Shell COM automation | com-shell, com-excel, com-outlook |
| `[System]` | PowerShell execution | ps-run |
| `[Electron]` | Electron app detection | electron-detect, electron-connect |
| `[Meta]` | Batch/orchestration | batch |

Every MCP tool also declares **safety annotations** (MCP ToolAnnotations):
- `readOnlyHint=True` — tool only observes, no side effects (22 tools)
- `destructiveHint=True` — tool can cause irreversible changes: `ps-run`, `web-pdf`, `com-outlook`
- `idempotentHint=True` — calling twice with same args = same result (all read-only tools)

## Prerequisites

- **Browser commands** (`web-*`): Chrome must be running with `--remote-debugging-port=9222`
- **Desktop commands** (`describe`, `find`, `click`, etc.): Work on any app, no setup needed
- **Electron commands**: Target app must be launched with `--remote-debugging-port=XXXX`

## Filter Presets (--focus)

Use with `describe`, `find`, `web-ax` to reduce output:

| Preset | What it matches |
|--------|----------------|
| `buttons` | Button, MenuButton, SplitButton, ToggleButton |
| `inputs` | Edit, ComboBox, Spinner, Slider, CheckBox, RadioButton |
| `interactive` | All clickable + typeable controls |
| `errors` | Elements with error/warning/alert in name or role |
| `dialogs` | Dialog, Window (popup), Alert, Modal |
| `navigation` | Menu, MenuItem, Tab, TabItem, Link, TreeItem |
| `headings` | Heading elements (h1-h6 on web) |
| `forms` | Form groups: inputs + labels + submit buttons |

## Output Format & Best Practices

All commands return JSON by default. **You MUST use `--format compact` for awareness commands** to avoid blowing up your context window.

### Critical Rules

1. **ALWAYS use `--format compact` for describe, windows, find, focused** — raw JSON is 70KB for `describe`. Compact is 5KB. Example: `python -m nexus describe --format compact`
2. **NEVER click coordinates without checking screen bounds first** — run `info` to get screen dimensions.
3. **Check `ok` field in responses** — errors return `{"ok": false, "error": "..."}`.
4. **Use `click-element "name"` over `click X Y` when possible** — more reliable than raw coordinates.
5. **Use `screenshot --mark` for visual navigation** — numbered badges + `click-mark N` is safest for unfamiliar UIs.
6. **Browser commands need Chrome with CDP** — start Chrome with `--remote-debugging-port=9222`.
7. **`--format` goes BEFORE the subcommand** — `python -m nexus --format compact describe`.
8. **Use `--heal` on click-element and web-click** when reliability matters — auto-recovers from common failures.
9. **Use `batch` for multi-step workflows** — variable interpolation lets steps reference previous results.

## Code-First Document Pipeline

```
1. Write HTML/CSS file
2. Open in Chrome:     python -m nexus web-navigate "file:///C:/path/to/doc.html"
3. Measure layout:     python -m nexus web-measure ".header, .body, h1, p"
4. Take screenshot:    python -m nexus screenshot
5. Fix CSS from measurements → save
6. Repeat 2-5 until correct
7. Export PDF:         python -m nexus web-pdf --output "output.pdf"
```

## Task Lifecycle (REQUIRED)

You MUST use the task lifecycle for every piece of work.

```bash
# 1. Start
python -m nexus task start "Create branded PDF for client X"

# 2. Do your work (commands are tagged automatically)
python -m nexus web-navigate "file:///C:/doc.html"
python -m nexus web-measure ".header, .body"

# 3. End
python -m nexus task end success              # or: fail, partial
python -m nexus task end partial --notes "Layout done but images missing"
```

- `python -m nexus task note "useful observation"` — add notes anytime
- `python -m nexus task status` — check if a task is active

## Trajectory Recording

Every command is logged to `E:\NexusData\trajectories/YYYY-MM-DD.jsonl`. Override with `NEXUS_DATA_DIR` env var.
