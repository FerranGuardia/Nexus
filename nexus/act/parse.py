"""Parsing utilities for intent resolution."""

import difflib
import re


# ---------------------------------------------------------------------------
# Role name → AXRole mapping (single source of truth)
# ---------------------------------------------------------------------------

ROLE_MAP = {
    "button": "AXButton", "link": "AXLink", "tab": "AXTab",
    "menu": "AXMenuItem", "field": "AXTextField", "checkbox": "AXCheckBox",
    "radio": "AXRadioButton", "text": "AXStaticText", "image": "AXImage",
    "slider": "AXSlider", "switch": "AXSwitch", "toggle": "AXSwitch",
    "icon": "AXImage", "label": "AXStaticText",
}

# Role words recognized in ordinals and spatial references
ROLE_WORDS = frozenset(ROLE_MAP.keys())


# ---------------------------------------------------------------------------
# Verb synonym expansion — normalize natural phrasing before dispatch
# ---------------------------------------------------------------------------

VERB_SYNONYMS = {
    # click synonyms
    "tap": "click", "hit": "click", "select": "click", "choose": "click",
    "pick": "click", "push": "click", "touch": "click",
    # type synonyms (not "write" — conflicts with "write clipboard")
    "enter": "type", "input": "type",
    # open synonyms (not "run" — conflicts with "run js")
    "launch": "open", "start": "open",
    # close synonyms (quit/exit handled directly in shortcut intents)

    # scroll synonyms
    "swipe": "scroll",
    # navigate synonyms
    "browse": "navigate", "visit": "navigate", "load": "navigate",
    # focus synonyms
    "find": "focus", "locate": "focus",
    # hover synonyms
    "mouseover": "hover",
    # switch synonyms
    "bring": "switch",
}

# Multi-word verb phrases that need special handling
PHRASE_SYNONYMS = {
    "press on": "click",
    "click on": "click",
    "tap on": "click",
    "go to": "navigate",
    "switch to": "switch to",
    "type in": "type",
    # "move to" intentionally omitted — "move" is a window management verb
    # Use "go to" / "visit" / "navigate" for URL navigation
    "look at": "focus",
}


# All known verbs for typo tolerance (canonical + synonyms)
_ALL_VERBS = frozenset(VERB_SYNONYMS.keys()) | frozenset(VERB_SYNONYMS.values()) | frozenset({
    "click", "type", "press", "open", "switch", "scroll", "hover", "focus",
    "drag", "tile", "move", "minimize", "restore", "resize", "fullscreen",
    "menu", "fill", "wait", "observe", "notify", "say", "navigate", "js",
    "close", "double-click", "right-click", "triple-click", "new", "run",
    "eval", "execute", "set", "write", "activate", "position", "copy",
    "paste", "undo", "redo", "quit", "exit", "maximize",
    # Shorthand variants
    "doubleclick", "dblclick", "rightclick", "rclick",
    "tripleclick", "tclick", "goto",
    # Modifier-click variants (prevent typo correction)
    "shift-click", "cmd-click", "command-click", "opt-click",
    "option-click", "ctrl-click", "control-click",
})
_TYPO_THRESHOLD = 0.75


def _normalize_action(action):
    """Expand verb synonyms so the dispatcher sees canonical verbs.

    Handles both single-word synonyms ("tap Save" → "click Save"),
    multi-word phrases ("press on Save" → "click Save"),
    and typo correction ("clikc Save" → "click Save").
    """
    stripped = action.strip()
    lower = stripped.lower()

    # Try multi-word phrase synonyms first (longest match wins)
    for phrase, canonical in PHRASE_SYNONYMS.items():
        if lower.startswith(phrase + " "):
            rest = stripped[len(phrase):].strip()
            return f"{canonical} {rest}"
        if lower == phrase:
            return canonical

    # Single-word verb synonym
    parts = stripped.split(None, 1)
    if parts:
        verb_lower = parts[0].lower()
        if verb_lower in VERB_SYNONYMS:
            canonical = VERB_SYNONYMS[verb_lower]
            rest = parts[1] if len(parts) > 1 else ""
            return f"{canonical} {rest}".strip()

        # Typo tolerance: fuzzy-match unknown verbs against known verbs
        # Skip if action contains ">" (menu path like "Edit > Paste")
        if len(verb_lower) >= 3 and verb_lower not in _ALL_VERBS and ">" not in stripped:
            matches = difflib.get_close_matches(
                verb_lower, _ALL_VERBS, n=1, cutoff=_TYPO_THRESHOLD,
            )
            if matches:
                corrected = matches[0]
                corrected = VERB_SYNONYMS.get(corrected, corrected)
                rest = parts[1] if len(parts) > 1 else ""
                return f"{corrected} {rest}".strip()

    return stripped


# ---------------------------------------------------------------------------
# Ordinal parsing — "click the 2nd button", "the third link", etc.
# ---------------------------------------------------------------------------

ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "last": -1,
}

# Matches "1st", "2nd", "3rd", "4th", "11th", "22nd", etc.
ORDINAL_NUM_RE = re.compile(r"^(\d+)(?:st|nd|rd|th)$", re.IGNORECASE)


def _parse_ordinal(text):
    """Parse ordinal references from a click target.

    Returns (ordinal, role, remaining_label) or None if no ordinal found.
    ordinal is 1-based (or -1 for "last").

    Supported patterns:
        "the 2nd button"         → (2, "button", "")
        "3rd link"               → (3, "link", "")
        "the last checkbox"      → (-1, "checkbox", "")
        "first Save button"      → (1, "button", "Save")
        "button 3"               → (3, "button", "")
        "second link on the page"→ (2, "link", "")
    """
    words = text.split()
    if not words:
        return None

    # Strip leading "the"
    if words[0].lower() == "the":
        words = words[1:]
    if not words:
        return None

    role_words = ROLE_WORDS

    # Pattern 1: "<ordinal> [label...] <role>" — "2nd button", "third Save button"
    ordinal = _word_to_ordinal(words[0])
    if ordinal is not None and len(words) >= 2:
        # Find the role word (usually the last word)
        for i in range(len(words) - 1, 0, -1):
            if words[i].lower() in role_words:
                role = words[i].lower()
                label = " ".join(words[1:i]).strip()
                return (ordinal, role, label)

    # Pattern 2: "<role> <number>" — "button 3", "link 2"
    if len(words) >= 2 and words[0].lower() in role_words and words[-1].isdigit():
        role = words[0].lower()
        ordinal = int(words[-1])
        label = " ".join(words[1:-1]).strip()
        return (ordinal, role, label)

    return None


def _word_to_ordinal(word):
    """Convert a word to an ordinal number, or None."""
    lower = word.lower()
    if lower in ORDINAL_WORDS:
        return ORDINAL_WORDS[lower]
    m = ORDINAL_NUM_RE.match(lower)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Spatial element resolution — "button near search", "field below Username"
# ---------------------------------------------------------------------------

SPATIAL_RELATIONS = [
    (re.compile(r'^(.+?)\s+(?:below|under|beneath|underneath)\s+(.+)$', re.IGNORECASE), 'below'),
    (re.compile(r'^(.+?)\s+(?:above|over)\s+(.+)$', re.IGNORECASE), 'above'),
    (re.compile(r'^(.+?)\s+(?:left\s+of|to\s+the\s+left\s+of)\s+(.+)$', re.IGNORECASE), 'left'),
    (re.compile(r'^(.+?)\s+(?:right\s+of|to\s+the\s+right\s+of)\s+(.+)$', re.IGNORECASE), 'right'),
    (re.compile(r'^(.+?)\s+(?:near|beside|next\s+to|by|close\s+to)\s+(.+)$', re.IGNORECASE), 'near'),
]

REGION_PATTERNS = [
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:top[- ]?right|upper[- ]?right)', re.IGNORECASE), 'top-right'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:top[- ]?left|upper[- ]?left)', re.IGNORECASE), 'top-left'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:bottom[- ]?right|lower[- ]?right)', re.IGNORECASE), 'bottom-right'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:bottom[- ]?left|lower[- ]?left)', re.IGNORECASE), 'bottom-left'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:top|upper)(?:\s+(?:area|region|part|corner|half))?$', re.IGNORECASE), 'top'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:bottom|lower)(?:\s+(?:area|region|part|corner|half))?$', re.IGNORECASE), 'bottom'),
    (re.compile(r'^(.+?)\s+(?:in|at)\s+(?:the\s+)?(?:center|middle|centre)', re.IGNORECASE), 'center'),
]


def _parse_spatial(text):
    """Parse spatial references from a click target.

    Returns (search_term, relation, reference) or None.

    Patterns:
        "button near search"          → ("button", "near", "search")
        "field below Username"        → ("field", "below", "Username")
        "close button above toolbar"  → ("close button", "above", "toolbar")
        "button in top-right"         → ("button", "region", "top-right")
    """
    stripped = text.strip()
    if stripped.lower().startswith("the "):
        stripped = stripped[4:]

    # Try directional/proximity patterns
    for pattern, relation in SPATIAL_RELATIONS:
        m = pattern.match(stripped)
        if m:
            search = m.group(1).strip()
            reference = m.group(2).strip()
            if reference.lower().startswith("the "):
                reference = reference[4:]
            if search and reference:
                return (search, relation, reference)

    # Try region patterns
    for pattern, region in REGION_PATTERNS:
        m = pattern.match(stripped)
        if m:
            search = m.group(1).strip()
            if search:
                return (search, "region", region)

    return None


def _filter_by_search(elements, search):
    """Filter elements by a search term — can be a role name, a label, or both."""
    search_lower = search.lower().strip()
    words = search_lower.split()

    role_word = None
    label_filter = ""

    if search_lower in ROLE_WORDS:
        role_word = search_lower
    elif len(words) >= 2 and words[-1] in ROLE_WORDS:
        role_word = words[-1]
        label_filter = " ".join(words[:-1])
    elif len(words) >= 2 and words[0] in ROLE_WORDS:
        role_word = words[0]
        label_filter = " ".join(words[1:])

    if role_word:
        ax_role = ROLE_MAP.get(role_word)
        if ax_role:
            matches = [el for el in elements if el.get("_ax_role") == ax_role]
        else:
            matches = [el for el in elements if role_word in el.get("role", "").lower()]
        if label_filter:
            labeled = [el for el in matches if label_filter in el.get("label", "").lower()]
            if labeled:
                matches = labeled
        return matches

    # Search by label
    exact = [el for el in elements if search_lower == el.get("label", "").lower()]
    if exact:
        return exact
    return [el for el in elements if search_lower in el.get("label", "").lower()]


# ---------------------------------------------------------------------------
# Container scoping — "click X in the row with/containing Y"
# ---------------------------------------------------------------------------

_CONTAINER_RE = re.compile(
    r'^(.+?)\s+in\s+(?:the\s+)?row\s+(?:with|containing|that\s+(?:has|contains))\s+(.+)$',
    re.IGNORECASE,
)
_CONTAINER_ROW_NUM_RE = re.compile(
    r'^(.+?)\s+in\s+(?:the\s+)?row\s+(\d+)$',
    re.IGNORECASE,
)


def _parse_container(text):
    """Parse container-scoped click: 'delete in the row with Alice'.

    Returns (target, row_match, row_index) or None.
    - target: what to click inside the row
    - row_match: text to find the row by (or None for row index)
    - row_index: 1-based row number (or None for text match)
    """
    stripped = text.strip()
    if stripped.lower().startswith("the "):
        stripped = stripped[4:]

    # "X in row 3"
    m = _CONTAINER_ROW_NUM_RE.match(stripped)
    if m:
        return (m.group(1).strip(), None, int(m.group(2)))

    # "X in the row with/containing Y"
    m = _CONTAINER_RE.match(stripped)
    if m:
        return (m.group(1).strip(), m.group(2).strip(), None)

    return None


# Key name mappings for "press" intent
KEY_ALIASES = {
    "cmd": "command", "command": "command",
    "ctrl": "control", "control": "control",
    "alt": "option", "opt": "option", "option": "option",
    "shift": "shift",
    "enter": "return", "return": "return",
    "esc": "escape", "escape": "escape",
    "tab": "tab",
    "space": "space",
    "delete": "delete", "backspace": "delete",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "home": "home", "end": "end",
    "pageup": "pageup", "pagedown": "pagedown",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
    "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
}


# ---------------------------------------------------------------------------
# Field parsing for "fill" intent
# ---------------------------------------------------------------------------

def _parse_fields(text):
    """Parse 'Name=Ferran, Email=f@x.com' into [(key, value), ...].

    Handles quoted values: Name="John Doe", Age=30
    """
    pairs = []
    # Split on comma, but respect quotes
    parts = re.split(r',\s*(?=[^"]*(?:"[^"]*"[^"]*)*$)', text)

    for part in parts:
        part = part.strip()
        if not part:
            continue
        eq = part.find("=")
        if eq == -1:
            continue
        key = part[:eq].strip()
        value = part[eq + 1:].strip()
        value = _strip_quotes(value)
        if key:
            pairs.append((key, value))

    return pairs


def _strip_quotes(text):
    """Strip surrounding quotes if present."""
    if len(text) >= 2:
        if (text[0] == '"' and text[-1] == '"') or (text[0] == "'" and text[-1] == "'"):
            return text[1:-1]
    return text


# ---------------------------------------------------------------------------
# Modifier key resolution
# ---------------------------------------------------------------------------

_MODIFIER_MAP = {
    "shift": "shift",
    "cmd": "command", "command": "command",
    "opt": "option", "option": "option", "alt": "option",
    "ctrl": "control", "control": "control",
}


def _resolve_modifiers(modifiers):
    """Resolve modifier shorthand names to pyautogui key names."""
    return [_MODIFIER_MAP.get(m.lower(), m.lower()) for m in modifiers]
