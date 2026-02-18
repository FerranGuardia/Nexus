# NX-016 — Element-Based Targeting + Action Verification

**Track**: Hand (digitus)
**Priority**: HIGH — solves the #1 daily pain point (mouse interference breaks coordinate clicks)
**Effort**: Medium
**Depends on**: NX-002 (smart traversal, done), web-ax (done)

---

## Problem

When Claude issues `click 450 300`, the coordinates are fragile:
- User approves a permission prompt → mouse moves → coordinates now wrong
- Window shifts, scrolls, or resizes between describe and click → miss
- Multi-monitor DPI differences can offset coordinates
- No feedback on whether the click hit the right thing

## Goal

Replace coordinate-based actions with **element-based targeting** as the primary action method. Coordinates become the fallback, not the default.

## Scope

### 1. Element Targeting by Name/Role
- `click-element "Save"` already exists but is basic — enhance it:
  - Fuzzy matching: "save" matches "Save Changes", "Save Draft", "Save As..."
  - Role-aware: `click-element --role button "Save"` narrows to buttons only
  - Index support: `click-element "Save" --index 2` for the second match
  - Web support: use CDP node resolution (`DOM.querySelector` + `DOM.focus` + `Input.dispatchMouseEvent`) instead of coordinates

### 2. Action Verification Loop
After every action (click, type, key), automatically:
1. Wait 200-500ms for UI to settle
2. Re-describe or screenshot the affected area
3. Compare expected state vs actual state
4. Return `{"action": "click", "target": "Save", "verified": true/false, "after_state": "..."}`

### 3. Pre-Action Window Focus
Before any action:
1. Identify which window owns the target element
2. `SetForegroundWindow()` to ensure it's focused
3. Validate the element is still visible and at expected position
4. Only then execute the action

### 4. Retry with Re-locate
If verification fails:
1. Re-scan for the target element (it may have moved)
2. If found at new position, retry the action
3. If not found, return error with current screen state
4. Max 2 retries before giving up

## Key Design Decisions
- Element targeting should work for BOTH native (UIA) and web (CDP) — unified interface
- Verification should be optional (`--verify` flag) since it adds latency
- The retry logic lives in Nexus, not in Claude — Claude shouldn't need to manually retry

## Files
- `nexus/digitus/element.py` — enhance `click_element`, add element resolution logic
- `nexus/digitus/input.py` — add verification loop to click/type/key
- `nexus/uia.py` — add fuzzy element search
- `nexus/digitus/web.py` — add CDP-based element clicking

## Success Criteria
- User can approve permissions, move mouse, and the next action still hits the right target
- Actions report whether they succeeded or failed
- No coordinate guessing needed for labeled UI elements
