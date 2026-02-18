# NX-014: Web Research Flow

**Branch:** `task/NX-014-web-research`
**Status:** PENDING
**Depends on:** web-markdown (already implemented)
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** Claude can read a single web page, but can't do a search-visit-extract
> research loop autonomously. Add a command that searches the web, visits top results, and extracts
> clean content from each.

---

## What

- Add `web-research "query"` command that:
  1. Navigates to DuckDuckGo/Brave Search with the query
  2. Extracts organic result links (top 3-5)
  3. Visits each result page
  4. Extracts content with Readability.js (existing `web-markdown` logic)
  5. Returns structured `[{url, title, content}]` per source
- Cap content per page (~4000 chars) to avoid context explosion
- Add `--engine duckduckgo|brave` flag (default: duckduckgo)
- Add `--max N` flag for number of results to visit (default: 3)
- Block ad/tracker URLs for faster page loads

## Why

Automated research loops are a key capability for Claude as an autonomous agent. Instead of asking the user to search and paste results, Claude can research topics independently. Pattern from WebVoyager / Browser-Use.

## Where

- **Read:** `nexus/oculus/web.py` (web-markdown logic), `nexus/cdp.py`
- **Write:**
  - `nexus/oculus/web.py` — add `web_research()` function
  - `nexus/run.py` — add `web-research` subcommand with query, --engine, --max args
  - `nexus/tests/test_web_research.py` (new) — tests

## Validation

- [ ] `web-research "python asyncio tutorial"` returns 3+ extracted articles
- [ ] Each result has url, title, and clean extracted content
- [ ] Content is capped at configured per-page limit
- [ ] `--max 5` visits 5 results instead of default 3
- [ ] `--engine brave` uses Brave Search instead of DuckDuckGo
- [ ] Gracefully handles: paywalled pages, JS-heavy SPAs, 404s
- [ ] Total execution time < 30 seconds for 3 results
- [ ] E2E test with a real search query

---

## Not in scope

- Caching search results across sessions (future brain-level feature)
- Summarization of results (Claude does that)
