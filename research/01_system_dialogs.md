# Research: Detecting and Interacting with macOS System Dialogs

**Date:** 2026-02-24
**Context:** Nexus is blind to system dialogs (Gatekeeper, SecurityAgent, network permission, etc.). This document covers every known technique for detecting and interacting with them.

---

## Table of Contents

1. [CoreServicesUIAgent](#1-coreservicesuiagent)
2. [SecurityAgent](#2-securityagent)
3. [UserNotificationCenter](#3-usernotificationcenter)
4. [CGWindowListCopyWindowInfo](#4-cgwindowlistcopywindowinfo)
5. [NSDistributedNotificationCenter](#5-nsdistributednotificationcenter)
6. [NSWorkspace Notifications](#6-nsworkspace-notifications)
7. [TCC / tccutil / Programmatic Permissions](#7-tcc--tccutil--programmatic-permissions)
8. [AppleScript GUI Scripting of System Processes](#8-applescript-gui-scripting-of-system-processes)
9. [Private APIs (SkyLight, CGSPrivate)](#9-private-apis-skylight-cgsprivate)
10. [MDM / PPPC Profiles](#10-mdm--pppc-profiles)
11. [spctl and Gatekeeper CLI Management](#11-spctl-and-gatekeeper-cli-management)
12. [xattr Quarantine Removal](#12-xattr-quarantine-removal)
13. [Screenshot + OCR Fallback](#13-screenshot--ocr-fallback)
14. [Existing Tools and Projects](#14-existing-tools-and-projects)
15. [Recommended Strategy for Nexus](#15-recommended-strategy-for-nexus)

---

## 1. CoreServicesUIAgent

### What It Is

CoreServicesUIAgent is a macOS launch agent located at `/System/Library/CoreServices/CoreServicesUIAgent.app`. It runs as the logged-in user and is responsible for displaying GUI dialogs when various system frameworks need user input. It is the primary process behind **Gatekeeper dialogs** (app verification, "are you sure you want to open this?", quarantine warnings).

### Internals (from Reverse Engineering)

Based on Scott Knight's reverse engineering analysis:

**Core Classes:**
- `CSUIController` (app delegate) -- initializes dispatch queue `com.apple.coreservices.uiagent.active-handler-queue`
- `CSUICodeEvaluationController` -- handles code evaluation service
- `CSUIMessageHandler` -- base class for all message handlers

**XPC Services:**

1. **`com.apple.coreservices.quarantine-resolver`** (C-based XPC):
   - `CSUIQuarantineMessageHandler` (cmd 0x1) -- delegates to `GKQuarantineResolver`, calls `XProtectAnalysis` for malware scanning
   - `CSUILaunchErrorHandler` (cmd 0x2) -- error dialogs for failed app launches
   - `CSUILSOpenHandler` (cmd 0x3) -- sandboxed app launch (callable by AppStore, iMessage, assistantd)
   - `CSUICheckAccessHandler` (cmd 0x5) -- file access checks via `access()` syscall
   - `CSUIGetDisplayNameHandler` (cmd 0x7) -- localized app name retrieval
   - `CSUIChangeDefaultHandlerHandler` (cmd 0x8) -- document handler prompts
   - `CSUIRecommendSafariHandler` (cmd 0x9) -- browser default handler dialogs

2. **`com.apple.coreservices.code-evaluation`** (NSXPCListener):
   - `presentPromptOfType:options:info:identifier:` -- dialog presentation
   - `updateQuarantineFlagsForInfo:setFlags:clearFlags:reply:` -- quarantine flag updates
   - `startProgressForInfo:`, `updateProgressForInfo:`, `closeProgressForInfo:` -- progress dialogs (the "Verifying..." bar)
   - `moveItemToTrashForInfo:`, `ejectVolumeForInfo:` -- file operations
   - `showOriginForInfo:`, `showSecurityPreferencesAnchor:` -- origin/settings display

**Security Validation:**
- Checks `xpc_connection_get_audit_token` to validate euid and asid match logged-in user
- Optional entitlement: `com.apple.private.coreservicesuiagent.allowedtouseCSUIFromOutsideSession`
- Sandboxed process validation using `sandbox_check_by_audit_token`

### Can Its Windows Be Detected?

**YES, via CGWindowListCopyWindowInfo.** CoreServicesUIAgent windows appear in the window list with `kCGWindowOwnerName = "CoreServicesUIAgent"`. This is the primary detection mechanism. See Section 4.

**Accessibility tree: UNCERTAIN.** There is no documented evidence that AXUIElementCreateApplication with CoreServicesUIAgent's PID yields a usable accessibility tree. Based on field testing, the AX tree for system processes is either empty or inaccessible. The process may not implement standard AX attributes.

### References

- [CoreServicesUIAgent internals -- Scott Knight](https://knight.sc/reverse%20engineering/2019/12/24/coreservicesuiagent-internals.html)
- [Gatekeeper CoreServicesUIAgent Analysis -- Abdulrahman Al-Hakami](https://alhakami16.medium.com/macos-coreservicesuiagent-analysis-53f4dc8d424c)

---

## 2. SecurityAgent

### What It Is

SecurityAgent is a separate system process (`/System/Library/Frameworks/Security.framework/Versions/A/MachServices/SecurityAgent.bundle`) that handles secure authentication prompts. It appears when:
- An app requests admin privileges (Authorization Services)
- Keychain access requires user confirmation
- System Preferences requires authentication ("click the lock to make changes")
- Touch ID / password prompts for privilege escalation

### Security Model

The Security Server is a Core Services daemon that handles authorization and authentication. SecurityAgent is its user-facing UI agent. **The Security Server has no public API** -- apps interact via Authorization Services, Keychain Services, etc., which internally communicate with SecurityAgent.

### Accessibility Tree Access

**Partially accessible, but unreliable.** Based on MacScripter forum reports:

**Known UI hierarchy (when accessible):**
```
SecurityAgent (Application)
  - Untitled (standard window)
    - AXGroup
      - AXTextField (username field)
      - AXSecureTextField (password field)
      - AXButton "OK" / "Allow" / "Unlock" / "Always Allow"
      - AXButton "Cancel" / "Deny"
```

**Critical reliability issues:**
- On macOS High Sierra+, `get window 1` intermittently returns "Invalid index" error
- `get every UI element of process "SecurityAgent"` sometimes returns empty lists
- Setting `frontmost` property often fails to properly activate windows
- Scripts triggered from Terminal/osascript have reduced GUI scripting capability
- Window becomes accessible only after user interaction in some cases

**Root cause assessment from forums:** Either deliberate security restrictions or WindowServer bugs affecting UI element registration. The behavior worsened significantly starting with macOS Mojave.

### References

- [GUI scripting SecurityAgent on macOS High Sierra -- MacScripter](https://www.macscripter.net/t/gui-scripting-securityagent-on-macos-high-sierra/71004)
- [SecurityAgent GUI hierarchy captured sporadically -- MacScripter](https://macscripter.net/viewtopic.php?id=48071)
- [SecurityAgent focus issue -- MacScripter](https://www.macscripter.net/t/security-agent-is-going-out-of-focus-when-triggering-apple-script-via-terminal/75804)
- [Security Server and Security Agent -- Apple Developer Archive](https://developer.apple.com/library/archive/documentation/Security/Conceptual/Security_Overview/Architecture/Architecture.html)

---

## 3. UserNotificationCenter

### What It Is

`com.apple.UserNotificationCenter` is a system process that handles permission dialogs when applications request access to resources like Documents, Downloads, or other protected folders. It is separate from both CoreServicesUIAgent and SecurityAgent.

### Known Issues

UserNotificationCenter dialogs are sometimes **unresponsive to clicks** -- a known macOS bug. Users report needing to `killall UserNotificationCenter` to dismiss stuck dialogs.

### Detection

Like CoreServicesUIAgent, its windows should appear in `CGWindowListCopyWindowInfo` output with `kCGWindowOwnerName = "UserNotificationCenter"`.

### References

- [macOS Monterey dialog bug -- Apple Community](https://discussions.apple.com/thread/253971041)
- [UserNotificationCenter not clickable -- Apple Community](https://discussions.apple.com/thread/254910503)

---

## 4. CGWindowListCopyWindowInfo

### Overview

This is the **most promising detection mechanism** for system dialogs. It is a public CoreGraphics API that enumerates ALL windows in the current user session, including those from system processes.

### API Details

```python
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionAll,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListExcludeDesktopElements,
    kCGNullWindowID
)

# Get ALL windows (including off-screen, system windows)
windows = CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID)

# Get only on-screen windows
windows = CGWindowListCopyWindowInfo(
    kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
    kCGNullWindowID
)
```

### Window Dictionary Keys

Each window is a dictionary with these keys:

| Key | Type | Description |
|-----|------|-------------|
| `kCGWindowOwnerName` | string | Process name (e.g., "CoreServicesUIAgent", "SecurityAgent") |
| `kCGWindowOwnerPID` | int | Process ID |
| `kCGWindowNumber` | int | Window ID |
| `kCGWindowName` | string | Window title (may be empty or absent for system dialogs) |
| `kCGWindowBounds` | dict | `{X, Y, Width, Height}` in screen coordinates |
| `kCGWindowLayer` | int | Window stacking level (see below) |
| `kCGWindowAlpha` | float | Transparency (0.0-1.0) |
| `kCGWindowIsOnscreen` | bool | Whether currently visible |
| `kCGWindowMemoryUsage` | int | Memory footprint |

### Window Layer Levels

System dialogs typically appear at elevated window levels:

| Level | Numeric Value | Description |
|-------|--------------|-------------|
| `kCGNormalWindowLevelKey` | 0 | Normal app windows |
| `kCGFloatingWindowLevelKey` | 3 | Floating panels |
| `kCGModalPanelWindowLevelKey` | 8 | Modal panels |
| `kCGDockWindowLevelKey` | 10 | Dock windows |
| `kCGUtilityWindowLevelKey` | 19 | Utility windows |
| `kCGMainMenuWindowLevelKey` | 20 | Menu bar |
| `kCGStatusWindowLevelKey` | 21 | Status bar items |
| `kCGPopUpMenuWindowLevelKey` | 101 | Popup menus |
| `kCGOverlayWindowLevelKey` | 102 | Overlays |
| `kCGDraggingWindowLevelKey` | 500 | Drag operations |
| `kCGScreenSaverWindowLevelKey` | 1000 | Screen saver |

System dialogs (Gatekeeper, SecurityAgent) likely appear at `kCGModalPanelWindowLevelKey` (8) or higher.

### Detection Strategy for Nexus

```python
SYSTEM_DIALOG_PROCESSES = {
    "CoreServicesUIAgent",   # Gatekeeper, quarantine, app verification
    "SecurityAgent",          # Password prompts, keychain access
    "UserNotificationCenter", # Folder access permission dialogs
    "TCCd",                   # TCC permission prompts (maybe)
    "authorizationhost",      # Authorization dialogs (maybe)
}

def detect_system_dialogs():
    """Poll CGWindowListCopyWindowInfo to find system dialog windows."""
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

    windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    dialogs = []
    for w in windows:
        owner = w.get('kCGWindowOwnerName', '')
        if owner in SYSTEM_DIALOG_PROCESSES:
            bounds = w.get('kCGWindowBounds', {})
            dialogs.append({
                'process': owner,
                'pid': w.get('kCGWindowOwnerPID'),
                'title': w.get('kCGWindowName', ''),
                'bounds': bounds,
                'layer': w.get('kCGWindowLayer', 0),
                'on_screen': w.get('kCGWindowIsOnscreen', False),
            })
    return dialogs
```

### References

- [CGWindowListCopyWindowInfo -- Apple Developer Documentation](https://developer.apple.com/documentation/coregraphics/1455137-cgwindowlistcopywindowinfo)
- [Python Examples of Quartz.CGWindowListCopyWindowInfo](https://www.programcreek.com/python/example/113139/Quartz.CGWindowListCopyWindowInfo)
- [PyGetWindow macOS implementation](https://github.com/asweigart/PyGetWindow/blob/master/src/pygetwindow/_pygetwindow_macos.py)
- [CGWindowLevel.h header](https://gist.github.com/rismay/ab10e87dc10a76c25986d52c65441bf2)
- [mac_list_windows_pids](https://github.com/sjitech/mac_list_windows_pids)

---

## 5. NSDistributedNotificationCenter

### Overview

NSDistributedNotificationCenter broadcasts notifications across process boundaries. It could theoretically be used to detect when system dialogs appear if Apple posts notifications for those events.

### Observing All Notifications

Prior to macOS Catalina, you could observe ALL distributed notifications:
```objc
[[NSDistributedNotificationCenter defaultCenter]
    addObserver:self
    selector:@selector(handleNotification:)
    name:nil  // nil = observe everything
    object:nil];
```

**IMPORTANT LIMITATION (Catalina+):** Apple restricted nil-name observation as a privileged operation. Applications using nil-name will stop receiving notifications on Catalina and later. You must now specify exact notification names.

### Known System Notifications

There is no documented notification for "system dialog appeared." However, potentially useful notifications include:
- `NSWorkspaceDidActivateApplicationNotification` -- when an app gains focus
- `com.apple.accessibility.api` -- accessibility state changes
- Various `com.apple.*` notifications (undocumented, may change)

### Practical Tool: notifyi

The [notifyi](https://github.com/melomac/notifyi) project is a command-line tool that logs distributed notifications. It could be used to **discover** what notifications (if any) are posted when system dialogs appear, by running it while triggering Gatekeeper or SecurityAgent dialogs.

### Verdict

**Not a reliable detection mechanism.** No known notifications are fired specifically for system dialog appearances. The nil-name observation restriction on Catalina+ makes broad snooping impractical.

### References

- [DistributedNotificationCenter -- Apple Developer Documentation](https://developer.apple.com/documentation/foundation/distributednotificationcenter)
- [NSDistributedNotificationCenter -- CocoaDev](https://cocoadev.github.io/NSDistributedNotificationCenter/)
- [notifyi -- NSDistributedNotification logger](https://github.com/melomac/notifyi)
- [NSDistributedNotificationCenter no longer supports nil names -- Michael Tsai](https://mjtsai.com/blog/2019/10/04/nsdistributednotificationcenter-no-longer-supports-nil-names/)

---

## 6. NSWorkspace Notifications

### didActivateApplicationNotification

Posted when an application becomes frontmost. Could detect SecurityAgent or CoreServicesUIAgent gaining focus:

```python
# Conceptual -- would need to be run in a Cocoa event loop
NSWorkspace.shared.notificationCenter.addObserver(
    ...,
    name: NSWorkspace.didActivateApplicationNotification,
    ...
)
# userInfo contains the activated app's bundleIdentifier and processIdentifier
```

**Limitation:** Background apps and menu bar apps don't trigger this notification until they have their own window. System dialog processes may or may not trigger it.

### frontmostApplication

`NSWorkspace.shared.frontmostApplication` returns the current frontmost app. Polling this could detect when SecurityAgent or CoreServicesUIAgent takes focus.

### References

- [didActivateApplicationNotification -- Apple Developer Documentation](https://developer.apple.com/documentation/appkit/nsworkspace/didactivateapplicationnotification)
- [frontmostApplication -- Apple Developer Documentation](https://developer.apple.com/documentation/appkit/nsworkspace/frontmostapplication)

---

## 7. TCC / tccutil / Programmatic Permissions

### TCC Database Locations

| Database | Path | Protection |
|----------|------|------------|
| User-level | `~/Library/Application Support/com.apple.TCC/TCC.db` | TCC-protected (FDA required to write) |
| System-wide | `/Library/Application Support/com.apple.TCC/TCC.db` | SIP-protected |

### Database Schema (access table)

| Field | Description |
|-------|-------------|
| `service` | Permission type (e.g., `kTCCServiceAccessibility`, `kTCCServiceSystemPolicyAllFiles`) |
| `client` | Bundle ID or absolute binary path |
| `client_type` | 0 = Bundle ID, 1 = absolute path |
| `auth_value` | 0 = denied, 1 = unknown, 2 = allowed, 3 = limited |
| `auth_reason` | Source: User Consent, System Set, MDM Policy, etc. |
| `csreq` | Code signature requirements (BLOB) |
| `last_modified` | Timestamp |

### Key TCC Services

| Service | Description |
|---------|-------------|
| `kTCCServiceAccessibility` | Accessibility control |
| `kTCCServiceAppleEvents` | Automation/Apple Events |
| `kTCCServiceSystemPolicyAllFiles` | Full Disk Access |
| `kTCCServiceScreenCapture` | Screen recording |
| `kTCCServiceCamera` | Camera |
| `kTCCServiceMicrophone` | Microphone |
| `kTCCServiceDeveloperTool` | Run unsigned software |
| `kTCCServicePostEvent` | Keyboard/mouse event posting |

### Querying TCC

```bash
# List all granted permissions (requires Terminal to have FDA)
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db \
  'SELECT service, client, auth_value FROM access WHERE auth_value=2'

# Check accessibility grants
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db \
  'SELECT client FROM access WHERE service="kTCCServiceAccessibility" AND auth_value=2'
```

### Can Permissions Be Pre-Granted?

**No -- not through supported means.** The entire point of TCC is user consent. However:

1. **MDM/PPPC profiles** can pre-grant most permissions (see Section 10)
2. **Direct database writes** are possible but require:
   - Disabling SIP for system database
   - Having FDA for user database
   - Computing correct `csreq` blobs via `codesign`
   - This is unsupported and may break with OS updates

3. **tccutil** (Apple's tool) only supports `reset`:
   ```bash
   tccutil reset Accessibility com.example.app
   tccutil reset All  # Nuclear option -- resets EVERYTHING
   ```

4. **Third-party tccutil.py** ([jacobsalmela/tccutil](https://github.com/jacobsalmela/tccutil)) supports insert/enable/disable operations on the user database.

### Privilege Escalation Vectors (for awareness)

- `kTCCServiceAppleEvents` over Finder => abuse Finder's FDA
- `kTCCServiceAccessibility` => keystroke injection to manipulate System Settings
- `kTCCServiceEndpointSecurityClient` => equivalent to FDA

### References

- [macOS TCC -- HackTricks](https://book.hacktricks.wiki/en/macos-hardening/macos-security-and-privilege-escalation/macos-security-protections/macos-tcc/index.html)
- [tccutil.py -- GitHub](https://github.com/jacobsalmela/tccutil)
- [How to modify TCC on macOS -- Entonos](https://entonos.com/2023/06/23/how-to-modify-tcc-on-macos/)
- [Resetting TCC -- Michael Tsai](https://mjtsai.com/blog/2023/02/09/resetting-tcc/)
- [Working Around macOS Privacy Controls -- Cedric Owens](https://cedowens.medium.com/initial-access-checks-on-macos-531dd2d0cee6)

---

## 8. AppleScript GUI Scripting of System Processes

### SecurityAgent

**Partially works, unreliably.** Example code:

```applescript
tell application "System Events"
    tell process "SecurityAgent"
        set frontmost to true
        delay 0.5
        set value of text field 1 of window 1 to "password"
        click button "Allow" of window 1
    end tell
end tell
```

**Known issues on modern macOS (Mojave+):**
- `get window 1` returns "Invalid index" intermittently
- `get every UI element` returns empty lists
- Scripts from osascript/Terminal have reduced GUI scripting capability
- SecurityAgent goes out of focus when triggered from shell scripts
- Window accessibility registration is sporadic

### CoreServicesUIAgent

**Theoretically addressable** via the same pattern:

```applescript
tell application "System Events"
    tell process "CoreServicesUIAgent"
        -- Enumerate elements
        get every UI element of window 1
        -- Click a button
        click button "Open" of window 1
    end tell
end tell
```

**No confirmed working examples found** in any forum or repository. The process name may not be recognized by System Events, or its windows may not expose AX elements.

### Limitations of osascript

A critical finding from MacScripter: **"osascript cannot execute GUI Scripting that forcibly manipulates menus"** when called from shell scripts. The execution environment has reduced GUI scripting capabilities compared to Script Editor.

### References

- [Mac Automation Scripting Guide -- Apple Developer](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/AutomatetheUserInterface.html)
- [AppleScript GUI Scripting -- macosxautomation.com](https://www.macosxautomation.com/applescript/uiscripting/)
- [GUI Scripting with AppleScript -- Sudoade](https://www.sudoade.com/gui-scripting-with-applescript/)

---

## 9. Private APIs (SkyLight, CGSPrivate)

### SkyLight Framework

Located at `/System/Library/PrivateFrameworks/SkyLight.framework/`. It is the client-side IPC interface for communicating with WindowServer via mach messages.

**Key characteristics:**
- Every application has its own WindowServer connection used for authorization
- Not all functions check `connection_holds_rights_on_window` -- some are callable without special privileges
- Dock.app has a "universal owner" connection that can modify ANY window
- yabai uses SkyLight by injecting into Dock.app (requires partial SIP disable)

**Potentially useful for Nexus:** SkyLight could theoretically access system window properties not exposed by CGWindowListCopyWindowInfo. However, most useful functions are protected by the connection authorization check.

### CGSPrivate Functions

From the [CGSPrivate.h header](https://gist.github.com/rjw57/5495406):

**Window Listing:**
- `CGSGetWindowCount(connection)` -- count windows for a connection
- `CGSGetWindowList(connection, count, list, countReturned)` -- get window IDs
- `CGSGetOnScreenWindowCount(connection)` -- count visible windows
- `CGSGetOnScreenWindowList(connection, count, list, countReturned)` -- list visible windows

**Window Properties:**
- `CGSGetWindowOwner(connection, windowID, ownerConnection)` -- get owning connection
- `CGSConnectionGetPID(connection, pid)` -- get PID from connection
- `CGSGetScreenRectForWindow(connection, windowID, rect)` -- get window bounds
- `CGSGetWindowLevel(connection, windowID, level)` -- get stacking level
- `CGSGetWindowAlpha(connection, windowID, alpha)` -- get transparency
- `CGSGetWindowProperty(connection, windowID, key, value)` -- arbitrary properties

**Window Manipulation:**
- `CGSMoveWindow(connection, windowID, point)` -- move window
- `CGSSetWindowAlpha(connection, windowID, alpha)` -- set transparency
- `CGSOrderWindow(connection, windowID, order, relativeToWindow)` -- z-order

### Practical Limitations

- These are **private, undocumented APIs** that can break with any macOS update
- The "connection authorization" model means you can only modify your own windows unless injecting into Dock.app
- **For detection only (read-only)**, some functions may work without special authorization
- The public `CGWindowListCopyWindowInfo` provides most of the same information for detection purposes

### Discovery Tools

- [macOS_headers dump](https://github.com/w0lfschild/macOS_headers) -- consistently maintained dump of most macOS headers
- [Exploring macOS private frameworks](https://www.jviotti.com/2023/11/20/exploring-macos-private-frameworks.html) -- technique guide
- `otool -L` to discover which private frameworks a binary links
- `RuntimeBrowser` and `Hopper Disassembler` for reverse engineering

### References

- [CGSPrivate.h gist](https://gist.github.com/rjw57/5495406)
- [SkyLightWindow -- display UI on lock screen](https://github.com/Lakr233/SkyLightWindow)
- [WindowServer -- The Eclectic Light Company](https://eclecticlight.co/2020/06/08/windowserver-display-compositor-and-input-event-router/)
- [yabai SIP discussion](https://github.com/koekeishiya/yabai/discussions/2274)
- [Unpacking SkyLight.framework -- Oreate AI](https://www.oreateai.com/blog/unpacking-macoss-skylightframework-more-than-just-a-pretty-name/0e154176ccd9239bd82add7a5e9910c1)

---

## 10. MDM / PPPC Profiles

### What PPPC Can Do

Privacy Preferences Policy Control (PPPC) profiles use the payload identifier `com.apple.TCC.configuration-profile-policy` and can pre-grant permissions to applications **without user interaction**.

### Grantable Permissions via MDM

| Permission | Can Grant | Can Deny |
|------------|----------|----------|
| Accessibility | Yes | Yes |
| AppleEvents/Automation | Yes | Yes |
| Full Disk Access | Yes | Yes |
| Address Book | Yes | Yes |
| Calendar | Yes | Yes |
| Photos | Yes | Yes |
| **Camera** | **No** (user-only) | Yes |
| **Microphone** | **No** (user-only) | Yes |
| **Screen Recording** | **No** (user-only) | Yes |

### Requirements

- Must be deployed through **User-approved MDM** (device must be MDM-enrolled)
- Requires computing code signing requirements for target apps
- Profile needs the app's Bundle ID and code signing identity

### Tools

- [PPPC-Utility by Jamf](https://github.com/jamf/PPPC-Utility) -- GUI tool for creating PPPC profiles
- SimpleMDM, Hexnode, ManageEngine, Meraki all support PPPC deployment

### Applicability to Nexus

**Limited for individual developers.** MDM enrollment is an enterprise feature. However, for a managed deployment scenario (e.g., deploying Nexus across a fleet of Macs), PPPC profiles could pre-approve accessibility and automation permissions to eliminate TCC dialogs entirely.

### Self-Signed Profiles

Configuration profiles can be manually installed without MDM, but:
- macOS will prompt the user to approve them in System Settings
- They cannot grant TCC permissions without being deployed through MDM
- They CAN configure Gatekeeper settings (allow identified developers, etc.)

### References

- [PPPC payload settings -- Apple Support](https://support.apple.com/guide/deployment/privacy-preferences-policy-control-payload-dep38df53c2a/web)
- [PrivacyPreferencesPolicyControl -- Apple Developer](https://developer.apple.com/documentation/devicemanagement/privacypreferencespolicycontrol)
- [Creating PPPC profiles -- Der Flounder](https://derflounder.wordpress.com/2018/08/31/creating-privacy-preferences-policy-control-profiles-for-macos/)
- [PPPC-Utility -- Jamf GitHub](https://github.com/jamf/PPPC-Utility)
- [Understanding PPPC -- dataJAR](https://datajar.co.uk/understanding-privacy-preference-policy-controls/)
- [SimpleMDM PPPC guide](https://simplemdm.com/blog/how-to-configure-simplemdm-privacy-preferences-profile/)

---

## 11. spctl and Gatekeeper CLI Management

### Available Commands

```bash
# Check if an app is approved
spctl -a /Applications/SomeApp.app
spctl --assess --verbose /Applications/SomeApp.app

# Add an app to the approval list (with label for group management)
spctl --add --label "Approved" /Applications/SomeApp.app

# Remove approval
spctl --remove --label "Approved"

# Enable/disable all apps under a label
spctl --enable --label "Approved"
spctl --disable --label "Approved"

# List all approval rules
spctl --list

# Global Gatekeeper control (requires sudo)
sudo spctl --master-disable  # Allow apps from anywhere
sudo spctl --master-enable   # Re-enable Gatekeeper
```

### CRITICAL: macOS Sequoia (15.x) Breaks This

**Starting with macOS Sequoia 15.3, `spctl --add` no longer works.** The only way to approve an unrecognized app is:
1. Attempt to run the app (it will be blocked)
2. Go to System Settings > Privacy & Security
3. Scroll down to the Security section
4. Click "Open Anyway" next to the blocked app

**`spctl --master-disable` still works** to reveal the "Allow apps from Anywhere" option in System Settings on Sequoia, but it no longer auto-approves.

### Pre-Sequoia Workflow

For macOS < 15.3, the full workflow to pre-approve an app:
```bash
# Remove quarantine attribute
xattr -d com.apple.quarantine /Applications/SomeApp.app

# Add to Gatekeeper approval list
spctl --add --label "MyApps" /Applications/SomeApp.app

# Verify
spctl --assess --verbose /Applications/SomeApp.app
```

### References

- [Managing Gatekeeper -- HeelpBook](https://www.heelpbook.net/2020/macos-x-managing-gatekeeper-terminal/)
- [Managing Gatekeeper from CLI -- Sam Merrell](https://www.merrell.dev/notes/20200807-managing-app-permissions-in-gatekeeper-from-the-command-line-on-macos/)
- [Gatekeeper bypass -- GitHub gist](https://gist.github.com/kennwhite/814ff7ed1fd62b921144035c877c3e4c)
- [Sequoia removes Gatekeeper override -- Michael Tsai](https://mjtsai.com/blog/2024/07/05/sequoia-removes-gatekeeper-contextual-menu-override/)
- [Disable Gatekeeper on Catalina](https://disable-gatekeeper.github.io/)
- [Gatekeeper -- Wikipedia](https://en.wikipedia.org/wiki/Gatekeeper_(macOS))

---

## 12. xattr Quarantine Removal

### The Quarantine Attribute

When a file is downloaded from the internet, macOS adds the `com.apple.quarantine` extended attribute. This is what triggers Gatekeeper verification.

### Removing It

```bash
# Remove from a single app
xattr -d com.apple.quarantine /Applications/SomeApp.app

# Remove recursively (for app bundles with nested binaries)
xattr -r -d com.apple.quarantine /Applications/SomeApp.app

# Check if the attribute exists
xattr -l /Applications/SomeApp.app | grep quarantine
```

### When This Helps

- Removes the "app downloaded from internet" Gatekeeper dialog entirely
- The app will launch as if it were locally created
- **Must be done BEFORE first launch** to prevent the dialog
- Does NOT bypass code signature verification -- only the quarantine check

### When This Doesn't Help

- Network permission dialogs ("find devices on local network")
- TCC permission dialogs (accessibility, camera, etc.)
- SecurityAgent password prompts
- Any dialog not related to Gatekeeper quarantine

### References

- [Clearing quarantine attribute -- Der Flounder](https://derflounder.wordpress.com/2012/11/20/clearing-the-quarantine-extended-attribute-from-downloaded-applications/)
- [macOS security and quarantine -- ISSCloud](https://www.isscloud.io/guides/macos-security-and-com-apple-quarantine-extended-attribute/)
- [Gatekeeping in macOS -- Red Canary](https://redcanary.com/blog/threat-detection/gatekeeper/)

---

## 13. Screenshot + OCR Fallback

### The Approach

When accessibility APIs fail (no AX tree for system dialogs), the fallback strategy is:

1. **Detect** a system dialog via CGWindowListCopyWindowInfo (get bounds)
2. **Screenshot** just the dialog region using `screencapture` or Quartz APIs
3. **OCR** the screenshot to extract text and identify buttons
4. **Click** at computed coordinates using pyautogui

### Apple Vision Framework via PyObjC

The best OCR approach on macOS -- native, fast, no external dependencies:

```python
import Quartz
from Foundation import NSURL, NSRange
import Vision

def ocr_image(image_path):
    """OCR an image using Apple Vision framework. Returns [(text, confidence, rect), ...]"""
    input_url = NSURL.fileURLWithPath_(image_path)
    input_image = Quartz.CIImage.imageWithContentsOfURL_(input_url)

    results = []

    def handler(request, error):
        observations = request.results()
        for obs in observations:
            text = obs.topCandidates_(1)[0]
            box_range = NSRange(0, len(text.string()))
            box_obs = text.boundingBoxForRange_error_(box_range, None)
            bbox = box_obs[0].boundingBox()

            image_w = input_image.extent().size.width
            image_h = input_image.extent().size.height
            rect = Vision.VNImageRectForNormalizedRect(bbox, image_w, image_h)

            results.append((text.string(), text.confidence(), rect))

    request_handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(
        input_image, None
    )
    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
    request_handler.performRequests_error_([request], None)

    return results
```

**Performance:** ~130ms (fast mode) to ~207ms (accurate mode) on M3 Max.

### ocrmac Library

A ready-made Python wrapper:

```bash
pip install ocrmac
```

```python
from ocrmac import ocrmac
# Returns [(text, confidence, [x, y, w, h]), ...]
annotations = ocrmac.OCR('dialog_screenshot.png').recognize()
```

### Region Screenshot

```bash
# Capture a specific region (x, y, width, height)
screencapture -x -R 100,200,400,300 /tmp/dialog.png

# Or programmatically via Quartz
from Quartz import CGWindowListCreateImage, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, CGRectMake
region = CGRectMake(100, 200, 400, 300)
image = CGWindowListCreateImage(region, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, 0)
```

### Full Pipeline

```python
def handle_system_dialog():
    """Detect, screenshot, OCR, and click through a system dialog."""
    # 1. Detect dialog
    dialogs = detect_system_dialogs()  # from Section 4
    if not dialogs:
        return None

    dialog = dialogs[0]
    bounds = dialog['bounds']

    # 2. Screenshot the dialog region
    import subprocess
    region = f"{bounds['X']},{bounds['Y']},{bounds['Width']},{bounds['Height']}"
    subprocess.run(['screencapture', '-x', '-R', region, '/tmp/dialog.png'])

    # 3. OCR to find buttons
    from ocrmac import ocrmac
    texts = ocrmac.OCR('/tmp/dialog.png').recognize()

    # 4. Find "Open" / "Allow" / "OK" button
    for text, confidence, bbox in texts:
        if text.lower() in ('open', 'allow', 'ok', 'continue', 'accept'):
            # Convert bbox to screen coordinates
            btn_x = bounds['X'] + bbox[0] + bbox[2] / 2
            btn_y = bounds['Y'] + bbox[1] + bbox[3] / 2

            import pyautogui
            pyautogui.click(btn_x, btn_y)
            return text

    return None
```

### References

- [Apple Vision Framework via PyObjC -- Yasoob Khalid](https://yasoob.me/posts/how-to-use-vision-framework-via-pyobjc/)
- [ocrmac -- GitHub](https://github.com/straussmaximilian/ocrmac)
- [macos-vision-ocr -- GitHub](https://github.com/bytefer/macos-vision-ocr)
- [macOCR -- GitHub](https://github.com/schappim/macOCR)
- [VNRecognizeTextRequest -- Apple Developer](https://developer.apple.com/documentation/vision/vnrecognizetextrequest)

---

## 14. Existing Tools and Projects

### mac-commander (MCP Server)

[GitHub: ohqay/mac-commander](https://github.com/ohqay/mac-commander)

An MCP server for macOS automation that includes:
- **Multi-strategy detection engine** combining visual analysis, OCR, color patterns, shape detection
- Detects 20+ UI element types including buttons, dialogs, checkboxes
- OCR-based fallback using Tesseract.js when accessibility APIs fail
- Error dialog auto-detection
- Confidence scoring for element detection

### macos-control-mcp

[GitHub: PeterHdd/macos-control-mcp](https://github.com/PeterHdd/macos-control-mcp)

MCP server providing:
- OCR via Apple Vision framework (VNRecognizeTextRequest) with Python bridge
- Mouse control via Quartz Core Graphics events
- Keyboard/app interaction via AppleScript
- Returns text with bounding box coordinates

### vision (kxrm/vision)

[GitHub: kxrm/vision](https://github.com/kxrm/vision)

Vision-based automation tools for macOS:
- Screenshot capture for full screen, app windows, and regions with coordinate grids
- OCR-based interaction (click on text, find elements)
- Mouse/keyboard controls

### macos-automator-mcp

[GitHub: steipete/macos-automator-mcp](https://github.com/steipete/macos-automator-mcp)

MCP server to run AppleScript and JXA for macOS automation:
- UI scripting via System Events
- Requires Accessibility permissions

### Hammerspoon

[GitHub: Hammerspoon/hammerspoon](https://github.com/Hammerspoon/hammerspoon)

Lua-based macOS automation with:
- `hs.window.filter` -- detect window creation/destruction events
- `hs.axuielement` -- full AX tree access
- `hs.application.watcher` -- detect app activation/deactivation
- Could detect system dialogs via window filter subscriptions

### Keyboard Maestro

Commercial automation tool that can:
- Trigger macros when a window with specific title appears
- React to dialog windows with pause + detect pattern
- Simulate clicks and keystrokes

---

## 15. Recommended Strategy for Nexus

### Layer 1: Prevention (Eliminate Dialogs Before They Appear)

Before launching apps, proactively remove quarantine and pre-approve:

```python
def pre_approve_app(app_path):
    """Remove quarantine attribute to prevent Gatekeeper dialogs."""
    import subprocess
    # Remove quarantine
    subprocess.run(['xattr', '-r', '-d', 'com.apple.quarantine', app_path])
    # Add to Gatekeeper approval list (pre-Sequoia only)
    subprocess.run(['spctl', '--add', '--label', 'Nexus', app_path])
```

### Layer 2: Detection (CGWindowListCopyWindowInfo Polling)

Add a background poller in Nexus that checks for system dialog windows:

```python
import threading
import time
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

SYSTEM_DIALOG_PROCESSES = {
    "CoreServicesUIAgent",
    "SecurityAgent",
    "UserNotificationCenter",
}

def _poll_system_dialogs(callback, interval=0.5):
    """Background thread that polls for system dialog windows."""
    while True:
        windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for w in (windows or []):
            owner = w.get('kCGWindowOwnerName', '')
            if owner in SYSTEM_DIALOG_PROCESSES:
                bounds = w.get('kCGWindowBounds', {})
                if bounds.get('Width', 0) > 50 and bounds.get('Height', 0) > 50:
                    callback({
                        'process': owner,
                        'pid': w.get('kCGWindowOwnerPID'),
                        'title': w.get('kCGWindowName', ''),
                        'bounds': bounds,
                        'layer': w.get('kCGWindowLayer', 0),
                    })
        time.sleep(interval)
```

### Layer 3: Identification (Screenshot + OCR)

When a system dialog is detected, screenshot and OCR it:

1. Use `CGWindowListCreateImage` with the dialog's bounds to capture just that window
2. Run Apple Vision OCR to extract all text and button labels
3. Classify the dialog type (Gatekeeper, permission, password, etc.)
4. Report the dialog type, text content, and available buttons to the AI agent

### Layer 4: Interaction (Coordinate Click or AppleScript)

Depending on the dialog type:

**For CoreServicesUIAgent (Gatekeeper):**
- Try AppleScript first: `tell process "CoreServicesUIAgent"` to click buttons
- Fall back to coordinate clicking based on OCR bounding boxes

**For SecurityAgent (password prompts):**
- Try AppleScript: `tell process "SecurityAgent"` (unreliable on modern macOS)
- Fall back to coordinate clicking for buttons
- **Never auto-type passwords** -- present the dialog info to the user

**For UserNotificationCenter:**
- Try AppleScript approach
- Fall back to coordinate clicking

### Layer 5: Reporting (Surface to AI Agent)

Integrate into `see()` output:

```python
# In fusion.py's see() function:
def see(...):
    # ... existing code ...

    # Check for system dialogs
    system_dialogs = detect_system_dialogs()
    if system_dialogs:
        sections.append("\n-- System Dialogs Detected --")
        for d in system_dialogs:
            sections.append(f"  {d['process']}: {d['title'] or '(untitled)'}")
            sections.append(f"    Bounds: {d['bounds']}")
            sections.append(f"    Layer: {d['layer']}")
            # If OCR was performed:
            if 'ocr_text' in d:
                sections.append(f"    Text: {d['ocr_text']}")
                sections.append(f"    Buttons: {d['buttons']}")
```

### Implementation Priority

1. **CGWindowListCopyWindowInfo polling** -- highest value, lowest effort
2. **xattr quarantine removal** -- simple prevention
3. **Screenshot + OCR pipeline** -- medium effort, handles the blind spot
4. **AppleScript interaction** -- try it, but don't depend on it
5. **NSWorkspace notifications** -- supplementary detection
6. **Private APIs** -- avoid unless absolutely necessary

### What Will NOT Work

- Direct AX tree access to system processes (restricted/empty)
- Programmatic TCC grants without MDM
- `spctl --add` on macOS Sequoia 15.3+
- Distributed notification snooping (restricted on Catalina+)
- SkyLight/CGSPrivate for manipulating system windows (authorization required)

---

## Summary Table

| Technique | Detection | Interaction | Reliability | Effort |
|-----------|-----------|-------------|-------------|--------|
| CGWindowListCopyWindowInfo poll | Excellent | None | High | Low |
| Screenshot + OCR | Good | Via coordinates | Medium | Medium |
| AppleScript GUI scripting | N/A | Direct | Low (modern macOS) | Low |
| NSWorkspace notifications | Moderate | None | Medium | Low |
| xattr quarantine removal | Prevention | Prevention | High | Trivial |
| spctl approval | Prevention | Prevention | Broken on Sequoia | Trivial |
| MDM/PPPC profiles | Prevention | Prevention | High (if enrolled) | High |
| TCC.db direct writes | Prevention | Prevention | Fragile, requires SIP off | High |
| Private APIs | Advanced | Advanced | Fragile | Very High |
| NSDistributedNotificationCenter | Poor | None | Low | Low |
