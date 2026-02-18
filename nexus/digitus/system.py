"""Digitus System — PowerShell and COM automation commands."""

import json
import os
import subprocess


def ps_run(script: str) -> dict:
    """Execute a PowerShell command and return structured output."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=15,
        )
        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            data = result.stdout.strip()
        return {
            "command": "ps-run",
            "success": result.returncode == 0,
            "data": data,
            "stderr": result.stderr.strip() or None,
        }
    except subprocess.TimeoutExpired:
        return {"command": "ps-run", "success": False, "error": "Command timed out after 15 seconds"}
    except Exception as e:
        return {"command": "ps-run", "success": False, "error": str(e)}


def com_shell(path: str | None = None) -> dict:
    """Browse files via COM Shell.Application."""
    import win32com.client
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        folder_path = os.path.normpath(path) if path else os.path.expanduser("~")
        namespace = shell.NameSpace(folder_path)
        if not namespace:
            return {"command": "com-shell", "success": False, "error": "Cannot access path: %s" % folder_path}
        items = []
        for item in namespace.Items():
            items.append({
                "name": item.Name,
                "path": item.Path,
                "size": item.Size,
                "type": item.Type,
                "is_folder": item.IsFolder,
                "modified": str(namespace.GetDetailsOf(item, 3)),
            })
        return {
            "command": "com-shell",
            "success": True,
            "path": folder_path,
            "items": items,
            "count": len(items),
        }
    except Exception as e:
        return {"command": "com-shell", "success": False, "error": str(e)}
