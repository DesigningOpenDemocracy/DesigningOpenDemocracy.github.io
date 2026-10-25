#!/usr/bin/env python3
"""Regression tests for the sitemap new-pages signal: check_rss.py's
read_sitemap()/record_sitemap_pages() and the section news_checkup.py builds
from them.

Why it exists: an org with no RSS feed was invisible to the news checkup.
Australian Democracy Network's site is a JavaScript app with no feed, and its
new Declaration campaign page and two event pages (October 2026) were only
spotted by a person, though its sitemap listed all three. What's pinned:

  - The first read of a sitemap is a baseline and lists nothing; otherwise
    every page on the site would arrive as "new" at once.
  - Only URLs absent from the previous read are new, and a page already
    recorded stays recorded with the date it first appeared.
  - A failed or unreadable read never overwrites the baseline, so a site that
    errors for a week doesn't then report every page as new.
  - Archive-style paths (tags, categories, pagination) are ignored, and a
    sitemap too large to track isn't tracked.
  - A sitemap index is followed to one child: the newest by <lastmod>.
  - Switching to a different sitemap starts a new baseline.
  - The checkup lists new pages for orgs with no feed, hides any already
    cited as an event, marks review through the sitemap's read date, and
    stops counting a tracked org as one it "can't see".

Offline: a fake session stands in for the network. Run with:

    python -m unittest discover tests
"""

import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import check_rss as cr  # noqa: E402
import news_checkup as nc  # noqa: E402

TODAY = date(2026, 10, 25)
SITEMAP = "https://ex.org/sitemap.xml"


def urlset(*paths, lastmod=None):
    lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
    urls = "".join(f"<url><loc>https://ex.org{p}</loc>{lm}</url>" for p in paths)
    return ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{urls}</urlset>").encode()


class FakeResponse:
    def __init__(self, body, status=200):
        self.content = body
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, bodies):
        self.bodies = bodies
        self.headers = {}
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        body = self.bodies.get(url)
        return FakeResponse(body or b"", 200 if body else 404)


class ReadSitemapTests(unittest.TestCase):
    def test_urlset(self):
        res = cr.read_sitemap(SITEMAP, session=FakeSession({SITEMAP: urlset("/a", "/b", lastmod="2026-10-01")}))
        self.assertEqual(res["pages"], ["https://ex.org/a", "https://ex.org/b"])
        self.assertEqual(res["lastmod"], date(2026, 10, 1))

    def test_index_follows_newest_child_only(self):
        index = ('<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                 "<sitemap><loc>https://ex.org/old.xml</loc><lastmod>2024-01-01</lastmod></sitemap>"
                 "<sitemap><loc>https://ex.org/new.xml</loc><lastmod>2026-10-20</lastmod></sitemap>"
                 "</sitemapindex>").encode()
        session = FakeSession({SITEMAP: index, "https://ex.org/new.xml": urlset("/fresh")})
        res = cr.read_sitemap(SITEMAP, session=session)
        self.assertEqual(res["pages"], ["https://ex.org/fresh"])
        self.assertEqual(session.calls, [SITEMAP, "https://ex.org/new.xml"])

    def test_index_with_unreadable_child_has_no_page_list(self):
        index = ('<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                 "<sitemap><loc>https://ex.org/post-sitemap.xml</loc></sitemap></sitemapindex>").encode()
        res = cr.read_sitemap(SITEMAP, session=FakeSession({SITEMAP: index}))
        self.assertIsNone(res["pages"])

    def test_unreadable_sitemap(self):
        self.assertIsNone(cr.read_sitemap(SITEMAP, session=FakeSession({})))


class RecordSitemapPagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        cr.record_discovery("ex", SITEMAP, TODAY, self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, *paths, today=TODAY):
        return cr.record_sitemap_pages("ex", SITEMAP, [f"https://ex.org{p}" for p in paths], today, self.dir)

    def test_first_read_is_a_baseline(self):
        self.assertEqual(self.record("/about", "/contact"), [])
        state = cr.load_feed_state("ex", self.dir)
        self.assertEqual(state["seen"], sorted([cr._seen_key("https://ex.org/about"),
                                                cr._seen_key("https://ex.org/contact")]))
        self.assertNotIn("pages", state)

    def test_new_urls_are_recorded_with_a_title_from_the_url(self):
        self.record("/about")
        new = self.record("/about", "/unlocking-better-politics-melbourne")
        self.assertEqual([p["title"] for p in new], ["unlocking better politics melbourne"])
        pages = cr.load_feed_state("ex", self.dir)["pages"]
        self.assertEqual(pages[0]["url"], "https://ex.org/unlocking-better-politics-melbourne")
        self.assertEqual(pages[0]["date"], "2026-10-25")

    def test_signals_come_from_the_url_title(self):
        self.record("/about")
        new = self.record("/about", "/annual-report-2026")
        self.assertIn("publication", new[0]["signals"])

    def test_a_page_keeps_the_date_it_first_appeared(self):
        self.record("/about")
        self.record("/about", "/declaration")
        self.record("/declaration", today=date(2026, 11, 22))  # /about gone: not new, nothing new
        self.record("/about", "/declaration", today=date(2026, 12, 20))  # /about back: new again
        pages = {p["url"]: p["date"] for p in cr.load_feed_state("ex", self.dir)["pages"]}
        self.assertEqual(pages["https://ex.org/declaration"], "2026-10-25")
        self.assertEqual(pages["https://ex.org/about"], "2026-12-20")

    def test_archive_paths_are_ignored(self):
        self.record("/about")
        self.assertEqual(self.record("/about", "/tag/democracy", "/category/news/", "/blog/page/2"), [])

    def test_too_large_to_track(self):
        self.record("/about")
        paths = [f"/p{i}" for i in range(cr.SITEMAP_SEEN_MAX + 1)]
        self.assertIsNone(self.record(*paths))
        self.assertNotIn("seen", cr.load_feed_state("ex", self.dir))

    def test_a_different_sitemap_starts_a_new_baseline(self):
        self.record("/about")
        cr.record_discovery("ex", "https://ex.org/other-sitemap.xml", TODAY, self.dir)
        self.assertNotIn("seen", cr.load_feed_state("ex", self.dir))

    def test_finding_a_feed_drops_page_tracking(self):
        self.record("/about")
        self.record("/about", "/new")
        cr.save_feed_items("ex", "https://ex.org/feed", [], TODAY, self.dir)
        state = cr.load_feed_state("ex", self.dir)
        self.assertNotIn("seen", state)
        self.assertNotIn("pages", state)

    def test_same_page_however_written_is_not_new(self):
        cr.record_sitemap_pages("ex", SITEMAP, ["http://www.ex.org/about/"], TODAY, self.dir)
        self.assertEqual(self.record("/about"), [])

    def test_index_skips_author_and_tag_children(self):
        children = [("https://ex.org/post-sitemap.xml", date(2025, 1, 1)),
                    ("https://ex.org/author-sitemap.xml", date(2026, 6, 1)),
                    ("https://ex.org/post_tag-sitemap.xml", date(2026, 7, 1))]
        self.assertEqual(cr._pick_child_sitemap(children), "https://ex.org/post-sitemap.xml")

    def test_titles(self):
        self.assertEqual(cr.page_title_from_url("https://ex.org/news/Big_News%20Day.html"), "Big News Day")
        self.assertEqual(cr.page_title_from_url("https://ex.org/"), "ex.org")


def org(slug, news_page="", sitemap_read=date(2026, 10, 20)):
    return {"slug": slug, "title": slug.title(), "rss_feed": "", "news_page": news_page,
            "rss_read": None, "sitemap_read": sitemap_read, "scrape": {}}


def tracked(*pages):
    return {"latest": None, "items": [], "failing": None, "read": False,
            "sitemap": SITEMAP, "tracked": True, "pages": list(pages)}


class CheckupSitemapTests(unittest.TestCase):
    def run_checkup(self, orgs, caches, recorded=(), state=None):
        return nc.checkup(orgs, set(recorded), state or {}, TODAY, load_items=lambda s: caches.get(s))

    def test_new_pages_are_listed_and_untracked_orgs_counted_unseen(self):
        r = self.run_checkup([org("adn"), org("dark")], {"adn": tracked(
            {"date": "2026-10-20", "title": "declaration", "url": "https://ex.org/declaration"},
            {"date": "2026-08-01", "title": "old", "url": "https://ex.org/old"})})
        self.assertEqual(len(r["feeds"]), 1)
        self.assertTrue(r["feeds"][0]["sitemap"])
        self.assertEqual([i["title"] for i in r["feeds"][0]["items"]], ["declaration"])
        self.assertEqual(r["uncovered"], 1)
        md = nc.render_markdown(r)
        self.assertIn("new page since", md)
        self.assertIn("titled from their URLs", md)

    def test_a_tracked_org_with_nothing_new_is_not_unseen(self):
        r = self.run_checkup([org("adn")], {"adn": tracked()})
        self.assertEqual(r["feeds"], [])
        self.assertEqual(r["uncovered"], 0)

    def test_recorded_pages_are_hidden(self):
        r = self.run_checkup([org("adn")], {"adn": tracked(
            {"date": "2026-10-20", "title": "declaration", "url": "https://ex.org/declaration"})},
            recorded={nc.norm_url("https://www.ex.org/declaration/")})
        self.assertEqual(r["feeds"], [])
        self.assertEqual(r["recorded"], 1)

    def test_review_is_marked_through_the_sitemap_read(self):
        r = self.run_checkup([org("adn")], {"adn": tracked(
            {"date": "2026-10-20", "title": "declaration", "url": "https://ex.org/declaration"})})
        state = {}
        nc.mark_reviewed(state, r)
        self.assertEqual(state, {"adn": {"reviewed": "2026-10-20"}})


if __name__ == "__main__":
    unittest.main()
