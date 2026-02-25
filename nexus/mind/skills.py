"""Skills — CLI-first knowledge for common tasks.

Skills are markdown files that teach the agent which CLI tools to use
before falling back to GUI interaction (see/do). They're exposed as
MCP resources so any connected agent can discover and read them.

Skill locations (user overrides bundled):
    ~/.nexus/skills/      user skills (persistent, editable)
    nexus/skills/         bundled skills (ship with repo)
"""

import json
import re
import shutil
from pathlib import Path

# Skill directories — user skills override bundled ones with same ID
SKILLS_DIR = Path.home() / ".nexus" / "skills"
BUNDLED_DIR = Path(__file__).parent.parent / "skills"


def list_skills() -> list[dict]:
    """List all available skills with metadata.

    Returns list of dicts:
        [{id, name, description, requires, install, source, available}]

    User skills override bundled skills with the same ID.
    """
    skills = {}

    # Bundled first (can be overridden)
    for md in _scan_dir(BUNDLED_DIR):
        sid = md.stem
        meta = _parse_frontmatter(md)
        skills[sid] = {
            "id": sid,
            "name": meta.get("name", sid),
            "description": meta.get("description", ""),
            "requires": meta.get("requires", []),
            "install": meta.get("install", ""),
            "source": "bundled",
            "available": _check_bins(meta.get("requires", [])),
        }

    # User skills override
    for md in _scan_dir(SKILLS_DIR):
        sid = md.stem
        meta = _parse_frontmatter(md)
        skills[sid] = {
            "id": sid,
            "name": meta.get("name", sid),
            "description": meta.get("description", ""),
            "requires": meta.get("requires", []),
            "install": meta.get("install", ""),
            "source": "user",
            "available": _check_bins(meta.get("requires", [])),
        }

    return sorted(skills.values(), key=lambda s: s["id"])


def read_skill(skill_id: str) -> str | None:
    """Read a skill's full markdown content.

    User skills take priority over bundled ones.
    Returns None if skill not found.
    """
    # Check user dir first
    user_path = SKILLS_DIR / f"{skill_id}.md"
    if user_path.exists():
        return user_path.read_text()

    # Fall back to bundled
    bundled_path = BUNDLED_DIR / f"{skill_id}.md"
    if bundled_path.exists():
        return bundled_path.read_text()

    return None


# App name → skill ID mapping for quick lookup
_APP_SKILL_MAP = {
    "mail": "email", "mail-app": "email",
    "safari": "safari",
    "google chrome": "browser", "chrome": "browser",
    "finder": "finder",
    "terminal": "terminal", "iterm": "terminal", "iterm2": "terminal",
    "docker": "docker", "docker desktop": "docker",
    "visual studio code": "vscode", "code": "vscode",
    "system settings": "system-settings", "system preferences": "system-settings",
}


def find_skill_for_app(app_name):
    """Find the most relevant skill for an app. Returns skill_id or None."""
    if not app_name:
        return None
    lower = app_name.lower()
    # Direct map first
    for pattern, skill_id in _APP_SKILL_MAP.items():
        if pattern in lower:
            return skill_id
    # Fuzzy search skill names/descriptions
    for s in list_skills():
        if lower in s["name"].lower() or lower in s.get("description", "").lower():
            return s["id"]
    return None


def _scan_dir(directory: Path) -> list[Path]:
    """Find all .md files in a directory."""
    if not directory.exists():
        return []
    return sorted(directory.glob("*.md"))


def _parse_frontmatter(path: Path) -> dict:
    """Parse YAML-like frontmatter from a markdown file.

    Supports simple key: value pairs and lists.
    No PyYAML dependency — just regex parsing.
    """
    try:
        text = path.read_text()
    except (IOError, OSError):
        return {}

    # Match --- delimited frontmatter
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    meta = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # key: value
        kv = re.match(r"^(\w+)\s*:\s*(.+)$", line)
        if not kv:
            continue

        key, val = kv.group(1), kv.group(2).strip()

        # List: [item1, item2]
        list_match = re.match(r"^\[(.+)\]$", val)
        if list_match:
            items = [i.strip().strip("\"'") for i in list_match.group(1).split(",")]
            meta[key] = items
        else:
            # Strip quotes
            meta[key] = val.strip("\"'")

    return meta


def _check_bins(requires: list) -> bool:
    """Check if all required CLI tools are installed."""
    if not requires:
        return True
    return all(shutil.which(b) is not None for b in requires)
