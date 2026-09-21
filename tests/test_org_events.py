#!/usr/bin/env python3
"""Regression tests for hooks/org_events.py.

_coins_for_event(): the COinS <span class="Z3988"> emitted for an org event
with a url:, and its evidence_sha256 pointer when the event also carries a
quote:. See Appendix E of internal-heartbeat/machine-verifiable-citation.md.

select_highlight(): which single event reaches the Democracy Landscape
index's quick-profile card. Pinned rather than eyeballed because the card
shows exactly one event out of up to a few dozen, so a wrong pick is
invisible — the card still renders, just with the wrong thing on it — and
because the ordering rule (upcoming first, then notable: tier, then
recency) is a judgment call this file is the record of.

Offline, stdlib-only. Run with:

    python -m unittest discover tests
"""

import datetime
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import org_events as oe  # noqa: E402
import text_fragment as tf  # noqa: E402


class CoinsForEventTests(unittest.TestCase):

    def test_event_without_url_gets_no_span(self):
        self.assertEqual(oe._coins_for_event({"title": "Founded"}), "")

    def test_event_with_url_but_no_quote_gets_span_without_evidence_pointer(self):
        result = oe._coins_for_event({
            "title": "Founded", "url": "https://example.org/x", "date": "2020-01-01",
        })
        self.assertIn('class="Z3988"', result)
        self.assertIn("rft.atitle=Founded", result)
        self.assertIn("rft.date=2020-01-01", result)
        self.assertNotIn("evidence_sha256", result)

    def test_event_with_quote_gets_evidence_pointer(self):
        quote = "The organisation was founded in 2020."
        result = oe._coins_for_event({
            "title": "Founded", "url": "https://example.org/x",
            "date": "2020-01-01", "quote": quote,
        })
        expected_id = hashlib.sha256(tf.normalize_ws(quote).encode("utf-8")).hexdigest()
        self.assertIn(
            "evidence_sha256=" + expected_id[:tf.EVIDENCE_SHA256_PREFIX_LEN], result)


TODAY = datetime.date(2026, 9, 21)


class SelectHighlightTests(unittest.TestCase):
    """Which event the quick-profile card shows. See the docstring on
    hooks/org_events.py's select_highlight() for the reasoning behind each
    rule pinned here."""

    def pick(self, events):
        return oe.select_highlight(events, today=TODAY)

    def test_no_events_gives_no_highlight(self):
        self.assertIsNone(self.pick(None))
        self.assertIsNone(self.pick([]))

    def test_undated_and_unparseable_events_are_skipped(self):
        # An entry with no usable date cannot be placed on either side of
        # today, so it must not be able to win by being first in the list.
        self.assertIsNone(self.pick([
            {"title": "No date at all"},
            {"date": "someday", "title": "Not a date"},
        ]))

    def test_upcoming_beats_a_major_past_event(self):
        got = self.pick([
            {"date": "2011-03-04", "title": "Founded", "notable": True},
            {"date": "2026-11-02", "title": "Members' meetup"},
        ])
        self.assertEqual(got["kind"], "upcoming")
        self.assertEqual(got["title"], "Members' meetup")

    def test_soonest_upcoming_wins_regardless_of_tier(self):
        # Deliberate: an org's nearest event is the one a reader could still
        # turn up to, even when a bigger one sits further out.
        got = self.pick([
            {"date": "2026-12-01", "title": "Annual conference", "notable": True},
            {"date": "2026-09-30", "title": "Working group"},
        ])
        self.assertEqual(got["title"], "Working group")

    def test_an_event_dated_today_still_counts_as_upcoming(self):
        got = self.pick([{"date": TODAY.isoformat(), "title": "Happening now"}])
        self.assertEqual(got["kind"], "upcoming")

    def test_past_major_beats_a_more_recent_untiered_event(self):
        got = self.pick([
            {"date": "2011-03-04", "title": "Founded", "notable": True},
            {"date": "2026-08-01", "title": "Routine catch-up"},
        ])
        self.assertEqual(got["kind"], "past")
        self.assertEqual(got["title"], "Founded")

    def test_past_medium_beats_untiered_but_loses_to_major(self):
        events = [
            {"date": "2026-08-01", "title": "Routine catch-up"},
            {"date": "2024-05-05", "title": "Public forum", "notable": "medium"},
        ]
        self.assertEqual(self.pick(events)["title"], "Public forum")
        events.append({"date": "2020-01-01", "title": "Launch", "notable": True})
        self.assertEqual(self.pick(events)["title"], "Launch")

    def test_notable_false_ranks_with_untiered(self):
        got = self.pick([
            {"date": "2020-01-01", "title": "Older", "notable": False},
            {"date": "2024-01-01", "title": "Newer"},
        ])
        self.assertEqual(got["title"], "Newer")

    def test_recency_breaks_ties_within_a_tier(self):
        got = self.pick([
            {"date": "2011-03-04", "title": "Founded", "notable": True},
            {"date": "2023-07-07", "title": "Platform launch", "notable": True},
        ])
        self.assertEqual(got["title"], "Platform launch")

    def test_short_title_is_preferred_for_the_one_line_card(self):
        got = self.pick([{
            "date": "2026-10-01",
            "title": 'Co-hosting "A very long narrative log line" with a partner org',
            "short_title": "A Very Long Narrative Log Line",
        }])
        self.assertEqual(got["title"], "A Very Long Narrative Log Line")

    def test_note_is_preferred_over_quote_and_marked_as_paraphrase(self):
        got = self.pick([{
            "date": "2024-01-01", "title": "X",
            "note": "Site states the org was founded in 2014.",
            "quote": "We were founded in 2014.",
        }])
        self.assertEqual(got["blurb"], "Site states the org was founded in 2014.")
        self.assertFalse(got["blurb_is_quote"])

    def test_quote_stands_in_when_there_is_no_note_and_is_flagged_as_one(self):
        # The template renders a quote as a blockquote on the strength of
        # this flag, so that someone else's sentence is never shown as DOD's
        # own summary of the event.
        got = self.pick([{
            "date": "2024-01-01", "title": "X",
            "quote": "The organisation was founded in 2014.",
        }])
        self.assertEqual(got["blurb"], "The organisation was founded in 2014.")
        self.assertTrue(got["blurb_is_quote"])

    def test_event_with_neither_note_nor_quote_has_no_blurb(self):
        got = self.pick([{"date": "2024-01-01", "title": "X"}])
        self.assertIsNone(got["blurb"])
        self.assertFalse(got["blurb_is_quote"])

    def test_long_blurb_is_cut_on_a_word_boundary(self):
        note = "word " * 200
        got = self.pick([{"date": "2024-01-01", "title": "X", "note": note}])
        self.assertTrue(got["blurb"].endswith("…"))
        self.assertLessEqual(len(got["blurb"]), oe.HIGHLIGHT_BLURB_CHARS + 1)
        self.assertNotIn("  ", got["blurb"])
        # cut on whitespace, so no half-word before the ellipsis
        self.assertTrue(got["blurb"][:-1].rstrip().endswith("word"))

    def test_short_blurb_is_left_alone(self):
        got = self.pick([{"date": "2024-01-01", "title": "X", "note": "Short note."}])
        self.assertEqual(got["blurb"], "Short note.")

    def test_dates_are_rendered_without_a_platform_specific_strftime(self):
        got = self.pick([{"date": "2026-10-07", "title": "X"}])
        self.assertEqual(got["date_display"], "7 Oct 2026")
        self.assertEqual(got["date"], "2026-10-07")

    def test_a_real_date_range_is_carried_but_a_same_day_end_date_is_not(self):
        got = self.pick([{"date": "2026-10-07", "end_date": "2026-10-10", "title": "X"}])
        self.assertEqual(got["end_date_display"], "10 Oct 2026")
        # A one-day event whose end_date repeats its start must not render
        # as "7 Oct 2026 – 7 Oct 2026".
        got = self.pick([{"date": "2026-10-07", "end_date": "2026-10-07", "title": "X"}])
        self.assertIsNone(got["end_date_display"])

    def test_yaml_date_objects_are_accepted_alongside_strings(self):
        # Most event dates in this corpus parse as strings, but an unquoted
        # one comes back from YAML as a datetime.date.
        got = self.pick([{"date": datetime.date(2026, 10, 7), "title": "X"}])
        self.assertEqual(got["date_display"], "7 Oct 2026")


if __name__ == "__main__":
    unittest.main()
