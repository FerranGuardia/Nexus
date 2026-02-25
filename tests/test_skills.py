"""Tests for the skills system — CLI knowledge for common tasks."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from nexus.mind import skills


# ── Fixtures ──


@pytest.fixture
def bundled_dir(tmp_path):
    """Create a temp dir with bundled skills."""
    d = tmp_path / "bundled"
    d.mkdir()

    (d / "github.md").write_text(
        "---\n"
        "name: github\n"
        "description: GitHub via gh CLI\n"
        "requires: [gh]\n"
        "install: brew install gh\n"
        "---\n\n"
        "# GitHub Skill\n\nUse `gh` for GitHub.\n"
    )

    (d / "email.md").write_text(
        "---\n"
        "name: email\n"
        "description: Email via himalaya\n"
        "requires: [himalaya]\n"
        "---\n\n"
        "# Email Skill\n"
    )

    return d


@pytest.fixture
def user_dir(tmp_path):
    """Create a temp dir with user skills."""
    d = tmp_path / "user"
    d.mkdir()
    return d


@pytest.fixture
def patched_dirs(bundled_dir, user_dir):
    """Patch skill directories to use temp dirs."""
    with patch.object(skills, "BUNDLED_DIR", bundled_dir), \
         patch.object(skills, "SKILLS_DIR", user_dir):
        yield bundled_dir, user_dir


# ── list_skills ──


class TestListSkills:
    def test_lists_bundled_skills(self, patched_dirs):
        result = skills.list_skills()
        ids = [s["id"] for s in result]
        assert "github" in ids
        assert "email" in ids

    def test_returns_sorted_by_id(self, patched_dirs):
        result = skills.list_skills()
        ids = [s["id"] for s in result]
        assert ids == sorted(ids)

    def test_skill_metadata_parsed(self, patched_dirs):
        result = skills.list_skills()
        gh = next(s for s in result if s["id"] == "github")
        assert gh["name"] == "github"
        assert gh["description"] == "GitHub via gh CLI"
        assert gh["requires"] == ["gh"]
        assert gh["install"] == "brew install gh"
        assert gh["source"] == "bundled"

    def test_user_skill_overrides_bundled(self, patched_dirs):
        bundled_dir, user_dir = patched_dirs

        # User has their own github skill
        (user_dir / "github.md").write_text(
            "---\n"
            "name: github\n"
            "description: My custom GitHub skill\n"
            "requires: [gh]\n"
            "---\n\n"
            "# Custom\n"
        )

        result = skills.list_skills()
        gh = next(s for s in result if s["id"] == "github")
        assert gh["source"] == "user"
        assert gh["description"] == "My custom GitHub skill"

    def test_user_skill_adds_new(self, patched_dirs):
        _, user_dir = patched_dirs

        (user_dir / "slack.md").write_text(
            "---\n"
            "name: slack\n"
            "description: Slack via CLI\n"
            "requires: [slack-cli]\n"
            "---\n\n"
            "# Slack\n"
        )

        result = skills.list_skills()
        ids = [s["id"] for s in result]
        assert "slack" in ids
        assert "github" in ids  # bundled still present

    def test_empty_dirs(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with patch.object(skills, "BUNDLED_DIR", empty), \
             patch.object(skills, "SKILLS_DIR", tmp_path / "nonexistent"):
            result = skills.list_skills()
            assert result == []

    def test_nonexistent_dirs(self, tmp_path):
        with patch.object(skills, "BUNDLED_DIR", tmp_path / "nope1"), \
             patch.object(skills, "SKILLS_DIR", tmp_path / "nope2"):
            result = skills.list_skills()
            assert result == []

    def test_availability_check_bin_exists(self, patched_dirs):
        with patch("shutil.which", return_value="/usr/bin/gh"):
            result = skills.list_skills()
            gh = next(s for s in result if s["id"] == "github")
            assert gh["available"] is True

    def test_availability_check_bin_missing(self, patched_dirs):
        with patch("shutil.which", return_value=None):
            result = skills.list_skills()
            gh = next(s for s in result if s["id"] == "github")
            assert gh["available"] is False

    def test_no_requires_means_available(self, patched_dirs):
        bundled_dir, _ = patched_dirs
        (bundled_dir / "tips.md").write_text(
            "---\n"
            "name: tips\n"
            "description: General tips\n"
            "---\n\n"
            "# Tips\n"
        )

        with patch("shutil.which", return_value=None):
            result = skills.list_skills()
            tips = next(s for s in result if s["id"] == "tips")
            assert tips["available"] is True


# ── read_skill ──


class TestReadSkill:
    def test_reads_bundled_skill(self, patched_dirs):
        content = skills.read_skill("github")
        assert content is not None
        assert "# GitHub Skill" in content

    def test_user_skill_takes_priority(self, patched_dirs):
        _, user_dir = patched_dirs

        (user_dir / "github.md").write_text("# My Custom GitHub\n")

        content = skills.read_skill("github")
        assert "My Custom GitHub" in content
        assert "# GitHub Skill" not in content

    def test_returns_none_for_missing(self, patched_dirs):
        assert skills.read_skill("nonexistent") is None

    def test_reads_full_content_with_frontmatter(self, patched_dirs):
        content = skills.read_skill("github")
        assert "---" in content  # frontmatter preserved
        assert "requires: [gh]" in content


# ── _parse_frontmatter ──


class TestParseFrontmatter:
    def test_basic_key_value(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: test\ndescription: A test\n---\n\n# Test\n")
        result = skills._parse_frontmatter(f)
        assert result["name"] == "test"
        assert result["description"] == "A test"

    def test_list_value(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nrequires: [gh, git]\n---\n")
        result = skills._parse_frontmatter(f)
        assert result["requires"] == ["gh", "git"]

    def test_quoted_values(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text('---\nname: "my skill"\n---\n')
        result = skills._parse_frontmatter(f)
        assert result["name"] == "my skill"

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# Just a markdown file\n\nNo frontmatter here.\n")
        result = skills._parse_frontmatter(f)
        assert result == {}

    def test_empty_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("")
        result = skills._parse_frontmatter(f)
        assert result == {}

    def test_comments_ignored(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: test\n# comment\ndescription: A test\n---\n")
        result = skills._parse_frontmatter(f)
        assert "name" in result
        assert "description" in result

    def test_missing_file(self, tmp_path):
        f = tmp_path / "nope.md"
        result = skills._parse_frontmatter(f)
        assert result == {}


# ── _check_bins ──


class TestCheckBins:
    def test_empty_requires_is_available(self):
        assert skills._check_bins([]) is True

    def test_all_bins_present(self):
        with patch("shutil.which", return_value="/usr/bin/thing"):
            assert skills._check_bins(["gh", "git"]) is True

    def test_one_bin_missing(self):
        def fake_which(name):
            return "/usr/bin/gh" if name == "gh" else None

        with patch("shutil.which", side_effect=fake_which):
            assert skills._check_bins(["gh", "himalaya"]) is False

    def test_all_bins_missing(self):
        with patch("shutil.which", return_value=None):
            assert skills._check_bins(["missing1", "missing2"]) is False


# ── _scan_dir ──


class TestScanDir:
    def test_finds_md_files(self, tmp_path):
        (tmp_path / "a.md").write_text("# A")
        (tmp_path / "b.md").write_text("# B")
        (tmp_path / "c.txt").write_text("not a skill")
        result = skills._scan_dir(tmp_path)
        names = [p.name for p in result]
        assert "a.md" in names
        assert "b.md" in names
        assert "c.txt" not in names

    def test_nonexistent_dir(self, tmp_path):
        result = skills._scan_dir(tmp_path / "nope")
        assert result == []

    def test_sorted_alphabetically(self, tmp_path):
        (tmp_path / "z.md").write_text("")
        (tmp_path / "a.md").write_text("")
        (tmp_path / "m.md").write_text("")
        result = skills._scan_dir(tmp_path)
        names = [p.name for p in result]
        assert names == sorted(names)


# ── Integration: bundled skills exist ──


class TestBundledSkills:
    """Verify the actual bundled skills ship correctly."""

    def test_bundled_dir_exists(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert BUNDLED_DIR.exists(), f"Bundled skills dir missing: {BUNDLED_DIR}"

    def test_github_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "github.md").exists()

    def test_email_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "email.md").exists()

    def test_apple_shortcuts_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "apple-shortcuts.md").exists()

    def test_browser_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "browser.md").exists()

    def test_all_bundled_skills_have_frontmatter(self):
        from nexus.mind.skills import BUNDLED_DIR
        for md in BUNDLED_DIR.glob("*.md"):
            meta = skills._parse_frontmatter(md)
            assert "name" in meta, f"{md.name} missing 'name' in frontmatter"
            assert "description" in meta, f"{md.name} missing 'description' in frontmatter"

    def test_safari_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "safari.md").exists()

    def test_vscode_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "vscode.md").exists()

    def test_finder_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "finder.md").exists()

    def test_system_settings_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "system-settings.md").exists()

    def test_terminal_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "terminal.md").exists()

    def test_docker_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "docker.md").exists()

    def test_system_dialogs_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "system-dialogs.md").exists()

    def test_electron_apps_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "electron-apps.md").exists()

    def test_keyboard_navigation_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "keyboard-navigation.md").exists()

    def test_file_save_as_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "file-save-as.md").exists()

    def test_screenshot_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "screenshot.md").exists()

    def test_notifications_skill_bundled(self):
        from nexus.mind.skills import BUNDLED_DIR
        assert (BUNDLED_DIR / "notifications.md").exists()

    def test_list_skills_includes_all_bundled(self):
        """list_skills() with real bundled dir finds all 16 skills."""
        result = skills.list_skills()
        ids = [s["id"] for s in result]
        expected = [
            "apple-shortcuts", "browser", "docker", "electron-apps",
            "email", "file-save-as", "finder", "github",
            "keyboard-navigation", "notifications", "safari",
            "screenshot", "system-dialogs", "system-settings",
            "terminal", "vscode",
        ]
        for skill_id in expected:
            assert skill_id in ids, f"Missing bundled skill: {skill_id}"
        assert len(result) == 16
