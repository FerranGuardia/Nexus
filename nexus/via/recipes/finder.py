"""Finder recipes — reveal, trash, eject, empty trash via AppleScript + CLI."""

from nexus.via.recipe import recipe, applescript, cli


@recipe(r"(?:reveal|show|open) (.+?) in finder")
def reveal_in_finder(m, pid=None):
    """Reveal a file or folder in Finder."""
    path = m.group(1).strip().strip("'\"")
    return cli(f'open -R "{path}"')


@recipe(r"(?:move |send )?(.+?) to (?:the )?trash", app="finder")
def trash_file(m, pid=None):
    """Move a file to trash via Finder."""
    path = m.group(1).strip().strip("'\"")
    return applescript(
        f'tell app "Finder" to delete POSIX file "{path}"'
    )


@recipe(r"empty (?:the )?trash")
def empty_trash(m, pid=None):
    """Empty the Finder trash."""
    return applescript('tell app "Finder" to empty trash')


@recipe(r"eject (.+)")
def eject_disk(m, pid=None):
    """Eject a disk or volume."""
    name = m.group(1).strip().strip("'\"")
    return applescript(f'tell app "Finder" to eject disk "{name}"')


@recipe(r"(?:create|make|new) folder (?:named? |called )?(.+?)(?:\s+(?:in|at)\s+(.+))?$")
def create_folder(m, pid=None):
    """Create a new folder."""
    name = m.group(1).strip().strip("'\"")
    location = m.group(2).strip().strip("'\"") if m.group(2) else "."
    return cli(f'mkdir -p "{location}/{name}"')


@recipe(r"(?:open|go to) (?:folder |directory )?(.+)", app="finder")
def open_folder(m, pid=None):
    """Open a folder in Finder."""
    path = m.group(1).strip().strip("'\"")
    return cli(f'open "{path}"')
