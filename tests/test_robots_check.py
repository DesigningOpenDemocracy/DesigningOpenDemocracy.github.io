#!/usr/bin/env python3
"""Regression tests for util/robots_check.py.

Offline — a fake session stands in for requests.Session(), so no real
network calls happen. Run with:

    python -m unittest discover tests

The motivating regression (test_unreachable_robots_txt_allows_everything):
load_robots()'s except-branch originally just swallowed the fetch/parse
error and returned the RobotFileParser as-is, on the assumption that an
un-parsed parser defaults to "no rules" and therefore "allow everything".
It doesn't — a RobotFileParser that never had parse()/read() called
successfully defaults can_fetch() to False, the opposite of the documented
"unreachable robots.txt is treated as allow everything" contract. Caught
by tests/test_check_event_urls.py's CheckUrlCachedTests suite going red
after wiring robots_check into check_event_urls.py — every fake-session
test started getting recorded as robots-blocked, since the fake session's
get() didn't return anything parse()-able. Fixed by explicitly setting
rp.allow_all = True in the except branch (that's the actual flag
can_fetch() checks first, not the parser's un-parsed default state).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

from robots_check import load_robots, robots_allowed  # noqa: E402


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeSession:
    """Returns a canned robots.txt body, or raises to simulate a fetch
    failure (network error, timeout, non-2xx — anything that would stop
    load_robots() from ever reaching rp.parse())."""

    def __init__(self, text=None, raises=False):
        self.text = text
        self.raises = raises
        self.requested = []

    def get(self, url, timeout=None):
        self.requested.append(url)
        if self.raises:
            raise ConnectionError("simulated network failure")
        return _FakeResponse(self.text)


class LoadRobotsTests(unittest.TestCase):

    def test_unreachable_robots_txt_allows_everything(self):
        # The regression this whole file exists for — see module docstring.
        session = _FakeSession(raises=True)
        rp = load_robots("https://example.org", session=session)
        self.assertTrue(rp.can_fetch("DOD-Bot", "https://example.org/anything"))

    def test_empty_robots_txt_allows_everything(self):
        session = _FakeSession(text="")
        rp = load_robots("https://example.org", session=session)
        self.assertTrue(rp.can_fetch("DOD-Bot", "https://example.org/anything"))

    def test_disallow_all_blocks_everything(self):
        session = _FakeSession(text="User-agent: *\nDisallow: /")
        rp = load_robots("https://example.org", session=session)
        self.assertFalse(rp.can_fetch("DOD-Bot", "https://example.org/anything"))

    def test_scoped_disallow_only_blocks_the_matching_path(self):
        session = _FakeSession(text="User-agent: *\nDisallow: /private/")
        rp = load_robots("https://example.org", session=session)
        self.assertTrue(rp.can_fetch("DOD-Bot", "https://example.org/public/page"))
        self.assertFalse(rp.can_fetch("DOD-Bot", "https://example.org/private/page"))

    def test_reused_parser_avoids_refetching(self):
        # The whole reason load_robots() exists separately from
        # robots_allowed(): check many candidate URLs on one site against
        # a single fetch, instead of one robots.txt request per candidate.
        session = _FakeSession(text="User-agent: *\nDisallow: /private/")
        rp = load_robots("https://example.org", session=session)
        for path in ("/a", "/b", "/private/c", "/d"):
            rp.can_fetch("DOD-Bot", "https://example.org" + path)
        self.assertEqual(session.requested, ["https://example.org/robots.txt"])


class RobotsAllowedTests(unittest.TestCase):

    def test_one_shot_allow(self):
        session = _FakeSession(text="User-agent: *\nDisallow: /private/")
        self.assertTrue(robots_allowed("https://example.org/public", "DOD-Bot", session=session))

    def test_one_shot_disallow(self):
        session = _FakeSession(text="User-agent: *\nDisallow: /private/")
        self.assertFalse(robots_allowed("https://example.org/private/x", "DOD-Bot", session=session))

    def test_one_shot_unreachable_allows(self):
        session = _FakeSession(raises=True)
        self.assertTrue(robots_allowed("https://example.org/anything", "DOD-Bot", session=session))


if __name__ == "__main__":
    unittest.main()
