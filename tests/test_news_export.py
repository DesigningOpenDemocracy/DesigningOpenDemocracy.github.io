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

    def test_upcoming_is_the_calendars_unless_major_and_announced(self):
        # calendar_export.py takes date >= today. Of those, only a major event
        # inside its announcement window is news too (AnnouncementTests).
        self.assertEqual(self.titles([ev(0, "today, notable", "medium"),
                                      ev(-3, "future, notable", "medium"),
                                      ev(1, "yesterday", "medium")]), ["yesterday"])

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


class AnnouncementTests(unittest.TestCase):
    """Major events are announced ANNOUNCE_LEAD_DAYS ahead; nothing else is."""

    lead = ne.ANNOUNCE_LEAD_DAYS[True]

    def collect(self, events, today=TODAY):
        return ne.collect_news([("a", org("A", events=events))], today)

    def test_major_event_inside_the_window_is_announced(self):
        items = self.collect([ev(-self.lead, "edge"), ev(-self.lead - 1, "too early"),
                              ev(0, "today")])
        self.assertEqual([(i["title"], i["upcoming"]) for i in items],
                         [("today", True), ("edge", True)])

    def test_notable_tier_is_never_announced(self):
        self.assertEqual(self.collect([ev(-1, "soon", "medium"), ev(0, "today", "medium")]), [])

    def test_publish_date_is_the_announcement_then_the_event(self):
        url = "https://x.example/forum"
        before = self.collect([ev(-10, url=url)])[0]
        self.assertEqual(before["published"], before["date"] - timedelta(days=self.lead))
        after = self.collect([ev(-10, url=url)], today=TODAY + timedelta(days=11))[0]
        self.assertFalse(after["upcoming"])
        self.assertEqual(after["published"], after["date"])
        # Same item to a subscriber, before and after.
        self.assertEqual(before["id"], after["id"])

    def test_coming_up_first_soonest_first_then_newest_first(self):
        items = self.collect([ev(3, "past recent"), ev(-20, "later"), ev(40, "past old"),
                              ev(-2, "sooner")])
        self.assertEqual([i["title"] for i in items],
                         ["sooner", "later", "past recent", "past old"])

    def test_unannounced_cohost_is_still_credited(self):
        # The major copy is announced; the co-host's notable-tier copy of the
        # same event can't be announced on its own, but it's the same event.
        url = "https://tickets.example/summit"
        items = ne.collect_news([
            ("a-cohost", org("Cohost", events=[ev(-5, "Cohost copy", "medium", url=url)])),
            ("b-host", org("Host", events=[ev(-5, "Host copy", True, url=url)])),
        ], TODAY)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Host copy")
        self.assertEqual(sorted(o["title"] for o in items[0]["orgs"]), ["Cohost", "Host"])

    def test_feed_marks_an_announcement(self):
        items = self.collect([ev(-10, "Forum", url="https://x.example/f",
                                 end_date=TODAY + timedelta(days=12))])
        with tempfile.TemporaryDirectory() as tmp:
            ne.write_feeds(items, ne.feed_slices([], items, {}), tmp, SITE, {})
            item = ET.parse(os.path.join(tmp, "news.xml")).getroot().find("channel/item")
            with open(os.path.join(tmp, "news.json"), encoding="utf-8") as f:
                feed = json.load(f)
        self.assertEqual(item.findtext("title"), "A: Forum (coming up 7 Oct 2026)")
        # Announced 30 days before 7 Oct; never a future pubDate.
        self.assertEqual(item.findtext("pubDate"), "Mon, 07 Sep 2026 00:00:00 +0000")
        self.assertIn("Coming up:</strong> Wednesday, 7 October 2026 to Friday, 9 October 2026",
                      item.findtext("description"))
        self.assertIs(feed["items"][0]["_dod"]["upcoming"], True)
        self.assertEqual(feed["items"][0]["date_published"], "2026-09-07T00:00:00+00:00")


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


class TopicTests(unittest.TestCase):
    """Orgs that only partly work on democracy (democracy_focus: partial)
    contribute only events marked democracy_related: true."""

    def titles(self, orgs):
        return [i["title"] for i in ne.collect_news(orgs, TODAY)]

    def test_partial_org_needs_an_explicit_yes(self):
        partial = org("Bank", democracy_focus="partial", events=[
            ev(5, "Unmarked"),
            ev(6, "Marked no", democracy_related=False),
            ev(7, "Marked yes", democracy_related=True),
            ev(8, "Truthy string is not a yes", democracy_related="yes"),
        ])
        self.assertEqual(self.titles([("bank", partial)]), ["Marked yes"])

    def test_democracy_focused_org_is_unaffected(self):
        core = org("Core", events=[ev(5, "Any notable event"),
                                   ev(6, "Even one marked no", democracy_related=False)])
        self.assertEqual(self.titles([("core", core)]), ["Any notable event", "Even one marked no"])

    def test_off_topic_cohost_still_joins_a_news_item(self):
        # The 888 / DOD case, in both filename orders: the partial org's
        # unmarked copy of the event can't create an item, but it is still
        # listed as a co-host of the democracy-focused org's item.
        url = "https://tickets.example/panel"
        for first, second in (("a-coop", "z-dod"), ("z-coop", "a-dod")):
            coop = org("Co-op", democracy_focus="partial", events=[ev(5, "Coop copy", url=url)])
            dod = org("DOD", events=[ev(5, "DOD copy", url=url)])
            orgs = sorted([(first, coop), (second, dod)])
            items = ne.collect_news(orgs, TODAY)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["title"], "DOD copy")
            self.assertEqual(sorted(o["title"] for o in items[0]["orgs"]), ["Co-op", "DOD"])

    def test_off_topic_event_alone_creates_nothing(self):
        coop = org("Co-op", democracy_focus="partial",
                   events=[ev(5, "Coop only", url="https://x.example/1")])
        self.assertEqual(self.titles([("coop", coop)]), [])


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


if __name__ == "__main__":
    unittest.main()
