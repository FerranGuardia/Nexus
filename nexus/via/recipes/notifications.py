"""Notification recipes — richer patterns for osascript notifications and TTS."""

from nexus.via.recipe import recipe, applescript


@recipe(r"(?:show )?notification\s+(.+?)(?:\s+(?:with title|titled)\s+(.+))?$")
def notify(m, pid=None):
    """Show a macOS notification."""
    message = m.group(1).strip().strip("'\"")
    title = m.group(2).strip().strip("'\"") if m.group(2) else "Nexus"
    return applescript(
        f'display notification "{message}" with title "{title}"'
    )


@recipe(r"(?:alert|dialog)\s+(.+)")
def alert(m, pid=None):
    """Show a modal alert dialog."""
    message = m.group(1).strip().strip("'\"")
    return applescript(
        f'display dialog "{message}" with title "Nexus" buttons {{"OK"}} default button "OK"'
    )
