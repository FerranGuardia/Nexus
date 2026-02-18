# NX-002: Smart Tree Traversal (COM Conditions)

**Branch:** `task/NX-002-smart-traversal`
**Status:** DONE
**Depends on:** None
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** Nexus walks the entire UI tree with slow recursive Python calls.
> Switch to native COM `FindAll()` conditions so Windows does the filtering, not Python.

---

## What

- Replace `collect_elements` in `nexus/uia.py` with COM `FindAll()` + condition-based queries
- Use `CreatePropertyCondition`, `AndCondition`, `OrCondition` to filter at the COM level
- Filter to actionable controls only: Button, Edit, Link, MenuItem, CheckBox, RadioButton, ComboBox, Tab, List, ListItem, TreeItem
- Filter out invisible elements (zero bounding rect) at COM level, not Python level
- Add `--depth` flag to `describe` (default: 3, current behavior walks deeper)
- Add `is_enabled` flag to element output
- Benchmark before/after on a heavy app (Chrome, VS Code, File Explorer)

## Why

The brute-force tree walking is the main bottleneck for native app awareness. Heavy apps like VS Code produce 200+ elements, most irrelevant. COM-level filtering should cut scan time by 50%+ and element count by 60%+.

## Where

- **Read:** `nexus/uia.py`, `nexus/oculus/uia.py`
- **Write:**
  - `nexus/uia.py` — rewrite `collect_elements`, `find_elements` to use COM conditions
  - `nexus/oculus/uia.py` — add `--depth` parameter, wire `is_enabled`
  - `nexus/run.py` — add `--depth` arg to `describe` subparser
  - `nexus/tests/test_traversal.py` (new) — unit tests for new traversal

## Validation

- [ ] `describe` uses COM `FindAll()` instead of recursive Python `GetChildren()`
- [ ] Only actionable control types are returned (no static text, no decorators)
- [ ] Zero-rect elements are filtered out
- [ ] `--depth 3` limits tree traversal depth
- [ ] `is_enabled` field present on each element
- [ ] Benchmark: scan time reduced vs current implementation
- [ ] Benchmark: element count reduced vs current implementation
- [ ] Existing `find` command still works with new traversal
- [ ] E2E tests pass (`pytest nexus/tests/ -v -m "not action"`)

---

## Not in scope

- Familiarity cache / known-app patterns (that's NX-005 caching)
- Compact output formatting (that's NX-001)
