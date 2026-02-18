# Nexus — Design Document

> "Playwright for your computer."
>
> **North star: Extend Claude's capabilities while minimizing context cost.**
> Every design decision gets measured against this: does it save tokens or spend them?

Nexus gives AI structured eyes and hands on the desktop — the things a terminal can't do. It's the precision layer (spatial, visual, UI interaction) that an LLM lacks, delivered in the cheapest possible format so the LLM can spend its context on thinking, not looking.

---

## The Idea

Playwright solved browser automation by making it **reliable** (auto-wait), **readable** (semantic locators), and **composable** (chaining, scoping, filtering). No reason those same ideas can't work for desktop apps.

Windows already exposes an accessibility tree (UI Automation) for every native app — buttons, text fields, menus, dialogs — all queryable by role, name, and state. That's our DOM equivalent.

**We don't invent. We mirror.**

---

## Creative Notes

> *This section is yours. Drop ideas, visual metaphors, naming thoughts, "what if" questions — anything. These feed into design decisions.*

-
-
-

---

## Architecture — The Mirror

### Playwright → Nexus mapping

| Playwright (browser world) | Nexus (desktop world) | Notes |
|---|---|---|
| `Playwright` | `Desktop` | Entry point. The "runtime" |
| `Browser` | *(the OS itself)* | No equivalent needed |
| `BrowserContext` | *(user session)* | Could map to virtual desktops later |
| `Page` | `Window` | A running app window |
| `Frame` | `Pane` | UI subtrees (panels, groups, dialogs) |
| `Locator` | `Locator` | Same name. The core abstraction |
| `expect()` | `expect()` | Same name. Assertions with auto-retry |

### What makes Playwright feel magical

1. **Locators are lazy** — they describe *what* to find, not *where* it is right now
2. **Auto-wait** — every action waits for the element to be ready (visible, enabled, stable)
3. **Semantic queries** — find by role ("button"), by text, by label — not fragile coordinates
4. **Strict by default** — if your query matches 2 things, it fails instead of guessing
5. **Chainable** — `dialog.get_by_role("button", name="OK")` scopes naturally

All five translate directly to desktop UI Automation.

---

## What Exists Today (v0 — CLI)

The current `nexus.py` is a working CLI with two halves:

### Eyes (awareness)
| Command | What it does |
|---|---|
| `describe` | Active window elements, cursor, focus |
| `windows` | List all open windows |
| `find "text"` | Search elements by name |
| `focused` | What has keyboard focus |
| `web-describe/find/text/links/tabs` | Chrome page awareness via CDP |

### Hands (actions)
| Command | What it does |
|---|---|
| `click-element "text"` | Find by name + click |
| `click X Y` | Click coordinates |
| `type "text"` | Type text |
| `key "ctrl+s"` | Key combos |
| `scroll N` | Scroll |
| `move/drag` | Mouse movement |
| `screenshot` | Capture screen |
| `web-click/navigate/input` | Chrome actions via CDP |

### What's good about v0
- All output is structured JSON (ready for AI consumption)
- Watchdog timeout (safety)
- Signal handling
- Works today — Claude uses it

### What's missing
- No reusable Python API (CLI-only)
- No auto-wait (fire and pray)
- No chaining or scoping (searches entire window)
- No state inspection (can't read checkbox state, text values)
- No assertions
- No app lifecycle (launch, activate, wait for window)
- Find is name-only (no role, no automation ID)

---

## Where We're Going (v1 — Library)

### The API at a glance

```python
from nexus import Desktop, expect

# Start
desktop = Desktop()

# Target a window
notepad = desktop.window("Notepad")
# or launch one
calc = desktop.launch("calc.exe")
# or get whatever's active
win = desktop.active_window()

# Find things (Locator API)
btn    = notepad.get_by_role("button", name="Save")
field  = notepad.get_by_role("textbox")
item   = notepad.get_by_name("File")
widget = notepad.get_by_automation_id("menuBar")

# Scoped / chained
dialog = notepad.get_by_role("dialog")
dialog.get_by_role("button", name="OK").click()

# Filtered
notepad.get_by_role("listitem") \
    .filter(has_text="readme.txt") \
    .first.click()

# Actions auto-wait
btn.click()                # waits for visible + enabled
field.fill("Hello world")  # waits, clears, types

# State queries (instant snapshot)
btn.is_visible()       # -> bool
btn.is_enabled()       # -> bool
field.input_value()    # -> str

# Assertions (auto-retry)
expect(btn).to_be_visible()
expect(field).to_have_value("Hello world")
expect(dialog).not_to_be_visible()

# Multiple matches
buttons = notepad.get_by_role("button")
buttons.count()        # -> int
buttons.first.click()
buttons.nth(2).click()
```

### How auto-wait works

Before any action (click, fill, etc.), Nexus polls until conditions are met:

| Action | Checks before executing |
|---|---|
| `click()` | visible, enabled, has nonzero bounds |
| `fill()` | visible, enabled |
| `focus()` | exists in tree |
| `wait_for()` | configurable (visible / hidden / exists) |

Default timeout: 5 seconds. Configurable per-action or globally.

```python
# Custom timeout
btn.click(timeout=10)

# Explicit wait
notepad.get_by_name("Loading").wait_for(state="hidden", timeout=15)
```

### How locators find elements

Under the hood, a Locator stores a **query recipe** (not a live reference):

```
Locator {
    window: Window           # scope
    parent: Locator | None   # for chaining
    strategy: "role" | "name" | "automation_id" | "type"
    value: str
    filters: [...]           # has_text, has, etc.
    nth: int | None          # if .first/.last/.nth() was used
}
```

When an action is called, Nexus:
1. Walks the UI Automation tree from the scope root
2. Applies the strategy + filters
3. Checks strictness (exactly 1 match, unless nth is set)
4. Runs actionability checks (auto-wait)
5. Performs the action

### UIA Control Patterns — the state layer

Windows UI Automation exposes "patterns" on controls — these are our state queries:

| UIA Pattern | What it gives us | Nexus API |
|---|---|---|
| `ValuePattern` | Text content of inputs | `locator.input_value()` |
| `TogglePattern` | Checked/unchecked/indeterminate | `locator.is_checked()` |
| `SelectionPattern` | Which items are selected | `locator.selected_items()` |
| `ExpandCollapsePattern` | Expanded/collapsed state | `locator.is_expanded()` |
| `InvokePattern` | "Click" without coordinates | `locator.invoke()` |
| `ScrollPattern` | Scrollable regions | `locator.scroll()` |
| `WindowPattern` | Minimize/maximize/close | `window.minimize()` etc. |
| `TextPattern` | Rich text content | `locator.text_content()` |

These are free — Windows already provides them. We just need to ask.

---

## Build Layers

Each layer is independently useful. We ship after each one.

### Layer 1 — Foundation
> `Desktop`, `Window`, `Locator` basics

- `Desktop()` entry point
- `desktop.window(title)`, `desktop.active_window()`, `desktop.windows()`
- `desktop.launch(path)` with `wait_for_window`
- `Locator` class with `get_by_role()`, `get_by_name()`, `get_by_automation_id()`
- `locator.click()`, `locator.fill()` — basic actions, no auto-wait yet
- CLI still works alongside (no breaking changes)

### Layer 2 — Auto-wait
> The feature that makes everything reliable

- Retry loop with configurable timeout
- Actionability checks: visible, enabled, nonzero bounds
- `locator.wait_for(state="visible"|"hidden"|"exists")`
- Timeout errors with useful messages ("Waiting for button 'Save' to be visible, but it was not found after 5s")

### Layer 3 — State & Patterns
> Read the state of things, not just find them

- `is_visible()`, `is_enabled()`, `is_checked()`, `is_expanded()`
- `input_value()`, `text_content()`
- `invoke()` — click without coordinates (UIA InvokePattern)
- `bounding_box()` — element rect

### Layer 4 — Chaining & Filtering
> Precise targeting in complex UIs

- Scoped queries: `dialog.get_by_role("button")`
- `.filter(has_text=, has=, has_not=)`
- `.first`, `.last`, `.nth(n)`, `.count()`, `.all()`
- `.or_()`, `.and_()` combinators

### Layer 5 — Assertions
> `expect()` with auto-retry

- `expect(locator).to_be_visible()`
- `expect(locator).to_be_enabled()`
- `expect(locator).to_have_value(expected)`
- `expect(locator).to_have_text(expected)`
- `not_to_*` counterparts
- Configurable assertion timeout

### Layer 6 — CLI v2
> Rebuild CLI as thin wrapper over the library

- Same commands, backed by the new classes
- New commands from new capabilities (`wait-for`, `value`, `state`)
- JSON output stays (backward compatible)

### Layer 7 — OCR Fallback
> For apps that have no accessibility tree

- Tesseract integration for text detection
- Hybrid: try UIA first, fall back to OCR
- Image-based locators for custom-rendered UIs

### Future / Ideas
- Record & replay (watch actions, generate script)
- MCP server (native tool for Claude, no CLI shelling)
- Cross-platform (AT-SPI on Linux, Accessibility API on macOS)
- Visual debugging (highlight matched elements on screen)
- Pytest plugin (`nexus` fixture, like Playwright's `page` fixture)

---

## The Bigger Idea — Perception & Skill Memory

Nexus as a Playwright mirror is Layer 1 of thinking. The deeper insight:

**Don't repeat work. Don't re-see what you've seen. Don't re-learn what you've done.**

### Problem 1: Efficient Perception (don't waste tokens seeing)

Claude has two input channels: **text** and **images**. Both cost tokens. Every token spent on perception is a token not spent on thinking.

Current state: Nexus dumps up to 120 elements as verbose JSON every time. That's wasteful when:
- Nothing changed since last look
- Claude only needs one element, not the whole tree
- The app is familiar (Claude has seen Notepad's UI a thousand times)

**Ideas for smarter perception:**

| Strategy | How it works | Token savings |
|---|---|---|
| **Compact format** | `BTN:Save[120,40,en]` instead of full JSON dict | ~70% smaller |
| **Diff updates** | "3 elements changed since last describe" | Huge for monitoring |
| **Scoped queries** | "just tell me about the dialog" not the whole window | Only send what's needed |
| **Familiarity cache** | Known app layouts stored — only send deviations | Near-zero for known apps |
| **Relevance filter** | Task-aware: "I'm looking for error messages" → only send relevant elements | Dramatic |
| **Hybrid vision** | Screenshot for overview, targeted JSON for specifics | Best of both channels |

The goal: Claude should spend **1 line of context** to understand a familiar screen, not 100.

### Problem 2: Skill Memory (don't re-learn what you've done)

Every time Claude figures out how to do something — draw a line in Blender, fill a form in an app, navigate a menu sequence — that knowledge evaporates at the end of the session.

A **skill store** changes this:

```
skills/
  blender/
    draw_line.yaml        # bpy commands to draw a line between two points
    move_vertex.yaml      # move a vertex to coordinates
    create_cube.yaml      # parameterized cube creation
    extrude_face.yaml     # extrude a selected face
  notepad/
    open_file.yaml        # menu sequence to open a file
    find_replace.yaml     # find and replace text
  general/
    save_dialog.yaml      # handle any standard Save dialog
    file_picker.yaml      # navigate a file picker to a path
```

Each skill is a **recipe** — a parameterized, tested sequence of actions:

```yaml
name: draw_line
app: blender
description: Draw a line (edge) between two 3D points
params:
  start: [x, y, z]
  end: [x, y, z]
steps:
  - bpy.ops.mesh.primitive_plane_add()
  - # ... the exact commands, discovered once, reused forever
learned_from: "session 2024-02-17, took 3 attempts to get right"
```

**Skills compose.** "Draw a triangle" = 3x "draw a line." "Model a cube frame" = 12x "draw a line." The vocabulary grows.

**Skills have versions.** Blender updates its API? Update the recipe, not every future session.

**Skills are portable.** Share them, import them, build libraries for different apps.

### The Piano Analogy

Think of Nexus as a piano. The instrument itself is generic — it has keys and plays notes. What makes it useful is the **keymap** — what each key does in a specific context.

A Blender keymap might look like:

```
[ambient_occlusion]  → bpy.context.scene.eevee.use_gtao = True
[add_cube]           → bpy.ops.mesh.primitive_cube_add(location=...)
[subdivision_surf]   → bpy.ops.object.modifier_add(type='SUBSURF')
[render_preview]     → bpy.ops.render.render('INVOKE_DEFAULT')
```

A Houdini keymap is completely different. A Photoshop keymap is different again. **Nexus doesn't care** — it just plays whatever key you point it at.

The difference this makes:

| Without keymap | With keymap |
|---|---|
| "Enable ambient occlusion" → Claude researches the API, tries commands, maybe fails, retries | "Enable ambient occlusion" → look up key, execute, done |
| 50 tokens of trial and error | 1 lookup + 1 action |
| Knowledge dies with the session | Knowledge lives in the keymap forever |

**Anyone can build their own keymap.** A Houdini specialist builds Houdini keys. A motion graphics person builds After Effects keys. The keymaps capture two things:

1. **What you can do via code** — API calls, scripts, commands (the fast path)
2. **What you have to do via UI** — click sequences, menu paths (Nexus navigates these)

Both are stored as reusable, parameterized entries. Both are just "keys on the piano."

**Keymaps are shareable.** One person figures out Blender, publishes their keymap, everyone benefits. Like community presets but for AI capabilities.

### How These Ideas Connect

Efficient perception + skill keymaps = an AI that gets **faster over time** instead of starting from zero every session.

| Session 1 | Session 50 |
|---|---|
| "What's on screen?" → 120 elements JSON | "What's on screen?" → "Blender, edit mode, cube selected" |
| "How do I draw a line?" → research, trial, error | "Draw a line from A to B" → recall key, execute |
| 80% tokens on figuring things out | 80% tokens on actual creative work |

This is the difference between a tool and a **collaborator that remembers.**

### Specialization without gatekeeping

The keymap approach means Nexus itself stays generic — a good instrument anyone can pick up. The specialization lives in the data, not the code. This means:

- No need to "support" every app — the community builds keymaps
- No bloated codebase — Nexus stays lean, keymaps are just data files
- Anyone can start: use Nexus raw, build keys as you learn, share when ready
- Different expertise levels: beginner keymaps (safe, simple) vs power-user keymaps

---

## File Structure (planned)

```
nexus/
  nexus.py              # v0 CLI (stays, eventually becomes thin wrapper)
  DESIGN.md              # this file

  # v1 library (added incrementally)
  __init__.py            # exports: Desktop, expect
  desktop.py             # Desktop class
  window.py              # Window class
  locator.py             # Locator class
  expect.py              # expect() assertions
  patterns.py            # UIA control pattern wrappers
  wait.py                # auto-wait / retry logic
  ocr.py                 # OCR fallback (Layer 7)
  cli.py                 # CLI v2 (Layer 6)
```

---

## Open Questions

> *Things to figure out as we build. Add your own.*

- **Naming**: "Nexus" is cool but Meta owns the trademark for VR. Ship concern or keep it as internal name?
- **Speed**: UI Automation tree walking can be slow on complex apps. Cache? Limit depth? Background indexing?
- **Electron apps**: VS Code, Discord, Slack have weak accessibility trees. Hybrid UIA + CDP approach? Or just use the web commands?
- **Gaming / custom UIs**: Pure OCR, or image template matching (like SikuliX)?
- **MCP vs CLI**: When we build the MCP server wrapper, does it replace the CLI or sit alongside?
-
-

---

## Principles

1. **Start with Playwright, don't stop there** — proven APIs as foundation, not ceiling
2. **Nexus is an instrument, not an agent** — sharp eyes, reliable hands, no brain. Claude is the brain
3. **Don't repeat work** — seen it? Cache it. Done it? Store the recipe. Familiar? Shorthand
4. **Each layer ships** — no "big bang" release, every increment is useful on its own
5. **Two channels, use them wisely** — text for precision, images for spatial. Minimize tokens for both
6. **CLI stays** — the library grows underneath, nothing breaks
7. **Safety** — timeouts, failsafes, no runaway automation
