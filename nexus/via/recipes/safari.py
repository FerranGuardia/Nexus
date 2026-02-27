"""Safari recipes — navigation and tab management via AppleScript."""

from nexus.via.recipe import recipe, applescript


@recipe(r"(?:go to|open|navigate to|visit|browse to)\s+(.+)", app="safari")
def navigate(m, pid=None):
    """Navigate Safari to a URL."""
    url = m.group(1).strip().strip("'\"")
    if not url.startswith(("http://", "https://", "file://", "about:")):
        url = f"https://{url}"
    return applescript(f'''
        tell application "Safari"
            if (count of windows) = 0 then make new document
            set URL of front document to "{url}"
            activate
        end tell
    ''')


@recipe(r"new tab(?:\s+(.+))?", app="safari")
def new_tab(m, pid=None):
    """Open a new Safari tab, optionally with a URL."""
    url = m.group(1).strip().strip("'\"") if m.group(1) else "about:blank"
    if url != "about:blank" and not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return applescript(f'''
        tell application "Safari"
            tell front window
                set current tab to (make new tab with properties {{URL:"{url}"}})
            end tell
        end tell
    ''')


@recipe(r"close (?:the )?(?:current )?tab", app="safari")
def close_tab(m, pid=None):
    """Close the current Safari tab."""
    return applescript('''
        tell application "Safari"
            tell front window to close current tab
        end tell
    ''')


@recipe(r"(?:reload|refresh)(?: (?:the )?(?:page|tab))?", app="safari")
def reload_page(m, pid=None):
    """Reload the current Safari page."""
    return applescript('''
        tell application "Safari"
            set URL of front document to URL of front document
        end tell
    ''')
