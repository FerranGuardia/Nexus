"""Tests for Nexus caching layer (NX-005)."""

import time

import pytest

from nexus.cache import cache_get, cache_put, cache_clear, _content_hash


class TestContentHash:
    def test_describe_hash_uses_key_fields(self):
        r1 = {"command": "describe", "window": {"title": "Notepad"}, "focused_element": {"name": "Edit"}, "element_count": 10}
        r2 = {"command": "describe", "window": {"title": "Notepad"}, "focused_element": {"name": "Edit"}, "element_count": 10}
        assert _content_hash(r1) == _content_hash(r2)

    def test_describe_hash_changes_on_focus(self):
        r1 = {"command": "describe", "window": {"title": "Notepad"}, "focused_element": {"name": "Edit"}, "element_count": 10}
        r2 = {"command": "describe", "window": {"title": "Notepad"}, "focused_element": {"name": "Save"}, "element_count": 10}
        assert _content_hash(r1) != _content_hash(r2)

    def test_describe_hash_changes_on_count(self):
        r1 = {"command": "describe", "window": {"title": "Notepad"}, "focused_element": {"name": "Edit"}, "element_count": 10}
        r2 = {"command": "describe", "window": {"title": "Notepad"}, "focused_element": {"name": "Edit"}, "element_count": 15}
        assert _content_hash(r1) != _content_hash(r2)

    def test_web_hash(self):
        r1 = {"command": "web-describe", "url": "https://example.com", "title": "Example"}
        r2 = {"command": "web-describe", "url": "https://example.com", "title": "Example"}
        assert _content_hash(r1) == _content_hash(r2)

    def test_web_hash_changes_on_url(self):
        r1 = {"command": "web-describe", "url": "https://example.com", "title": "Example"}
        r2 = {"command": "web-describe", "url": "https://other.com", "title": "Example"}
        assert _content_hash(r1) != _content_hash(r2)


class TestMemoryCache:
    def setup_method(self):
        cache_clear()

    def test_miss_returns_none(self):
        assert cache_get("describe", {}) is None

    def test_put_then_get(self):
        result = {"command": "describe", "window": {"title": "Test"}, "focused_element": None, "element_count": 5}
        cache_put("describe", {}, result)
        cached = cache_get("describe", {}, ttl=10.0)
        assert cached is not None
        assert cached["changed"] is False
        assert "age" in cached

    def test_ttl_expiry(self):
        result = {"command": "describe", "window": {"title": "Test"}, "focused_element": None, "element_count": 5}
        cache_put("describe", {}, result)
        time.sleep(0.05)
        cached = cache_get("describe", {}, ttl=0.01)
        assert cached is None

    def test_different_kwargs_different_keys(self):
        r1 = {"command": "find", "query": "foo", "matches": [], "count": 0}
        r2 = {"command": "find", "query": "bar", "matches": [], "count": 0}
        cache_put("find", {"query": "foo"}, r1)
        cache_put("find", {"query": "bar"}, r2)
        assert cache_get("find", {"query": "foo"}, ttl=10.0) is not None
        assert cache_get("find", {"query": "bar"}, ttl=10.0) is not None
        assert cache_get("find", {"query": "baz"}, ttl=10.0) is None

    def test_clear(self):
        result = {"command": "describe", "window": {"title": "Test"}, "focused_element": None, "element_count": 5}
        cache_put("describe", {}, result)
        cache_clear()
        assert cache_get("describe", {}) is None


class TestFileCache:
    def setup_method(self):
        cache_clear()

    def test_file_put_then_get(self):
        result = {"command": "describe", "window": {"title": "Test"}, "focused_element": None, "element_count": 5}
        cache_put("describe", {}, result, use_file=True)
        cached = cache_get("describe", {}, ttl=10.0, use_file=True)
        assert cached is not None
        assert cached["changed"] is False

    def test_file_ttl_expiry(self):
        result = {"command": "describe", "window": {"title": "Test"}, "focused_element": None, "element_count": 5}
        cache_put("describe", {}, result, use_file=True)
        cached = cache_get("describe", {}, ttl=0.0, use_file=True)
        assert cached is None
