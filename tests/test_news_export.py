#!/usr/bin/env python3
"""Regression tests for hooks/news_export.py — Landscape News and its feeds.

What's pinned, and why each is worth pinning rather than eyeballing:

  - Which events are news: a notable: tier, dated before today and within the
    window. The boundary with the calendar (date >= today) has to be exact,
    or an event sits on both pages or on neither.
  - Co-hosted events recorded on two org pages merge into one item, not two
    in every subscriber's reader.
  - Item ids stay put when a title is reworded or a co-host merges in: a
    changed id reaches every subscriber as a brand-new item.
  - Every country and topic in the landscape gets a feed even with nothing
    in the window, so a subscribed URL never 404s through a quiet year.
  - The feeds are well-formed and escape what they're given.

Offline and stdlib-only apart from the python-frontmatter the hook needs.
Run with:

    python -m unittest discover tests
"""

import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

import news_export as ne  # noqa: E402

TODAY = date(2026, 9, 27)
SITE = "https://example.org"


def org(title, country="AU", concepts=None, events=None, **extra):
    m = {"title": title, "country": country, "concepts": concepts or [],
         "events": events or []}
    m.update(extra)
    return m


def ev(days_ago, title="Something happened", notable=True, url=None, kind="launch", **extra):
    # "launch" by default: news once it's happened, so the tests below that
    # aren't about kind exercise the rest of the selection rule on its own. KindTests pins
    # what each kind does.
    e = {"date": TODAY - timedelta(days=days_ago), "title": title, "notable": notable,
         "kind": kind}
    if url is not None:
        e["url"] = url
    e.update(extra)
    return e


class SelectionTests(unittest.TestCase):
    """What counts as news."""

    def titles(self, events):
        items = ne.collect_news([("a", org("A", events=events))], TODAY)
        return [i["title"] for i in items]

    def test_only_tiered_events(self):
        self.assertEqual(
            self.titles([ev(5, "major", True), ev(5, "medium", "medium"),
                         ev(5, "plain", False), ev(5, "absent", None),
                         ev(5, "typo", "high")]),
            ["major", "medium"])

    def test_today_belongs_to_the_calendar_not_the_news(self):
        # calendar_export.py takes date >= today, so news must take < today.
        self.assertEqual(self.titles([ev(0, "today"), ev(1, "yesterday"),
                                      ev(-3, "future")]), ["yesterday"])

    def test_a_running_event_stays_on_the_calendar_until_it_ends(self):
        # calendar_export keeps an event while it's under way, so news must
        # not take it until its end_date has passed.
        running = ev(3, "running", "medium", end_date=TODAY + timedelta(days=1))
        ended = ev(5, "ended", "medium", end_date=TODAY - timedelta(days=1))
        self.assertEqual(self.titles([running, ended]), ["ended"])

    def test_window_edges(self):
        w = ne.NEWS_WINDOW_DAYS
        self.assertEqual(self.titles([ev(w, "edge"), ev(w + 1, "too old")]), ["edge"])

    def test_newest_first_major_before_notable_on_the_same_day(self):
        items = ne.collect_news([
            ("a", org("A", events=[ev(10, "older"), ev(2, "notable", "medium")])),
            ("b", org("B", events=[ev(2, "major", True)])),
        ], TODAY)
        self.assertEqual([i["title"] for i in items], ["major", "notable", "older"])

    def test_event_country_overrides_org_country(self):
        items = ne.collect_news([("a", org("A", country="US",
                                           events=[ev(3, country="AU")]))], TODAY)
        self.assertEqual(items[0]["countries"], ["AU"])


class MergeTests(unittest.TestCase):
    """Co-hosted events recorded on each co-host's page."""

    def test_same_date_and_url_merge(self):
        url = "https://tickets.example/panel"
        items = ne.collect_news([
            ("888", org("888", concepts=["cooperative"],
                        events=[ev(5, "Panel with DOD", "medium", url=url)])),
            ("dod", org("DOD", country="NZ", concepts=["democracy", "cooperative"],
                        events=[ev(5, "Panel with 888", True, url=url)])),
        ], TODAY)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual([o["slug"] for o in item["orgs"]], ["888", "dod"])
        self.assertEqual(item["title"], "Panel with DOD")   # first org's wording
        self.assertIs(item["notable"], True)                # stronger tier wins
        self.assertEqual(item["countries"], ["AU", "NZ"])
        self.assertEqual(item["concepts"], ["cooperative", "democracy"])

    def test_different_url_or_date_stays_separate(self):
        items = ne.collect_news([
            ("a", org("A", events=[ev(5, url="https://x.example/1")])),
            ("b", org("B", events=[ev(5, url="https://x.example/2"),
                                   ev(6, url="https://x.example/1")])),
        ], TODAY)
        self.assertEqual(len(items), 3)

    def test_urlless_events_never_merge(self):
        items = ne.collect_news([
            ("a", org("A", events=[ev(5, "same", source="A book, p. 12, 2019 edition")])),
            ("b", org("B", events=[ev(5, "same", source="A book, p. 12, 2019 edition")])),
        ], TODAY)
        self.assertEqual(len(items), 2)


class GuidTests(unittest.TestCase):

    def guid(self, orgs):
        return ne.collect_news(orgs, TODAY)[0]["id"]

    def test_title_rewording_keeps_the_id(self):
        url = "https://x.example/launch"
        before = self.guid([("a", org("A", events=[ev(4, "Launching the handbook", url=url)]))])
        after = self.guid([("a", org("A", events=[ev(4, "Launched the handbook", url=url)]))])
        self.assertEqual(before, after)

    def test_cohost_merging_in_keeps_the_id(self):
        url = "https://x.example/panel"
        alone = self.guid([("b", org("B", events=[ev(4, url=url)]))])
        merged = self.guid([("a", org("A", events=[ev(4, "Other wording", url=url)])),
                            ("b", org("B", events=[ev(4, url=url)]))])
        self.assertEqual(alone, merged)

    def test_ids_differ_between_items(self):
        items = ne.collect_news([("a", org("A", events=[
            ev(4, url="https://x.example/1"), ev(4, url="https://x.example/2"),
            ev(4, "no url one"), ev(4, "no url two")]))], TODAY)
        self.assertEqual(len({i["id"] for i in items}), 4)


class LinkTests(unittest.TestCase):

    def test_quote_becomes_a_text_fragment(self):
        items = ne.collect_news([("a", org("A", events=[
            ev(3, url="https://x.example/p", quote="launched the second edition")]))], TODAY)
        self.assertEqual(items[0]["url"], "https://x.example/p")
        self.assertIn("#:~:text=", items[0]["href"])

    def test_dead_url_with_archive_links_the_archive(self):
        url = "https://gone.example/p"
        arch = "https://web.archive.org/web/2026/https://gone.example/p"
        items = ne.collect_news(
            [("a", org("A", events=[ev(3, url=url)]))], TODAY,
            archive_info={url: {"archive_url": arch, "url_status": "dead"}})
        self.assertEqual(items[0]["href"], arch)

    def test_live_url_with_archive_keeps_the_original(self):
        url = "https://live.example/p"
        items = ne.collect_news(
            [("a", org("A", events=[ev(3, url=url)]))], TODAY,
            archive_info={url: {"archive_url": "https://web.archive.org/x"}})
        self.assertEqual(items[0]["href"], url)


class FeedSliceTests(unittest.TestCase):

    def test_quiet_countries_and_topics_still_get_feeds(self):
        orgs = [("a", org("A", country="AU", concepts=["sortition"], events=[ev(3)])),
                ("b", org("B", country="IS", concepts=["liquid-democracy"]))]
        items = ne.collect_news(orgs, TODAY)
        slices = ne.feed_slices(orgs, items, {})
        self.assertEqual({r["code"]: r["count"] for r in slices["countries"]},
                         {"AU": 1, "IS": 0})
        self.assertEqual({r["slug"]: r["count"] for r in slices["topics"]},
                         {"sortition": 1, "liquid-democracy": 0})

    def test_unsafe_slugs_never_become_file_names(self):
        orgs = [("a", org("A", country="../x", concepts=["../../etc", "Bad Slug", "ok-slug"]))]
        slices = ne.feed_slices(orgs, [], {})
        self.assertEqual(slices["countries"], [])
        self.assertEqual([r["slug"] for r in slices["topics"]], ["ok-slug"])

    def test_topic_label_prefers_the_concept_page_title(self):
        self.assertEqual(ne.topic_label("citizens-assembly", {"citizens-assembly": "Citizens’ Assembly"}),
                         "Citizens’ Assembly")
        self.assertEqual(ne.topic_label("liquid-democracy", {}), "Liquid Democracy")


class WriteFeedsTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.orgs = [
            ("a", org("A & Co", country="AU", concepts=["sortition"], events=[
                ev(3, "Launch <b>", True, url="https://x.example/a?x=1&y=2",
                   note="Note with <script>alert(1)</script>", notable_reason="Flagship")])),
            ("b", org("B", country="NZ", concepts=["democracy"], events=[
                ev(9, "Report", "medium", source="Annual report, printed edition 2026")])),
            ("c", org("C", country="IS", concepts=["liquid-democracy"])),
        ]
        self.items = ne.collect_news(self.orgs, TODAY)
        self.slices = ne.feed_slices(self.orgs, self.items, {})
        ne.write_feeds(self.items, self.slices, self.tmp.name, SITE, {})

    def rss_items(self, name):
        root = ET.parse(os.path.join(self.tmp.name, name)).getroot()
        self.assertEqual(root.tag, "rss")
        return root.find("channel").findall("item")

    def test_every_slice_is_written_and_well_formed(self):
        self.assertEqual(len(self.rss_items("news.xml")), 2)
        self.assertEqual(len(self.rss_items("news-AU.xml")), 1)
        self.assertEqual(len(self.rss_items("news-NZ.xml")), 1)
        self.assertEqual(len(self.rss_items("news-IS.xml")), 0)   # quiet, not missing
        self.assertEqual(len(self.rss_items("news-topic-sortition.xml")), 1)
        self.assertEqual(len(self.rss_items("news-topic-liquid-democracy.xml")), 0)

    def test_item_shape(self):
        first = self.rss_items("news.xml")[0]
        self.assertEqual(first.findtext("title"), "A & Co: Launch <b>")
        self.assertEqual(first.findtext("link"), "https://x.example/a?x=1&y=2")
        self.assertEqual(first.find("guid").get("isPermaLink"), "false")
        self.assertEqual(first.findtext("pubDate"), "Thu, 24 Sep 2026 00:00:00 +0000")
        cats = [c.text for c in first.findall("category")]
        self.assertIn("Major", cats)
        self.assertIn("Australia", cats)
        # The description is HTML carried as text: markup from frontmatter is
        # escaped inside it, never live.
        desc = first.findtext("description")
        self.assertIn("&lt;script&gt;", desc)
        self.assertNotIn("<script>", desc)

    def test_urlless_item_links_to_the_org_profile(self):
        second = self.rss_items("news.xml")[1]
        self.assertEqual(second.findtext("link"), f"{SITE}/organisations/b/")
        self.assertIn("Cited: Annual report", second.findtext("description"))

    def test_json_feed(self):
        with open(os.path.join(self.tmp.name, "news.json"), encoding="utf-8") as f:
            feed = json.load(f)
        self.assertEqual(feed["version"], "https://jsonfeed.org/version/1.1")
        self.assertEqual(feed["feed_url"], f"{SITE}/news.json")
        rss_ids = [i.findtext("guid") for i in self.rss_items("news.xml")]
        self.assertEqual([i["id"] for i in feed["items"]], rss_ids)
        self.assertEqual(feed["items"][0]["_dod"]["tier"], "major")
        self.assertEqual(feed["items"][1]["_dod"]["tier"], "medium")
        self.assertEqual(feed["items"][0]["date_published"], "2026-09-24T00:00:00+00:00")

    def test_unchanged_feeds_are_not_rewritten(self):
        path = os.path.join(self.tmp.name, "news.xml")
        os.utime(path, (1, 1))
        ne.write_feeds(self.items, self.slices, self.tmp.name, SITE, {})
        self.assertEqual(os.stat(path).st_mtime, 1)


class NoAnnouncementTests(unittest.TestCase):
    """Nothing upcoming or running is News, whatever its tier or kind: that
    is the calendar's. Major events used to be announced 30 days ahead
    under "Coming up"; removed 2026-09-30 as a copy of the calendar."""

    def test_upcoming_major_events_are_not_news(self):
        for kind in ("gathering", "launch", "news"):
            with self.subTest(kind=kind):
                self.assertEqual(ne.collect_news(
                    [("a", org("A", events=[ev(-3, "soon", kind=kind)]))], TODAY), [])

    def test_a_running_major_event_is_not_news(self):
        running = ev(2, "running", end_date=TODAY + timedelta(days=2))
        self.assertEqual(ne.collect_news([("a", org("A", events=[running]))], TODAY), [])


class ArchiveTests(unittest.TestCase):
    """/archive/ is collect_news() with the limits off."""

    def test_every_tier_and_no_window(self):
        events = [ev(2, "recent major", True), ev(5, "untiered", False),
                  ev(4000, "long ago", "medium"), ev(-3, "upcoming", True)]
        items = ne.collect_news([("a", org("A", events=events))], TODAY,
                                window_days=None, notable_only=False, kinds=None)
        self.assertEqual([i["title"] for i in items], ["recent major", "untiered", "long ago"])

    def test_news_itself_still_skips_untiered(self):
        items = ne.collect_news([("a", org("A", events=[ev(5, "untiered", False)]))], TODAY)
        self.assertEqual(items, [])


class KindTests(unittest.TestCase):
    """kind: keeps News and the calendar apart. A gathering (something to
    attend) is only ever the calendar's. A news item (something that
    happened) is only ever News'. A launch is both, in turn."""

    def titles(self, events, **kw):
        return [i["title"] for i in ne.collect_news([("a", org("A", events=events))], TODAY, **kw)]

    def test_past_gatherings_are_not_news(self):
        self.assertEqual(
            self.titles([ev(3, "conference", kind="gathering"), ev(3, "handbook", kind="news"),
                         ev(3, "report launch", kind="launch")]),
            ["handbook", "report launch"])

    def test_missing_kind_reads_as_a_gathering(self):
        e = ev(3, "untagged")
        del e["kind"]
        self.assertEqual(self.titles([e]), [])

    def test_archive_keeps_every_kind(self):
        events = [ev(3, "conference", kind="gathering"), ev(4, "handbook", kind="news")]
        self.assertEqual(self.titles(events, window_days=None, notable_only=False,
                                     kinds=None),
                         ["conference", "handbook"])


POST = """---
title: "{title}"
date: {date}
summary: A summary of the post.
{extra}---

Body.
"""


class BlogPostNewsTests(unittest.TestCase):
    """DOD blog posts reach News by opting in with `news:` in their own
    frontmatter (collect_blog_news), not as an events: entry on DOD's page:
    a writeup is something DOD published, not something that happened."""

    def setUp(self):
        if ne.frontmatter is None or ne._post_slugify is None:
            self.skipTest("python-frontmatter / pymdownx not installed")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.orgs = [(ne.DOD_SLUG, org("Designing Open Democracy", concepts=["sortition"]))]

    def post(self, name, days_ago=3, title="A recap", extra="news: true\n"):
        with open(os.path.join(self.tmp.name, name + ".md"), "w", encoding="utf-8") as f:
            f.write(POST.format(title=title, date=TODAY - timedelta(days=days_ago), extra=extra))

    def collect(self):
        return ne.collect_blog_news(self.orgs, TODAY, posts_dir=self.tmp.name)

    def test_only_opted_in_published_posts_in_the_window(self):
        self.post("in", title="In")
        self.post("major", title="Major", extra="news: major\n")
        self.post("not-flagged", title="Not flagged", extra="")
        self.post("draft", title="Draft", extra="news: true\ndraft: true\n")
        self.post("old", title="Old", days_ago=ne.NEWS_WINDOW_DAYS + 1)
        self.post("future", title="Future", days_ago=-2)
        items = {i["title"]: i for i in self.collect()}
        self.assertEqual(set(items), {"In", "Major"})
        self.assertEqual(items["In"]["notable"], "medium")
        self.assertIs(items["Major"]["notable"], True)

    def test_attributed_to_dod_and_linked_to_the_post(self):
        self.post("recap", title="Democracy beyond the ballot box: recap of our International Day of Democracy panel")
        (item,) = self.collect()
        self.assertEqual(item["kind"], "post")
        self.assertEqual(item["org_slug"], ne.DOD_SLUG)
        self.assertEqual(item["concepts"], ["sortition"])
        self.assertEqual(item["note"], "A summary of the post.")
        d = TODAY - timedelta(days=3)
        self.assertEqual(item["href"], f"/blog/{d:%Y/%m/%d}/democracy-beyond-the-ballot-box-recap-of-our-international-day-of-democracy-panel/")

    def test_post_url_matches_the_blog_plugin(self):
        # Real published URLs, including the em dash that slugifies to a
        # double hyphen: if these drift, News links to 404s.
        for title, d, url in [
            ("Democracy beyond the ballot box: recap of our International Day of Democracy panel",
             date(2026, 9, 26),
             "/blog/2026/09/26/democracy-beyond-the-ballot-box-recap-of-our-international-day-of-democracy-panel/"),
            ("RadicalxChange is launching a Melbourne chapter — here's what it is", date(2026, 8, 7),
             "/blog/2026/08/07/radicalxchange-is-launching-a-melbourne-chapter--heres-what-it-is/"),
        ]:
            with self.subTest(title=title):
                self.assertEqual(ne.post_url({"title": title, "date": d}), url)
        self.assertEqual(ne.post_url({"title": "X", "slug": "custom", "date": {"created": date(2026, 1, 2)}}),
                         "/blog/2026/01/02/custom/")

    def test_countries_default_to_dods_and_can_be_set(self):
        self.orgs = [(ne.DOD_SLUG, org("Designing Open Democracy", country="AU"))]
        self.post("default", title="Default")
        self.post("taiwan", title="Taiwan", extra="news: true\nnews_countries: tw\n")
        self.post("both", title="Both", extra="news: true\nnews_countries: [AU, NZ, AU]\n")
        items = {i["title"]: i["countries"] for i in self.collect()}
        self.assertEqual(items, {"Default": ["AU"], "Taiwan": ["TW"], "Both": ["AU", "NZ"]})

    def test_unknown_country_fails_loudly(self):
        self.post("typo", title="Typo", extra="news: true\nnews_countries: [XQ]\n")
        with self.assertRaises(ValueError):
            self.collect()

    def test_title_falls_back_to_the_first_heading(self):
        # Older posts carry their title only as a `# ` heading, which is
        # what the blog plugin uses too.
        self.assertEqual(
            ne.post_url({"date": date(2026, 8, 3)},
                        "# We scored 21 parties on internal democracy and reform advocacy\n\nBody."),
            "/blog/2026/08/03/we-scored-21-parties-on-internal-democracy-and-reform-advocacy/")

    def test_archive_takes_older_posts(self):
        self.post("old", title="Old", days_ago=ne.NEWS_WINDOW_DAYS + 200)
        self.assertEqual(self.collect(), [])
        self.assertEqual([i["title"] for i in ne.collect_blog_news(
            self.orgs, TODAY, posts_dir=self.tmp.name, window_days=None)], ["Old"])

    def test_feed_links_are_absolute(self):
        self.post("recap", title="A recap")
        (item,) = self.collect()
        self.assertTrue(ne._item_link(item, SITE).startswith(SITE + "/blog/"))
        self.assertIn(f'href="{SITE}/blog/', ne.item_html(item, SITE, {}))


class CoverageUrlCorpusTests(unittest.TestCase):
    """Every event's coverage_url into the blog points at a real post.

    The link is typed by hand and runs to ~120 characters of slugified
    title, and a wrong one renders a "DOD coverage →" link to a 404 with
    nothing failing. Checked against post_url(), which is pinned to the blog
    plugin's real URLs above."""

    def test_blog_coverage_links_resolve(self):
        if ne.frontmatter is None or ne._post_slugify is None:
            self.skipTest("python-frontmatter / pymdownx not installed")
        import glob
        posts = set()
        for path in glob.glob(os.path.join(ne.POSTS_DIR, "*.md")):
            post = ne.frontmatter.load(path)
            if not post.metadata.get("draft"):
                posts.add(ne.post_url(post.metadata, post.content))
        bad = [(slug, str(e.get("date")), e["coverage_url"])
               for slug, m in ne.load_orgs()
               for e in m.get("events") or []
               if isinstance(e, dict) and str(e.get("coverage_url", "")).startswith("/blog/")
               and e["coverage_url"] not in posts]
        self.assertEqual(bad, [])


class ArchiveTabTests(unittest.TestCase):
    """The archive is outside the nav, so the hook lights the News tab while
    it renders, and must switch it off again after."""

    def setUp(self):
        import types
        self.types = types
        ne._lit.clear()
        self.news = self.page("news.md")
        self.nav = types.SimpleNamespace(pages=[self.page("calendar.md"), self.news])

    def page(self, src):
        return self.types.SimpleNamespace(file=self.types.SimpleNamespace(src_uri=src), active=False)

    def render(self, p):
        ne.on_page_context({}, page=p, config={}, nav=self.nav)
        seen = self.news.active
        ne.on_post_page("", page=p, config={})
        return seen

    def test_archive_lights_news_only_while_rendering(self):
        self.assertTrue(self.render(self.page("archive.md")))
        self.assertFalse(self.news.active)
        self.assertFalse(self.render(self.page("about.md")))

    def test_news_page_itself_is_left_to_mkdocs(self):
        self.news.active = True
        self.render(self.news)
        self.assertTrue(self.news.active)


if __name__ == "__main__":
    unittest.main()
