---
name: finder
description: Finder automation — keyboard shortcuts, Go To Folder, CLI alternatives
requires: []
---

# Finder Skill

Finder has a good AX tree. But for most file operations, CLI is faster and more reliable.

## When to use Nexus GUI

- Visual file browsing and preview (Quick Look)
- Drag and drop operations
- Tag management and color labels
- Get Info / file metadata (when CLI alternatives are insufficient)

## When NOT to use (use CLI instead)

- Listing files: `ls -la /path`
- Moving/copying files: `mv`, `cp`
- Deleting files: `rm` (or `trash` via `brew install trash`)
- Creating folders: `mkdir -p /path`
- Finding files: `find`, `mdfind` (Spotlight), `fd`
- Opening files: `open /path/to/file`
- Revealing in Finder: `open -R /path/to/file`

## Keyboard Shortcuts

```
do("press cmd+shift+g")     # Go To Folder (type a path directly)
do("press space")            # Quick Look (preview selected file)
do("press cmd+i")            # Get Info
do("press cmd+shift+n")     # New Folder
do("press cmd+delete")      # Move to Trash
do("press cmd+shift+delete") # Empty Trash
do("press cmd+d")            # Duplicate
do("press cmd+l")            # Make Alias
do("press enter")            # Rename selected file
do("press cmd+up")           # Go to parent folder
do("press cmd+down")         # Open selected folder
do("press cmd+1")            # Icon view
do("press cmd+2")            # List view
do("press cmd+3")            # Column view
do("press cmd+4")            # Gallery view
do("press cmd+shift+.")     # Toggle hidden files
do("press cmd+n")            # New Finder window
do("press cmd+t")            # New tab
do("press cmd+f")            # Search
do("press cmd+shift+c")     # Go to Computer
do("press cmd+shift+h")     # Go to Home
do("press cmd+shift+d")     # Go to Desktop
do("press cmd+shift+a")     # Go to Applications
do("press cmd+option+l")    # Go to Downloads
```

## CLI File Operations

```bash
# Open a folder in Finder
open /path/to/folder

# Reveal a file in Finder
open -R /path/to/file

# Get file info
mdls /path/to/file          # Spotlight metadata
stat /path/to/file          # File stats
file /path/to/file          # File type

# Spotlight search (fast, indexed)
mdfind "search term"
mdfind -onlyin ~/Documents "report"
mdfind "kMDItemKind == 'PDF'"

# Copy file path from Finder selection
osascript -e 'tell app "Finder" to get POSIX path of (selection as alias)'

# Get frontmost Finder window path
osascript -e 'tell app "Finder" to get POSIX path of (target of front window as alias)'

# Trash a file (recoverable, unlike rm)
osascript -e 'tell app "Finder" to delete POSIX file "/path/to/file"'
```

## AppleScript Alternatives

```bash
# List files in current Finder window
osascript -e 'tell app "Finder" to get name of every item of front window'

# Get selection
osascript -e 'tell app "Finder" to get name of selection'

# Create folder
osascript -e 'tell app "Finder" to make new folder at desktop with properties {name:"New Folder"}'

# Set file label/tag
osascript -e 'tell app "Finder" to set label index of file "doc.pdf" of desktop to 2'
```

## Tips

- `mdfind` (Spotlight CLI) is usually faster than `find` for file searches
- Go To Folder (Cmd+Shift+G) accepts full POSIX paths and ~ for home
- Quick Look (Space) works for images, PDFs, code files — no need to open them
- Column view (Cmd+3) gives the best AX tree for navigation
- On Spanish macOS, Finder labels are in Spanish ("Carpeta nueva" not "New Folder")
