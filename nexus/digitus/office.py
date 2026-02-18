"""Digitus Office — COM automation for Excel, Word, and Outlook.

Uses win32com.client to interact with Office apps directly via COM objects.
No UI clicking needed — works with documents programmatically.
Can run headless (no visible window) for Excel and Word.

Pure functions: params → dict. COM objects are created and released per call.
"""

import os


def com_excel(action: str = "list", path: str | None = None,
              range_: str | None = None, cell: str | None = None,
              value: str | None = None, sheet: str | None = None) -> dict:
    """Excel automation via COM.

    Actions:
        list: list open workbooks (or open one if path given)
        read: read a cell range (e.g. "A1:D10")
        write: write a value to a cell (e.g. cell="B2", value="hello")
        sheets: list sheets in the active workbook
    """
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    try:
        try:
            xl = win32com.client.Dispatch("Excel.Application")
        except Exception as e:
            return {"command": "com-excel", "ok": False, "error": "Cannot start Excel: %s" % str(e)}

        # Open workbook if path given
        if path:
            path = os.path.abspath(path)
            try:
                wb = xl.Workbooks.Open(path)
            except Exception as e:
                return {"command": "com-excel", "ok": False, "error": "Cannot open '%s': %s" % (path, str(e))}
        else:
            wb = xl.ActiveWorkbook
            if wb is None:
                # List nothing if no workbook open
                if action == "list":
                    workbooks = []
                    for i in range(1, xl.Workbooks.Count + 1):
                        workbooks.append({"name": xl.Workbooks(i).Name, "path": xl.Workbooks(i).FullName})
                    return {"command": "com-excel", "action": "list", "workbooks": workbooks, "count": len(workbooks)}
                return {"command": "com-excel", "ok": False, "error": "No active workbook. Provide a --path to open one."}

        # Switch sheet if requested
        if sheet:
            try:
                ws = wb.Sheets(sheet)
                ws.Activate()
            except Exception as e:
                return {"command": "com-excel", "ok": False, "error": "Sheet '%s' not found: %s" % (sheet, str(e))}
        else:
            ws = wb.ActiveSheet

        if action == "list":
            workbooks = []
            for i in range(1, xl.Workbooks.Count + 1):
                workbooks.append({"name": xl.Workbooks(i).Name, "path": xl.Workbooks(i).FullName})
            return {
                "command": "com-excel",
                "action": "list",
                "active": wb.Name,
                "sheet": ws.Name,
                "workbooks": workbooks,
                "count": len(workbooks),
            }

        elif action == "sheets":
            sheets = []
            for i in range(1, wb.Sheets.Count + 1):
                sheets.append(wb.Sheets(i).Name)
            return {"command": "com-excel", "action": "sheets", "workbook": wb.Name, "sheets": sheets}

        elif action == "read":
            if not range_:
                return {"command": "com-excel", "ok": False, "error": "read action requires --range (e.g. A1:D10)"}
            try:
                rng = ws.Range(range_)
                data = rng.Value
                # Convert to list of lists (single cell returns scalar)
                if data is None:
                    rows = [[None]]
                elif not isinstance(data, tuple):
                    rows = [[data]]
                else:
                    rows = [list(row) for row in data]
                return {
                    "command": "com-excel",
                    "action": "read",
                    "sheet": ws.Name,
                    "range": range_,
                    "data": rows,
                    "rows": len(rows),
                    "cols": len(rows[0]) if rows else 0,
                }
            except Exception as e:
                return {"command": "com-excel", "ok": False, "error": "Read failed: %s" % str(e)}

        elif action == "write":
            if not cell or value is None:
                return {"command": "com-excel", "ok": False, "error": "write action requires --cell and --value"}
            try:
                ws.Range(cell).Value = value
                return {
                    "command": "com-excel",
                    "action": "write",
                    "sheet": ws.Name,
                    "cell": cell,
                    "value": value,
                    "ok": True,
                }
            except Exception as e:
                return {"command": "com-excel", "ok": False, "error": "Write failed: %s" % str(e)}

        else:
            return {"command": "com-excel", "ok": False, "error": "Unknown action: %s" % action}

    finally:
        pythoncom.CoUninitialize()


def com_word(action: str = "read", path: str | None = None,
             start: int | None = None, end: int | None = None) -> dict:
    """Word document access via COM.

    Actions:
        read: return full text (or paragraph range with start/end)
        info: document metadata (pages, words, paragraphs)
    """
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    try:
        try:
            word = win32com.client.Dispatch("Word.Application")
        except Exception as e:
            return {"command": "com-word", "ok": False, "error": "Cannot start Word: %s" % str(e)}

        if path:
            path = os.path.abspath(path)
            try:
                doc = word.Documents.Open(path)
            except Exception as e:
                return {"command": "com-word", "ok": False, "error": "Cannot open '%s': %s" % (path, str(e))}
        else:
            doc = word.ActiveDocument
            if doc is None:
                return {"command": "com-word", "ok": False, "error": "No active document. Provide a --path to open one."}

        if action == "info":
            return {
                "command": "com-word",
                "action": "info",
                "name": doc.Name,
                "path": doc.FullName,
                "pages": doc.ComputeStatistics(2),  # wdStatisticPages
                "words": doc.ComputeStatistics(0),   # wdStatisticWords
                "paragraphs": doc.Paragraphs.Count,
            }

        elif action == "read":
            paragraphs = []
            total = doc.Paragraphs.Count
            s = max(1, start or 1)
            e = min(total, end or total)

            for i in range(s, e + 1):
                text = doc.Paragraphs(i).Range.Text.strip()
                if text:
                    paragraphs.append(text)

            return {
                "command": "com-word",
                "action": "read",
                "name": doc.Name,
                "paragraphs": paragraphs,
                "range": [s, e],
                "total_paragraphs": total,
            }

        else:
            return {"command": "com-word", "ok": False, "error": "Unknown action: %s" % action}

    finally:
        pythoncom.CoUninitialize()


def com_outlook(action: str = "inbox", count: int = 5, item_id: str | None = None,
                to: str | None = None, subject: str | None = None, body: str | None = None) -> dict:
    """Outlook email access via COM.

    Actions:
        inbox: list last N inbox items
        read: read full email by EntryID
        send: send an email (requires to, subject, body)
    """
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    try:
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mapi = outlook.GetNamespace("MAPI")
        except Exception as e:
            return {"command": "com-outlook", "ok": False, "error": "Cannot start Outlook: %s" % str(e)}

        if action == "inbox":
            try:
                inbox = mapi.GetDefaultFolder(6)  # olFolderInbox
                messages = inbox.Items
                messages.Sort("[ReceivedTime]", True)
                items = []
                for i in range(min(count, messages.Count)):
                    msg = messages.Item(i + 1)
                    items.append({
                        "subject": getattr(msg, "Subject", ""),
                        "sender": getattr(msg, "SenderName", ""),
                        "date": str(getattr(msg, "ReceivedTime", "")),
                        "preview": getattr(msg, "Body", "")[:200],
                        "entry_id": getattr(msg, "EntryID", ""),
                        "unread": getattr(msg, "UnRead", False),
                    })
                return {
                    "command": "com-outlook",
                    "action": "inbox",
                    "items": items,
                    "count": len(items),
                }
            except Exception as e:
                return {"command": "com-outlook", "ok": False, "error": "Inbox read failed: %s" % str(e)}

        elif action == "read":
            if not item_id:
                return {"command": "com-outlook", "ok": False, "error": "read action requires --id (EntryID)"}
            try:
                msg = mapi.GetItemFromID(item_id)
                return {
                    "command": "com-outlook",
                    "action": "read",
                    "subject": msg.Subject,
                    "sender": msg.SenderName,
                    "date": str(msg.ReceivedTime),
                    "body": msg.Body[:8000],
                    "body_length": len(msg.Body),
                }
            except Exception as e:
                return {"command": "com-outlook", "ok": False, "error": "Read failed: %s" % str(e)}

        elif action == "send":
            if not to or not subject:
                return {"command": "com-outlook", "ok": False, "error": "send requires --to and --subject"}
            try:
                mail = outlook.CreateItem(0)  # olMailItem
                mail.To = to
                mail.Subject = subject
                mail.Body = body or ""
                mail.Send()
                return {
                    "command": "com-outlook",
                    "action": "send",
                    "ok": True,
                    "to": to,
                    "subject": subject,
                }
            except Exception as e:
                return {"command": "com-outlook", "ok": False, "error": "Send failed: %s" % str(e)}

        else:
            return {"command": "com-outlook", "ok": False, "error": "Unknown action: %s" % action}

    finally:
        pythoncom.CoUninitialize()
