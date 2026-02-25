---
name: electron-apps
description: Electron app accessibility — which work, which don't, workarounds
requires: []
---

# Electron Apps Skill

Electron apps embed Chromium. Their accessibility trees are built asynchronously and require explicit enabling. Some work well, others are blind.

## App Status

| App | Bundle ID | AX Tree | Notes |
|-----|-----------|---------|-------|
| VS Code | com.microsoft.VSCode | Good | Depth 14-20, auto-enabled by Nexus |
| Slack | com.slack.Slack | Good | Standard Electron, works well |
| Discord | com.discordapp.Discord | Good | Standard Electron |
| Figma | com.figma.Desktop | Moderate | Complex canvas, limited AX |
| Notion | com.notion.Notion | Good | Standard Electron |
| 1Password | com.1password.1password | Good | Standard Electron |
| Obsidian | md.obsidian | Good | Standard Electron |
| Spotify | com.spotify.client | Poor | Custom renderer, limited tree |
| Docker Desktop | com.docker.docker | **Blind** | Nested Electron — see Docker skill |
| Microsoft Teams | com.microsoft.teams2 | **Blind** | Migrated to Edge WebView2, not Electron |

## How Nexus Enables Electron Accessibility

1. Detects Electron by bundle ID from `_ELECTRON_BUNDLE_IDS` set
2. Sets `AXManualAccessibility = true` on the app's AXUIElement
3. Waits ~2s for Chromium to build the tree asynchronously
4. Polls for >4 elements (window frame = 4, content = more)

## When the Tree Is Empty

If AXManualAccessibility succeeds (error=0) but the tree stays at ~4 elements:

**Try 1: Force renderer accessibility (requires app relaunch)**
```bash
# Quit the app first
osascript -e 'tell application "AppName" to quit'
sleep 2

# Relaunch with flag
open -a "/Applications/AppName.app" --args --force-renderer-accessibility
sleep 3

# Now try see()
```

**Try 2: Target child processes (for nested architectures)**
```bash
# Find the actual Electron process
ps aux | grep "Electron"
# Set AXManualAccessibility on that PID instead
```

**Try 3: Use CDP (Chrome DevTools Protocol)**
```bash
# Relaunch with debug port
osascript -e 'tell application "AppName" to quit'
sleep 2
open -a "/Applications/AppName.app" --args --remote-debugging-port=9222
sleep 5

# Discover targets
curl http://localhost:9222/json

# Now use Nexus CDP: do("navigate ..."), do("js ...")
```

**Try 4: Screenshot + OCR (Phase 2 fallback)**
When everything else fails, fall back to visual perception.

## Detecting Electron Apps Dynamically

Instead of maintaining a hardcoded bundle ID list, check for Electron Framework:
```bash
# Check if an app is Electron
ls "/Applications/AppName.app/Contents/Frameworks/" | grep -i electron
# If "Electron Framework.framework" exists → it's Electron

# Check nested apps
ls "/Applications/AppName.app/Contents/MacOS/"*.app 2>/dev/null
```

## AXEnhancedUserInterface vs AXManualAccessibility

| | AXEnhancedUserInterface | AXManualAccessibility |
|--|------------------------|----------------------|
| Origin | Apple (macOS standard) | Electron (custom) |
| Set on | Window | Application |
| Works on Chrome | Yes | No |
| Works on Electron | Yes | Yes |
| Side effects | Breaks window managers | None |
| Discoverable | Yes (in attribute list) | No (must know it exists) |

**Rule:** Use AXManualAccessibility for Electron. Use AXEnhancedUserInterface only for vanilla Chrome.

## Performance Impact

- Enabling accessibility on Electron apps causes a ~2-5s hang on first enable
- Ongoing performance cost: ~5-10% (Chromium telemetry)
- Large apps (VS Code with many tabs) build trees slower

## Tips

- Nexus auto-enables accessibility for known Electron apps — no manual setup needed
- After enabling, wait at least 2s before querying the tree
- Use `see(query="...")` — Electron trees are enormous, full tree is wasteful
- If an Electron app has a CLI, always prefer it (e.g., `code` for VS Code, `slack-cli` for Slack)
- Electron version matters: AXManualAccessibility works on Electron 10+, fixed properly in 26+
