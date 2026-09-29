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
from datetime import date
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
        # A 404 isn't bot protection, so it must never become a sticky
        # block. Since 2026-09-28 it's recorded as a failure instead, which
        # backs off (util/backoff.py) rather than being skipped forever.
        cache = {}
        session = _FakeSession(_FakeResponse(404), _FakeResponse(404))
        ceu.check_url_cached("https://example.org/page", session, timeout=5, cache=cache, use_cache=True)
        entry = cache["https://example.org/page"]
        self.assertNotIn("blocked", entry)
        self.assertEqual(entry["failing"]["error"], "HTTP_404")
        self.assertEqual(entry["failing"]["count"], 1)

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



class FailureBackoffTests(unittest.TestCase):
    """A dead link (404/5xx/unreachable) used to be requested every week, a
    HEAD and then a GET to double-check, for as long as it stayed cited.
    It's now recorded in the shared cache's `failing` field and backed off
    (util/backoff.py); a URL a human marked dead is only rechecked
    quarterly, and one marked unfit never."""

    URL = "https://example.org/page"
    TODAY = date(2026, 9, 28)

    def failing(self, last, count=1, error="HTTP_404"):
        return {"error": error, "since": last, "count": count, "last": last}

    def test_backing_off_url_is_answered_without_a_request(self):
        cache = {self.URL: {"failing": self.failing("2026-09-22")}}  # retry on 09-29
        session = _FakeSession(_FakeResponse(200))
        got = ceu.check_url_cached(self.URL, session, 5, cache, today=self.TODAY)
        self.assertEqual(got, (404, None, None, True))
        self.assertEqual(session.calls, [])

    def test_network_failure_is_replayed_as_an_error(self):
        cache = {self.URL: {"failing": self.failing("2026-09-22", error="NETWORK_ERROR")}}
        got = ceu.check_url_cached(self.URL, _FakeSession(_FakeResponse(200)), 5, cache, today=self.TODAY)
        self.assertEqual(got, (None, None, "NETWORK_ERROR", True))

    def test_due_retry_that_succeeds_clears_the_record(self):
        cache = {self.URL: {"failing": self.failing("2026-09-21")}}  # retry on 09-28
        session = _FakeSession(_FakeResponse(200))
        status, _, _, skipped = ceu.check_url_cached(self.URL, session, 5, cache, today=self.TODAY)
        self.assertEqual((status, skipped, session.calls), (200, False, ["HEAD"]))
        self.assertNotIn("failing", cache.get(self.URL, {}))

    def test_repeat_failure_widens_the_interval(self):
        cache = {self.URL: {"failing": self.failing("2026-09-21")}}
        session = _FakeSession(_FakeResponse(404), _FakeResponse(404))
        ceu.check_url_cached(self.URL, session, 5, cache, today=self.TODAY)
        record = cache[self.URL]["failing"]
        self.assertEqual((record["count"], record["since"], record["last"]), (2, "2026-09-21", "2026-09-28"))

    def test_no_cache_retries_now(self):
        cache = {self.URL: {"failing": self.failing("2026-09-27")}}
        session = _FakeSession(_FakeResponse(200))
        ceu.check_url_cached(self.URL, session, 5, cache, use_cache=False, today=self.TODAY)
        self.assertEqual(session.calls, ["HEAD"])

    def test_marked_unfit_is_never_requested(self):
        cache = {self.URL: {"url_status": "unfit"}}
        session = _FakeSession(_FakeResponse(200))
        got = ceu.check_url_cached(self.URL, session, 5, cache, today=self.TODAY)
        self.assertEqual(got[0], ceu.MARKED_STATUS)
        self.assertEqual(session.calls, [])

    def test_marked_dead_is_rechecked_quarterly(self):
        cache = {self.URL: {"url_status": "dead", "failing": self.failing("2026-07-01", count=9)}}
        quiet = _FakeSession(_FakeResponse(404), _FakeResponse(404))
        self.assertEqual(ceu.check_url_cached(self.URL, quiet, 5, cache, today=date(2026, 9, 28))[0],
                         ceu.MARKED_STATUS)  # 89 days
        self.assertEqual(quiet.calls, [])
        due = _FakeSession(_FakeResponse(404), _FakeResponse(404))
        ceu.check_url_cached(self.URL, due, 5, cache, today=date(2026, 9, 29))  # 90 days
        self.assertEqual(due.calls, ["HEAD", "GET"])


if __name__ == "__main__":
    unittest.main()
