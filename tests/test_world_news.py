#!/usr/bin/env python3
"""Regression tests for util/world_news.py, the heartbeat's world-news
worklist.

What's pinned, and why each is worth pinning rather than eyeballing:

  - The vocabulary: named mechanisms match in several languages; the US
    Democratic Party doesn't count as the topic; the bare word "democracy"
    is only a weak signal, used when nothing specific matched.
  - Weak-only stories from a single outlet are counted, not listed, which is
    most of what keeps the worklist short.
  - The same story from several outlets is one line, and those come first.
  - A source is read at most every SOURCE_RECHECK_HOURS and backs off when
    failing, so several heartbeat runs a day don't re-ask anyone.
  - Only matching headlines are stored, with tracking parameters stripped,
    pruned after WORLD_KEEP_DAYS.
  - A first run lists by date (it stamps everything as just seen); later runs
    list what was first seen after the last review.
  - The sources file loads and every entry is complete.

Offline. Run with:

    python -m unittest discover tests
"""

import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import world_news as wn  # noqa: E402

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def item(title, source="BBC World", d="2026-10-24", url=None, seen=NOW, labels=None, mentions=None):
    out = {"date": d, "seen": seen.isoformat(), "title": title,
           "url": url or f"https://{source.replace(' ', '').lower()}.example/{abs(hash(title))}",
           "source": source, "region": "global",
           "labels": labels if labels is not None else wn.labels_for(title)}
    if mentions:
        out["mentions"] = mentions
    return out


class LabelTests(unittest.TestCase):
    def test_specific_mechanisms(self):
        self.assertEqual(wn.labels_for("Ireland to hold citizens' assembly on electoral reform"),
                         ["deliberative", "electoral system"])
        self.assertEqual(wn.labels_for("Mali junta postpones elections again"), ["backsliding"])
        self.assertEqual(wn.labels_for("City council adopts participatory budgeting"), ["participatory"])
        self.assertEqual(wn.labels_for("Senate passes lobbying disclosure bill"), ["integrity"])

    def test_other_languages(self):
        self.assertIn("deliberative", wn.labels_for("Madrid convoca una asamblea ciudadana sobre el clima"))
        self.assertIn("deliberative", wn.labels_for("Bundestag beruft neuen Bürgerrat ein"))
        self.assertIn("participatory", wn.labels_for("Porto Alegre retoma o orçamento participativo"))
        self.assertIn("direct democracy", wn.labels_for("Le gouvernement annonce un référendum"))

    def test_party_names_are_not_the_topic(self):
        self.assertEqual(wn.labels_for("Democratic Party picks new chair"), [])
        self.assertEqual(wn.labels_for("Democrats win Virginia governor's race"), [])

    def test_bare_democracy_is_weak_and_only_when_nothing_specific_matched(self):
        self.assertEqual(wn.labels_for("Is democracy in retreat?"), [wn.WEAK_LABEL])
        self.assertEqual(wn.labels_for("Democracy advocates call for referendum"), ["direct democracy"])

    def test_unrelated(self):
        self.assertEqual(wn.labels_for("Storm batters coast as thousands lose power"), [])

    def test_excerpt_counts(self):
        self.assertEqual(wn.labels_for("A vote in Fiji", "The government's constitutional amendment passed."),
                         ["constitutional"])


class GroupingTests(unittest.TestCase):
    def test_same_story_across_outlets_is_one(self):
        stories = wn.group_stories([
            item("Ireland announces citizens' assembly on electoral reform", "BBC World"),
            item("Ireland to convene citizens' assembly on electoral reform", "RTE"),
            item("Mali junta postpones elections again", "Al Jazeera"),
        ])
        self.assertEqual(sorted(len(s["sources"]) for s in stories), [1, 2])

    def test_several_outlets_rank_first_then_mentions(self):
        stories = wn.rank(wn.group_stories([
            item("Mali junta postpones elections again", "Al Jazeera", d="2026-10-25"),
            item("Ireland announces citizens' assembly on electoral reform", "BBC World", d="2026-10-20"),
            item("Ireland to convene citizens' assembly on electoral reform", "RTE", d="2026-10-20"),
            item("Report on lobbying in Canberra", "ABC", d="2026-10-21", mentions=["Australia Institute"]),
        ]))
        self.assertEqual(len(stories[0]["sources"]), 2)
        self.assertEqual(stories[1]["mentions"], ["Australia Institute"])


class ScheduleTests(unittest.TestCase):
    def test_read_at_most_every_recheck_hours(self):
        recent = {"read": (NOW - timedelta(hours=5)).isoformat()}
        old = {"read": (NOW - timedelta(hours=wn.SOURCE_RECHECK_HOURS)).isoformat()}
        self.assertFalse(wn.source_due(recent, NOW)[0])
        self.assertTrue(wn.source_due(old, NOW)[0])
        self.assertTrue(wn.source_due({}, NOW)[0])

    def test_failing_source_backs_off(self):
        rec = {"failing": {"error": "HTTP_404", "since": "2026-10-24", "count": 1, "last": "2026-10-24"}}
        self.assertFalse(wn.source_due(rec, NOW)[0])
        self.assertTrue(wn.source_due(rec, NOW + timedelta(days=7))[0])


class MergeTests(unittest.TestCase):
    def entry(self, title, link, d=date(2026, 10, 24)):
        return {"title": title, "link": link, "published": d, "summary_html": ""}

    def test_only_matches_are_kept_and_tracking_is_stripped(self):
        import check_rss as cr
        state = {"sources": {}, "items": []}
        added = wn.merge_matches(state, {"name": "Scroll", "region": "IN"}, [
            self.entry("Election Commission faces electoral roll challenge", "https://ex.in/a?utm_source=rss"),
            self.entry("Cricket: India win series", "https://ex.in/b"),
        ], NOW, clean_url=cr.strip_tracking)
        self.assertEqual(added, 1)
        self.assertEqual(state["items"][0]["url"], "https://ex.in/a")
        self.assertEqual(state["items"][0]["source"], "Scroll")

    def test_known_links_are_not_restamped_and_old_items_pruned(self):
        state = {"sources": {}, "items": [
            item("Old referendum story", d="2026-08-01", url="https://ex.org/old"),
            item("Referendum called", d="2026-10-24", url="https://ex.org/new",
                 seen=NOW - timedelta(days=1)),
        ]}
        wn.merge_matches(state, {"name": "BBC World"}, [self.entry("Referendum called", "https://ex.org/new")], NOW)
        self.assertEqual([i["url"] for i in state["items"]], ["https://ex.org/new"])
        self.assertEqual(state["items"][0]["seen"], (NOW - timedelta(days=1)).isoformat())


class WorklistTests(unittest.TestCase):
    def test_first_run_lists_by_date(self):
        state = {"sources": {}, "items": [item("Referendum called", d="2026-10-24"),
                                          item("Referendum long ago", d="2026-09-01")]}
        self.assertEqual([i["title"] for i in wn.pending(state, NOW)], ["Referendum called"])

    def test_after_a_review_lists_what_was_seen_since(self):
        state = {"reviewed": (NOW - timedelta(hours=1)).isoformat(), "sources": {}, "items": [
            item("Referendum called", seen=NOW - timedelta(hours=2)),
            item("Older story first seen today", d="2026-09-01"),
        ]}
        self.assertEqual([i["title"] for i in wn.pending(state, NOW)], ["Older story first seen today"])

    def test_weak_single_outlet_stories_are_counted_not_listed(self):
        state = {"sources": {"BBC World": {}}, "items": [
            item("Is democracy in retreat?", "The Conversation"),
            item("Why democracy matters now", "BBC World"),
            item("Mali junta postpones elections again", "Al Jazeera"),
        ]}
        md = wn.render(state, NOW)
        self.assertIn("Mali junta", md)
        self.assertNotIn("in retreat", md)
        self.assertIn("2 more matched only the word \"democracy\"", md)


class SourcesFileTests(unittest.TestCase):
    def test_sources_load_and_are_complete(self):
        sources = wn.load_sources()
        self.assertGreaterEqual(len(sources), 20)
        for s in sources:
            self.assertTrue(s["url"].startswith("https://"), s["name"])
            for key in ("name", "region", "lang", "kind"):
                self.assertTrue(s.get(key), f"{s.get('name')}: {key}")
            self.assertIn(s["kind"], {"wire", "regional", "specialist"})


if __name__ == "__main__":
    unittest.main()
