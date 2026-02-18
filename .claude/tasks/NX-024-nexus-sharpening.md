# NX-024 — Nexus Design Sharpening

**Track**: All pillars (Oculus, Cortex, Digitus)
**Priority**: HIGH — directly improves Claude's success rate per session
**Effort**: Medium (3 focused subtasks)
**Depends on**: All existing NX tasks (audit-based refinement)

---

## Problem

Based on a full audit of Nexus (Feb 2026), Claude succeeds ~65% of the time on non-trivial tasks without manual correction. The remaining ~35% failures come from:

1. **Ambiguous tool output** — describe/find return data that's correct but doesn't highlight what matters for the decision at hand
2. **Silent failures** — tools return partial results or empty data without explaining why, causing Claude to make wrong assumptions
3. **Missing "what changed?" signal** — after an action, Claude has to re-describe and mentally diff, wasting a round-trip and sometimes missing the change
4. **Stale/broken code paths** — web-layout-diff crashes (bad cdp_page kwargs), duplicated dispatch tables drift apart, dead code confuses audits
5. **Error messages are for developers, not for LLMs** — Python tracebacks instead of structured "what failed + what to try next"

**Goal**: Improve Claude's first-attempt success rate by sharpening the signal quality of every tool response. Token budget is secondary — spend tokens where they improve decisions, save them where they don't.

---

## Subtasks

### A. Fix Known Bugs (cleanup first)

1. **Fix `web_layout_diff` crash** — `oculus/image.py` ~line 439 calls `cdp_page(tab=tab, port=port)` but `cdp_page()` only takes a URL string. Construct proper CDP URL from port.
2. **Delete dead `CdpPool` class** — `cdp.py` has ~100 lines of unused connection pool code. Remove it.
3. **Fix stale tool count** — `tools_schema.py` line 165 says "39 tools", actual count is 47+ CLI / 50 MCP.
4. **Unify `click_mark` in MCP** — `mcp_server.py` has inline pyautogui logic instead of delegating to the core command. Make it delegate.
5. **Unify dispatch tables** — `run.py` has `_build_commands()` and `_build_daemon_commands()` (~300 lines duplicated). Single registry with thin adapter.

### B. Actionable Error Responses (all tools)

Every tool that can fail should return structured errors, not tracebacks:

```json
{
  "status": "error",
  "error": "Element 'Submit' not found in active window 'Settings'",
  "context": {"window": "Settings", "visible_buttons": ["OK", "Cancel", "Apply"]},
  "suggestions": ["Try 'OK' instead", "Check if a dialog is covering the target"]
}
```

Priority targets (most common failure points):
- `click_element` — already has healing, but non-heal mode errors are bare
- `web_click` — "element not found" with no alternatives listed
- `web_input` — fails silently when selector doesn't match
- `describe` — returns empty tree without explaining why (minimized window? wrong focus?)

### C. Tool Description Sharpening (MCP)

The MCP tool descriptions are what Claude reads every turn to decide which tool to use. Current descriptions are functional but not decision-oriented. Rewrite them to be:

- **When to use this vs alternatives** (e.g., `find` vs `describe --match`)
- **What the output looks like** (so Claude knows what to expect)
- **Common pitfalls** (e.g., "web_click needs exact visible text, not aria-label")
- Keep descriptions concise — aim for 2-3 sentences max, not paragraphs

---

## Files (expected changes)

- `nexus/oculus/image.py` — fix cdp_page bug
- `nexus/cdp.py` — remove dead CdpPool
- `nexus/run.py` — unify dispatch tables
- `nexus/mcp_server.py` — delegate click_mark, sharpen tool descriptions
- `nexus/tools_schema.py` — fix stale count
- `nexus/digitus/element.py` — structured errors
- `nexus/digitus/web.py` — structured errors

## Success Criteria

- All known bugs fixed (A1-A5)
- Error responses are structured JSON with suggestions, not tracebacks
- All MCP tool descriptions rewritten with decision-oriented guidance
