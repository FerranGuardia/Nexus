---
name: system-settings
description: System Settings navigation — deep paths, search field, admin password panes
requires: []
---

# System Settings Skill

System Settings (macOS Ventura+) is a SwiftUI app with a good AX tree. Navigation is sidebar-based. The search field is the fastest way to find any setting.

## Fastest Approach: Search Field

```
do("open System Settings")
do("click search field")
do("type wifi")                    # Search finds it instantly
do("click Wi-Fi")                  # Click the result
```

The search field is always at the top. Typing filters the sidebar in real-time. This is faster than navigating the sidebar hierarchy.

## Opening Specific Panes (CLI)

```bash
# Open System Settings to a specific pane (macOS 13+)
open "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension"
open "x-apple.systempreferences:com.apple.Network-Settings.extension"
open "x-apple.systempreferences:com.apple.wifi-settings-extension"
open "x-apple.systempreferences:com.apple.Accessibility-Settings.extension"
open "x-apple.systempreferences:com.apple.Desktop-Settings.extension"
open "x-apple.systempreferences:com.apple.Displays-Settings.extension"
open "x-apple.systempreferences:com.apple.Sound-Settings.extension"
open "x-apple.systempreferences:com.apple.Bluetooth-Settings.extension"
open "x-apple.systempreferences:com.apple.Keyboard-Settings.extension"

# Generic open
open -a "System Settings"
```

## Common Navigation Paths

| Setting | Path | Search term |
|---------|------|-------------|
| Wi-Fi | Network > Wi-Fi | "wifi" |
| Bluetooth | Bluetooth | "bluetooth" |
| Accessibility | Accessibility | "accessibility" |
| Privacy & Security | Privacy & Security | "privacy" |
| Display | Displays | "display" |
| Sound | Sound | "sound" |
| Keyboard | Keyboard | "keyboard" |
| Trackpad | Trackpad | "trackpad" |
| About This Mac | General > About | "about" |
| Software Update | General > Software Update | "update" |
| Storage | General > Storage | "storage" |
| Login Items | General > Login Items | "login items" |
| Time Machine | General > Time Machine | "time machine" |
| Sharing | General > Sharing | "sharing" |

## Admin Password Panes

Some panes require authentication ("click the lock"):

- Privacy & Security > Accessibility
- Privacy & Security > Full Disk Access
- General > Login Items
- Users & Groups

When you see a lock icon:
1. `do("click lock")` — opens SecurityAgent password dialog
2. **WARNING:** SecurityAgent dialogs are often invisible to Nexus
3. If the password dialog is not visible in see(), the user must handle it manually
4. After authentication, the lock opens and settings become editable

## AX Tree Tips

- System Settings uses SwiftUI — elements have clear roles and labels
- The sidebar is a list (AXList) with clickable rows
- Detail panes change dynamically when sidebar selection changes
- Use `see(query="...")` to find specific toggles or buttons
- Toggles are AXCheckBox with AXValue 0 (off) or 1 (on)

## CLI Alternatives

```bash
# Read defaults
defaults read com.apple.dock autohide
defaults read NSGlobalDomain AppleInterfaceStyle  # "Dark" or not set

# Write defaults (some settings)
defaults write com.apple.dock autohide -bool true && killall Dock
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Toggle dark mode
osascript -e 'tell app "System Events" to tell appearance preferences to set dark mode to not dark mode'

# Get macOS version
sw_vers

# Network info
networksetup -listallhardwareports
networksetup -getinfo Wi-Fi
networksetup -setairportpower en0 on

# Firewall
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# Check disk space
df -h
diskutil list
```

## Tips

- On Spanish macOS, the app is "Ajustes del Sistema" but `open -a "System Settings"` still works
- URL schemes (`x-apple.systempreferences:`) bypass sidebar navigation entirely
- The search field is always the fastest path — type 2-3 characters and the setting appears
- After changing settings, some require logout or restart (networksetup changes are immediate)
- `defaults` command can read/write many settings without opening the GUI at all
