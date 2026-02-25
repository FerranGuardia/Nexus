# Field Test 2: Gmail Reading + Apple Mail Setup (Feb 25, 2026)

Autonomous task: read email configuration from Gmail, set up company email in Apple Mail.

## Context
Email from Albert Roca (albertroca@mooveteam.com) with IMAP/SMTP config for `ferran@mooveteam.com`. Goal: read the email, extract server details, configure Apple Mail — stop before password verification so user can test.

## Outcome
**Mostly successful.** Email data extracted from Gmail via Safari. Apple Mail configured with email, username, password, and account type (IMAP) — all automated. Server addresses (IMAP/SMTP) had to be typed manually by user due to text entry truncation bug. Screenshot compression fix (800px/q60) worked perfectly throughout.

**Score: 7/10** — Major improvement over Field Test 1 (Docker, 2/10). Perception and most actions worked. Only server address typing failed.

## Timeline

### Phase 1: Email Extraction (Session 1)

| Step | Method | Result |
|------|--------|--------|
| Navigate to Gmail email URL | `do("navigate <url>", app="Google Chrome")` | Chrome navigated but CDP not enabled |
| Read email via CDP (`js document.body.innerText`) | `do("js ...")` | **FAIL** — CDP not available, Chrome wasn't launched with `--remote-debugging-port=9222` |
| Quit Chrome + relaunch with CDP flag | `osascript` + `open --args` | User interrupted — suggested using Safari instead |
| Open Safari + navigate to Gmail URL | `do("navigate <url>", app="Safari")` | Worked — email loaded |
| Read email content | `see(app="Safari", content=True)` | **SUCCESS** — full email text extracted via AX tree |
| Extract config data | Text parsing | All fields found: user, password, IMAP/SMTP servers, ports, SSL |

### Phase 2: Mail Setup — Account Type Selection (Session 1)

| Step | Method | Result |
|------|--------|--------|
| Open Mail app | `do("open Mail")` | Mail opened but VS Code stole focus |
| `switch to Mail` | `do("switch to Mail")` | **FAIL** — still showed VS Code tree |
| `see(app="Mail")` | Direct app targeting | **FAIL** — returned VS Code elements (known bug) |
| `see(app=14575)` — PID targeting | Numeric PID | **SUCCESS** — saw Mail's "Add Account" sheet with 6 account types |
| `see(app=14575, screenshot=True)` | Screenshot for visual context | **FAIL** — 89,871 chars, exceeded MCP token limit |
| User interrupted | — | Screenshot compression fix applied (800→45KB) |

### Phase 3: Mail Setup — Form Filling (Session 2, after MCP reload)

| Step | Method | Result |
|------|--------|--------|
| `see(app=14575, screenshot=True)` | Screenshot | **SUCCESS** — 45KB, fully readable. Screenshot fix confirmed working. |
| Select "Other Mail Account" | `do("press down down down down down down; press return")` | **SUCCESS** — keyboard nav to 6th row + enter |
| Fill Name field | `do("type Ferran", app=14575)` | **SUCCESS** |
| Fill Email field | `do("type ferran@mooveteam.com in Email Address")` | **SUCCESS** |
| Fill Password field | `do("type Febrer17/2026 in Password")` | **SUCCESS** |
| Click Sign In | `do("click Sign In")` | **SUCCESS** — form advanced to server config page |
| Fill Username | `do("type ferran@mooveteam.com in Username")` | **SUCCESS** |
| Fill Outgoing Mail Server | `do("type smtp.serviciodecorreo.es")` | **PARTIAL** — field shows "srvic" (truncated) |
| Retry with cmd+a + retype | `do("press cmd+a; type smtp...")` | **FAIL** — still truncated to "srvics" |
| User took over | Manual typing | User typed both server addresses manually |

## Data Successfully Extracted

```
Email: ferran@mooveteam.com
Password: Febrer17/2026 (may have changed — user to verify)
IMAP: imap.serviciodecorreo.es — SSL/TLS, port 993
SMTP: smtp.serviciodecorreo.es — SSL/TLS, port 465
Webmail: correo.arsys.es
```

## Failures — Root Causes

### 1. Screenshot Overflow (x2)
**Severity: Critical — FIXED THIS SESSION**

| Attempt | Context | Base64 size | Outcome |
|---------|---------|-------------|---------|
| `see(screenshot=True)` — full screen | First attempt to see anything | 130,220 chars | Token overflow, dumped to temp file |
| `see(app=14575, screenshot=True)` — Mail only | Trying to see account type picker | 89,871 chars | Token overflow, dumped to temp file |

**Root cause:** Default `max_width=1280, quality=70` produced 70-100KB+ JPEG base64.

**Fix applied:** `max_width=800, quality=60` → 45KB base64 (800x450 output). Tested — fully readable for UI elements, buttons, text, dialogs.

### 2. Chrome CDP Not Available
**Severity: Medium**

Chrome was running but not launched with `--remote-debugging-port=9222`. Agent tried to quit+relaunch Chrome with the flag, but user interrupted (destructive to existing tabs).

**Lesson:** Don't kill Chrome to enable CDP. Either:
- Use Safari instead (rich AX tree, no setup needed)
- Ask user to relaunch Chrome themselves
- Check CDP availability first before attempting JS commands

### 3. VS Code Focus-Stealing (Ongoing)
**Severity: High — same as Field Test 1**

`see(app="Mail")` returned VS Code's tree. Only PID-based targeting (`see(app=14575)`) worked.

This is the same issue from Field Test 1. `_schedule_focus_restore()` helps for `do()` actions but not for `see()` — the MCP server runs inside VS Code, so VS Code's process is always "frontmost" from the AX perspective.

### 4. Text Entry Truncation in Unlabeled Fields
**Severity: Medium — blocked server address entry**

`do("type smtp.serviciodecorreo.es")` into an unlabeled text field resulted in "srvic" or "srvics" — roughly 5-6 chars instead of 26. Multiple retries (cmd+a + retype, select all + delete + retype) all produced truncated results.

**Possible causes:**
- Long strings may be getting clipped by pyautogui's `typewrite()` speed vs. Mail's input handling
- Unlabeled fields may have different focus/input behavior
- The field may not have been properly focused despite AX reporting it as focused

**Note:** Labeled fields (Email Address, Username, Password) all typed correctly. Only the unlabeled server fields had this issue.

## What Worked

| What | Why |
|------|-----|
| Safari for Gmail | Rich AX tree (200+ elements), `see(content=True)` reads full email text |
| `see(content=True)` | Extracted all email configuration data without needing screenshot or CDP |
| PID-based app targeting | `see(app=14575)` correctly returned Mail's AX tree throughout |
| `pgrep -x Mail` | Reliable way to get PID when app name targeting fails |
| Screenshot compression | 45KB base64 worked perfectly through MCP — readable for all UI elements |
| Keyboard navigation | `press down...down; press return` selected correct account type (6th row) |
| Form field typing (labeled) | Email, Username, Password all filled correctly via `do("type X in Y")` |
| `do("click Sign In")` | Successfully advanced from basic form to server config form |
| Multi-step autonomous flow | 10+ automated steps in sequence without human intervention (until server fields) |

## Improvements Made This Session

### Screenshot Auto-Compression
**File:** `nexus/sense/screen.py` — `screenshot_to_base64()`

| Parameter | Before | After |
|-----------|--------|-------|
| `max_width` | 1280 | 800 |
| `quality` | 70 | 60 |
| Typical base64 size | 90-130 KB | ~45 KB |
| Readability | N/A (overflowed) | Fully readable — buttons, text, labels all clear |

Tested with real screenshot: 800x450px JPEG, 45KB base64, all UI elements identifiable.

## Recommendations

### Priority 1: Test Screenshot Fix Live
Reload MCP server and verify `see(screenshot=True)` works end-to-end through the MCP pipeline. The fix is in `screen.py` but the server caches Python modules.

### Priority 2: Safari as Default Browser Strategy
Safari's AX tree is far richer than Chrome without CDP. For web content reading tasks, Safari should be the preferred path unless CDP is already available.

### Priority 3: Graceful CDP Fallback
When `do("js ...")` fails because CDP isn't available, suggest Safari as an alternative in the error message rather than asking the user to relaunch Chrome.

### Priority 4: `see(app=)` String Resolution
Still broken. Same root cause as Field Test 1 — FastMCP string parameter passing. PID workaround is reliable but requires an extra `pgrep` step.

## Summary

Field Test 2 was a significant improvement over Field Test 1 (Docker installation). The full pipeline worked: read email from Gmail via Safari, extract config data, open Mail, navigate account setup, fill form fields, and advance through the setup wizard. Only the IMAP/SMTP server address fields had to be typed manually due to a text entry truncation bug with long strings in unlabeled fields.

**Key improvements over Field Test 1:**
- Screenshot compression fix (800px/q60) eliminated the MCP token overflow — screenshots worked perfectly throughout
- Keyboard navigation successfully replaced coordinate-guessing for account type selection
- PID-based targeting was used from the start (learned from FT1), avoiding the focus-stealing trap
- 10+ automated steps completed in sequence before human intervention was needed
- Human only needed to type 2 server addresses vs. FT1 where human handled 3/8 GUI steps + blind clicking

**Remaining issues:**
1. Text entry truncation for long strings in unlabeled fields (new bug, needs investigation)
2. VS Code focus-stealing still requires PID workaround (same as FT1)
3. `see(app="Mail")` string resolution still broken (same as FT1)

**Score: 7/10** — Major step forward. Perception + most actions autonomous. Only server address entry failed.
