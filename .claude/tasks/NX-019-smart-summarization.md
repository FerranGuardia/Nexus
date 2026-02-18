# NX-019 — Smart Result Summarization

**Track**: Brain (cortex)
**Priority**: MEDIUM — reduces tokens, improves Claude's decision speed
**Effort**: Medium
**Depends on**: NX-001 (compact output, done)

---

## Problem

Even with compact output (NX-001), Nexus returns **every** element. Claude must scan 50-200 lines to understand the screen. For most tasks, Claude only needs a high-level picture:

- "What app am I looking at?"
- "What are the main actions available?"
- "Is there an error or dialog?"
- "Where is the focus?"

The full element list is only needed when Claude is searching for a specific control.

## Goal

Add a **summary layer** that returns a natural-language screen description + key stats, with the full element list available on demand.

## Scope

### 1. Auto-Summary Header
Every `describe` response starts with a summary block:
```
SUMMARY: Chrome — google.com/search | 3 inputs, 12 links, 4 buttons | Focus: Search box | No errors
ELEMENTS (48 total):
[Btn] Search | (450,300) ...
...
```

### 2. Summary-Only Mode
`describe --summary` returns ONLY the summary, no element list:
```json
{
  "summary": {
    "app": "Chrome",
    "title": "Google Search",
    "url": "https://google.com/search",
    "element_counts": {"button": 4, "input": 3, "link": 12, "text": 29},
    "focused": {"name": "Search", "role": "input"},
    "errors": [],
    "dialogs": [],
    "notable": ["Search results loaded", "10 organic results visible"]
  }
}
```

### 3. Relevance Scoring
Rank elements by likely importance:
- **High**: focused element, errors, dialogs, primary action buttons (Submit, Save, OK, Cancel)
- **Medium**: form inputs, navigation links, headings
- **Low**: decorative text, icons, separators, status bar items
- In summary mode, only high+medium elements listed. Low filtered out.

### 4. Spatial Grouping
Instead of flat list, group by screen region:
```
TOP BAR: [Btn] Back, [Btn] Forward, [Edit] URL bar *focused*, [Btn] Menu
SIDEBAR: [Link] Home, [Link] Settings, [Link] Profile
MAIN CONTENT: [Heading] Search Results, [Link] Result 1, [Link] Result 2...
BOTTOM: [Text] "10 results found"
```
- Regions detected by y-coordinate clustering (top 10% = toolbar, etc.)
- Or by parent container analysis in UIA/CDP tree

### 5. Web-Specific Intelligence
For web pages, add structured extraction:
- Page type detection: "search results", "form", "article", "dashboard", "login"
- Form state: "2/5 fields filled, Submit button enabled"
- Navigation state: "on page 2 of 5", "tab 3 of 4 selected"

## Key Design Decisions
- Summary is always generated (cheap computation), shown by default in compact mode
- `--summary` = summary only, `--full` = everything, default = summary + elements
- Relevance scoring is rule-based (role + name pattern matching), not ML
- Spatial grouping is approximate (y-coordinate bands) — good enough for Claude

## Files
- `nexus/cortex/` — new module for brain-layer processing (finally using cortex!)
- `nexus/cortex/summarize.py` — summary generation, relevance scoring, spatial grouping
- `nexus/oculus/uia.py` — pipe describe output through summarizer
- `nexus/oculus/web.py` — pipe web-describe output through summarizer

## Success Criteria
- `describe --summary` returns ~5 lines instead of 50-200
- Claude can decide "I need to click Save" from summary alone without scanning full tree
- Spatial grouping gives Claude layout awareness without coordinates
