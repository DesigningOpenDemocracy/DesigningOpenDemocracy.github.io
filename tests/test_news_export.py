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


def ev(days_ago, title="Something happened", notable=True, url=None, **extra):
    e = {"date": TODAY - timedelta(days=days_ago), "title": title, "notable": notable}
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
        # Notable, not major: major events are announced ahead (below).
        self.assertEqual(self.titles([ev(0, "today", "medium"), ev(1, "yesterday", "medium"),
                                      ev(-3, "future", "medium")]), ["yesterday"])

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


class AnnouncementTests(unittest.TestCase):
    """Major events enter News ANNOUNCE_DAYS before they start."""

    def collect(self, events, **kw):
        return ne.collect_news([("a", org("A", events=events))], TODAY, **kw)

    def test_major_event_is_announced_inside_its_lead_time(self):
        lead = ne.ANNOUNCE_DAYS[True]
        items = self.collect([ev(-lead, "on the edge"), ev(-(lead + 1), "too far out")])
        self.assertEqual([i["title"] for i in items], ["on the edge"])
        self.assertTrue(items[0]["upcoming"])
        self.assertEqual(items[0]["announced"], TODAY)

    def test_notable_events_are_not_announced(self):
        self.assertEqual(self.collect([ev(-3, "soon", "medium")]), [])

    def test_a_running_major_event_stays_as_on_now(self):
        items = self.collect([ev(2, "running", end_date=TODAY + timedelta(days=2))])
        self.assertTrue(items[0]["upcoming"] and items[0]["ongoing"])

    def test_announcements_lead_soonest_first_then_past_newest_first(self):
        items = self.collect([ev(5, "past older"), ev(-20, "later"), ev(1, "past newer"),
                              ev(-2, "sooner")])
        self.assertEqual([i["title"] for i in items],
                         ["sooner", "later", "past newer", "past older"])

    def test_feeds_publish_it_under_the_announcement_date(self):
        items = self.collect([ev(-10, "Summit")])
        rss = ne.render_rss(items, title="t", description="d", page_url="p",
                            feed_url="f", site_url="https://x", concept_titles={})
        self.assertIn(ne._pub_date(TODAY - timedelta(days=ne.ANNOUNCE_DAYS[True] - 10)), rss)
        self.assertIn("(coming up", rss)

    def test_the_archive_takes_no_announcements(self):
        self.assertEqual(self.collect([ev(-3, "soon")], window_days=None,
                                      notable_only=False, announce_days={}), [])

    def test_a_major_event_can_ask_for_more_notice(self):
        items = self.collect([ev(-80, "summit", announce_days=90),
                              ev(-80, "default notice")])
        self.assertEqual([i["title"] for i in items], ["summit"])
        self.assertEqual(items[0]["announced"], TODAY - timedelta(days=10))

    def test_or_less(self):
        self.assertEqual(self.collect([ev(-20, "late", announce_days=7)]), [])

    def test_a_notable_event_cannot_opt_itself_in(self):
        self.assertEqual(self.collect([ev(-3, "soon", "medium", announce_days=30)]), [])

    def test_an_invalid_value_falls_back_to_the_default(self):
        # check_event_sourcing.py fails the build on these; the hook just
        # doesn't let them change anything.
        for bad in (0, 400, "90", True):
            with self.subTest(value=bad):
                items = self.collect([ev(-80, "summit", announce_days=bad)])
                self.assertEqual(items, [])


class ArchiveTests(unittest.TestCase):
    """/archive/ is collect_news() with the limits off."""

    def test_every_tier_and_no_window(self):
        events = [ev(2, "recent major", True), ev(5, "untiered", False),
                  ev(4000, "long ago", "medium"), ev(-3, "upcoming", True)]
        items = ne.collect_news([("a", org("A", events=events))], TODAY,
                                window_days=None, notable_only=False, announce_days={})
        self.assertEqual([i["title"] for i in items], ["recent major", "untiered", "long ago"])

    def test_news_itself_still_skips_untiered(self):
        items = ne.collect_news([("a", org("A", events=[ev(5, "untiered", False)]))], TODAY)
        self.assertEqual(items, [])


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
