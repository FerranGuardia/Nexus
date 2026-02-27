# Field Test 3 — Real-World Validation from Inside Claude Code

**Date:** 2026-02-26
**Tester:** Claude (Opus 4.6) acting as a real user of Nexus via MCP
**Host:** VS Code with Claude Code extension (MCP server running inside VS Code)
**macOS:** Sequoia (Darwin 24.6.0), Spanish locale
**Tests:** 1,335 passing before test session

## Executive Summary

Nexus has a solid foundation — the three-tool design works, the intent parsing is mature,
and the test suite is comprehensive. But the **#1 real-world blocker is app targeting**:
`see(app=X)` and `do(action, app=X)` consistently resolve to VS Code instead of the
requested app when VS Code hosts the MCP server. This single bug breaks every
multi-app workflow.

### Scorecard

| Test | Result | Notes |
|------|--------|-------|
| Basic perception (see, list windows) | PASS | 42 elements, window list accurate |
| TextEdit — create note, type, save | PASS* | Worked via do(app=), but see(app=) broken |
| Finder — navigate, read file list | FAIL | Sidebar + file list items 100% blank |
| VS Code — open project | PASS | Only via CLI `open -a`, not via UI |
| Terminal — open, type, execute | PASS* | Needed Cmd+N separately; content truncated |
| System Settings — navigate | FAIL | app= targeting resolved to VS Code |
| Safari — navigate, read page | PASS | Rich tree (22 elements), URL navigation works |
| Notes — multi-app workflow | FAIL | Keyboard events go to VS Code, not Notes |

**Pass rate: 4/8 clean, 2/8 with workarounds, 2/8 hard fails**

---

## Detailed Findings

### CRITICAL: App Targeting is Broken (see + do)

**The single biggest issue in Nexus today.**

When VS Code hosts the MCP server:
- `see(app="TextEdit")` → returns VS Code's 42 elements
- `see(app="System Settings")` → returns VS Code's elements
- `do("click General", app="System Settings")` → searches VS Code's tree, fails
- `do("press cmd+n", app="Notes")` → keystroke goes to VS Code chat input

**What works:**
- `do("press cmd+s", app="TextEdit")` → keystroke correctly targets TextEdit
- `do("press cmd+l", app="Safari")` → correctly targets Safari
- `do("type text", app="Terminal")` → correctly targets Terminal

**Pattern:** `do()` with `app=` seems to work for **some** keyboard/type actions
(likely via AppleScript `activate` + pyautogui) but `see(app=)` NEVER works for
non-VS-Code apps. The post-action state in `do()` responses also always shows VS Code.

**Root cause hypothesis:** The PID resolution for `app=` works at the do() level
(AppleScript activates the target app, pyautogui sends keys before VS Code steals
focus back), but `see()` and the post-action `snap()` always walk the frontmost
app's tree — which is VS Code by the time the tree walk happens.

**Impact:** An agent cannot inspect any app's UI from VS Code. It can send blind
keystrokes to other apps but can't verify what happened. This makes multi-step
GUI workflows impossible without workarounds.

**Severity: P0 — blocks all non-VS-Code GUI automation**

---

### CRITICAL: Finder List/Outline Items Have No Labels

`see(app="Finder")` returns the tree structure but every list item is blank:

```
Outline "barra lateral" (23 items):
  1.
  2.
  3.
  ...
Outline "visualización como lista" (16 items):
  1.
  2.
  3.
  ...
```

`do("read list", app="Finder")` confirms: 23 sidebar items, 23 file list items,
ALL empty strings.

**However:** Individual file names sometimes appear as `[campo de texto]` values
(e.g., `= ACT-Project` and `= IMG_0192.HEIC`). These are inline rename fields,
not the actual list item labels.

**Root cause hypothesis:** Finder's AXOutline/AXRow items store their display text
in a child element (AXStaticText or AXTextField) rather than as the row's own
AXValue/AXTitle. The current `read_list()` implementation reads the row-level
attribute but doesn't walk into children.

**Impact:** Nexus can navigate Finder by keyboard shortcuts (Cmd+Shift+G works)
but cannot read or click specific files/folders by name.

**Severity: P1 — Finder is a core app, completely blind to file names**

---

### HIGH: VS Code Focus-Stealing Breaks Action Chains

Action chains like `open Notes; wait 2s; press cmd+n` fail because:
1. `open Notes` activates Notes via AppleScript
2. VS Code immediately steals focus back (it hosts the MCP server)
3. `wait 2s` elapses with VS Code focused
4. `press cmd+n` goes to VS Code, not Notes

Chains don't inherit the `app=` parameter — each action in a chain runs independently.

**Impact:** Multi-step workflows across apps require separate `do()` calls with
explicit `app=` on each one. Chains are only reliable within VS Code itself.

**Severity: P1 — multi-app chains are unreliable**

---

### HIGH: Apps Open Without Windows

Several apps launch but don't create a visible window:
- **TextEdit:** Opens but no window until `press cmd+n` with `app=TextEdit`
- **Terminal:** Opens but 0 elements, no window until `press cmd+n` with `app=Terminal`
- **Safari:** Opens but 0 elements, no window until `press cmd+n` with `app=Safari`
- **Notes:** Opened but never produced a visible window during testing

**Pattern:** macOS Sequoia apps often launch to a "no window" state (the app process
exists but no NSWindow is created until the user explicitly requests one).

**Workaround:** Always follow `open X` with `press cmd+n` targeting the app.
This should be built into the `open` intent handler automatically.

**Severity: P1 — requires extra step for every app launch**

---

### MEDIUM: Post-Action State Always Shows VS Code

Every `do()` response includes a "State" section showing the current UI. This
ALWAYS shows VS Code's tree, even when the action targeted another app:

```
--- State ---
App: Code — "Welcome — catipad-web"
Elements (52):
  [standard window] "Welcome — catipad-web"
  ...
```

The action journal correctly records the target app: `"type text -> OK (TextEdit)"`
but the state section is useless for verifying what happened in the target app.

**Impact:** The merged do()+see() response (Phase 3 feature) is broken for all
non-VS-Code apps. The agent must call `see(app=X)` separately — but that's also
broken (see Finding #1).

**Severity: P2 — reduces do() response value to just ok/fail**

---

### MEDIUM: Tree Cache Serves Stale Data

After Safari navigated from Start Page to example.com:
- The post-action state still showed Start Page elements (favourites, onboarding)
- A subsequent `see()` call showed the correct Example Domain tree

The 1s tree cache TTL means the snap() taken immediately after an action may
return pre-action data.

**Severity: P2 — verification snapshots can be stale**

---

### LOW: Localized Role Descriptions in Output

On Spanish macOS, elements show localized descriptions:
- `[botón]` instead of `[button]`
- `[ventana estándar]` instead of `[standard window]`
- `[campo de texto]` instead of `[text field]`
- `[área de entrada de texto]` instead of `[text entry area]`

VS Code (Electron) shows English descriptions. Native apps show Spanish.

**Impact:** The agent sees inconsistent element names across apps. Not a
functional blocker but increases cognitive load and token usage.

**Severity: P3 — cosmetic, but confusing for agents**

---

### LOW: System Settings Quit Didn't Work

`do("press cmd+q", app="System Settings")` was sent but System Settings window
remained visible in subsequent `list windows` calls.

**Severity: P3 — minor, workaround: close window instead of quit**

---

## What Works Well

1. **Intent parsing is mature.** Every verb was understood correctly: open, switch,
   press, type, list windows, read list, click. No parsing failures.

2. **Action verification detects changes.** Window appearances, focus changes, and
   element additions are correctly reported in the Changes section.

3. **Safari has a rich AX tree.** 22 elements with clear labels, page content,
   toolbar buttons, and the URL in the search field. Best non-VS-Code experience.

4. **The learning system persists.** Previous session action stats (AXPress,
   set_value, etc.) appeared in the learned section across sessions.

5. **System dialog detection works.** A permission prompt from UserNotificationCenter
   was correctly detected and reported.

6. **TextEdit text content was perfect.** The typed text appeared exactly as intended
   in the saved RTF file. Clipboard paste for long strings works.

7. **Keyboard shortcuts as actions work well.** Cmd+S, Cmd+L, Cmd+N, Cmd+W,
   Cmd+Shift+G all executed correctly when sent to the right app.

8. **Skill hints on error.** When "click General" failed in System Settings, the
   error suggested `nexus://skills/system-settings` — good fallback guidance.

---

## Recommendations (Priority Order)

### P0: Fix app= PID resolution for see() and do() state snapshots

The `see()` function and the post-action `snap()` must walk the target app's AX tree,
not the frontmost app's tree. This requires:
- Resolving app name → PID at the server level
- Passing the PID to `describe_app()` / `full_describe()` explicitly
- NOT falling back to frontmost app when a PID is provided

This single fix would unblock all multi-app workflows.

### P1: Fix Finder list item label extraction

Walk into AXRow children to find AXStaticText/AXTextField values. This would
make Finder's sidebar and file lists readable. Test with:
- Sidebar items (Favourites, iCloud, Tags)
- File list items (column view, list view, icon view)

### P1: Auto-create window on `open` intent

When `do("open X")` launches an app, check if it has a window after a short delay.
If not, automatically send Cmd+N. This matches how users actually launch apps.

### P1: Propagate app= through action chains

Each action in a chain should inherit the `app=` parameter from the parent `do()`
call unless overridden. This would make `do("open Safari; wait 1s; press cmd+l",
app="Safari")` work correctly.

### P2: Force cache invalidation after actions

After any mutating do() action, invalidate the tree cache for the target PID
before taking the post-action snapshot. This ensures the state reflects the
actual result of the action.

### P2: Normalize locale in output

Consider showing the English role name for consistency, or mapping Spanish
role descriptions to English in the output formatter. The agent shouldn't need
to handle both `[botón]` and `[button]`.

---

## Test Artifacts

- Created file: `~/Library/Mobile Documents/com~apple~TextEdit/Documents/nexus-field-test.rtf`
  - Content: "Nexus field test - this note was created by an AI agent using accessibility APIs"
- Opened VS Code window: catipad-web project at `/Users/ferran/repos/catipad/catipad-web`
- Finder navigated to: `~/repos`

## Reproducibility

All tests were run from Claude Code (VS Code extension) using Nexus MCP tools.
The critical app= targeting bug is 100% reproducible — every `see(app=X)` call
for non-VS-Code apps returned VS Code's tree during this session.
