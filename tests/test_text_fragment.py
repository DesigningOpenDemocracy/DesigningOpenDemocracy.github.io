#!/usr/bin/env python3
"""Regression tests for util/text_fragment.py's pure functions.

Offline, stdlib-only (matches text_fragment.py's own dependency-free
design) — no network, no fixture files needed. Run with:

    python -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import text_fragment as tf  # noqa: E402


class NormalizeWsTests(unittest.TestCase):

    def test_collapses_runs_of_whitespace(self):
        self.assertEqual(tf.normalize_ws("a   b\tc\n\nd"), "a b c d")

    def test_strips_leading_and_trailing(self):
        self.assertEqual(tf.normalize_ws("  hello world  "), "hello world")

    def test_empty_string(self):
        self.assertEqual(tf.normalize_ws(""), "")


class CountOccurrencesTests(unittest.TestCase):

    def test_counts_whitespace_tolerant_matches(self):
        page = "The quick brown fox. The quick   brown\nfox again."
        self.assertEqual(tf.count_occurrences(page, "quick brown fox"), 2)

    def test_zero_when_absent(self):
        self.assertEqual(tf.count_occurrences("hello world", "goodbye"), 0)

    def test_empty_inputs_return_zero(self):
        self.assertEqual(tf.count_occurrences("", "quote"), 0)
        self.assertEqual(tf.count_occurrences("page", ""), 0)


class FindSpanTests(unittest.TestCase):

    def test_locates_span_in_raw_coordinates(self):
        page = "Intro paragraph.\n\nThe org was founded in 2015 by activists."
        span = tf.find_span(page, "founded in 2015")
        self.assertIsNotNone(span)
        start, end = span
        self.assertEqual(page[start:end], "founded in 2015")

    def test_whitespace_tolerant(self):
        page = "The org was   founded\nin 2015 by activists."
        span = tf.find_span(page, "founded in 2015")
        self.assertIsNotNone(span)

    def test_none_when_not_found(self):
        self.assertIsNone(tf.find_span("hello world", "goodbye"))

    def test_none_on_empty_inputs(self):
        self.assertIsNone(tf.find_span("", "quote"))
        self.assertIsNone(tf.find_span("page", ""))

    def test_offsets_are_page_text_coordinates_not_normalized(self):
        # Regression: a prior paragraph_hash() implementation searched a
        # whitespace-normalized COPY for the quote, then reused that offset
        # to index into the ORIGINAL text — drifting by one character per
        # "\n\n" paragraph break preceding the quote (each one collapses to
        # a single space under normalization). find_span() must return
        # offsets valid in page's own coordinate space, not the normalized
        # one, so callers never have to translate between the two.
        page = "Short.\n\nAlso short.\n\nThe org was founded in 2015."
        span = tf.find_span(page, "founded in 2015")
        self.assertIsNotNone(span)
        start, end = span
        self.assertEqual(page[start:end], "founded in 2015")
        # If offsets had instead come from the normalized copy, they would
        # land too early here, since "\n\n" -> " " shrinks the text by one
        # character at each of the two paragraph breaks above.
        normalized_len_diff = len(page) - len(tf.normalize_ws(page))
        self.assertGreater(normalized_len_diff, 0)


class SplitEllipsisTests(unittest.TestCase):

    def test_no_ellipsis_returns_none(self):
        self.assertIsNone(tf._split_ellipsis("a plain quote"))

    def test_splits_before_and_after(self):
        result = tf._split_ellipsis("The org was founded... to promote democracy")
        self.assertEqual(result, ("The org was founded", "to promote democracy"))

    def test_empty_side_returns_none(self):
        self.assertIsNone(tf._split_ellipsis("...trailing text only"))
        self.assertIsNone(tf._split_ellipsis("leading text only..."))

    def test_whitespace_around_ellipsis_is_stripped(self):
        result = tf._split_ellipsis("Start here  ...  end here")
        self.assertEqual(result, ("Start here", "end here"))


class QuoteMatchesTests(unittest.TestCase):

    def test_verbatim_match_without_ellipsis(self):
        page = "The Alliance was founded in 2015 by local activists."
        self.assertTrue(tf.quote_matches(page, "founded in 2015 by local activists"))

    def test_no_match_without_ellipsis(self):
        page = "The Alliance was founded in 2015."
        self.assertFalse(tf.quote_matches(page, "founded in 2019"))

    def test_ellipsis_quote_matches_when_both_sides_present_in_order(self):
        page = "The Alliance was founded in 2015 by local activists to promote transparency."
        self.assertTrue(tf.quote_matches(page, "founded in 2015... promote transparency"))

    def test_ellipsis_quote_fails_when_order_reversed(self):
        page = "Promote transparency was the goal. The Alliance was founded in 2015."
        self.assertFalse(tf.quote_matches(page, "founded in 2015... promote transparency"))

    def test_ellipsis_quote_fails_when_end_missing(self):
        page = "The Alliance was founded in 2015 by local activists."
        self.assertFalse(tf.quote_matches(page, "founded in 2015... something not on page"))

    def test_empty_inputs_return_false(self):
        self.assertFalse(tf.quote_matches("", "quote"))
        self.assertFalse(tf.quote_matches("page", ""))


class MakeTextFragmentTests(unittest.TestCase):

    def test_short_quote_encodes_whole_string(self):
        frag = tf.make_text_fragment("hello world")
        self.assertEqual(frag, "text=hello%20world")

    def test_long_quote_uses_textstart_textend(self):
        words = ["word{}".format(i) for i in range(80)]  # well over 300 chars
        quote = " ".join(words)
        frag = tf.make_text_fragment(quote)
        self.assertIn(",", frag)
        start_part, end_part = frag[len("text="):].split(",", 1)
        self.assertIn("word0", start_part)
        self.assertIn("word79", end_part)

    def test_ellipsis_quote_uses_textstart_textend_of_the_two_sides(self):
        frag = tf.make_text_fragment("founded in 2015... to promote transparency")
        self.assertEqual(
            frag,
            "text=founded%20in%202015,to%20promote%20transparency",
        )


class FragmentUrlTests(unittest.TestCase):

    def test_add_fragment_to_url_appends_directive(self):
        url = tf.add_fragment_to_url("https://example.org/about", "hello world")
        self.assertEqual(url, "https://example.org/about#:~:text=hello%20world")

    def test_add_fragment_to_url_none_without_quote(self):
        self.assertIsNone(tf.add_fragment_to_url("https://example.org/about", ""))
        self.assertIsNone(tf.add_fragment_to_url("", "hello world"))

    def test_add_fragment_to_url_never_overwrites_existing_fragment(self):
        # An existing fragment (even a plain page anchor) is left alone —
        # the caller (with_fragment) falls back to the unmodified url so
        # the anchor is preserved rather than clobbered.
        url = tf.add_fragment_to_url("https://example.org/about#section-2", "hello world")
        self.assertIsNone(url)

    def test_with_fragment_returns_url_unchanged_when_not_derivable(self):
        self.assertEqual(tf.with_fragment("https://example.org/about", ""), "https://example.org/about")

    def test_with_fragment_returns_fragment_bearing_url(self):
        result = tf.with_fragment("https://example.org/about", "hello world")
        self.assertEqual(result, "https://example.org/about#:~:text=hello%20world")

    def test_extract_and_strip_fragment_round_trip(self):
        url = "https://example.org/about#:~:text=hello%20world"
        self.assertEqual(tf.extract_fragment(url), "hello world")
        self.assertEqual(tf.strip_fragment(url), "https://example.org/about")

    def test_extract_fragment_none_for_plain_anchor(self):
        self.assertIsNone(tf.extract_fragment("https://example.org/about#section-2"))

    def test_strip_fragment_preserves_non_text_anchor(self):
        url = "https://example.org/about#section-2"
        self.assertEqual(tf.strip_fragment(url), url)


class SpacingAutofixTests(unittest.TestCase):

    def test_none_when_already_exact_match(self):
        page = "Democracy — with participation, works."
        quote = "Democracy — with participation, works."
        self.assertIsNone(tf.spacing_autofix(page, quote))

    def test_fixes_missing_space_around_em_dash(self):
        page = "Democracy — with participation, works."
        quote = "Democracy —with participation, works."
        corrected = tf.spacing_autofix(page, quote)
        self.assertEqual(corrected, "Democracy — with participation, works.")

    def test_none_for_real_content_difference(self):
        page = "The event happened in 2020."
        quote = "The event happened in 2021."
        self.assertIsNone(tf.spacing_autofix(page, quote))

    def test_none_when_corrected_text_is_ambiguous(self):
        # The corrected substring occurs twice on the page — spacing_autofix
        # must refuse rather than silently pick one, per its docstring
        # ("an ambiguous highlight is worth leaving for a human").
        page = "Democracy —with all. Later: Democracy —with all again."
        quote = "Democracy —with all"
        self.assertIsNone(tf.spacing_autofix(page, quote))

    def test_none_when_page_continues_past_quote(self):
        # Deliberately not auto-fixed: where a quote ends is an editorial
        # choice, and "page has extra text" is a real drift signal that
        # should stay a MISMATCH, not be silently absorbed.
        page = "The pilot ran successfully, followed by a full rollout."
        quote = "The pilot ran successfully."
        self.assertIsNone(tf.spacing_autofix(page, quote))

    def test_none_on_empty_inputs(self):
        self.assertIsNone(tf.spacing_autofix("", "quote"))
        self.assertIsNone(tf.spacing_autofix("page", ""))


class ClosestMatchHintTests(unittest.TestCase):

    def test_none_on_empty_inputs(self):
        self.assertIsNone(tf.closest_match_hint("", "quote"))
        self.assertIsNone(tf.closest_match_hint("page", ""))

    def test_none_when_nothing_resembles_the_quote(self):
        page = "Zebra pattern colors and unrelated topics entirely."
        quote = "The democratic accountability framework requires transparency."
        self.assertIsNone(tf.closest_match_hint(page, quote, min_ratio=0.6))

    def test_finds_near_miss_passage(self):
        page = "The Alliance was founded in 2015 to promote transparency."
        quote = "The Alliance was founded in 2016 to promote transparency."
        hint = tf.closest_match_hint(page, quote)
        self.assertIsNotNone(hint)
        passage, ratio, diff = hint
        self.assertGreater(ratio, 0.6)
        self.assertIn("2015", passage)


class FootnoteParsingTests(unittest.TestCase):

    def test_parse_footnote_def_matches_definition_line(self):
        result = tf.parse_footnote_def('[^tvfy-about]: "some quote," [About](https://x.org/about).')
        self.assertEqual(result[0], "tvfy-about")
        self.assertIn("some quote", result[1])

    def test_parse_footnote_def_none_for_non_definition_line(self):
        self.assertIsNone(tf.parse_footnote_def("This is regular prose, not a footnote def."))

    def test_footnote_citation_extracts_url_title_and_quote(self):
        body = '"today the Foundation launched a new site," [About](https://example.org/about), Example Org.'
        result = tf.footnote_citation(body)
        self.assertIsNotNone(result)
        url, title, quote = result
        self.assertEqual(url, "https://example.org/about")
        self.assertEqual(title, "About")
        self.assertEqual(quote, "today the Foundation launched a new site,")

    def test_footnote_citation_none_when_quote_is_only_the_link_text(self):
        # A page title wrapped in quotes AS the link's own text (no
        # separate excerpt) doesn't count as a verbatim quote — the whole
        # [text](url) span is stripped before searching for a quoted
        # phrase, so nothing is left to match.
        body = '["About"](https://example.org/about)'
        self.assertIsNone(tf.footnote_citation(body))

    def test_footnote_citation_none_with_multiple_links(self):
        body = ('"a claim," [Source A](https://a.example.org), also see '
                '[Source B](https://b.example.org).')
        self.assertIsNone(tf.footnote_citation(body))

    def test_footnote_citation_none_without_quoted_phrase(self):
        body = "No quotes here, just [a link](https://example.org)."
        self.assertIsNone(tf.footnote_citation(body))

    def test_footnote_citation_none_for_non_http_link(self):
        body = '"a quote," [ref](mailto:info@example.org).'
        self.assertIsNone(tf.footnote_citation(body))

    def test_iter_footnote_citations_yields_only_qualifying_definitions(self):
        source = "\n".join([
            "Some prose.",
            '[^good]: "founded in 2015," [About](https://example.org/about).',
            "[^no-quote]: [About](https://example.org/about) with no quote.",
            "Not a footnote at all.",
        ])
        results = list(tf.iter_footnote_citations(source))
        self.assertEqual(len(results), 1)
        label, url, title, quote = results[0]
        self.assertEqual(label, "good")
        self.assertEqual(quote, "founded in 2015,")


if __name__ == "__main__":
    unittest.main()
