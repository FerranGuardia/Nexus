"""File operation recipes — CLI-based file management."""

from nexus.via.recipe import recipe, cli


@recipe(r"(?:find|search for|locate) files? (?:named? |called )?(.+?)(?:\s+in\s+(.+))?$")
def find_files(m, pid=None):
    """Find files by name using Spotlight."""
    name = m.group(1).strip().strip("'\"")
    location = m.group(2).strip().strip("'\"") if m.group(2) else None
    if location:
        return cli(f'mdfind -onlyin "{location}" "kMDItemDisplayName == *{name}*"')
    return cli(f'mdfind "kMDItemDisplayName == *{name}*" | head -20')


@recipe(r"^(?:disk |storage )?(?:usage|space)(?: (?:of|on|for)\s+(.+))?$")
def disk_usage(m, pid=None):
    """Check disk usage."""
    path = m.group(1).strip().strip("'\"") if m.group(1) else "/"
    return cli(f'df -h "{path}" | tail -1')


@recipe(r"^(?:file |what is the )?size (?:of )?(.+)")
def file_size(m, pid=None):
    """Get file or directory size."""
    path = m.group(1).strip().strip("'\"")
    return cli(f'du -sh "{path}" 2>/dev/null | cut -f1')
