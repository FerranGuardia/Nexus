# NX-020 — Self-Healing Actions

**Track**: Hand (digitus)
**Priority**: MEDIUM — reduces failed actions, less back-and-forth
**Effort**: Medium
**Depends on**: NX-016 (element targeting), NX-005 (caching, done)

---

## Problem

When a Nexus action fails (element moved, window lost focus, timing issue), it just returns an error. Claude has to:
1. Read the error
2. Re-describe the screen
3. Figure out what went wrong
4. Retry manually

This burns 3-4 round-trips on a problem Nexus could often fix itself.

## Goal

Nexus actions should **automatically recover** from common failures before returning an error to Claude. Only escalate to Claude when self-healing exhausts its options.

## Scope

### 1. Common Failure Recovery

| Failure | Auto-Recovery |
|---------|--------------|
| Element not found at coordinates | Re-locate by name/role, retry at new position |
| Window not in foreground | `SetForegroundWindow()`, wait 200ms, retry |
| Element not enabled/clickable | Wait up to 2s for enabled state, then retry |
| Click hit wrong element | Verify via post-click describe, undo if possible |
| Dialog/popup blocked target | Detect overlay, try to dismiss (Escape/close button) |
| Page still loading (web) | Wait for `networkidle` or `domcontentloaded`, retry |

### 2. Recovery Pipeline
```
attempt_action(target)
  → success? → verify result → return
  → fail? → diagnose failure type
    → recoverable? → apply recovery → retry (max 2)
    → unrecoverable? → return error + current state + suggestions
```

### 3. Rich Error Responses
When self-healing fails, return actionable info:
```json
{
  "action": "click-element",
  "target": "Save",
  "status": "failed",
  "attempts": 3,
  "diagnosis": "Element 'Save' found but obscured by dialog 'Unsaved Changes'",
  "suggestions": ["Dismiss the dialog first", "Try click-element 'Discard'"],
  "current_state": {"focused": "Unsaved Changes dialog", "visible_buttons": ["Discard", "Cancel"]}
}
```

### 4. Timing Intelligence
- Learn per-app timing patterns: "Chrome needs 500ms after click before UI updates"
- Adaptive waits: start at 200ms, increase if verification fails, cap at 3s
- Store timing data in cache (NX-005) per app/window class

### 5. Undo Support
For destructive actions that hit the wrong target:
- Detect if the action produced an unexpected result
- If `Ctrl+Z` is applicable (text input, editor), auto-undo
- Report the accidental action to Claude so it has context

## Key Design Decisions
- Self-healing is opt-in initially (`--heal` flag), becomes default once proven reliable
- Max 2 retry attempts — don't spin forever
- Recovery adds latency (200ms-3s) — acceptable tradeoff for reliability
- Diagnosis logic is rule-based, not ML — pattern matching on failure types
- Never auto-recover from ambiguous situations (e.g., multiple matching elements)

## Files
- `nexus/digitus/healing.py` — new module for recovery logic
- `nexus/digitus/input.py` — wrap actions with healing pipeline
- `nexus/digitus/element.py` — enhanced element resolution for re-locate
- `nexus/digitus/web.py` — web-specific recovery (wait for load, etc.)

## Success Criteria
- 70%+ of common failures auto-recovered without Claude intervention
- Failed actions return actionable suggestions, not just "element not found"
- No false-positive recoveries (don't "fix" things that aren't broken)
