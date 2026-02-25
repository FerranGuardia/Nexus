---
name: file-save-as
description: Save/Save As dialog navigation — keyboard-first, common locations
requires: []
---

# File Save As Skill

Save dialogs follow a standard macOS pattern. Keyboard navigation is fastest.

## Quick Save (no dialog)

```
do("press cmd+s")     # Save in place (no dialog if already saved)
```

## Save As

```
do("press cmd+shift+s")              # Open Save As dialog
# Or: do("click File > Save As")

do("type myfile.txt")                 # Type filename (field is auto-focused)
do("press cmd+shift+g")             # Open "Go to Folder" sheet
do("type /path/to/directory")       # Type full path
do("press enter")                    # Confirm directory
do("press enter")                    # Click Save (default button)
```

## Expanded vs Compact Dialog

Save dialogs have two modes:
- **Compact**: filename + location dropdown + Save/Cancel
- **Expanded**: full file browser (toggle with the disclosure button)

The disclosure button (small arrow next to the filename field) toggles between modes. In compact mode, use the "Where" dropdown or Cmd+Shift+G.

## Common Locations (via "Where" dropdown or keyboard)

```
# Navigate to specific locations
do("press cmd+shift+g")     # Go to Folder
do("type ~/Desktop")         # Desktop
do("type ~/Documents")       # Documents
do("type ~/Downloads")       # Downloads
do("type /tmp")              # Temp directory
do("press enter")            # Confirm
```

## File Format Selection

Many apps show a format dropdown in the Save dialog:
```
do("click format popup")     # Open format dropdown
do("click PDF")              # Select format
```

## Replace Existing File

If a file with the same name exists, macOS shows a confirmation:
- **Replace**: overwrites the file
- **Cancel**: goes back to the dialog

```
do("press enter")            # Confirm replacement (Replace is default)
# Or: do("press escape")    # Cancel
```

## Tips

- The filename field is auto-focused when the dialog opens — just start typing
- Cmd+Shift+G works in ALL file dialogs (Save, Open, Export)
- Tab navigates between filename field, location dropdown, and buttons
- Enter always activates the default (blue) button — usually "Save"
- On Spanish macOS: "Guardar" (Save), "Cancelar" (Cancel), "Reemplazar" (Replace)
