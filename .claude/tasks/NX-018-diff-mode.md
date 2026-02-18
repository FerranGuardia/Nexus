# NX-018 — Diff Mode for Describe

**Track**: Brain (cortex)
**Priority**: HIGH — massive context savings on repeated scans
**Effort**: Medium
**Depends on**: NX-005 (caching, done)

---

## Problem

Every `describe` call dumps the full UI tree (50-200 elements). When Claude calls `describe` repeatedly during a task (common pattern: describe → act → describe again to verify), most elements haven't changed. Claude processes the same 150 unchanged elements just to notice 2 that changed.

This is the #1 token waste in Nexus usage.

## Goal

After the first `describe`, subsequent calls return only what **changed** — new elements, removed elements, changed properties (focus, enabled state, text).

## Scope

### 1. Automatic Diff Detection
- Cache the last `describe` result per window (already in NX-005 cache layer)
- On next `describe`, compare current tree vs cached:
  - **Added**: elements present now but not before
  - **Removed**: elements present before but not now
  - **Changed**: same element (matched by name+role+parent) with different properties (focused, enabled, value, position)
  - **Unchanged**: skip entirely
- Return format:
```json
{
  "command": "describe",
  "mode": "diff",
  "since": "2024-01-15T10:30:45",
  "added": [...],
  "removed": [...],
  "changed": [{"name": "Search", "changes": {"focused": [false, true]}}],
  "unchanged_count": 147,
  "summary": "Focus moved to Search input. 1 new dialog appeared. 147 elements unchanged."
}
```

### 2. Compact Diff Format
In compact output mode, diff looks like:
```
DIFF since 2.3s ago (147 unchanged)
+ [Dialog] Save Changes? | (300,200) 400x150    ← new
~ [Edit] Search | focused                        ← changed
- [Btn] Loading... |                              ← removed
```

### 3. Smart Change Detection
Not just element-level diff — detect semantic changes:
- "A dialog appeared" (new top-level window/popup)
- "Focus moved from X to Y"
- "Page navigated" (web: URL changed)
- "Content loaded" (element count jumped significantly)
- "Error appeared" (new element with "error" in name/role)

### 4. Force Full Scan
- `describe --force` bypasses diff and returns full tree (already in cache layer)
- `describe --diff` explicitly requests diff mode
- Auto-detect: if >50% elements changed, return full tree instead of diff (diff would be bigger than full)

## Key Design Decisions
- Element matching: by (name + role + parent_name) tuple, not by position
- Diff should work for both UIA (native) and CDP (web) describe results
- The "summary" line is the most important output — Claude reads that first to decide if full details matter
- Cache is per-window, invalidated on window title change

## Files
- `nexus/cache.py` — extend with diff computation
- `nexus/oculus/uia.py` — wire diff into describe
- `nexus/oculus/web.py` — wire diff into web-describe

## Success Criteria
- Second `describe` call returns 80%+ fewer tokens when little changed
- Claude can detect "a dialog appeared" from the diff summary without scanning the full tree
- Correctly identifies focus changes, new elements, removed elements
