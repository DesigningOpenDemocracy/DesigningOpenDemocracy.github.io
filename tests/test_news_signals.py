#!/usr/bin/env python3
"""Regression tests for the news checkup's triage hints: util/news_signals.py,
how check_rss.py stores them, and the checkup's "Start here" list.

What's pinned, and why each is worth pinning rather than eyeballing:

  - Real titles from the first checkup (2026-09-28) land where a reviewer
    would put them: a flagship report and a leadership change are worth a
    look; a job ad, a polling roundup and a petition are routine. These are
    the cases the signals exist for.
  - Words that only look like signals don't fire: a court appeal isn't a
    fundraising appeal, and Spanish "vale" isn't an Australian obituary.
  - Mentions are case-sensitive whole names, skip one-word org names
    (ordinary words like "Involve"), and never count a feed's own orgs.
  - Only labels are stored, never post text, and the checkup ranks by them
    without hiding anything.

Offline. Run with:

    python -m unittest discover tests
"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import check_rss as cr  # noqa: E402
import news_checkup as nc  # noqa: E402
import news_signals as ns  # noqa: E402

TODAY = date(2026, 9, 28)


class SignalTests(unittest.TestCase):
    def worth(self, title, lede=""):
        return ns.signals(title, lede)[0]

    def routine(self, title, lede=""):
        return ns.signals(title, lede)[1]

    def test_real_titles_worth_a_look(self):
        self.assertIn("publication", self.worth(
            "Democracy Beyond Elections: A Handbook on Citizens' Assemblies"))
        self.assertIn("deliberative process", self.worth(
            "Democracy Beyond Elections: A Handbook on Citizens' Assemblies"))
        self.assertIn("leadership change", self.worth(
            "Kyle Redman appointed Executive Director as Iain Walker steps back"))
        self.assertIn("death", self.worth("Remembering Katherine Cunningham"))
        self.assertIn("death", self.worth("Vale Katherine Cunningham"))

    def test_curly_apostrophes_match_like_straight_ones(self):
        # The handbook's real title, as the newDemocracy feed writes it.
        self.assertIn("deliberative process", self.worth(
            "Democracy Beyond Elections: A Handbook on Citizens’ Assemblies"))
        self.assertIn("job ad", self.routine("We’re hiring"))
        self.assertEqual(ns.mentions("with People’s Voice", [("pv", ["People's Voice"], "")]),
                         ["People's Voice"])

    def test_real_titles_routine(self):
        self.assertIn("job ad", self.routine(
            "We're looking for a Director of International Democratic Lottery Services"))
        self.assertIn("newsletter or roundup", self.routine(
            "August 2026 in the polls: The latest UK monthly political polling averages"))
        self.assertIn("petition", self.routine("עצומה – גרוניס הציבור מחכה לתשובות!"))

    def test_lookalikes_do_not_fire(self):
        self.assertNotIn("fundraising", self.routine("Court appeal lodged over electoral boundaries"))
        self.assertIn("fundraising", self.routine("Our winter appeal"))
        self.assertNotIn("death", self.worth("¿Vale la pena votar?"))
        self.assertEqual(self.worth("Reporters gather"), [])  # whole words only

    def test_lede_counts_but_only_its_opening(self):
        self.assertIn("publication", self.worth("Out today", "Our new report finds that"))
        far = "x " * ns.LEDE_CHARS + "report"
        self.assertNotIn("publication", self.worth("Out today", ns.lede(far)))

    def test_no_signal_is_empty_not_missing(self):
        self.assertEqual(ns.signals("40% de Bolivia para los mineros"), ([], []))


class MentionTests(unittest.TestCase):
    NAMES = [("idea", ["International IDEA"], ""), ("club", ["Democracy Club"], "https://club/feed"),
             ("involve", [], ""), ("self", ["Self Org"], "https://self/feed")]

    def test_case_sensitive_whole_names(self):
        self.assertEqual(ns.mentions("with International IDEA and a democracy club", self.NAMES),
                         ["International IDEA"])

    def test_feed_own_orgs_excluded(self):
        self.assertEqual(ns.mentions("Self Org and Democracy Club", self.NAMES, {"self"}),
                         ["Democracy Club"])

    def test_one_word_names_are_not_matched(self):
        self.assertEqual(ns._names_for("Involve"), [])
        self.assertEqual(ns._names_for("Kongra Star (Women's Congress)"), ["Kongra Star"])
        self.assertEqual(ns._names_for("The Australia Institute — Democracy & Accountability Program"),
                         ["The Australia Institute"])


RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
<item><title>Out today</title><link>https://ex.org/p</link>
<pubDate>Mon, 21 Sep 2026 09:00:00 +0000</pubDate>
<description>&lt;p&gt;Our new &lt;b&gt;report&lt;/b&gt; is here.&lt;/p&gt;</description>
<content:encoded>&lt;p&gt;Written with International IDEA. The full text goes on.&lt;/p&gt;</content:encoded>
</item></channel></rss>"""


class StoredLabelsTests(unittest.TestCase):
    def test_annotate_then_save_keeps_labels_not_text(self):
        entries = cr.parse_feed_entries(RSS)
        self.assertIn("report", entries[0]["summary_html"])
        ns.annotate(entries, MentionTests.NAMES)
        (item,) = cr.merge_feed_items([], entries, TODAY)
        self.assertEqual(item, {"date": "2026-09-21", "title": "Out today", "url": "https://ex.org/p",
                                "signals": ["publication"], "mentions": ["International IDEA"]})


def post(title, url, **labels):
    return {"date": "2026-09-20", "title": title, "url": url, **labels}


class StartHereTests(unittest.TestCase):
    def report(self):
        org = {"slug": "a", "title": "A", "rss_feed": "https://a/feed", "news_page": "",
               "rss_read": date(2026, 9, 25), "scrape": {}}
        items = [post("We're hiring a report writer", "https://a/1"),
                 post("Annual summit report released", "https://a/2", mentions=["International IDEA"]),
                 post("A quiet update", "https://a/3"),
                 post("New handbook launched", "https://a/4")]
        return nc.checkup([org], set(), {}, TODAY,
                          load_items=lambda slug: {"latest": "2026-09-20", "items": items})

    def test_ranked_by_signal_count_and_routine_left_out(self):
        picks = nc.start_here(self.report())
        self.assertEqual([p[1]["url"] for p in picks], ["https://a/2", "https://a/4"])

    def test_every_post_still_listed_with_its_tags(self):
        md = nc.render_markdown(self.report())
        self.assertIn("## Start here", md)
        self.assertIn("A quiet update](https://a/3)\n", md)
        self.assertIn("likely routine: job ad", md)
        self.assertIn("mentions International IDEA", md)

    def test_a_feeds_usual_output_does_not_lead(self):
        # A survey org: nearly every post is a "report". The one that also
        # says something else still leads; the rest stay listed, tagged.
        org = {"slug": "survey", "title": "Survey Org", "rss_feed": "https://s/feed",
               "news_page": "", "rss_read": date(2026, 9, 25), "scrape": {}}
        items = [post(f"New report on topic {n}", f"https://s/{n}") for n in range(5)]
        items.append(post("New report launched at our annual conference", "https://s/big"))
        report = nc.checkup([org], set(), {}, TODAY,
                            load_items=lambda slug: {"latest": "2026-09-20", "items": items})
        self.assertEqual(report["feeds"][0]["usual"], {"publication"})
        picks = nc.start_here(report)
        self.assertEqual([p[1]["url"] for p in picks], ["https://s/big"])
        self.assertEqual(picks[0][2], ["flagship event", "launch"])
        md = nc.render_markdown(report)
        self.assertIn("New report on topic 0](https://s/0) · publication", md)
        self.assertIn("its usual output", md)

    def test_small_feeds_have_no_usual_output(self):
        self.assertEqual(nc.usual_labels([post("New report", "https://x/1")] * 4), set())

    def test_title_signals_cover_posts_saved_before_signals_existed(self):
        worth, routine, named = nc.triage({"title": "New handbook launched"})
        self.assertEqual((worth, routine, named), (["launch", "publication"], [], []))


if __name__ == "__main__":
    unittest.main()
