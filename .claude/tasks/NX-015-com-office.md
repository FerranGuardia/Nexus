# NX-015: COM Office Tools (Excel, Word, Outlook)

**Branch:** `task/NX-015-com-office`
**Status:** PENDING
**Depends on:** None (com-shell pattern already established)
**Tracking:** `.claude/tasks/INDEX.md`
**Started:** —
**Finished:** —

---

> **In plain English:** Office apps have rich COM APIs — no need to click through the UI.
> Add commands for Excel, Word, and Outlook that work directly with documents via COM objects.

---

## What

### H2: `com-excel` — Excel without clicking
- `com-excel --open PATH` — open a workbook (or list open workbooks)
- `com-excel --read RANGE` — read cell range (e.g., "A1:D10")
- `com-excel --write CELL VALUE` — write to a cell
- `com-excel --sheet NAME` — switch active sheet
- Uses `win32com.client.Dispatch("Excel.Application")`
- Can run headless (`Visible=False`) — no window needed

### H3: `com-word` — Word document access
- `com-word --open PATH` — open a document
- `com-word --read` — return full text content
- `com-word --read-range START END` — return text from paragraph range
- Uses `win32com.client.Dispatch("Word.Application")`

### H4: `com-outlook` — Email access
- `com-outlook --inbox N` — read last N inbox items (subject, sender, date, preview)
- `com-outlook --read ID` — read full email body
- `com-outlook --send TO SUBJECT BODY` — send an email
- Uses `win32com.client.Dispatch("Outlook.Application")` with MAPI namespace

## Why

Office automation via UI is slow and fragile. COM gives direct access to the document object model. pywin32 is already installed — zero new dependencies. Follows the "Code-First, UI-Fallback" design principle.

## Where

- **Read:** `nexus/digitus/system.py` (com-shell pattern)
- **Write:**
  - `nexus/digitus/office.py` (new) — `com_excel()`, `com_word()`, `com_outlook()`
  - `nexus/run.py` — add `com-excel`, `com-word`, `com-outlook` subcommands
  - `nexus/tests/test_com_office.py` (new) — tests (marked with `@pytest.mark.office`)

## Validation

- [ ] `com-excel --open test.xlsx --read A1:C5` returns cell data
- [ ] `com-excel --write B2 "hello"` writes to a cell
- [ ] `com-word --open test.docx --read` returns document text
- [ ] `com-outlook --inbox 5` returns last 5 inbox items
- [ ] Works with Office not running (COM starts it automatically)
- [ ] Headless mode: Excel/Word operations don't flash windows
- [ ] Returns clear error when Office is not installed
- [ ] Tests marked with `office` marker (skip on machines without Office)

---

## Not in scope

- PowerPoint COM automation (low demand, add later if needed)
- Advanced Excel features (charts, formulas, macros)
- Outlook calendar/contacts access
