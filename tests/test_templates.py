"""Tests for dialog templates (nexus/sense/templates.py)."""

import pytest

from nexus.sense import templates


class TestMatchTemplate:
    def test_gatekeeper_open(self):
        tid, tmpl = templates.match_template(
            "Docker is an app downloaded from the internet. Are you sure?",
            process="CoreServicesUIAgent",
        )
        assert tid == "gatekeeper_open"
        assert "open" in tmpl["buttons"]

    def test_gatekeeper_spanish(self):
        tid, tmpl = templates.match_template(
            "aplicación descargada de internet",
            process="CoreServicesUIAgent",
        )
        assert tid == "gatekeeper_open"

    def test_gatekeeper_verifying(self):
        tid, _ = templates.match_template("Verifying Docker Desktop...", process="CoreServicesUIAgent")
        assert tid == "gatekeeper_verifying"

    def test_password_prompt(self):
        tid, tmpl = templates.match_template(
            "Enter your password to allow this",
            process="SecurityAgent",
        )
        assert tid == "password_prompt"
        assert "ok" in tmpl["buttons"]

    def test_keychain_access(self):
        tid, _ = templates.match_template(
            "App wants to access the keychain",
            process="SecurityAgent",
        )
        assert tid == "keychain_access"

    def test_network_permission(self):
        tid, _ = templates.match_template(
            "Docker wants to find devices on your local network",
            process="UserNotificationCenter",
        )
        assert tid == "network_permission"

    def test_folder_access(self):
        tid, _ = templates.match_template(
            "App would like to access files in your Documents",
            process="UserNotificationCenter",
        )
        assert tid == "folder_access"

    def test_save_dialog(self):
        tid, _ = templates.match_template("Do you want to save changes?")
        assert tid == "save_dialog"

    def test_no_match(self):
        tid, tmpl = templates.match_template("just some random text")
        assert tid is None
        assert tmpl is None

    def test_empty_text(self):
        tid, tmpl = templates.match_template("")
        assert tid is None

    def test_none_text(self):
        tid, tmpl = templates.match_template(None)
        assert tid is None

    def test_process_filter(self):
        # Password text but wrong process should not match password_prompt
        tid, _ = templates.match_template("password", process="UserNotificationCenter")
        assert tid != "password_prompt"

    def test_damaged_app(self):
        tid, _ = templates.match_template(
            '"Docker" is damaged and can\'t be opened',
            process="CoreServicesUIAgent",
        )
        assert tid == "gatekeeper_damaged"


class TestResolveButton:
    def test_basic_resolve(self):
        tmpl = templates.DIALOG_TEMPLATES["gatekeeper_open"]
        bounds = {"x": 100, "y": 200, "w": 400, "h": 300}
        x, y = templates.resolve_button(tmpl, "open", bounds)
        # 0.75 * 400 + 100 = 400
        assert x == 400
        # 0.85 * 300 + 200 = 455
        assert y == 455

    def test_cancel_button(self):
        tmpl = templates.DIALOG_TEMPLATES["gatekeeper_open"]
        bounds = {"x": 100, "y": 200, "w": 400, "h": 300}
        x, y = templates.resolve_button(tmpl, "cancel", bounds)
        assert x == 320  # 0.55 * 400 + 100
        assert y == 455  # 0.85 * 300 + 200

    def test_missing_button(self):
        tmpl = templates.DIALOG_TEMPLATES["gatekeeper_open"]
        bounds = {"x": 0, "y": 0, "w": 400, "h": 300}
        result = templates.resolve_button(tmpl, "nonexistent", bounds)
        assert result is None

    def test_zero_bounds(self):
        tmpl = templates.DIALOG_TEMPLATES["gatekeeper_open"]
        bounds = {"x": 0, "y": 0, "w": 0, "h": 0}
        x, y = templates.resolve_button(tmpl, "open", bounds)
        assert x == 0
        assert y == 0


class TestResolveField:
    def test_password_field(self):
        tmpl = templates.DIALOG_TEMPLATES["password_prompt"]
        bounds = {"x": 100, "y": 200, "w": 400, "h": 300}
        x, y = templates.resolve_field(tmpl, "password", bounds)
        assert x == 320  # 0.55 * 400 + 100
        assert y == 395  # 0.65 * 300 + 200

    def test_missing_field(self):
        tmpl = templates.DIALOG_TEMPLATES["gatekeeper_open"]
        bounds = {"x": 0, "y": 0, "w": 400, "h": 300}
        result = templates.resolve_field(tmpl, "password", bounds)
        assert result is None


class TestAllTemplates:
    def test_returns_dict(self):
        result = templates.all_templates()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_all_have_descriptions(self):
        result = templates.all_templates()
        for tid, desc in result.items():
            assert isinstance(desc, str)
            assert len(desc) > 0

    def test_known_templates_present(self):
        result = templates.all_templates()
        assert "gatekeeper_open" in result
        assert "password_prompt" in result
        assert "network_permission" in result


class TestTemplateIntegrity:
    """Verify all templates are well-formed."""

    def test_all_templates_have_match_phrases(self):
        for tid, tmpl in templates.DIALOG_TEMPLATES.items():
            assert "match_phrases" in tmpl, f"{tid} missing match_phrases"
            assert len(tmpl["match_phrases"]) > 0, f"{tid} has empty match_phrases"

    def test_all_templates_have_description(self):
        for tid, tmpl in templates.DIALOG_TEMPLATES.items():
            assert "description" in tmpl, f"{tid} missing description"

    def test_all_buttons_have_rel_coords(self):
        for tid, tmpl in templates.DIALOG_TEMPLATES.items():
            for btn_key, btn in tmpl.get("buttons", {}).items():
                assert "rel_x" in btn, f"{tid}.{btn_key} missing rel_x"
                assert "rel_y" in btn, f"{tid}.{btn_key} missing rel_y"
                assert 0 <= btn["rel_x"] <= 1, f"{tid}.{btn_key} rel_x out of range"
                assert 0 <= btn["rel_y"] <= 1, f"{tid}.{btn_key} rel_y out of range"

    def test_all_buttons_have_labels(self):
        for tid, tmpl in templates.DIALOG_TEMPLATES.items():
            for btn_key, btn in tmpl.get("buttons", {}).items():
                assert "labels" in btn, f"{tid}.{btn_key} missing labels"
                assert len(btn["labels"]) > 0, f"{tid}.{btn_key} has empty labels"
