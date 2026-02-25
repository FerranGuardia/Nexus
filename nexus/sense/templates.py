"""Known dialog templates — pre-computed button positions for standard macOS dialogs.

When OCR identifies a known dialog pattern, templates provide instant button
coordinates without needing full OCR processing. ~50ms lookup.
"""


# Template format: each template matches on OCR text patterns and provides
# button positions as relative coordinates (0-1) within the dialog bounds.
# Relative positions adapt to different dialog sizes and resolutions.

DIALOG_TEMPLATES = {
    "gatekeeper_open": {
        "match_phrases": [
            "downloaded from the internet",
            "descargada de internet",
            "developer cannot be verified",
            "no se puede verificar",
        ],
        "process": "CoreServicesUIAgent",
        "description": "Gatekeeper: app from internet — Open/Cancel",
        "buttons": {
            "open": {"rel_x": 0.75, "rel_y": 0.85, "labels": ["Open", "Abrir"]},
            "cancel": {"rel_x": 0.55, "rel_y": 0.85, "labels": ["Cancel", "Cancelar"]},
        },
    },
    "gatekeeper_verifying": {
        "match_phrases": [
            "verifying",
            "verificando",
            "checking its security",
        ],
        "process": "CoreServicesUIAgent",
        "description": "Gatekeeper: verifying app (auto-dismisses)",
        "buttons": {},  # No actionable buttons
    },
    "gatekeeper_damaged": {
        "match_phrases": [
            "is damaged",
            "está dañad",
            "move to trash",
            "mover a la papelera",
        ],
        "process": "CoreServicesUIAgent",
        "description": "Gatekeeper: app damaged — Move to Trash/Cancel",
        "buttons": {
            "trash": {"rel_x": 0.75, "rel_y": 0.85, "labels": ["Move to Trash", "Trasladar a la Papelera"]},
            "cancel": {"rel_x": 0.45, "rel_y": 0.85, "labels": ["Cancel", "Cancelar"]},
        },
    },
    "password_prompt": {
        "match_phrases": [
            "password",
            "contraseña",
            "wants to make changes",
            "quiere realizar cambios",
        ],
        "process": "SecurityAgent",
        "description": "Admin password required",
        "buttons": {
            "ok": {"rel_x": 0.82, "rel_y": 0.88, "labels": ["OK", "Aceptar", "Unlock", "Desbloquear"]},
            "cancel": {"rel_x": 0.65, "rel_y": 0.88, "labels": ["Cancel", "Cancelar"]},
        },
        "fields": {
            "password": {"rel_x": 0.55, "rel_y": 0.65},
        },
    },
    "keychain_access": {
        "match_phrases": [
            "keychain",
            "llavero",
            "wants to access",
            "quiere acceder",
        ],
        "process": "SecurityAgent",
        "description": "Keychain access request",
        "buttons": {
            "allow": {"rel_x": 0.82, "rel_y": 0.88, "labels": ["Allow", "Permitir"]},
            "always_allow": {"rel_x": 0.65, "rel_y": 0.88, "labels": ["Always Allow", "Permitir siempre"]},
            "deny": {"rel_x": 0.48, "rel_y": 0.88, "labels": ["Deny", "Denegar"]},
        },
    },
    "network_permission": {
        "match_phrases": [
            "find devices on your local network",
            "encontrar dispositivos en tu red local",
            "find and connect",
            "buscar y conectarse",
        ],
        "process": "UserNotificationCenter",
        "description": "Network discovery permission",
        "buttons": {
            "allow": {"rel_x": 0.75, "rel_y": 0.85, "labels": ["Allow", "Permitir"]},
            "dont_allow": {"rel_x": 0.45, "rel_y": 0.85, "labels": ["Don't Allow", "No permitir"]},
        },
    },
    "folder_access": {
        "match_phrases": [
            "would like to access",
            "quiere acceder a",
            "files in your",
            "archivos en tu",
        ],
        "process": "UserNotificationCenter",
        "description": "Folder access request",
        "buttons": {
            "ok": {"rel_x": 0.75, "rel_y": 0.85, "labels": ["OK", "Aceptar"]},
            "dont_allow": {"rel_x": 0.45, "rel_y": 0.85, "labels": ["Don't Allow", "No permitir"]},
        },
    },
    "save_dialog": {
        "match_phrases": [
            "do you want to save",
            "¿deseas guardar",
            "save changes",
            "guardar los cambios",
        ],
        "process": None,  # Can come from any app
        "description": "Save changes dialog",
        "buttons": {
            "save": {"rel_x": 0.82, "rel_y": 0.88, "labels": ["Save", "Guardar"]},
            "dont_save": {"rel_x": 0.55, "rel_y": 0.88, "labels": ["Don't Save", "No guardar"]},
            "cancel": {"rel_x": 0.38, "rel_y": 0.88, "labels": ["Cancel", "Cancelar"]},
        },
    },
}


def match_template(ocr_text, process=None):
    """Find the best matching template for OCR text + process name.

    Args:
        ocr_text: Combined text from OCR results (lowercased).
        process: Process name (e.g., "CoreServicesUIAgent").

    Returns:
        (template_id, template_dict) or (None, None) if no match.
    """
    ocr_lower = ocr_text.lower() if ocr_text else ""
    best_match = None
    best_score = 0

    for tid, template in DIALOG_TEMPLATES.items():
        # Process must match if specified in template
        if template["process"] and process and template["process"] != process:
            continue

        # Count matching phrases
        score = 0
        for phrase in template["match_phrases"]:
            if phrase.lower() in ocr_lower:
                score += 1

        if score > best_score:
            best_score = score
            best_match = tid

    if best_match:
        return best_match, DIALOG_TEMPLATES[best_match]
    return None, None


def resolve_button(template, button_key, dialog_bounds):
    """Resolve a button's absolute screen coordinates from template + dialog bounds.

    Args:
        template: Template dict from DIALOG_TEMPLATES.
        button_key: Button name (e.g., "open", "cancel").
        dialog_bounds: Dict {x, y, w, h} — dialog's screen position.

    Returns:
        (abs_x, abs_y) screen coordinates for clicking, or None.
    """
    buttons = template.get("buttons", {})
    btn = buttons.get(button_key)
    if not btn:
        return None

    dx = dialog_bounds.get("x", 0)
    dy = dialog_bounds.get("y", 0)
    dw = dialog_bounds.get("w", 0)
    dh = dialog_bounds.get("h", 0)

    abs_x = int(dx + btn["rel_x"] * dw)
    abs_y = int(dy + btn["rel_y"] * dh)
    return abs_x, abs_y


def resolve_field(template, field_key, dialog_bounds):
    """Resolve a field's absolute screen coordinates from template + dialog bounds.

    Args:
        template: Template dict from DIALOG_TEMPLATES.
        field_key: Field name (e.g., "password").
        dialog_bounds: Dict {x, y, w, h}.

    Returns:
        (abs_x, abs_y) screen coordinates for clicking, or None.
    """
    fields = template.get("fields", {})
    field = fields.get(field_key)
    if not field:
        return None

    dx = dialog_bounds.get("x", 0)
    dy = dialog_bounds.get("y", 0)
    dw = dialog_bounds.get("w", 0)
    dh = dialog_bounds.get("h", 0)

    abs_x = int(dx + field["rel_x"] * dw)
    abs_y = int(dy + field["rel_y"] * dh)
    return abs_x, abs_y


def all_templates():
    """Return all template IDs and descriptions for reference."""
    return {tid: t["description"] for tid, t in DIALOG_TEMPLATES.items()}
