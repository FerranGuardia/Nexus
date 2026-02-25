# Electron Accessibility on macOS: Deep Research

Research date: February 24, 2026
Purpose: Understanding why some Electron apps have empty/minimal accessibility trees on macOS, and how to work around this for Nexus GUI automation.

---

## Table of Contents

1. [Chromium Accessibility Architecture](#1-chromium-accessibility-architecture)
2. [AXManualAccessibility: What It Does and Why It Fails](#2-axmanualaccessibility)
3. [AXEnhancedUserInterface vs AXManualAccessibility](#3-axenhanceduserinterface-vs-axmanualaccessibility)
4. [--force-renderer-accessibility Flag](#4---force-renderer-accessibility-flag)
5. [Electron's app.accessibilitySupportEnabled](#5-electrons-appaccessibilitysupportenabled)
6. [Why the Tree Can Be Empty After Enabling](#6-why-the-tree-can-be-empty-after-enabling)
7. [Nested Electron Apps (Docker Desktop Pattern)](#7-nested-electron-apps-docker-desktop-pattern)
8. [Docker Desktop Specifically](#8-docker-desktop-specifically)
9. [CDP for Electron Apps](#9-cdp-for-electron-apps)
10. [Alternative Approaches](#10-alternative-approaches)
11. [Known Issues and Limitations](#11-known-issues-and-limitations)
12. [Recommendations for Nexus](#12-recommendations-for-nexus)
13. [References](#13-references)

---

## 1. Chromium Accessibility Architecture

### The Pipeline: DOM -> AXNodeData -> Platform AX Tree -> AXUIElement

Chromium's accessibility is a multi-layer, multi-process system:

```
RENDERER PROCESS                          BROWSER PROCESS                    macOS
+------------------+                      +-------------------------+        +-------------+
| DOM Nodes        |                      | BrowserAccessibility-   |        | AXUIElement |
|   |              |   IPC (mojom)        |   ManagerMac            |        | (NSAccess-  |
|   v              |   push model         |   |                     |        |  ibility)   |
| Blink AXObject   | ---- AXNodeData ---> |   v                    |        |             |
|   |              |   (delta updates)    | BrowserAccessibility    | -----> | VoiceOver   |
|   v              |                      |   |                     |        | Nexus       |
| AXNodeObject     |                      |   v                    |        | Other AT    |
|   |              |                      | AXPlatformNode          |        |             |
|   v              |                      |   (gfx::NativeView-     |        |             |
| WebAXObject      |                      |    Accessible = id)     |        |             |
+------------------+                      +-------------------------+        +-------------+
```

**Key classes in the chain:**

1. **AXObject / AXNodeObject / AXLayoutObject** (Blink, renderer process): Internal accessibility tree paralleling the DOM. Not all DOM nodes map 1:1 -- some are synthetic.

2. **AXNodeData** (cross-platform): Sparse data structure with mandatory `id` and `role`, plus typed attribute arrays. This is the IPC payload.

3. **AXTreeSerializer**: Walks the tree and generates `AXTreeUpdate` deltas -- only changed nodes are serialized, not the full tree every time.

4. **IPC via `ax.mojom.RenderAccessibilityHost::HandleAXEvents()`**: Ships serialized delta-updates from renderer to browser process.

5. **BrowserAccessibilityManager** (browser process): Merges AXNodeData trees into `BrowserAccessibility` objects. Links trees from multiple frames/iframes.

6. **BrowserAccessibilityManagerMac**: macOS-specific subclass that dispatches events via `NotifyAccessibilityEvent`.

7. **AXPlatformNode** + **AXPlatformNodeDelegate**: Cross-platform abstraction. On macOS, `gfx::NativeViewAccessible` is typedef'd to `id` (generic Objective-C object implementing NSAccessibility).

### Push Model (Critical for Understanding Delays)

Chromium uses a **push model**, not pull. The renderer pushes the full tree on first enable, then incremental updates. The browser process caches the complete tree and serves all platform API queries from that cache. This is necessary because:

- All native accessibility APIs (NSAccessibility, MSAA, etc.) are **synchronous**
- Chromium's multi-process architecture prohibits synchronous IPC from browser to sandboxed renderer
- The renderer can only serialize when the document lifecycle is "clean" (after CSS resolution and layout)

**Implication for Nexus**: After enabling accessibility, there's an inherent delay while the renderer serializes the full tree and pushes it to the browser process via IPC. This explains the ~1-2 second delay we observe.

Sources:
- https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/overview.md
- https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/browser/how_a11y_works_2.md
- https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/browser/how_a11y_works_3.md

---

## 2. AXManualAccessibility

### What It Is

`AXManualAccessibility` is a **custom accessibility attribute** invented by the Electron project. It does NOT exist in vanilla Chromium/Chrome. It was created to solve a specific problem:

- Chromium only enables its accessibility tree when it detects VoiceOver via the `AXEnhancedUserInterface` attribute
- Setting `AXEnhancedUserInterface` has nasty side effects (breaks window positioning/animations)
- Other assistive technologies (not VoiceOver) had no way to trigger accessibility in Electron apps

The attribute was added in PR #10305 (2017) and lives in `shell/browser/mac/electron_application.mm`.

### How It Works

When an external tool sets `AXManualAccessibility` to `kCFBooleanTrue` on an Electron app's AXUIElement:

1. Electron's custom `ElectronApplication` class intercepts the `accessibilitySetValue:forAttribute:` call
2. It calls `app.setAccessibilitySupportEnabled(true)` internally
3. This triggers Chromium to start building the accessibility tree in the renderer
4. The renderer serializes and pushes the tree to the browser process
5. The tree becomes available via macOS AXUIElement queries

### Code to Enable (Objective-C)

```objc
#define kAXManualAccessibility @"AXManualAccessibility"
AXUIElementRef appRef = AXUIElementCreateApplication(pid);
CFBooleanRef value = enabled ? kCFBooleanTrue : kCFBooleanFalse;
AXError err = AXUIElementSetAttributeValue(appRef, (__bridge CFStringRef)kAXManualAccessibility, value);
```

### Code to Enable (Python/pyobjc -- what Nexus uses)

```python
from ApplicationServices import AXUIElementCreateApplication, AXUIElementSetAttributeValue
from CoreFoundation import kCFBooleanTrue

app_ref = AXUIElementCreateApplication(pid)
err = AXUIElementSetAttributeValue(app_ref, "AXManualAccessibility", kCFBooleanTrue)
# err == 0 means kAXErrorSuccess
```

### Why It Sometimes Fails

**Bug history (fixed in Electron 26+):**
- Before PR #38102 (April 2023): Setting the attribute would *appear* to fail because Electron unconditionally called `[super accessibilitySetValue:value forAttribute:attribute]` for custom attributes. Since the superclass doesn't recognize `AXManualAccessibility`, it returned failure -- but the attribute was actually being set successfully.
- PR #38102 fixed this so the return code correctly indicates success.
- PR #38142 extended the fix across all protocol methods (some accessibility methods use different protocols on macOS).
- Issue #37465: `AXUIElementCopyAttributeNames` doesn't include `AXManualAccessibility` in its list, making it impossible for external tools to discover the attribute via standard APIs.

**When it genuinely fails (tree stays empty):**

1. **Not an Electron app**: Only Electron apps implement this attribute. Vanilla Chrome does not. CEF (Chromium Embedded Framework) does not.
2. **Old Electron version**: Apps built with Electron < 10 may not support it at all.
3. **App disables it**: Some Electron apps explicitly call `app.commandLine.appendSwitch('disable-renderer-accessibility')` which overrides external accessibility requests.
4. **Nested/wrapper architecture**: The attribute must be set on the correct process (see Section 7).
5. **Timing**: The tree builds asynchronously. Querying immediately after enable will show an empty tree.

Sources:
- https://github.com/electron/electron/pull/10305
- https://github.com/electron/electron/issues/7206
- https://github.com/electron/electron/pull/38102
- https://github.com/electron/electron/pull/38142
- https://github.com/electron/electron/issues/37465

---

## 3. AXEnhancedUserInterface vs AXManualAccessibility

| Aspect | AXEnhancedUserInterface | AXManualAccessibility |
|--------|------------------------|----------------------|
| Origin | Apple (macOS standard) | Electron (custom) |
| Who uses it | VoiceOver | Third-party AT |
| Works on Chrome | Yes | No (Electron only) |
| Works on Electron | Yes | Yes |
| Side effects | Breaks window positioning/animations | None known |
| Discovery | Listed in AXUIElementCopyAttributeNames | NOT listed |
| Set on | Window | Application |

**Important**: Chromium and Electron listen for `AXEnhancedUserInterface` on the **window**, and `AXManualAccessibility` on the **application**. This is a common source of confusion.

The Vimac project (keyboard-driven macOS navigation) documented this well: they initially used `AXEnhancedUserInterface` but had to switch to `AXManualAccessibility` because it broke window managers like Magnet and Rectangle.

Source:
- https://github.com/nchudleigh/vimac/issues/78
- https://developer.apple.com/forums/thread/659755

---

## 4. --force-renderer-accessibility Flag

### What It Does

`--force-renderer-accessibility` is a **Chromium command-line switch** that forces accessibility to be enabled regardless of whether any assistive technology is detected.

### Optional AXMode Parameter

```
--force-renderer-accessibility           # defaults to "complete"
--force-renderer-accessibility=basic     # minimal tree
--force-renderer-accessibility=form-controls  # forms only
--force-renderer-accessibility=complete  # full tree
```

**AXMode levels filter what gets serialized:**
- `basic`: Only essential structure
- `form-controls`: Structure + form elements (useful for password managers)
- `complete`: Everything (what VoiceOver/Nexus needs)

### How to Use It Externally

For any Electron app on macOS:

```bash
# Method 1: Using 'open --args'
open -a "/Applications/Slack.app" --args --force-renderer-accessibility

# Method 2: Direct binary execution
/Applications/Slack.app/Contents/MacOS/Slack --force-renderer-accessibility

# Method 3: For Docker Desktop
open -a "/Applications/Docker.app" --args --force-renderer-accessibility
```

### Advantages Over AXManualAccessibility

- Works on ALL Chromium-based apps (Chrome, Electron, CEF)
- No version dependency on Electron's custom attribute implementation
- Takes effect immediately at startup (no async delay for tree building -- the tree is built from the start)

### Disadvantages

- Requires relaunching the app with the flag
- Cannot be set on an already-running app
- Performance impact (accessibility is always on)
- The app developer can strip command-line args (rare but possible)

### Can It Be Set as an Environment Variable?

No. `--force-renderer-accessibility` is a command-line switch, not an environment variable. However, `ELECTRON_ENABLE_LOGGING` is a valid env var for logging.

Source:
- https://akrabat.com/making-slack-accessible-on-macos/
- https://github.com/microsoft/vscode/issues/84833
- https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/overview.md

---

## 5. Electron's app.accessibilitySupportEnabled

### The API

```javascript
// In Electron main process:
app.setAccessibilitySupportEnabled(true);

// Or read current state:
const enabled = app.accessibilitySupportEnabled;
```

### Relationship to AXManualAccessibility

These are two paths to the same result:

```
External tool sets AXManualAccessibility=true
    -> Electron's ElectronApplication intercepts
    -> Calls app.setAccessibilitySupportEnabled(true)
    -> Chromium starts building AX tree

Electron app code calls app.setAccessibilitySupportEnabled(true)
    -> Same result, but from inside the app
```

### Priority Chain

System assistive utilities (VoiceOver) have priority over the API. If VoiceOver is active, the accessibility state is managed by the system regardless of what the app or external tools request.

### Performance Warning

From Electron docs: "Rendering accessibility tree can significantly affect the performance of your app. It should not be enabled by default."

Chrome's telemetry shows ~5-10% of users have accessibility enabled, often unknowingly (triggered by password managers, antivirus, etc.).

Source:
- https://www.electronjs.org/docs/latest/api/app
- https://www.electronjs.org/docs/latest/tutorial/accessibility
- https://developer.chrome.com/blog/chromium-accessibility-performance

---

## 6. Why the Tree Can Be Empty After Enabling

### The Async Build Process

When accessibility is enabled on an Electron app (via AXManualAccessibility, app.setAccessibilitySupportEnabled, or VoiceOver), the following happens asynchronously:

1. **Browser process** receives the "enable accessibility" signal
2. **Browser process** sends AXMode flags to ALL renderer processes
3. **Each renderer** marks its document as needing accessibility serialization
4. **Each renderer** waits for the document lifecycle to be "clean" (CSS resolved, layout complete)
5. **Each renderer** serializes its full AXNodeData tree via AXTreeSerializer
6. **Each renderer** calls `HandleAXEvents()` IPC to push the tree to the browser process
7. **Browser process** BrowserAccessibilityManager merges the trees
8. **Platform objects** (AXUIElement wrappers) are created on demand

Steps 3-7 take **1-2 seconds** typically, sometimes longer for complex pages. During this time, querying the AXUIElement tree returns only the window frame elements (the browser process chrome, not the web content).

### Why Nexus Sees Only 4 Elements

The ~4 elements visible immediately are the **browser process UI chrome**:
- AXWindow
- AXToolbar (sometimes)
- AXBrowser or AXWebArea placeholder

These exist in the browser process and are always available. The web content lives in the renderer process and arrives via IPC after the async build.

### Nexus's Current Polling Strategy (access.py)

```python
# Polls 8 times at 250ms intervals = 2s max
for _ in range(8):
    time.sleep(0.25)
    children = ax_attr(window, "AXChildren")
    if children and len(children) > 4:
        break  # Tree is populating
```

This is reasonable for VS Code and Slack. For Docker Desktop, the tree never gets past 4 elements, suggesting a deeper problem than timing.

### Reasons the Tree NEVER Populates

1. **AXManualAccessibility not reaching the correct process** (nested app architecture)
2. **Renderer process not responding to accessibility enable** (sandboxed, crashed, or intentionally disabled)
3. **Web content not loaded yet** (app shows blank/loading screen)
4. **CEF-based instead of Electron** (doesn't support AXManualAccessibility)
5. **App explicitly disables accessibility** via `--disable-renderer-accessibility` in its code

---

## 7. Nested Electron Apps (Docker Desktop Pattern)

### The Problem

Some macOS apps wrap an Electron application inside a native (or another Electron) outer shell. Docker Desktop is the canonical example:

```
/Applications/Docker.app/                              <-- Native wrapper (com.docker.docker)
    Contents/
        MacOS/
            Docker Desktop                             <-- Main binary
            Docker Desktop.app/                        <-- NESTED Electron app
                Contents/
                    Frameworks/
                        Electron Framework.framework/  <-- Chromium renderer
                    MacOS/
                        Docker Desktop                 <-- Inner Electron binary
```

### Why AXManualAccessibility Fails on Nested Apps

When Nexus does:
```python
app_ref = AXUIElementCreateApplication(pid_of_docker)
AXUIElementSetAttributeValue(app_ref, "AXManualAccessibility", kCFBooleanTrue)
```

The `pid_of_docker` is the **outer wrapper process** (the native Docker launcher). This process may not be the one running Electron's `ElectronApplication` class that handles `AXManualAccessibility`.

The actual Electron renderer lives in a **child process** with a different PID.

### How Electron Spawns Processes on macOS

A typical Electron app spawns:

| Process | Bundle Location | Role |
|---------|----------------|------|
| Main | `App.app/Contents/MacOS/App` | Browser process (main) |
| Helper (GPU) | `Contents/Frameworks/App Helper (GPU).app` | GPU compositing |
| Helper (Renderer) | `Contents/Frameworks/App Helper (Renderer).app` | Web content rendering |
| Helper (Plugin) | `Contents/Frameworks/App Helper (Plugin).app` | Plugin hosting |
| Helper | `Contents/Frameworks/App Helper.app` | General utility |

**Accessibility is managed by the main (browser) process**, not the renderer helper. But AXManualAccessibility must be set on the process running `ElectronApplication`.

### The Docker Desktop Wrinkle

Docker Desktop has an additional layer: the outer `com.docker.docker` process is a **native Go binary** that launches the inner Electron app. The inner Electron app may run as a child process with its own PID.

**To target the inner Electron process:**
1. Find the inner `Docker Desktop` process PID (not the outer `com.docker.docker`)
2. Set AXManualAccessibility on THAT PID

```bash
# Find the inner Electron process
ps aux | grep "Docker Desktop" | grep -v grep
# Look for the one with "Electron" in its path or with --type= flags
```

### General Strategy for Nested Apps

```python
def find_electron_renderer_pids(outer_pid):
    """Find child processes that are Electron renderers."""
    import subprocess
    result = subprocess.run(
        ['pgrep', '-P', str(outer_pid)],
        capture_output=True, text=True
    )
    child_pids = [int(p) for p in result.stdout.strip().split('\n') if p]

    # Also check for processes with matching bundle
    for pid in child_pids:
        # Try setting AXManualAccessibility on each child
        app_ref = AXUIElementCreateApplication(pid)
        err = AXUIElementSetAttributeValue(
            app_ref, "AXManualAccessibility", kCFBooleanTrue
        )
        if err == 0:
            return pid  # Found the Electron main process
    return None
```

---

## 8. Docker Desktop Specifically

### Architecture

Docker Desktop is a hybrid application:

- **Outer wrapper**: Native binary (`com.docker.docker`) -- a Go-based backend that manages the Docker VM, CLI tools, and system integration
- **Inner Electron app**: JavaScript/React frontend that provides the dashboard UI
- **Backend VM**: Runs the actual container runtime (containerd, Docker Engine)
- **Helper processes**: GPU, renderer, plugin helpers typical of Electron

The ASAR archive containing the JavaScript bundle is at:
`/Applications/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/Resources/app.asar`

### DevTools Access

Docker Desktop has a hidden DevTools shortcut: press `up, up, down, down, left, right, left, right, p, d, t` (a Konami Code variant) to open Chrome DevTools within the app. This confirms it's a standard Electron app internally.

### Why Accessibility Is Broken

Based on field testing (Feb 24, 2026 -- see FIELD_TEST_DOCKER_INSTALL.md):

1. `com.docker.docker` is not in Nexus's `_ELECTRON_BUNDLE_IDS` set
2. Even after adding it and enabling AXManualAccessibility with error=0, only 4 window-frame elements appear
3. The content tree from the renderer process never populates

**Likely root causes:**

1. **Wrong PID targeted**: AXManualAccessibility was set on the outer Go wrapper process, not the inner Electron browser process
2. **The inner Electron app may disable accessibility**: Docker Desktop may use `--disable-renderer-accessibility` or similar
3. **Nested bundle architecture**: The `ElectronApplication` class only exists in the inner app's process space

### Potential Solutions for Docker Desktop

1. **Find the inner Electron PID and target it directly** with AXManualAccessibility
2. **Launch Docker Desktop with `--force-renderer-accessibility`**:
   ```bash
   open -a "/Applications/Docker.app" --args --force-renderer-accessibility
   ```
   Note: This may not work if the outer wrapper doesn't pass args to the inner Electron app.
3. **Launch the inner Electron app directly** (if possible):
   ```bash
   "/Applications/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/MacOS/Docker Desktop" --force-renderer-accessibility
   ```
4. **Connect via CDP** and use JavaScript to enable accessibility or interact with the UI directly (see Section 9)

Source:
- https://sensepost.com/blog/2023/an-offensive-look-at-docker-desktop-extensions/
- https://github.com/docker/roadmap/issues/31
- https://docs.docker.com/desktop/setup/install/mac-install/

---

## 9. CDP for Electron Apps

### Overview

Chrome DevTools Protocol (CDP) is the most powerful alternative when AXManualAccessibility fails. It gives you direct access to the DOM, JavaScript execution, and even accessibility tree queries.

### Launching Electron Apps with CDP

```bash
# Generic Electron app
open -a "/Applications/MyApp.app" --args --remote-debugging-port=9222

# Docker Desktop
open -a "/Applications/Docker.app" --args --remote-debugging-port=9222

# Direct binary
"/Applications/Docker.app/Contents/MacOS/Docker Desktop" --remote-debugging-port=9222

# VS Code
open -a "/Applications/Visual Studio Code.app" --args --remote-debugging-port=9222
```

### Connecting to CDP

After launching with `--remote-debugging-port`, the app exposes a JSON API:

```bash
# List available targets (pages/windows)
curl http://localhost:9222/json

# Returns something like:
# [
#   {
#     "id": "...",
#     "title": "Docker Desktop",
#     "type": "page",
#     "url": "...",
#     "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/..."
#   }
# ]
```

### What CDP Can Do for Automation

1. **DOM.getDocument()** -- get the full DOM tree (equivalent to what the AX tree exposes, but richer)
2. **Runtime.evaluate()** -- execute arbitrary JavaScript in the renderer
3. **Accessibility.getFullAXTree()** -- get Chromium's internal accessibility tree directly via CDP
4. **Page.captureScreenshot()** -- take screenshots of specific elements
5. **DOM.querySelector()** -- find elements by CSS selector
6. **Input.dispatchMouseEvent()** -- click at coordinates
7. **Input.dispatchKeyEvent()** -- send keyboard input

### Python Libraries for CDP

```python
# Using websocket-client (what Nexus already uses for Chrome CDP)
import websocket
import json

ws = websocket.create_connection("ws://localhost:9222/devtools/page/TARGET_ID")
ws.send(json.dumps({
    "id": 1,
    "method": "Accessibility.getFullAXTree",
    "params": {}
}))
result = json.loads(ws.recv())
# result contains the full accessibility tree
```

### electron-inject (Python Package)

The `electron-inject` package wraps the CDP approach:

```bash
pip install electron-inject

# Enable DevTools hotkeys in an app
python -m electron_inject --enable-devtools-hotkeys - /Applications/Docker.app/Contents/MacOS/"Docker Desktop"

# Inject custom JavaScript
python -m electron_inject -r ./my_script.js - /Applications/MyApp.app/Contents/MacOS/MyApp
```

How it works internally:
1. Launches the Electron app with `--remote-debugging-port`
2. Connects to the CDP websocket
3. Uses `Runtime.evaluate` to inject JavaScript into each renderer window
4. Can inject scripts into all windows discovered within a timeout period

**Status**: The package is unmaintained (last update 2019) but the approach is still valid.

### electron-injector (Rust)

A more modern alternative:
```bash
# Install via cargo
cargo install electron-injector

# Inject JS
electron-injector --port 9222 --file inject.js
```

### CDP Approach for Docker Desktop

Since Docker Desktop's AX tree is empty, CDP is the most promising fallback:

```bash
# 1. Quit Docker Desktop
osascript -e 'tell application "Docker" to quit'

# 2. Relaunch with CDP
open -a "/Applications/Docker.app" --args --remote-debugging-port=9223

# 3. Wait for it to start, then discover targets
curl http://localhost:9223/json

# 4. Connect and get the DOM
# Now you can query elements, click buttons, fill forms via CDP
```

Source:
- https://github.com/tintinweb/electron-inject
- https://github.com/itsKaynine/electron-injector
- https://www.form3.tech/blog/engineering/electron-injection
- https://gist.github.com/0xdevalias/428e56a146e3c09ec129ee58584583ba

---

## 10. Alternative Approaches

### 10.1 set-electron-app-accessible (C CLI tool)

A small C utility that enables accessibility for Electron apps via AXManualAccessibility:

```bash
# Build
make

# Use with PID
./set-electron-app-accessible <PID>

# Use from AppleScript
tell application "System Events"
    set pid to unix id of first process whose name is "Docker Desktop"
    do shell script "./set-electron-app-accessible " & pid
end tell
```

Source: https://github.com/JonathanGawrych/set-electron-app-accessible

### 10.2 Accessibility.getFullAXTree via CDP

If connected via CDP, you can get the Chromium accessibility tree directly without going through macOS AXUIElement at all:

```python
# Via CDP websocket
ws.send(json.dumps({
    "id": 1,
    "method": "Accessibility.enable",
    "params": {}
}))
ws.recv()

ws.send(json.dumps({
    "id": 2,
    "method": "Accessibility.getFullAXTree",
    "params": {}
}))
tree = json.loads(ws.recv())
# tree["result"]["nodes"] contains all accessible nodes
```

This bypasses the macOS accessibility layer entirely and reads Chromium's internal representation directly. This would work even if AXManualAccessibility fails.

### 10.3 DOM Inspection via CDP

Even without the accessibility tree, CDP gives full DOM access:

```python
# Get the DOM document
ws.send(json.dumps({
    "id": 1,
    "method": "DOM.getDocument",
    "params": {"depth": -1}  # full tree
}))
doc = json.loads(ws.recv())

# Query for specific elements
ws.send(json.dumps({
    "id": 2,
    "method": "DOM.querySelectorAll",
    "params": {"nodeId": doc["result"]["root"]["nodeId"], "selector": "button"}
}))
buttons = json.loads(ws.recv())
```

### 10.4 Runtime.evaluate for Direct UI Manipulation

```python
# Click a button by its text content
ws.send(json.dumps({
    "id": 1,
    "method": "Runtime.evaluate",
    "params": {
        "expression": """
            Array.from(document.querySelectorAll('button'))
                .find(b => b.textContent.includes('Accept'))
                ?.click()
        """
    }
}))
```

### 10.5 ASAR Extraction and Modification

For truly desperate cases, you can extract and modify an Electron app's code:

```bash
# Extract ASAR
npx asar extract "/Applications/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/Resources/app.asar" /tmp/docker-app

# Modify main.js to add:
# app.setAccessibilitySupportEnabled(true)

# Repack
npx asar pack /tmp/docker-app "/Applications/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/Resources/app.asar"
```

**Warning**: This modifies signed binaries and may break code signature validation. macOS may refuse to run the modified app.

### 10.6 Debugtron

An Electron-based tool specifically for debugging production Electron apps:
- Connects via remote debugging protocol
- Can inspect running Electron apps
- Provides a GUI for DevTools interaction

---

## 11. Known Issues and Limitations

### 11.1 New Microsoft Teams: AXManualAccessibility No Longer Works

The new Microsoft Teams has migrated from Electron to **Edge WebView2**. This means:
- AXManualAccessibility is an Electron-specific attribute -- WebView2 does not implement it
- `--force-renderer-accessibility` may still work (it's a Chromium flag, and WebView2 is Chromium-based)
- The accessibility tree IS available via macOS Accessibility Inspector and VoiceOver, but third-party tools struggle

Source: https://techcommunity.microsoft.com/discussions/teamsdeveloper/enable-accessibility-tree-on-macos-in-the-new-teams-work-or-school/4033014

### 11.2 AXManualAccessibility Not Discoverable

`AXUIElementCopyAttributeNames` on an Electron app does NOT include `AXManualAccessibility` in its response. External tools cannot discover that the attribute exists through standard accessibility APIs. You have to know it exists and try setting it blindly.

Source: https://github.com/electron/electron/pull/38102 (comment by schacon)

### 11.3 ARM64 Renderer Process Permissions Bug

On Apple Silicon (M1/M2/M3), accessibility permissions may not propagate from the main process to renderer processes in packaged DMG builds. The main process reports `Access: true` while the renderer reports `Access: false`. This was reported in Electron #38094 and closed without a fix.

Source: https://github.com/electron/electron/issues/38094

### 11.4 Electron App Freezes When Accessibility Enabled

Multiple reports (issues #17314, #19621) describe Electron apps hanging for several seconds when accessibility is first enabled. This is because building the full tree is expensive (serialization + IPC + platform wrapper creation). For large apps like VS Code, this can take 2-5 seconds.

Source:
- https://github.com/electron/electron/issues/17314
- https://github.com/electron/electron/issues/19621

### 11.5 AXEnhancedUserInterface Side Effects

Setting `AXEnhancedUserInterface` on a window:
- Breaks window positioning with tools like Magnet, Rectangle, Moom
- Causes animations to become sluggish
- Can interfere with window snapping features
- Mozilla filed bug 1664992 requesting an alternative attribute for this reason

Source: https://bugzilla.mozilla.org/show_bug.cgi?id=1664992

### 11.6 Performance Cost of Accessibility

Chrome telemetry shows the accessibility system has a "quite high" total performance cost. Approximately 5-10% of users have it enabled (often unknowingly via password managers or antivirus). Recent optimizations achieved:
- 20% improvement from switching closure-based scheduling to enum-based
- Up to 825% improvement in scrolling tests by including scroll offsets with bounding box serialization

Source: https://developer.chrome.com/blog/chromium-accessibility-performance

---

## 12. Recommendations for Nexus

### 12.1 Immediate: Fix Docker Desktop Detection

```python
_ELECTRON_BUNDLE_IDS = {
    "com.microsoft.VSCode",
    "com.microsoft.VSCodeInsiders",
    "com.electron.",
    "com.github.Electron",
    "com.slack.Slack",
    "com.spotify.client",
    "com.discordapp.Discord",
    "com.obsidian",
    "com.hnc.Discord",
    "com.figma.Desktop",
    "com.notion.Notion",
    "com.1password.1password",
    "com.docker.docker",       # ADD THIS
}
```

But also implement child-process PID discovery to target the actual Electron browser process.

### 12.2 Implement Multi-PID AXManualAccessibility

When AXManualAccessibility on the main PID fails to populate the tree (>4 elements after 2s), try child processes:

```python
def _ensure_electron_accessibility_deep(pid):
    """Try AXManualAccessibility on main PID and children."""
    # Try main PID first
    _ensure_electron_accessibility(pid)

    # If tree still empty, try child processes
    window = ax_attr(AXUIElementCreateApplication(pid), "AXFocusedWindow")
    if window:
        children = ax_attr(window, "AXChildren")
        if children and len(children) > 4:
            return  # Main PID worked

    # Try children
    import subprocess
    result = subprocess.run(['pgrep', '-P', str(pid)], capture_output=True, text=True)
    for child_pid in result.stdout.strip().split('\n'):
        if child_pid:
            _ensure_electron_accessibility(int(child_pid))
```

### 12.3 Add --force-renderer-accessibility Launch Strategy

When Nexus detects an Electron app with an empty tree, offer to relaunch it:

```python
def relaunch_with_accessibility(app_path):
    """Relaunch an Electron app with --force-renderer-accessibility."""
    import subprocess
    # Quit the app
    subprocess.run(['osascript', '-e', f'tell application "{app_name}" to quit'])
    time.sleep(1)
    # Relaunch with flag
    subprocess.run(['open', '-a', app_path, '--args', '--force-renderer-accessibility'])
    time.sleep(3)  # Wait for tree to build
```

### 12.4 Add CDP Fallback for Blind Electron Apps

When all accessibility approaches fail, try CDP:

1. Check if the app is already running with a debug port
2. If not, relaunch with `--remote-debugging-port=RANDOM_PORT`
3. Connect via CDP and use `Accessibility.getFullAXTree()` or `DOM.getDocument()`
4. Map CDP elements to click coordinates using `DOM.getBoxModel()`

This is the nuclear option but works for ALL Chromium-based apps regardless of their accessibility configuration.

### 12.5 Implement Electron Detection Heuristic

Instead of maintaining a hardcoded list of bundle IDs, detect Electron apps dynamically:

```python
def _detect_electron(app_path):
    """Check if an app bundle contains Electron Framework."""
    import os
    # Check for Electron Framework in Frameworks directory
    frameworks_dir = os.path.join(app_path, "Contents", "Frameworks")
    if os.path.exists(frameworks_dir):
        for item in os.listdir(frameworks_dir):
            if "Electron" in item:
                return True

    # Check nested apps
    macos_dir = os.path.join(app_path, "Contents", "MacOS")
    if os.path.exists(macos_dir):
        for item in os.listdir(macos_dir):
            if item.endswith(".app"):
                nested = os.path.join(macos_dir, item, "Contents", "Frameworks")
                if os.path.exists(nested):
                    for f in os.listdir(nested):
                        if "Electron" in f:
                            return True
    return False
```

### 12.6 Increase Polling Window for Nested Apps

For nested Electron apps, increase the wait time since the tree build involves more IPC hops:

```python
# Current: 8 * 250ms = 2s
# Proposed for nested apps: 20 * 250ms = 5s
max_polls = 20 if is_nested_electron else 8
```

### 12.7 Priority of Approaches (Decision Tree)

```
1. Check if app is Electron (bundle heuristic)
2. If Electron:
   a. Set AXManualAccessibility on main PID
   b. Wait 2s, check tree
   c. If still empty, try child PIDs
   d. If still empty, try --force-renderer-accessibility relaunch
   e. If still empty, try CDP (--remote-debugging-port)
3. If not Electron but Chromium-based:
   a. Set AXEnhancedUserInterface on window (with caveats about side effects)
   b. Or use --force-renderer-accessibility
   c. Or use CDP
4. If nothing works:
   a. Fall back to screenshot + OCR
   b. Fall back to coordinate-based clicking
```

---

## 13. References

### Chromium Accessibility Architecture
- [Chromium Accessibility Overview](https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/overview.md)
- [How Chrome Accessibility Works, Part 1](https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/browser/how_a11y_works.md)
- [How Chrome Accessibility Works, Part 2](https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/browser/how_a11y_works_2.md)
- [How Chrome Accessibility Works, Part 3](https://chromium.googlesource.com/chromium/src/+/main/docs/accessibility/browser/how_a11y_works_3.md)
- [Chromium Accessibility Technical Documentation](https://www.chromium.org/developers/design-documents/accessibility/)
- [Mac Accessibility in Chromium](https://www.chromium.org/developers/accessibility/mac-accessibility/)
- [Chromium Accessibility Performance](https://developer.chrome.com/blog/chromium-accessibility-performance)

### Electron Accessibility
- [Electron Accessibility Tutorial](https://www.electronjs.org/docs/latest/tutorial/accessibility)
- [Electron app API (accessibilitySupportEnabled)](https://www.electronjs.org/docs/latest/api/app)
- [PR #10305: AXManualAccessibility attribute (original)](https://github.com/electron/electron/pull/10305)
- [Issue #7206: Allow Mac accessibility for non-VoiceOver apps](https://github.com/electron/electron/issues/7206)
- [PR #38102: Fix AXManualAccessibility showing failure](https://github.com/electron/electron/pull/38102)
- [PR #38142: Handle AXManualAccessibility cross-protocol](https://github.com/electron/electron/pull/38142)
- [Issue #37465: AXManualAccessibility can't be set](https://github.com/electron/electron/issues/37465)
- [Issue #30644: Setting Accessibility via Swift returns attributeUnsupported](https://github.com/electron/electron/issues/30644)
- [Issue #38094: Accessibility Access in Render process (ARM64 bug)](https://github.com/electron/electron/issues/38094)
- [Issue #17314: Electron hangs with accessibility permissions](https://github.com/electron/electron/issues/17314)
- [Issue #19621: Electron freezes macOS with accessibility](https://github.com/electron/electron/issues/19621)

### Docker Desktop
- [Docker Desktop Architecture](https://docs.docker.com/desktop/)
- [Docker Roadmap: Electron UI](https://github.com/docker/roadmap/issues/31)
- [SensePost: Offensive look at Docker Desktop Extensions](https://sensepost.com/blog/2023/an-offensive-look-at-docker-desktop-extensions/)
- [Docker Desktop Mac Install](https://docs.docker.com/desktop/setup/install/mac-install/)
- [Docker Desktop Mac Permission Requirements](https://docs.docker.com/desktop/setup/install/mac-permission-requirements/)

### Tools and Workarounds
- [set-electron-app-accessible](https://github.com/JonathanGawrych/set-electron-app-accessible) -- C CLI tool for enabling Electron accessibility
- [electron-inject](https://github.com/tintinweb/electron-inject) -- Python CDP injection tool
- [electron-injector](https://github.com/itsKaynine/electron-injector) -- Rust CDP injection tool
- [electron-test-mcp](https://github.com/lazy-dinosaur/electron-test-mcp) -- MCP server for testing Electron apps via CDP
- [Making Slack accessible on macOS](https://akrabat.com/making-slack-accessible-on-macos/) -- --force-renderer-accessibility guide
- [Adventures into Electron code injection on MacOS](https://www.form3.tech/blog/engineering/electron-injection) -- Security analysis of CDP injection
- [Debugging Electron Apps (comprehensive gist)](https://gist.github.com/0xdevalias/428e56a146e3c09ec129ee58584583ba)

### macOS Accessibility
- [AXUIElement.h Documentation](https://developer.apple.com/documentation/applicationservices/axuielement_h)
- [Accessibility Programming Guide for OS X](https://developer.apple.com/library/archive/documentation/Accessibility/Conceptual/AccessibilityMacOSX/)
- [AXEnhancedUserInterface breaks window managers (Mozilla bug)](https://bugzilla.mozilla.org/show_bug.cgi?id=1664992)

### Related Discussions
- [Vimac: Chrome/Chromium/Firefox support](https://github.com/nchudleigh/vimac/issues/78) -- AXEnhancedUserInterface vs AXManualAccessibility
- [Enable AX Tree in new Teams](https://techcommunity.microsoft.com/discussions/teamsdeveloper/enable-accessibility-tree-on-macos-in-the-new-teams-work-or-school/4033014)
- [VS Code --force-renderer-accessibility support](https://github.com/microsoft/vscode/issues/84833)
- [Spotify: enable Accessibility programmatically](https://community.spotify.com/t5/Spotify-for-Developers/enable-Accessibility-programmatically-on-macOS/td-p/5410113)
- [Chrome performance hit from accessibility permissions](https://github.com/rxhanson/Rectangle/issues/1065)
