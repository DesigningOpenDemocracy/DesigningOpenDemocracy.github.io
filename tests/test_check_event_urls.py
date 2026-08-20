#!/usr/bin/env python3
"""Regression tests for util/check_event_urls.py: check_url()'s narrowed
GET-fallback condition, and check_url_cached()'s shared "blocked" cache
(the same cache/field format util/check_fragments.py uses).

Offline — no real network calls; a fake session records which HTTP
methods were actually called. Run with:

    python -m unittest discover tests
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import check_event_urls as ceu  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code, url="https://example.org/page", text=""):
        self.status_code = status_code
        self.url = url
        self.text = text

    def close(self):
        pass


class _FakeSession:
    """Records every head()/get() call to the page under test and returns
    canned responses in order, so a test can assert exactly which HTTP
    methods actually fired (the whole point of the GET-fallback-narrowing
    fix). check_url_cached() also fetches robots.txt before touching the
    page itself — that preflight is answered here with an empty ("allow
    everything") robots.txt and deliberately left out of self.calls, since
    these tests are about the page-fetch method/ordering, not the
    robots.txt implementation detail."""

    def __init__(self, head_response, get_response=None, robots_disallow=False):
        self.head_response = head_response
        self.get_response = get_response
        self.robots_disallow = robots_disallow
        self.calls = []

    def head(self, url, timeout=None, allow_redirects=None):
        self.calls.append("HEAD")
        return self.head_response

    def get(self, url, timeout=None, allow_redirects=None, stream=None):
        if url.endswith("/robots.txt"):
            text = "User-agent: *\nDisallow: /" if self.robots_disallow else ""
            return _FakeResponse(200, url=url, text=text)
        self.calls.append("GET")
        return self.get_response


class CheckUrlGetFallbackTests(unittest.TestCase):

    def test_403_from_head_does_not_trigger_get_fallback(self):
        session = _FakeSession(_FakeResponse(403))
        status, final_url, error = ceu.check_url("https://example.org/page", session, timeout=5)
        self.assertEqual(session.calls, ["HEAD"])  # no GET follow-up
        self.assertEqual(status, 403)

    def test_429_from_head_does_not_trigger_get_fallback(self):
        session = _FakeSession(_FakeResponse(429))
        status, final_url, error = ceu.check_url("https://example.org/page", session, timeout=5)
        self.assertEqual(session.calls, ["HEAD"])
        self.assertEqual(status, 429)

    def test_404_from_head_still_triggers_get_fallback(self):
        session = _FakeSession(_FakeResponse(404), _FakeResponse(404))
        status, final_url, error = ceu.check_url("https://example.org/page", session, timeout=5)
        self.assertEqual(session.calls, ["HEAD", "GET"])

    def test_405_from_head_still_triggers_get_fallback(self):
        session = _FakeSession(_FakeResponse(405), _FakeResponse(200))
        status, final_url, error = ceu.check_url("https://example.org/page", session, timeout=5)
        self.assertEqual(session.calls, ["HEAD", "GET"])
        self.assertEqual(status, 200)

    def test_200_from_head_does_not_trigger_get_fallback(self):
        session = _FakeSession(_FakeResponse(200))
        status, final_url, error = ceu.check_url("https://example.org/page", session, timeout=5)
        self.assertEqual(session.calls, ["HEAD"])


class CheckUrlCachedTests(unittest.TestCase):

    def test_blocked_url_is_skipped_without_a_request(self):
        cache = {"https://example.org/page": {"blocked": "HTTP_403", "blocked_since": "2026-01-01"}}
        session = _FakeSession(_FakeResponse(200))  # would prove a request happened if called
        status, final_url, error, skipped = ceu.check_url_cached(
            "https://example.org/page", session, timeout=5, cache=cache, use_cache=True)
        self.assertEqual(session.calls, [])  # no network call at all
        self.assertTrue(skipped)
        self.assertEqual(status, 403)

    def test_fresh_403_gets_recorded_as_blocked(self):
        cache = {}
        session = _FakeSession(_FakeResponse(403))
        ceu.check_url_cached("https://example.org/page", session, timeout=5, cache=cache, use_cache=True)
        self.assertEqual(cache["https://example.org/page"]["blocked"], "HTTP_403")
        self.assertIn("blocked_since", cache["https://example.org/page"])

    def test_fresh_429_gets_recorded_as_blocked(self):
        cache = {}
        session = _FakeSession(_FakeResponse(429))
        ceu.check_url_cached("https://example.org/page", session, timeout=5, cache=cache, use_cache=True)
        self.assertEqual(cache["https://example.org/page"]["blocked"], "HTTP_429")

    def test_dead_link_is_not_recorded_as_blocked(self):
        cache = {}
        session = _FakeSession(_FakeResponse(404), _FakeResponse(404))
        ceu.check_url_cached("https://example.org/page", session, timeout=5, cache=cache, use_cache=True)
        self.assertNotIn("https://example.org/page", cache)

    def test_no_cache_bypasses_the_blocked_skip(self):
        cache = {"https://example.org/page": {"blocked": "HTTP_403", "blocked_since": "2026-01-01"}}
        session = _FakeSession(_FakeResponse(200))
        status, final_url, error, skipped = ceu.check_url_cached(
            "https://example.org/page", session, timeout=5, cache=cache, use_cache=False)
        self.assertEqual(session.calls, ["HEAD"])  # request was actually made
        self.assertFalse(skipped)
        self.assertEqual(status, 200)

    def test_successful_recheck_clears_a_stale_blocked_flag(self):
        cache = {"https://example.org/page": {"blocked": "HTTP_403", "blocked_since": "2026-01-01"}}
        session = _FakeSession(_FakeResponse(200))
        ceu.check_url_cached("https://example.org/page", session, timeout=5, cache=cache, use_cache=False)
        self.assertNotIn("https://example.org/page", cache)  # nothing left worth keeping

    def test_robots_disallowed_url_is_not_requested(self):
        # session.head_response would prove a request happened if HEAD/GET
        # were actually called — the point is that they aren't.
        cache = {}
        session = _FakeSession(_FakeResponse(200), robots_disallow=True)
        status, final_url, error, skipped = ceu.check_url_cached(
            "https://example.org/page", session, timeout=5, cache=cache, use_cache=True)
        self.assertEqual(session.calls, [])  # no HEAD/GET to the page itself
        self.assertFalse(skipped)  # first time seeing this — not a cache hit
        self.assertEqual(status, ceu.ROBOTS_STATUS)
        self.assertEqual(cache["https://example.org/page"]["blocked"], ceu.ROBOTS_STATUS)

    def test_robots_disallowed_is_sticky_like_403(self):
        # Regression: check_url_cached()'s cached-blocked branch used to do
        # int(blocked.rsplit("_", 1)[-1]) unconditionally, which raises on
        # "ROBOTS_DISALLOWED" (no trailing number) instead of "HTTP_403".
        cache = {"https://example.org/page": {"blocked": ceu.ROBOTS_STATUS, "blocked_since": "2026-01-01"}}
        session = _FakeSession(_FakeResponse(200))  # would prove a request happened if called
        status, final_url, error, skipped = ceu.check_url_cached(
            "https://example.org/page", session, timeout=5, cache=cache, use_cache=True)
        self.assertEqual(session.calls, [])
        self.assertTrue(skipped)
        self.assertEqual(status, ceu.ROBOTS_STATUS)


if __name__ == "__main__":
    unittest.main()
