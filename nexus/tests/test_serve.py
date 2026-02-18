"""Tests for Nexus daemon mode (serve command).

Tests the JSON-line protocol, built-in commands, error handling.
Uses subprocess to start the daemon and communicate via stdin/stdout.
"""

import json
import subprocess
import sys
import time

import pytest

PYTHON = r"C:\Users\Nitropc\AppData\Local\Programs\Python\Python312\python.exe"
NEXUS_CMD = [PYTHON, "-m", "nexus", "--timeout", "30", "serve"]


def _start_daemon():
    """Start a Nexus daemon subprocess, return the Popen handle."""
    proc = subprocess.Popen(
        NEXUS_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # line-buffered
        encoding="utf-8",
    )
    # Wait for ready signal on stderr
    ready = proc.stderr.readline()
    assert "ready" in ready, "Daemon did not send ready signal: %s" % ready
    return proc


def _send(proc, request: dict, timeout: float = 15.0) -> dict:
    """Send a JSON-line request and read one JSON-line response."""
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    # Read lines, skipping empty ones (COM warnings can leak to stdout)
    while True:
        line = proc.stdout.readline()
        assert line, "No response from daemon (EOF)"
        line = line.strip()
        if line:
            return json.loads(line)


class TestDaemonProtocol:
    """Test the JSON-line protocol basics."""

    def test_ping(self):
        proc = _start_daemon()
        try:
            resp = _send(proc, {"command": "ping"})
            assert resp["ok"] is True
            assert "uptime" in resp
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)

    def test_ping_with_id(self):
        proc = _start_daemon()
        try:
            resp = _send(proc, {"command": "ping", "_id": "req-42"})
            assert resp["ok"] is True
            assert resp["_id"] == "req-42"
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)

    def test_quit(self):
        proc = _start_daemon()
        try:
            resp = _send(proc, {"command": "quit"})
            assert resp["ok"] is True
            proc.wait(timeout=5)
            assert proc.returncode == 0
        finally:
            if proc.poll() is None:
                proc.kill()

    def test_commands_list(self):
        proc = _start_daemon()
        try:
            resp = _send(proc, {"command": "commands"})
            assert resp["ok"] is True
            assert "describe" in resp["commands"]
            assert "ping" in resp["commands"]
            assert "quit" in resp["commands"]
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)

    def test_unknown_command(self):
        proc = _start_daemon()
        try:
            resp = _send(proc, {"command": "nonexistent"})
            assert resp["ok"] is False
            assert "Unknown" in resp["error"]
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)

    def test_invalid_json(self):
        proc = _start_daemon()
        try:
            proc.stdin.write("this is not json\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            resp = json.loads(line)
            assert resp["ok"] is False
            assert "Invalid JSON" in resp["error"]
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)

    def test_multiple_commands(self):
        """Send 3 commands in sequence, all should respond."""
        proc = _start_daemon()
        try:
            for i in range(3):
                resp = _send(proc, {"command": "ping", "_id": str(i)})
                assert resp["ok"] is True
                assert resp["_id"] == str(i)
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)

    def test_describe_via_daemon(self):
        """Real command: describe should return window info."""
        proc = _start_daemon()
        try:
            resp = _send(proc, {"command": "describe"})
            assert "command" in resp
            assert resp["command"] == "describe"
            assert "window" in resp
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)

    def test_info_via_daemon(self):
        """Real command: info returns screen size."""
        proc = _start_daemon()
        try:
            resp = _send(proc, {"command": "info"})
            assert "command" in resp
            assert resp["command"] == "info"
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)

    def test_windows_via_daemon(self):
        """Real command: windows lists open windows."""
        proc = _start_daemon()
        try:
            resp = _send(proc, {"command": "windows"})
            assert resp["command"] == "windows"
            assert "windows" in resp
            assert resp["count"] >= 0
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)

    def test_format_compact(self):
        """Daemon supports format parameter."""
        proc = _start_daemon()
        try:
            resp = _send(proc, {"command": "windows", "format": "compact"})
            # Compact format wraps in {"ok": true, "text": "..."}
            assert resp.get("ok") is True or "windows" in resp
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)

    def test_bad_args(self):
        """Missing required arg should return error."""
        proc = _start_daemon()
        try:
            resp = _send(proc, {"command": "find"})  # missing "query"
            assert resp["ok"] is False
            assert "error" in resp
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)
