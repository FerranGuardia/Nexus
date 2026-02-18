# NX-001: Compact Output Format

**Branch:** `task/NX-001-compact-output`
**Status:** DONE
**Depends on:** None
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** Nexus dumps massive JSON blobs that eat Claude's context window.
> Add a compact one-liner-per-element format that's 60-80% smaller while still parseable.

---

## What

- Add `--format compact|json|minimal` flag to all Oculus commands
- `json` = current behavior (backward compat, default for now)
- `compact` = one-liner per element:
  ```
  [Btn] Save | (120,340) 80x30
  [Edit] Search... | (200,50) 300x24 *focused*
  [Link] Settings | (50,400) 60x18
  ```
- `minimal` = just names and types, no coordinates
- Apply to: `describe`, `find`, `windows`, `focused`, all `web-*` commands
- Compact format must be **parseable back** (Claude can extract coords from it)
- Formatter is a pure function: takes command result dict, returns formatted string

## Why

Every token spent on verbose JSON is a token Claude can't spend thinking. The `describe` command dumps up to 120 elements x 8 fields — massive. Compact output is the single biggest token-saving improvement. Unlocks all use cases.

## Where

- **Read:** `nexus/run.py`, `nexus/oculus/uia.py`, `nexus/oculus/web.py`
- **Write:**
  - `nexus/format.py` (new) — pure formatter functions: `format_compact()`, `format_minimal()`
  - `nexus/run.py` — add `--format` global arg, apply formatter before JSON output
  - `nexus/tests/test_format.py` (new) — unit tests for formatter

## Fix

- Add a `--format` argument to the argparse global args (not per-subcommand)
- In `main()`, after getting `result` from the command, pass through formatter if format != json
- Formatter is a standalone pure function — no coupling to command internals
- Each element type (UIA, web node, window) gets its own compact representation
- Include role abbreviation map: `Button→Btn`, `Edit→Edit`, `Link→Link`, `MenuItem→Menu`, etc.

## Validation

- [ ] `--format compact` produces one-liner-per-element output for `describe`
- [ ] `--format minimal` produces names-only output
- [ ] `--format json` (or no flag) produces current JSON output (no regression)
- [ ] Compact format works for all Oculus commands (UIA + web)
- [ ] Compact output is parseable — coords can be extracted via regex
- [ ] Token count reduced by 60%+ vs JSON for same `describe` result
- [ ] Unit tests for formatter cover all element types
- [ ] E2E test: `python -m nexus --format compact describe` produces valid output
- [ ] No regressions in existing E2E tests (`pytest nexus/tests/ -v -m "not action"`)

---

## Not in scope

- Changing default format from json to compact (that's a later decision after testing)
- Applying format to Digitus (action) commands — they return status, not element lists
