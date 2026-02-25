# Field Test: Docker Desktop Installation (Feb 24, 2026)

Autonomous task: install Docker Desktop on Intel Mac using Nexus for GUI interaction.

## Outcome
Docker installed via `brew install --cask docker-desktop`. GUI setup required human intervention for 3 system dialogs and final completion. **Nexus was effectively blind for the entire GUI portion.**

## Timeline

| Step | Method | Result |
|------|--------|--------|
| Check system (brew, arch, existing docker) | Bash | Clean — no issues |
| `brew install --cask docker-desktop` | Bash | Failed — needs `sudo mkdir` for `/usr/local/cli-plugins` |
| Pre-create directory with `echo pw \| sudo -S` | Bash | Worked |
| Retry brew install | Bash | Installed successfully |
| Launch Docker (`open -a Docker`) | Bash | Backend started, GUI didn't appear |
| See Docker window via Nexus | `see(app="Docker")` | **FAIL** — returned VS Code tree |
| Switch to Docker | `do("switch to Docker")` | **FAIL** — osascript timed out (10s) |
| Switch to Docker Desktop | `do("switch to Docker Desktop")` | Worked (focus change reported) |
| See Docker after switch | `see()` | **FAIL** — still VS Code tree |
| See by PID | `see(app=99288)` | Partial — 4 elements (window frame only) |
| Enable AXManualAccessibility | Python direct | error=0 (success), but tree stayed at 4 elements |
| Gatekeeper dialog ("app from internet") | Nexus | **BLIND** — user had to click Open |
| Accept subscription agreement | Coordinate clicking | Worked after ~6 blind attempts |
| Finish setup dialog | Coordinate clicking | **ACCIDENTALLY clicked "Use advanced settings"** instead of "Finish" — expanded unwanted config options |
| Grid-click to find Finish button | pyautogui grid | 20+ positions tried, never hit the button |
| Tab+Enter navigation | Keyboard | Eventually triggered password prompt (happy accident) |
| Password entry | pyautogui.typewrite | Worked — entered password correctly |
| Password dialog confirmation | Keyboard Enter | Worked |
| Network permission ("find devices") | Nexus | **BLIND** — user had to handle |
| Welcome screen / final setup | User | **User took over** to complete |

## Limitations Found

### 1. System Dialogs Are Completely Invisible
**Severity: Critical**

macOS security/permission dialogs cannot be seen or interacted with:
- Gatekeeper: "Docker is an app downloaded from the internet"
- Network: "Allow Docker to find devices on your local network"
- Password prompts (SecurityAgent)

These run in `CoreServicesUIAgent` / `SecurityAgent` — processes that don't expose accessibility elements to non-system apps. `see(app="NotificationCenter")` and `see(app="UserNotificationCenter")` both fall back to VS Code.

**Impact:** Any installation or first-run flow that triggers macOS security prompts requires human intervention.

### 2. `see(app=)` Almost Never Works via MCP
**Severity: Critical**

Every `see(app="X")` call returned VS Code's tree regardless of what app was targeted:
- `see(app="Docker")` → VS Code
- `see(app="Docker Desktop")` → VS Code
- `see(app="NotificationCenter")` → VS Code
- `see(app="UserNotificationCenter")` → VS Code

Only `see(app=<numeric_PID>)` partially worked (returned Docker's 4 window-frame elements).

**Root cause:** Known MCP server PID resolution bug — string app names don't resolve correctly through FastMCP parameter chain.

### 3. Docker Desktop Electron Tree Is Empty
**Severity: High**

`com.docker.docker` is not in `_ELECTRON_BUNDLE_IDS` (access.py:90). Even after manually enabling `AXManualAccessibility` with error=0, only 4 elements showed — the window frame. Content tree never populated.

Docker Desktop uses a **nested Electron app**: `/Applications/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/Frameworks/Electron Framework.framework`

Current Electron detection only checks top-level bundle IDs. Nested architectures may need different handling.

### 4. Coordinate Clicking Is Blind and Error-Prone
**Severity: High**

Without an accessibility tree, the only option is coordinate-based clicking. This is a terrible UX loop:
1. Take screenshot (`screencapture -x`)
2. Read image to visually estimate button position
3. Calculate coordinates from window position + size (AppleScript)
4. Click coordinates
5. Take another screenshot to verify
6. Repeat if missed

**Actual results:**
- Accept button: ~6 attempts over multiple coordinate guesses
- Finish button: **never found** in 20+ attempts
- Accidentally clicked "Use advanced settings" instead — changed dialog state unexpectedly
- No way to verify what was clicked without another screenshot cycle

### 5. `see(screenshot=True)` Exceeds MCP Token Limits
**Severity: Medium**

`see(screenshot=True)` returned 146,405 characters — exceeds MCP max tokens. Result was dumped to a temp file that's impractical to process.

**Workaround that worked:** `screencapture -x /tmp/x.png` + Read tool (which renders the image natively).

### 6. Keyboard Navigation Unreliable in Electron
**Severity: Medium**

- `press Return` had zero effect on Docker Desktop buttons
- `Tab` navigation was inconsistent — sometimes reached elements, sometimes didn't
- Tab+Enter eventually triggered the password flow, but it was accidental (a "happy accident" as noted)

### 7. No Feedback Loop for Blind Actions
**Severity: High**

When Nexus can't see elements, there's no way to know:
- What was clicked
- Whether the click hit a target
- What changed on screen after the action

The `do()` verification reports "Changes (0 new, 0 gone, 0 modified)" because it's comparing VS Code's tree, not Docker's.

## What Worked

| What | Why |
|------|-----|
| `brew install --cask` | CLI install — no GUI needed |
| `echo pw \| sudo -S` | Bypassed TTY requirement for sudo |
| `screencapture -x` + Read tool | Reliable visual feedback when Nexus was blind |
| AppleScript `get position/size of window` | Gave coordinates for estimation |
| AppleScript `tell app to activate` | Reliably brought Docker to front |
| `pyautogui.typewrite()` | Successfully typed password into system dialog |
| `osascript` process listing | Found Docker's PID and process info |

## Recommendations for Nexus

### Priority 1: Fix `see(app=)` Resolution
The string-to-PID resolution in server.py is the single biggest blocker. If this worked, most of the coordinate-guessing nightmare would have been avoided for normal apps.

### Priority 2: System Dialog Detection
Options:
- Poll `CoreServicesUIAgent` for windows on every `see()` call
- Use `screencapture` + OCR as a fallback perception layer
- Monitor `NSDistributedNotificationCenter` for system dialog events
- AppleScript: `tell process "CoreServicesUIAgent" to get every window` (returned empty in testing, but worth investigating with proper permissions)

### Priority 3: Screenshot Size for MCP
- Reduce JPEG quality (currently too high?)
- Resize to max 1280px width before base64 encoding
- Or: return a file path instead of inline base64

### Priority 4: Nested Electron App Support
- Add `com.docker.docker` to `_ELECTRON_BUNDLE_IDS`
- Investigate why AXManualAccessibility doesn't unlock the tree for Docker Desktop
- May need to target the inner `Docker Desktop.app` PID specifically (the renderer process?)

### Priority 5: Coordinate-Click Feedback
After any blind coordinate click:
- Auto-capture a small screenshot region around the click point
- Compare before/after to detect visual change
- Report what pixel colors changed (crude but better than nothing)

## Summary

Nexus handled the CLI portion flawlessly. The moment we entered GUI territory — especially system dialogs and an Electron app — it was effectively blind. The human had to intervene for 3 out of ~8 GUI steps. The remaining GUI steps were solved through brute-force coordinate clicking with a 30%+ miss rate.

**Bottom line:** Nexus needs to solve the `see(app=)` bug and system dialog blindness before it can handle installation workflows autonomously.
