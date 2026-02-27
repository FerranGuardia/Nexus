"""App lifecycle recipes — force quit, hide, restart via AppleScript."""

from nexus.via.recipe import recipe, applescript


@recipe(r"force quit (?:app )?(.+)")
def force_quit(m, pid=None):
    """Force quit an application."""
    app = m.group(1).strip().strip("'\"")
    return applescript(f'tell app "{app}" to quit')


@recipe(r"hide (?:app )?(.+)")
def hide_app(m, pid=None):
    """Hide an application."""
    app = m.group(1).strip().strip("'\"")
    return applescript(
        f'tell app "System Events" to set visible of process "{app}" to false'
    )


@recipe(r"(?:show|unhide) (?:all )?(?:hidden )?(?:apps?|windows?)")
def show_all(m, pid=None):
    """Show all hidden applications."""
    return applescript(
        'tell app "System Events" to set visible of every process to true'
    )
