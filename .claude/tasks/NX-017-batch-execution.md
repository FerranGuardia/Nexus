# NX-017 — Batch Execution Mode

**Track**: Infra
**Priority**: HIGH — reduces context round-trips, less interference window
**Effort**: Medium
**Depends on**: NX-003 (daemon mode, done)

---

## Problem

Each Nexus command is a separate subprocess call with its own:
- Python startup (~300-500ms cold, ~50ms via daemon)
- Context round-trip (output goes to Claude, Claude decides next step, calls again)
- Interference window (user can disrupt state between calls)

A typical flow: `describe → find "button" → click-element "Save"` = 3 round-trips through Claude's context. The intermediate results (full UI tree, find results) burn tokens but Claude only needs the final outcome.

## Goal

Execute multi-step command sequences in a single call. Only the final result enters Claude's context.

## Scope

### 1. `batch` Command
```
python -m nexus batch "describe; find 'Save'; click-element 'Save'"
```
- Semicolon-separated commands executed sequentially
- Each command's output available to the next (via shared context dict)
- Only the last command's output (or a summary) returned to caller
- If any command fails, stop and return the error + which step failed

### 2. Conditional Execution
```
python -m nexus batch "find 'Save' | click-element '$name'"
```
- Pipe `|` passes previous output fields to next command
- `$name`, `$x`, `$y` interpolation from previous result
- `?` prefix for conditional: `"find 'Error' ? screenshot"` (only screenshot if error found)

### 3. Plan Execution
```
python -m nexus run-plan plan.json
```
- JSON file with steps, conditions, and expected outcomes:
```json
{
  "steps": [
    {"cmd": "describe", "extract": "focused_element"},
    {"cmd": "click-element", "args": "Save", "verify": true},
    {"cmd": "describe", "expect": {"focused_element": {"not": "Save"}}}
  ]
}
```
- Built-in verification at each step
- Returns summary: steps completed, verifications passed/failed, final state

### 4. Daemon Integration
- When daemon (NX-003) is running, batch executes in-process — zero subprocess overhead
- Shared state between commands (UIA tree, CDP connection) persists across the batch
- Significantly faster than sequential CLI calls

## Key Design Decisions
- Keep it simple: semicolon chaining first, fancy interpolation later
- Batch should work in both CLI mode and daemon mode
- Error handling: fail-fast by default, `--continue-on-error` flag for resilience
- Output: return only final result by default, `--verbose` for all intermediate results

## Files
- `nexus/run.py` — add batch command dispatch
- `nexus/batch.py` — new module for batch parsing and execution
- `nexus/serve.py` — daemon batch support

## Success Criteria
- `describe + find + click` in one call instead of three
- 60%+ reduction in context tokens for multi-step operations
- Intermediate results don't pollute Claude's context
