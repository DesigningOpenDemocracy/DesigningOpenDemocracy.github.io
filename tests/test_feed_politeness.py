#!/usr/bin/env python3
"""Regression tests for how often DOD's scripts ask other people's servers
for things: util/backoff.py, and check_rss.py's feed schedule, conditional
GET and discovery memory.

What's pinned, and why each is worth pinning rather than eyeballing:

  - The backoff schedule: 7, 14, 28, 56, then 90 days, cleared by a
    success. Before it, a feed or citation that 404'd was requested again
    on every weekly run, forever.
  - A feed's validators go back out as If-None-Match / If-Modified-Since,
    and a 304 costs no body and changes nothing on disk.
  - A feed body over the cap is abandoned, not downloaded in full: the
    landscape had a 22 MB malformed feed read in full every week.
  - "Not XML" (a failure, backed off) is told apart from "valid but empty"
    (a feed, read monthly).
  - An org with no feed is probed at most every FEED_REPROBE_DAYS (spread
    per org), with only its known sitemap read in between. Until
    2026-09-28 discovery re-ran 23 paths for every such org on every run.
  - The weekly interval is strictly less-than: `<= 7` with a weekly cron
    skipped every org on alternate weeks.

Offline: a fake session stands in for the network. Run with:

    python -m unittest discover tests
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import backoff  # noqa: E402
import check_rss as cr  # noqa: E402

TODAY = date(2026, 9, 28)

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>A post</title><link>https://ex.org/p</link><pubDate>Mon, 21 Sep 2026 09:00:00 +0000</pubDate></item>
</channel></rss>"""
EMPTY_RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>"""


class FakeResponse:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self.read_bytes = 0
        self.closed = False

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._body), chunk_size):
            chunk = self._body[i:i + chunk_size]
            self.read_bytes += len(chunk)
            yield chunk

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.calls = []

    def get(self, url, timeout=None, headers=None, stream=False):
        self.calls.append({"url": url, "headers": dict(headers or {})})
        return self.response


class BackoffTests(unittest.TestCase):
    def test_schedule_doubles_to_a_quarter(self):
        self.assertEqual([backoff.retry_days(n) for n in range(1, 7)], [7, 14, 28, 56, 90, 90])

    def test_record_keeps_first_failure_date(self):
        f = backoff.record_failure(None, "HTTP_404", TODAY)
        f = backoff.record_failure(f, "HTTP_410", TODAY + timedelta(days=7))
        self.assertEqual(f, {"error": "HTTP_410", "since": "2026-09-28", "count": 2, "last": "2026-10-05"})

    def test_backing_off_until_the_retry_date_then_not(self):
        f = backoff.record_failure(None, "HTTP_404", TODAY)
        self.assertTrue(backoff.backing_off(f, TODAY + timedelta(days=6)))
        self.assertFalse(backoff.backing_off(f, TODAY + timedelta(days=7)))  # next weekly run
        self.assertFalse(backoff.backing_off(None, TODAY))

    def test_spread_stays_inside_half_the_window(self):
        offsets = {backoff.spread_days(f"org-{i}", 90) for i in range(200)}
        self.assertTrue(offsets <= set(range(45)))
        self.assertGreater(len(offsets), 20)  # actually spread
        self.assertEqual(backoff.spread_days("x", 90), backoff.spread_days("x", 90))


class FetchFeedTests(unittest.TestCase):
    def test_validators_are_sent_and_304_costs_no_body(self):
        s = FakeSession(FakeResponse(304))
        got = cr.fetch_feed("https://ex.org/feed", session=s,
                            validators={"etag": '"abc"', "last_modified": "Mon, 21 Sep 2026 09:00:00 GMT"})
        self.assertEqual(got, {"status": "not_modified"})
        self.assertEqual(s.calls[0]["headers"], {"If-None-Match": '"abc"',
                                                 "If-Modified-Since": "Mon, 21 Sep 2026 09:00:00 GMT"})
        self.assertEqual(s.response.read_bytes, 0)

    def test_ok_returns_entries_and_the_new_validators(self):
        s = FakeSession(FakeResponse(200, RSS, {"ETag": '"v2"'}))
        got = cr.fetch_feed("https://ex.org/feed", session=s)
        self.assertEqual(got["status"], "ok")
        self.assertEqual([e["title"] for e in got["entries"]], ["A post"])
        self.assertEqual(got["validators"], {"etag": '"v2"'})
        self.assertEqual(s.calls[0]["headers"], {})  # nothing to send the first time

    def test_declared_oversize_body_is_never_read(self):
        s = FakeSession(FakeResponse(200, b"x" * 100, {"Content-Length": str(cr.FEED_MAX_BYTES + 1)}))
        self.assertEqual(cr.fetch_feed("https://ex.org/feed", session=s)["error"], "TOO_LARGE")
        self.assertEqual(s.response.read_bytes, 0)

    def test_undeclared_oversize_body_is_abandoned(self):
        big = b"<rss>" + b"x" * (cr.FEED_MAX_BYTES + 200000)
        s = FakeSession(FakeResponse(200, big))
        self.assertEqual(cr.fetch_feed("https://ex.org/feed", session=s)["error"], "TOO_LARGE")
        self.assertLess(s.response.read_bytes, len(big))
        self.assertTrue(s.response.closed)

    def test_broken_and_empty_are_different(self):
        broken = cr.fetch_feed("u", session=FakeSession(FakeResponse(200, b"<html>not a feed")))
        empty = cr.fetch_feed("u", session=FakeSession(FakeResponse(200, EMPTY_RSS)))
        self.assertEqual(broken, {"status": "error", "error": "UNPARSEABLE"})
        self.assertEqual((empty["status"], empty["entries"]), ("ok", []))

    def test_http_error(self):
        got = cr.fetch_feed("u", session=FakeSession(FakeResponse(404)))
        self.assertEqual(got, {"status": "error", "error": "HTTP_404"})


class FeedStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def entries(self):
        return [{"date": date(2026, 9, 21), "published": date(2026, 9, 21),
                 "title": "A post", "link": "https://ex.org/p"}]

    def test_failure_keeps_saved_posts_and_success_clears_it(self):
        cr.save_feed_items("ex", "https://ex.org/feed", self.entries(), TODAY, self.dir, {"etag": '"v1"'})
        cr.record_feed_failure("ex", "https://ex.org/feed", "HTTP_500", TODAY, self.dir)
        state = cr.load_feed_state("ex", self.dir)
        self.assertEqual(len(state["items"]), 1)
        self.assertEqual(state["failing"]["error"], "HTTP_500")
        self.assertEqual(state["fetch"], {"etag": '"v1"'})
        cr.save_feed_items("ex", "https://ex.org/feed", self.entries(), TODAY, self.dir, {"etag": '"v1"'})
        self.assertNotIn("failing", cr.load_feed_state("ex", self.dir))

    def test_304_clears_a_failure_without_touching_the_rest(self):
        cr.save_feed_items("ex", "https://ex.org/feed", self.entries(), TODAY, self.dir)
        cr.record_feed_failure("ex", "https://ex.org/feed", "NETWORK_ERROR", TODAY, self.dir)
        cr.mark_feed_unchanged("ex", self.dir)
        state = cr.load_feed_state("ex", self.dir)
        self.assertNotIn("failing", state)
        self.assertEqual(len(state["items"]), 1)

    def test_unchanged_state_is_not_rewritten(self):
        self.assertTrue(cr.save_feed_items("ex", "u", self.entries(), TODAY, self.dir))
        self.assertFalse(cr.save_feed_items("ex", "u", self.entries(), TODAY, self.dir))

    def test_key_order_is_fixed(self):
        cr.record_discovery("ex", "https://ex.org/sitemap.xml", TODAY, self.dir)
        cr.record_feed_failure("ex", "https://ex.org/feed", "HTTP_404", TODAY, self.dir)
        with open(os.path.join(self.dir, "ex.json"), encoding="utf-8") as f:
            self.assertEqual(list(json.load(f)), ["feed", "failing", "probed", "sitemap"])

    def test_finding_a_feed_drops_discovery_bookkeeping(self):
        cr.record_discovery("ex", "https://ex.org/sitemap.xml", TODAY, self.dir)
        cr.save_feed_items("ex", "https://ex.org/feed", self.entries(), TODAY, self.dir)
        state = cr.load_feed_state("ex", self.dir)
        self.assertNotIn("probed", state)
        self.assertNotIn("sitemap", state)


class ScheduleTests(unittest.TestCase):
    def test_weekly_is_strictly_less_than_seven(self):
        state = {"latest": "2026-09-20"}
        self.assertFalse(cr.feed_due(state, "2026-09-22", TODAY)[0])  # 6 days
        self.assertTrue(cr.feed_due(state, "2026-09-21", TODAY)[0])   # 7 days: the next weekly run

    def test_dormant_and_empty_feeds_are_read_monthly(self):
        for latest in ("2019-06-26", None):
            state = {"latest": latest}
            self.assertFalse(cr.feed_due(state, "2026-09-14", TODAY)[0])  # 14 days
            self.assertTrue(cr.feed_due(state, "2026-08-31", TODAY)[0])   # 28 days

    def test_never_read_feed_is_due(self):
        self.assertTrue(cr.feed_due({}, None, TODAY)[0])

    def test_failing_feed_waits_out_its_backoff(self):
        failing = backoff.record_failure(backoff.record_failure(None, "HTTP_404", date(2026, 9, 14)),
                                         "HTTP_404", date(2026, 9, 21))  # 2nd failure: wait 14 days
        due, why = cr.feed_due({"failing": failing}, "2026-06-01", TODAY)
        self.assertFalse(due)
        self.assertIn("next try 2026-10-05", why)
        self.assertTrue(cr.feed_due({"failing": failing}, "2026-06-01", date(2026, 10, 5))[0])

    def test_discovery_runs_once_then_waits(self):
        self.assertEqual(cr.discovery_action("ex", {}, None, TODAY), ("probe", None))
        window = cr.FEED_REPROBE_DAYS - backoff.spread_days("ex", cr.FEED_REPROBE_DAYS)
        probed = {"probed": TODAY.isoformat()}
        self.assertEqual(cr.discovery_action("ex", probed, None, TODAY + timedelta(days=window - 1))[0], "skip")
        self.assertEqual(cr.discovery_action("ex", probed, None, TODAY + timedelta(days=window))[0], "probe")
        self.assertGreater(window, cr.FEED_REPROBE_DAYS // 2)

    def test_known_sitemap_is_read_monthly_between_probes(self):
        state = {"probed": TODAY.isoformat(), "sitemap": "https://ex.org/sitemap.xml"}
        self.assertEqual(cr.discovery_action("ex", state, "2026-09-28", TODAY + timedelta(days=27))[0], "skip")
        self.assertEqual(cr.discovery_action("ex", state, "2026-09-28", TODAY + timedelta(days=28)),
                         ("sitemap", "https://ex.org/sitemap.xml"))


if __name__ == "__main__":
    unittest.main()
