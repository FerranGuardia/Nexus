---
name: safari
description: Safari automation — keyboard shortcuts, AX tree tips, CLI alternatives
requires: []
---

# Safari Skill

Safari has the richest accessibility tree on macOS (200+ elements). Use keyboard shortcuts to skip tree walks when possible.

## When to use Nexus GUI

- Interacting with logged-in web content (cookies/sessions preserved)
- Filling forms on web pages
- Navigating complex web UIs with dynamic elements
- Reading authenticated page content

## When NOT to use (use CLI instead)

- Reading a public URL: use `curl` or WebFetch
- Downloading files: `curl -LO <url>`
- Getting page source: `curl -s <url>`

## Keyboard Shortcuts (fastest — no tree walk)

```
do("press cmd+l")         # Focus address bar (go to URL)
do("press cmd+t")         # New tab
do("press cmd+w")         # Close tab
do("press cmd+shift+t")   # Reopen last closed tab
do("press cmd+1")         # Switch to tab 1 (cmd+2 for tab 2, etc.)
do("press cmd+shift+]")   # Next tab
do("press cmd+shift+[")   # Previous tab
do("press cmd+r")         # Reload page
do("press cmd+f")         # Find on page
do("press cmd+,")         # Preferences
do("press cmd+shift+n")   # New private window
do("press cmd+d")         # Bookmark page
do("press cmd+option+l")  # Show downloads
do("press cmd+y")         # Show history
do("press cmd+shift+h")   # Go to Home page
do("press space")         # Page down
do("press shift+space")   # Page up
do("press cmd+up")        # Scroll to top
do("press cmd+down")      # Scroll to bottom
```

## Nexus + Safari (AppleScript integration)

```
do("get url")              # Get current URL (via AppleScript)
do("get tabs")             # List all open tabs
do("navigate <url>")       # Go to URL (via AppleScript)
```

## AX Tree Tips

- Safari's tree is HUGE — always use `see(query="...")` instead of bare `see()`
- Web content elements nest deep (AXWebArea → groups → elements)
- Links are AXLink, buttons are AXButton, text fields are AXTextField
- Forms: look for AXTextField and AXSecureTextField (password)
- Tables: Safari renders HTML tables as AXTable with rows/columns

## Common Patterns

```
# Go to URL without opening Safari GUI
osascript -e 'tell app "Safari" to set URL of current tab of front window to "https://example.com"'

# Get page source
osascript -e 'tell app "Safari" to do JavaScript "document.documentElement.outerHTML" in current tab of front window'

# Get page text
osascript -e 'tell app "Safari" to do JavaScript "document.body.innerText" in current tab of front window'

# Count tabs
osascript -e 'tell app "Safari" to count tabs of front window'
```

## Tips

- Safari has full AppleScript support — prefer it over GUI interaction for navigation
- `do JavaScript` in AppleScript executes JS in the page context (like Chrome CDP)
- On Spanish macOS, Safari menu items are in Spanish but shortcuts are universal
- Reader mode (Cmd+Shift+R) simplifies the AX tree significantly
