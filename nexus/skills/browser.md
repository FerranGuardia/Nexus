---
name: browser
description: Chrome automation — when to use CLI/CDP vs Nexus GUI, common patterns
requires: []
---

# Browser Skill

Guidance on when to use direct CLI/CDP vs Nexus see/do for browser tasks.

## Decision tree

```
Need to read a public URL?
  → WebFetch tool or curl (don't open a browser)

Need to interact with a web app (click, type, fill forms)?
  → Nexus do("navigate <url>") + do("click/type/fill...")

Need to run JavaScript on a page?
  → Nexus do("js <expression>")

Need to extract structured data from a page?
  → Nexus do("js document.querySelectorAll('...')") or do("read table")

Need authenticated access (logged-in session)?
  → Use Chrome CDP through Nexus (preserves cookies/session)
```

## Open URLs

```bash
# Quick open (uses default browser)
open "https://example.com"

# Open in Chrome specifically
open -a "Google Chrome" "https://example.com"

# Open in Chrome with CDP enabled (for Nexus control)
open -a "Google Chrome" --args --remote-debugging-port=9222
```

## Nexus CDP Intents

When Chrome is running with `--remote-debugging-port=9222`:

```
do("navigate https://example.com")     # go to URL
do("js document.title")                # run JavaScript
do("js document.querySelector('.price').textContent")
do("get url")                          # current URL
do("get tabs")                         # list open tabs
do("switch tab 2")                     # switch to tab 2
do("new tab https://example.com")      # open new tab
do("close tab")                        # close current tab
```

## Common JS Patterns

```
# Extract all links
do("js [...document.querySelectorAll('a')].map(a => a.href + ' ' + a.textContent.trim()).join('\\n')")

# Extract table data
do("js [...document.querySelectorAll('table tr')].map(r => [...r.cells].map(c => c.textContent.trim()).join('\\t')).join('\\n')")

# Get form field values
do("js Object.fromEntries([...document.querySelectorAll('input')].map(i => [i.name, i.value]))")

# Check if element exists
do("js !!document.querySelector('.error-message')")

# Get page text content
do("js document.body.innerText.substring(0, 2000)")
```

## CLI Alternatives (no browser needed)

```bash
# Fetch a URL and extract text
curl -s "https://example.com" | textutil -stdin -format html -convert txt -stdout

# Download a file
curl -LO "https://example.com/file.pdf"

# API requests
curl -s "https://api.github.com/repos/owner/repo" | jq '.description'

# Check HTTP status
curl -sI "https://example.com" | head -1
```

## Safety — cleanup after yourself

- `--remote-debugging-port=9222` opens a debug port. Close Chrome or restart without the flag when done.
- `curl` with auth tokens: never echo tokens to stdout or log files.
- If you open Chrome with CDP for a task, note it — don't leave debug ports open indefinitely.

## Tips

- WebFetch/curl is always faster than opening a browser — use for read-only public pages
- CDP through Nexus preserves your logged-in sessions (Gmail, Slack web, etc.)
- For authenticated APIs, prefer CLI tools (gh, himalaya) over browser automation
- If Chrome isn't running with CDP, Nexus can still use see/do on the Chrome GUI via accessibility
- `do("js ...")` returns stringified results — use JSON.stringify for objects
