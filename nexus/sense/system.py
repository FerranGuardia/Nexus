"""System dialog detection via CGWindowListCopyWindowInfo.

Detects Gatekeeper, SecurityAgent, and permission dialogs that are invisible
to the accessibility tree. Combines window detection with OCR for identification.
"""

from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
)


# System processes that display dialogs invisible to AX
SYSTEM_DIALOG_PROCESSES = frozenset({
    "CoreServicesUIAgent",    # Gatekeeper (quarantine, app verification)
    "SecurityAgent",          # Password prompts, keychain, admin auth
    "UserNotificationCenter", # Folder access, permission dialogs
})

# Minimum window size to be considered a real dialog (not a stub)
MIN_DIALOG_WIDTH = 50
MIN_DIALOG_HEIGHT = 50


def detect_system_dialogs():
    """Poll CGWindowListCopyWindowInfo for system dialog windows.

    Returns:
        List of dicts: [{process, pid, title, bounds, layer, on_screen}]
        Empty list if no system dialogs are visible.
    """
    try:
        windows = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
        )
    except Exception:
        return []

    if not windows:
        return []

    dialogs = []
    for w in windows:
        owner = w.get("kCGWindowOwnerName", "")
        if owner not in SYSTEM_DIALOG_PROCESSES:
            continue

        bounds = w.get("kCGWindowBounds", {})
        width = bounds.get("Width", 0)
        height = bounds.get("Height", 0)

        # Skip tiny/stub windows
        if width < MIN_DIALOG_WIDTH or height < MIN_DIALOG_HEIGHT:
            continue

        dialogs.append({
            "process": owner,
            "pid": w.get("kCGWindowOwnerPID", 0),
            "title": w.get("kCGWindowName", ""),
            "bounds": {
                "x": bounds.get("X", 0),
                "y": bounds.get("Y", 0),
                "w": width,
                "h": height,
            },
            "layer": w.get("kCGWindowLayer", 0),
            "on_screen": w.get("kCGWindowIsOnscreen", False),
            "window_id": w.get("kCGWindowNumber", 0),
        })

    return dialogs


def classify_dialog(dialog, ocr_results=None):
    """Classify a system dialog by type using process name and OCR text.

    Args:
        dialog: Dict from detect_system_dialogs().
        ocr_results: Optional list from ocr.ocr_region() for the dialog area.

    Returns:
        dict with: type, description, suggested_action, buttons[]
    """
    process = dialog["process"]
    ocr_text = ""
    if ocr_results:
        ocr_text = " ".join(r["text"] for r in ocr_results).lower()

    # CoreServicesUIAgent patterns
    if process == "CoreServicesUIAgent":
        if any(phrase in ocr_text for phrase in [
            "downloaded from the internet",
            "descargada de internet",
            "apple cannot check",
            "developer cannot be verified",
            "no se puede verificar",
        ]):
            return {
                "type": "gatekeeper",
                "description": "Gatekeeper: app downloaded from internet",
                "suggested_action": "Click Open to allow, or Cancel to block",
                "buttons": _find_buttons(ocr_results, ["open", "abrir", "cancel", "cancelar"]),
            }
        if any(phrase in ocr_text for phrase in [
            "verifying", "verificando",
            "checking", "comprobando",
        ]):
            return {
                "type": "gatekeeper_verifying",
                "description": "Gatekeeper: verifying app (wait for it to finish)",
                "suggested_action": "Wait — this dialog dismisses itself",
                "buttons": [],
            }
        return {
            "type": "system_prompt",
            "description": f"System prompt from CoreServicesUIAgent",
            "suggested_action": "Review the dialog text and choose an action",
            "buttons": _find_buttons(ocr_results, ["ok", "cancel", "open", "allow"]),
        }

    # SecurityAgent patterns
    if process == "SecurityAgent":
        if any(phrase in ocr_text for phrase in [
            "password", "contraseña",
            "authenticate", "autenticar",
        ]):
            return {
                "type": "password_prompt",
                "description": "Password required for privileged operation",
                "suggested_action": "User must enter password manually",
                "buttons": _find_buttons(ocr_results, ["ok", "cancel", "unlock", "allow", "desbloquear", "permitir"]),
            }
        return {
            "type": "auth_prompt",
            "description": "Authentication required",
            "suggested_action": "User must authenticate",
            "buttons": _find_buttons(ocr_results, ["ok", "cancel", "allow", "deny"]),
        }

    # UserNotificationCenter
    if process == "UserNotificationCenter":
        if any(phrase in ocr_text for phrase in [
            "find devices", "encontrar dispositivos",
            "local network", "red local",
        ]):
            return {
                "type": "network_permission",
                "description": "App wants to find devices on local network",
                "suggested_action": "Allow or Don't Allow — user decision",
                "buttons": _find_buttons(ocr_results, ["allow", "don't allow", "permitir", "no permitir"]),
            }
        if any(phrase in ocr_text for phrase in [
            "access", "acceder",
            "folder", "carpeta",
        ]):
            return {
                "type": "folder_permission",
                "description": "App requesting folder access",
                "suggested_action": "Allow or Don't Allow — user decision",
                "buttons": _find_buttons(ocr_results, ["ok", "allow", "don't allow", "permitir"]),
            }
        return {
            "type": "permission_prompt",
            "description": "Permission dialog",
            "suggested_action": "Review and choose",
            "buttons": _find_buttons(ocr_results, ["ok", "allow", "cancel", "deny"]),
        }

    return {
        "type": "unknown",
        "description": f"System dialog from {process}",
        "suggested_action": "Review the dialog",
        "buttons": [],
    }


def _find_buttons(ocr_results, button_labels):
    """Find button-like text in OCR results matching common button labels.

    Returns list of {label, center_x, center_y} for each found button.
    """
    if not ocr_results:
        return []

    buttons = []
    for label in button_labels:
        label_lower = label.lower()
        for r in ocr_results:
            text_lower = r["text"].lower().strip()
            if text_lower == label_lower or label_lower in text_lower:
                buttons.append({
                    "label": r["text"],
                    "center_x": r["center"]["x"],
                    "center_y": r["center"]["y"],
                })
                break  # One match per button label

    return buttons


def format_system_dialogs(dialogs, classifications=None):
    """Format system dialogs for see() output.

    Args:
        dialogs: List from detect_system_dialogs().
        classifications: Optional list from classify_dialog() (same length).

    Returns:
        Formatted string for see() output.
    """
    if not dialogs:
        return ""

    lines = [f"SYSTEM DIALOGS ({len(dialogs)}):"]

    for i, d in enumerate(dialogs):
        classification = classifications[i] if classifications and i < len(classifications) else None

        if classification:
            dtype = classification["type"].upper()
            desc = classification["description"]
            lines.append(f"  [{dtype}] {desc}")
            lines.append(f"    Process: {d['process']} (pid {d['pid']})")
            lines.append(f"    Bounds: x={d['bounds']['x']}, y={d['bounds']['y']}, "
                        f"w={d['bounds']['w']}, h={d['bounds']['h']}")
            if classification["suggested_action"]:
                lines.append(f"    Action: {classification['suggested_action']}")
            if classification["buttons"]:
                btn_strs = [f"\"{b['label']}\" @ {b['center_x']},{b['center_y']}"
                           for b in classification["buttons"]]
                lines.append(f"    Buttons: {', '.join(btn_strs)}")
        else:
            lines.append(f"  {d['process']}: {d['title'] or '(untitled)'}")
            lines.append(f"    Bounds: x={d['bounds']['x']}, y={d['bounds']['y']}, "
                        f"w={d['bounds']['w']}, h={d['bounds']['h']}")

    return "\n".join(lines)
