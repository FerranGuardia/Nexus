---
name: system-dialogs
description: macOS system dialog detection, prevention, and workarounds
requires: []
---

# System Dialogs Skill

System dialogs (Gatekeeper, SecurityAgent, permission prompts) are **invisible to the accessibility tree**. They run in protected system processes. This skill teaches prevention and detection.

## Prevention (eliminate dialogs before they appear)

### Gatekeeper (app downloaded from internet)

```bash
# Remove quarantine attribute BEFORE first launch
xattr -r -d com.apple.quarantine /Applications/SomeApp.app

# Check if quarantine exists
xattr -l /Applications/SomeApp.app | grep quarantine

# Verify app is approved (pre-Sequoia only)
spctl --assess --verbose /Applications/SomeApp.app
```

**IMPORTANT (macOS Sequoia 15.3+):** `spctl --add` no longer works. The only way to approve an app is:
1. Try to open it (gets blocked)
2. System Settings > Privacy & Security > scroll to Security
3. Click "Open Anyway"

### TCC Permission Prompts (accessibility, camera, etc.)

These CANNOT be prevented programmatically. The user must grant them manually.

```bash
# Check what's already granted (needs Full Disk Access)
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db \
  'SELECT service, client FROM access WHERE auth_value=2'
```

Guide the user to: System Settings > Privacy & Security > [specific permission]

## Detection

### CGWindowListCopyWindowInfo (best method)

System dialogs appear as windows owned by specific processes:

| Process | Dialog Type |
|---------|------------|
| `CoreServicesUIAgent` | Gatekeeper (app verification, quarantine) |
| `SecurityAgent` | Password prompts, keychain access, admin auth |
| `UserNotificationCenter` | Folder access permission prompts |

Detection approach (Nexus Phase 2 will automate this):
```python
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
for w in windows:
    owner = w.get('kCGWindowOwnerName', '')
    if owner in ('CoreServicesUIAgent', 'SecurityAgent', 'UserNotificationCenter'):
        bounds = w.get('kCGWindowBounds', {})
        print(f"SYSTEM DIALOG: {owner} at {bounds}")
```

### Quick Check via Shell

```bash
# Check if any system dialog processes have visible windows
python3 -c "
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
for w in CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID):
    owner = w.get('kCGWindowOwnerName', '')
    if owner in ('CoreServicesUIAgent', 'SecurityAgent', 'UserNotificationCenter'):
        print(f'{owner}: {w.get(\"kCGWindowBounds\", {})}')
"
```

## Interaction Workarounds

### AppleScript (unreliable on modern macOS)

```bash
# Try clicking a button in CoreServicesUIAgent (may fail)
osascript -e '
tell application "System Events"
    tell process "CoreServicesUIAgent"
        click button "Open" of window 1
    end tell
end tell'

# Try SecurityAgent (often fails on Mojave+)
osascript -e '
tell application "System Events"
    tell process "SecurityAgent"
        set value of text field 1 of window 1 to "password"
        click button "OK" of window 1
    end tell
end tell'
```

### Keyboard Navigation (more reliable)

For password dialogs:
```
do("press tab")      # Move between fields
do("type password")  # Type into focused field (be careful!)
do("press enter")    # Confirm / OK
do("press escape")   # Cancel
```

For Gatekeeper dialogs:
```
do("press tab")      # Focus between Cancel / Open
do("press space")    # Activate focused button
```

### Coordinate Clicking (last resort)

If you know the dialog bounds from CGWindowListCopyWindowInfo:
```python
import pyautogui
# Gatekeeper "Open" button is typically at right-center of dialog
dialog_x = bounds['X'] + bounds['Width'] * 0.75
dialog_y = bounds['Y'] + bounds['Height'] * 0.85
pyautogui.click(dialog_x, dialog_y)
```

## Common Dialog Patterns

| Dialog | Trigger | Prevention | Buttons |
|--------|---------|-----------|---------|
| "app downloaded from internet" | First launch of downloaded app | `xattr -r -d com.apple.quarantine` | Open / Cancel |
| "wants to find devices on network" | App uses Bonjour/mDNS | None — user must decide | Allow / Don't Allow |
| Admin password prompt | Privileged operation | None | OK / Cancel + password field |
| Keychain access | App requests keychain item | None | Allow / Deny / Always Allow |
| Accessibility permission | App requests AX access | None — user grants in Settings | (redirects to Settings) |
| Full Disk Access | App requests FDA | None — user grants in Settings | (redirects to Settings) |

## Tips

- Always try `xattr` removal before launching downloaded apps
- SecurityAgent goes out of focus when triggered from scripts — unreliable
- `UserNotificationCenter` dialogs sometimes freeze — `killall UserNotificationCenter` unsticks them
- The best strategy: prevent what you can, detect what you can't prevent, tell the user what you can't handle
- Never auto-type passwords without explicit user instruction
