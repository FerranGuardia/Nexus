"""Nexus e2e test configuration."""

import json
import os
import subprocess
import urllib.request
import urllib.error

import pytest

PYTHON = r"C:\Users\Nitropc\AppData\Local\Programs\Python\Python312\python.exe"
NEXUS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_nexus(*args, timeout=15):
    """Run a nexus command via `python -m nexus` and return parsed JSON output."""
    cmd = [PYTHON, "-m", "nexus"] + list(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, cwd=NEXUS_ROOT,
        encoding="utf-8",
    )
    assert result.returncode == 0, f"Nexus failed (rc={result.returncode}): {result.stderr[:500]}"
    output = result.stdout.strip()
    assert output, "Nexus produced no output"
    return json.loads(output)


def pytest_configure(config):
    config.addinivalue_line("markers", "web: requires Chrome running with --remote-debugging-port=9222")
    config.addinivalue_line("markers", "action: involves mouse/keyboard actions (potentially disruptive)")


def _chrome_cdp_available():
    try:
        req = urllib.request.urlopen("http://localhost:9222/json/version", timeout=2)
        req.close()
        return True
    except (urllib.error.URLError, OSError):
        return False


@pytest.fixture(autouse=True)
def _skip_web_if_no_chrome(request):
    """Auto-skip tests marked @pytest.mark.web when Chrome CDP is unavailable."""
    if request.node.get_closest_marker("web"):
        if not _chrome_cdp_available():
            pytest.skip("Chrome CDP not available on localhost:9222")


@pytest.fixture
def save_cursor():
    """Save and restore cursor position around action tests."""
    data = run_nexus("info")
    orig_x = data["cursor"]["x"]
    orig_y = data["cursor"]["y"]
    yield data
    run_nexus("move", str(orig_x), str(orig_y))
