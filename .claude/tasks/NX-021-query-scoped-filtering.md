# NX-021 — Query-Scoped Filtering

**Track**: Eye (oculus) + Brain (cortex)
**Priority**: MEDIUM — token savings at source, programmatic tool calling pattern
**Effort**: Low-Medium
**Depends on**: NX-001 (compact output, done), NX-002 (smart traversal, done)

---

## Problem

`describe` returns everything. `web-ax` returns everything. `web-describe` returns everything. Even with compact output, Claude gets 50-200 elements when it only needs "what buttons are on screen" or "is there an error dialog."

The Anthropic programmatic tool calling insight: **filter at the source, not in context.**

## Goal

Every read command accepts an optional **query/focus parameter** that filters output before it reaches Claude. Less data generated = less tokens burned = faster decisions.

## Scope

### 1. `--focus` Filter for Describe
```bash
nexus describe --focus buttons        # only Button elements
nexus describe --focus inputs         # only Edit/Input elements
nexus describe --focus errors         # elements with "error" in name/role
nexus describe --focus dialogs        # popup/dialog windows
nexus describe --focus "Save"         # elements containing "Save"
nexus describe --focus interactive    # all clickable/typeable elements
```

### 2. `--focus` Filter for Web Commands
```bash
nexus web-ax --focus forms            # form elements only
nexus web-ax --focus navigation       # nav, links, menus
nexus web-ax --focus "search"         # elements matching "search"
nexus web-describe --focus headings   # page structure only
```

### 3. Built-in Focus Presets
| Preset | Filters to |
|--------|-----------|
| `buttons` | Button, MenuButton, SplitButton, ToggleButton |
| `inputs` | Edit, ComboBox, Spinner, Slider, CheckBox, RadioButton |
| `interactive` | All clickable + typeable controls |
| `errors` | Elements with error/warning/alert in name, role, or state |
| `dialogs` | Dialog, Window (popup), Alert, Modal elements |
| `navigation` | Menu, MenuItem, Tab, TabItem, Link, TreeItem |
| `headings` | Text elements that are headings (web: h1-h6, native: by style) |
| `forms` | Form groups: inputs + labels + submit buttons |

### 4. Regex/Glob Name Filter
```bash
nexus describe --match "Save*"        # glob pattern on element name
nexus describe --match "btn-.*"       # regex pattern
nexus web-ax --match "*submit*"       # case-insensitive glob
```

### 5. Spatial Filtering
```bash
nexus describe --region top           # top 20% of screen
nexus describe --region "0,0,800,200" # specific rect
nexus describe --region center        # center 60% of screen
```

### 6. Combination Filters
```bash
nexus describe --focus buttons --region top    # buttons in top area
nexus describe --focus interactive --match "*save*"  # interactive elements matching "save"
```

## Implementation

### For UIA (native)
- Apply filters during tree traversal (NX-002 smart traversal already supports conditions)
- Role filter → COM `FindAll()` with `ControlTypeCondition`
- Name filter → COM `FindAll()` with `PropertyCondition(Name, pattern)`
- Spatial filter → post-filter by bounding rect

### For CDP (web)
- AXTree already has role info — filter nodes before returning
- Name matching on `name` field of AX nodes
- Spatial filter via `getBoundingClientRect()` check

### Filter at traversal, not post-process
The filter should prevent tree walking into irrelevant branches, not just hide results after a full scan. This means:
- If `--focus buttons`, don't recurse into Text containers
- If `--region top`, skip elements whose parent is below the cutoff
- Real performance gain, not just cosmetic filtering

## Key Design Decisions
- `--focus` is the primary interface (human-readable presets)
- `--match` for freeform name patterns
- `--region` for spatial constraints
- All three can combine
- Default (no filter) = current behavior (backward compat)
- Presets are hardcoded role lists, not ML — predictable and fast

## Files
- `nexus/oculus/uia.py` — add filter params to describe(), find()
- `nexus/oculus/web.py` — add filter params to web_describe(), web_ax()
- `nexus/run.py` — parse --focus, --match, --region args
- `nexus/cortex/filters.py` — new module for preset definitions and filter logic

## Success Criteria
- `describe --focus buttons` returns 5 elements instead of 150
- Filters applied during traversal, not post-scan (measurable speed gain)
- Claude can get exactly the info it needs in one call, no manual parsing
