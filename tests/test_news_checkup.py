#!/usr/bin/env python3
"""Regression tests for the news checkup: util/news_checkup.py, and the feed
cache util/check_rss.py writes for it (parse_feed_entries,
merge_feed_items, save_feed_items).

What's pinned, and why each is worth pinning rather than eyeballing:

  - Atom posts link to the post, not whatever <link> comes first. Blogger
    lists rel="replies" and rel="edit" ahead of rel="alternate", and a
    checkup of comment-feed links is useless.
  - The cache merges rather than replaces, so a post that falls off a busy
    feed between two probe runs is still there to review.
  - Tracking parameters are stripped before a link is saved, since the
    checkup's links get copied into `url:` citations.
  - A post already cited by any org's event is hidden, however the URL was
    pasted (www., trailing slash, utm_ parameters).
  - --mark-reviewed records the date the feed was *read*, never today:
    marking through today would hide a post published between the probe's
    read and the review, permanently. It also never moves a date backwards.
  - "Never read", "read, but the feed listed nothing" and "read, but its
    newest post is years old" are reported apart; the fix for each is
    different, and pruning old posts from the cache mustn't turn a dormant
    feed into an apparently broken one.

Offline: no network, fixtures in a tempdir. Run with:

    python -m unittest discover tests
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import check_rss as cr  # noqa: E402
import news_checkup as nc  # noqa: E402

TODAY = date(2026, 9, 28)

RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
  <item><title>Launch of the handbook</title><link>https://ex.org/handbook/</link>
        <pubDate>Mon, 14 Sep 2026 09:00:00 +0000</pubDate></item>
  <item><title>From guid</title><guid>https://ex.org/guid-post</guid>
        <dc:date>2026-09-10T08:00:00Z</dc:date></item>
  <item><title>No date</title><link>https://ex.org/undated</link></item>
</channel></rss>"""

ATOM_BLOGGER = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Old post, edited today</title>
    <published>2025-01-02T00:00:00Z</published>
    <updated>2026-09-27T00:00:00Z</updated>
    <link rel="replies" type="application/atom+xml" href="https://ex.blogspot.com/feeds/1/comments"/>
    <link rel="edit" href="https://www.blogger.com/feeds/edit/1"/>
    <link rel="alternate" type="text/html" href="https://ex.blogspot.com/2025/01/old.html"/>
  </entry>
</feed>"""


def entry(d, title, link):
    return {"date": d, "published": d, "title": title, "link": link}


class ParseFeedEntriesTests(unittest.TestCase):
    def test_rss_items_dated_and_linked(self):
        got = cr.parse_feed_entries(RSS)
        self.assertEqual([(e["published"], e["title"], e["link"]) for e in got], [
            (date(2026, 9, 14), "Launch of the handbook", "https://ex.org/handbook/"),
            (date(2026, 9, 10), "From guid", "https://ex.org/guid-post"),
        ])  # the undated item is dropped

    def test_atom_prefers_the_alternate_link(self):
        (e,) = cr.parse_feed_entries(ATOM_BLOGGER)
        self.assertEqual(e["link"], "https://ex.blogspot.com/2025/01/old.html")

    def test_atom_keeps_published_and_updated_apart(self):
        (e,) = cr.parse_feed_entries(ATOM_BLOGGER)
        # activity keys on <updated>, as it always has; the checkup on
        # <published>, so an old post edited today doesn't read as new.
        self.assertEqual(e["date"], date(2026, 9, 27))
        self.assertEqual(e["published"], date(2025, 1, 2))

    def test_not_xml_is_empty(self):
        self.assertEqual(cr.parse_feed_entries(b"<html><body>nope"), [])

    def test_latest_entry(self):
        self.assertEqual(cr.latest_entry(cr.parse_feed_entries(RSS))[1], "Launch of the handbook")
        self.assertEqual(cr.latest_entry([]), (None, None, None))


class FeedItemCacheTests(unittest.TestCase):
    def test_merge_keeps_posts_that_fell_off_the_feed(self):
        stored = [{"date": "2026-09-01", "title": "Earlier", "url": "https://ex.org/a"}]
        got = cr.merge_feed_items(stored, [entry(date(2026, 9, 20), "Later", "https://ex.org/b")], TODAY)
        self.assertEqual([i["url"] for i in got], ["https://ex.org/b", "https://ex.org/a"])

    def test_merge_prefers_the_feed_copy_of_a_known_post(self):
        stored = [{"date": "2026-09-01", "title": "Typo tittle", "url": "https://ex.org/a"}]
        got = cr.merge_feed_items(stored, [entry(date(2026, 9, 1), "Typo title", "https://ex.org/a")], TODAY)
        self.assertEqual([i["title"] for i in got], ["Typo title"])

    def test_merge_prunes_old_posts_and_caps(self):
        stored = [{"date": "2025-01-01", "title": "Ancient", "url": "https://ex.org/old"}]
        fresh = [entry(date(2026, 9, d), f"p{d}", f"https://ex.org/{d}") for d in range(1, 11)]
        got = cr.merge_feed_items(stored, fresh, TODAY, keep_days=180, max_items=3)
        self.assertEqual([i["title"] for i in got], ["p10", "p9", "p8"])

    def test_tracking_parameters_are_stripped(self):
        link = "https://ex.org/p/?utm_source=rss&id=4&utm_medium=rss"
        got = cr.merge_feed_items([], [entry(date(2026, 9, 1), "P", link)], TODAY)
        self.assertEqual(got[0]["url"], "https://ex.org/p/?id=4")
        self.assertEqual(cr.strip_tracking("https://ex.org/p"), "https://ex.org/p")

    def test_save_writes_once_and_reports_no_change(self):
        with tempfile.TemporaryDirectory() as d:
            e = [entry(date(2026, 9, 1), "P", "https://ex.org/p")]
            self.assertTrue(cr.save_feed_items("ex", "https://ex.org/feed", e, TODAY, feeds_dir=d))
            self.assertFalse(cr.save_feed_items("ex", "https://ex.org/feed", e, TODAY, feeds_dir=d))
            with open(os.path.join(d, "ex.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["feed"], "https://ex.org/feed")
            self.assertEqual(data["latest"], "2026-09-01")
            self.assertEqual(len(data["items"]), 1)

    def test_dormant_feed_keeps_its_latest_date_after_pruning(self):
        with tempfile.TemporaryDirectory() as d:
            cr.save_feed_items("ex", "https://ex.org/feed", [entry(date(2019, 6, 26), "Old", "https://ex.org/o")],
                               TODAY, feeds_dir=d)
            got = nc.load_feed_items("ex", feeds_dir=d)
            self.assertEqual((got["latest"], got["items"], got["read"]), ("2019-06-26", [], True))

    def test_empty_feed_is_saved_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            cr.save_feed_items("ex", "https://ex.org/feed", [], TODAY, feeds_dir=d)
            got = nc.load_feed_items("ex", feeds_dir=d)
            self.assertEqual((got["latest"], got["items"], got["read"]), (None, [], True))
            self.assertIsNone(nc.load_feed_items("missing", feeds_dir=d))


def org(slug, rss_feed="", news_page="", rss_read=date(2026, 9, 25), scrape=None, title=None):
    return {"slug": slug, "title": title or slug.title(), "rss_feed": rss_feed,
            "news_page": news_page, "rss_read": rss_read, "scrape": scrape or {}}


def post(d, title, url):
    return {"date": d, "title": title, "url": url}


def cache(*posts, latest="newest"):
    """A saved feed cache as load_feed_items returns it. `latest` defaults
    to the newest post given, as a read that listed those posts would set."""
    if latest == "newest":
        latest = max((p["date"] for p in posts), default=None)
    return {"latest": latest, "items": list(posts)}


class CheckupTests(unittest.TestCase):
    def run_checkup(self, orgs, items, recorded=(), state=None, **kw):
        return nc.checkup(orgs, set(recorded), state or {}, TODAY,
                          load_items=lambda slug: items.get(slug), **kw)

    def test_default_window_for_an_org_never_reviewed(self):
        r = self.run_checkup([org("a", "https://a.org/feed")], {"a": cache(
            post("2026-09-20", "Recent", "https://a.org/1"),
            post("2026-08-01", "Too old", "https://a.org/2"),
        )})
        self.assertEqual([i["title"] for i in r["feeds"][0]["items"]], ["Recent"])
        self.assertEqual(r["feeds"][0]["since"], date(2026, 8, 29))

    def test_review_state_sets_the_window(self):
        r = self.run_checkup([org("a", "https://a.org/feed")], {"a": cache(
            post("2026-09-20", "After review", "https://a.org/1"),
            post("2026-09-18", "On review day", "https://a.org/2"),
            post("2026-09-17", "Before review", "https://a.org/3"),
        )}, state={"a": {"reviewed": "2026-09-18"}})
        self.assertEqual([i["title"] for i in r["feeds"][0]["items"]], ["After review", "On review day"])

    def test_since_override_ignores_state(self):
        r = self.run_checkup([org("a", "https://a.org/feed")],
                             {"a": cache(post("2026-09-17", "P", "https://a.org/3"))},
                             state={"a": {"reviewed": "2026-09-18"}}, since_override=date(2026, 9, 1))
        self.assertEqual(len(r["feeds"][0]["items"]), 1)

    def test_posts_already_cited_as_events_are_hidden(self):
        r = self.run_checkup([org("a", "https://a.org/feed")], {"a": cache(
            post("2026-09-20", "Recorded", "https://a.org/launch/"),
            post("2026-09-21", "New", "https://a.org/other"),
        )}, recorded={nc.norm_url("http://www.a.org/launch?utm_source=x#top")})
        self.assertEqual([i["title"] for i in r["feeds"][0]["items"]], ["New"])
        self.assertEqual(r["recorded"], 1)

    def test_shared_feed_is_one_section(self):
        feed = "https://parent.org/feed"
        items = cache(post("2026-09-20", "P", "https://parent.org/p"))
        r = self.run_checkup([org("parent", feed), org("chapter", feed)],
                             {"parent": items, "chapter": items})
        self.assertEqual(len(r["feeds"]), 1)
        self.assertEqual([o["slug"] for o in r["feeds"][0]["orgs"]], ["parent", "chapter"])
        self.assertEqual(len(r["feeds"][0]["items"]), 1)

    def test_never_read_empty_and_dormant_are_reported_apart(self):
        r = self.run_checkup([org("unread", "https://u.org/feed"), org("empty", "https://e.org/feed"),
                              org("quiet", "https://q.org/feed"), org("dormant", "https://d.org/feed")],
                             {"empty": cache(), "quiet": cache(post("2026-08-01", "Seen", "https://q.org/1")),
                              "dormant": cache(latest="2019-06-26")})
        self.assertEqual([s["orgs"][0]["slug"] for s in r["uncollected"]], ["unread"])
        self.assertEqual([s["orgs"][0]["slug"] for s in r["empty"]], ["empty"])
        self.assertEqual([s["orgs"][0]["slug"] for s in r["quiet"]], ["quiet", "dormant"])
        md = nc.render_markdown(r)
        self.assertIn("No new posts: `quiet`.", md)
        self.assertIn("`dormant` (2019-06-26)", md)

    def test_a_feed_that_breaks_keeps_its_unreviewed_posts(self):
        r = self.run_checkup([org("a", "https://a.org/feed")],
                             {"a": cache(post("2026-09-20", "Saved last week", "https://a.org/1"), latest=None)})
        self.assertEqual([s["orgs"][0]["slug"] for s in r["empty"]], ["a"])
        self.assertEqual([i["title"] for i in r["feeds"][0]["items"]], ["Saved last week"])

    def test_failing_feed_is_reported_with_its_retry_and_keeps_its_posts(self):
        failing = {"error": "HTTP_404", "since": "2026-09-21", "count": 2, "last": "2026-09-28"}
        r = self.run_checkup([org("a", "https://a.org/feed"), org("b", "https://b.org/feed")], {
            "a": {**cache(post("2026-09-20", "Saved before it broke", "https://a.org/1")), "failing": failing},
            "b": {"latest": None, "items": [], "failing": failing, "read": False},
        })
        self.assertEqual([s["orgs"][0]["slug"] for s in r["failing"]], ["a", "b"])
        self.assertEqual(r["uncollected"], [])  # failing, not "never tried"
        self.assertEqual(r["empty"], [])
        self.assertEqual([i["title"] for i in r["feeds"][0]["items"]], ["Saved before it broke"])
        self.assertIn("HTTP_404 since 2026-09-21, 2 failed read(s), next try 2026-10-12",
                      nc.render_markdown(r))

    def test_news_page_orgs_use_the_last_scrape(self):
        orgs = [
            org("fresh", news_page="https://f.org/news",
                scrape={"date": "2026-09-20", "note": "Latest post: X", "checked": "2026-09-25"}),
            org("stale", news_page="https://s.org/news", scrape={"date": "2026-06-01"}),
            org("nothing"),
        ]
        r = self.run_checkup(orgs, {})
        self.assertEqual([p["org"]["slug"] for p in r["pages"]], ["fresh"])
        self.assertEqual(r["uncovered"], 1)

    def test_stale_read_is_flagged(self):
        r = self.run_checkup([org("a", "https://a.org/feed", rss_read=date(2026, 8, 1))],
                             {"a": cache(post("2026-09-20", "P", "https://a.org/1"))})
        self.assertTrue(r["feeds"][0]["stale"])


class MarkReviewedTests(unittest.TestCase):
    def report(self, orgs, items):
        return nc.checkup(orgs, set(), {}, TODAY, load_items=lambda slug: items.get(slug))

    def test_marks_through_the_read_date_not_today(self):
        state = {}
        r = self.report([org("a", "https://a.org/feed", rss_read=date(2026, 9, 25))],
                        {"a": cache(post("2026-09-20", "P", "https://a.org/1"))})
        nc.mark_reviewed(state, r)
        self.assertEqual(state, {"a": {"reviewed": "2026-09-25"}})

    def test_quiet_feeds_are_marked_too(self):
        state = {}
        r = self.report([org("a", "https://a.org/feed")], {"a": cache()})
        nc.mark_reviewed(state, r)
        self.assertEqual(state, {})  # empty feed: nothing was reviewed
        r = self.report([org("a", "https://a.org/feed")], {"a": cache(post("2026-01-01", "Old", "https://a.org/1"))})
        nc.mark_reviewed(state, r)
        self.assertEqual(state, {"a": {"reviewed": "2026-09-25"}})

    def test_never_moves_backwards(self):
        state = {"a": {"reviewed": "2026-09-27"}}
        r = self.report([org("a", "https://a.org/feed", rss_read=date(2026, 9, 25))],
                        {"a": cache(post("2026-09-27", "P", "https://a.org/1"))})
        self.assertEqual(nc.mark_reviewed(state, r), 0)
        self.assertEqual(state["a"]["reviewed"], "2026-09-27")

    def test_unread_feed_is_not_marked(self):
        state = {}
        r = self.report([org("a", "https://a.org/feed")], {})
        nc.mark_reviewed(state, r)
        self.assertEqual(state, {})

    def test_news_page_marked_through_its_scrape(self):
        state = {}
        r = self.report([org("p", news_page="https://p.org/news",
                             scrape={"date": "2026-09-20", "checked": "2026-09-26"})], {})
        nc.mark_reviewed(state, r)
        self.assertEqual(state, {"p": {"reviewed": "2026-09-26"}})


class RenderTests(unittest.TestCase):
    def test_titles_cannot_break_their_links(self):
        r = nc.checkup([org("a", "https://a.org/feed")], set(), {}, TODAY,
                       load_items=lambda s: cache(post("2026-09-20", "[Draft]\n report", "https://a.org/1")))
        md = nc.render_markdown(r)
        self.assertIn("- 2026-09-20 — [\\[Draft\\] report](https://a.org/1)", md)
        self.assertIn("**1 new post from 1 feed**", md)


if __name__ == "__main__":
    unittest.main()
