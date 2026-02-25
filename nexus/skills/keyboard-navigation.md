---
name: keyboard-navigation
description: Universal macOS keyboard shortcuts, Tab/Space navigation, focus control
requires: []
---

# Keyboard Navigation Skill

Keyboard shortcuts skip tree walks entirely. They're the fastest action method — ~50ms vs ~300ms for AX element search + click.

## Universal macOS Shortcuts

### Window Management
```
Cmd+W              Close window/tab
Cmd+Q              Quit application
Cmd+M              Minimize window
Cmd+H              Hide application
Cmd+Option+H       Hide others
Cmd+Tab            Switch application
Cmd+`              Switch window within app
Cmd+N              New window/document
Cmd+Shift+N        New folder / private window
```

### Text Editing (works in any text field)
```
Cmd+A              Select all
Cmd+C              Copy
Cmd+V              Paste
Cmd+X              Cut
Cmd+Z              Undo
Cmd+Shift+Z        Redo
Cmd+F              Find
Cmd+G              Find next
Cmd+Shift+G        Find previous
Cmd+S              Save
Cmd+Shift+S        Save As
Cmd+P              Print

Option+Left        Move word left
Option+Right       Move word right
Cmd+Left           Move to line start
Cmd+Right          Move to line end
Cmd+Up             Move to document start
Cmd+Down           Move to document end

Shift + any move   Extend selection
Option+Delete      Delete word backward
Fn+Delete          Forward delete
```

### Dialog Navigation
```
Tab                Next field/button
Shift+Tab          Previous field/button
Space              Activate focused button
Enter/Return       Default button (blue/highlighted)
Escape             Cancel / close dialog
Cmd+.              Cancel (equivalent to Escape)
```

**IMPORTANT:** macOS requires "Keyboard navigation" to be enabled for Tab to cycle through all controls. Check: System Settings > Keyboard > "Keyboard navigation" toggle. Without this, Tab only moves between text fields.

### Enabling Keyboard Navigation
```bash
# Enable via defaults (takes effect immediately in most apps)
defaults write NSGlobalDomain AppleKeyboardUIMode -int 2

# Or guide user to: System Settings > Keyboard > Keyboard navigation
```

## Focus and Accessibility

### Full Keyboard Access
```
Ctrl+F1            Toggle Full Keyboard Access
Ctrl+F2            Focus menu bar
Ctrl+F3            Focus Dock
Ctrl+F4            Focus next window (all apps)
Ctrl+F5            Focus toolbar
Ctrl+F6            Focus floating window
Ctrl+F7            Toggle keyboard navigation mode
Ctrl+F8            Focus status menus (right side of menu bar)
```

### Menu Bar Navigation
```
Ctrl+F2            Focus menu bar
Left/Right         Navigate between menus
Down/Up            Navigate within menu
Enter              Activate menu item
Escape             Close menu
Type letters       Jump to menu item starting with that letter
```

## Using Keyboard Shortcuts with Nexus

```
# Direct shortcut (fastest)
do("press cmd+s")

# Tab navigation for dialogs
do("press tab")              # Move focus
do("press shift+tab")        # Move focus back
do("press space")            # Activate button
do("press enter")            # Default action

# Menu bar access
do("press ctrl+f2")         # Focus menu bar
do("press right")           # Move to next menu
do("press down")            # Open menu
do("type s")                # Jump to item starting with "s"
do("press enter")           # Activate
```

## Common Patterns

### Save File Dialog
```
do("press cmd+s")                    # Open save dialog
do("type filename.txt")              # Type filename
do("press cmd+shift+g")             # Go to folder
do("type /path/to/dir")             # Type path
do("press enter")                    # Confirm path
do("press enter")                    # Save
```

### Open File Dialog
```
do("press cmd+o")                    # Open dialog
do("press cmd+shift+g")             # Go to folder
do("type /path/to/file")            # Type path
do("press enter")                    # Confirm
do("press enter")                    # Open
```

### Print Dialog
```
do("press cmd+p")                    # Open print dialog
do("press enter")                    # Print with defaults
# Or press Tab to navigate between options
```

## Tips

- Shortcuts are THE fastest action method — no tree walk, no element search
- Always check if a keyboard shortcut exists before falling back to tree-based clicking
- Spanish macOS uses the same shortcut keys but different menu labels
- Full Keyboard Access (Ctrl+F1) is essential for dialog navigation
- In save/open dialogs, Cmd+Shift+G opens "Go to Folder" — type a full path
- Escape is the universal "cancel/dismiss" — works for dialogs, menus, popovers
- Space activates the focused button; Enter activates the default (blue) button
