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


class NormalizeWsParenSpacingTests(unittest.TestCase):
    """html_to_text() can insert a space just inside a parenthesis where the
    rendered page has none — inline-tag boundaries like `(<i>N</i> = 5734)`
    extract as '( N = 5734)'. Human-pasted quotes always carry the rendered
    form, so matching drops whitespace immediately inside parens."""

    def test_drops_space_after_open_paren(self):
        self.assertEqual(tf.normalize_ws("Participants ( N = 5734) preferred"),
                         "Participants (N = 5734) preferred")

    def test_drops_space_before_close_paren(self):
        self.assertEqual(tf.normalize_ws("(see this thing ) here"),
                         "(see this thing) here")

    def test_keeps_legitimate_space_before_open_paren(self):
        self.assertEqual(tf.normalize_ws("word (with space) unchanged"),
                         "word (with space) unchanged")

    def test_multiline_artifact_form(self):
        self.assertEqual(tf.normalize_ws("(\n  N = 5734\n)"), "(N = 5734)")

    def test_quote_matches_across_paren_spacing_difference(self):
        page = tf.html_to_text("<p>Participants (<i>N</i> = 5734) preferred "
                               "AI-generated statements.</p>")
        quote = "Participants (N = 5734) preferred AI-generated statements."
        self.assertTrue(tf.quote_matches(page, quote))


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

    def test_footnote_citation_handles_paren_in_url(self):
        # A Wikipedia disambiguation-style URL (e.g. .../Politics_(Aristotle))
        # contains a literal ")" before the markdown link's own closing paren.
        # MD_LINK_RE's URL group used to stop at the first ")" it saw,
        # silently truncating the url to end right before "Aristotle)" —
        # confirmed via check_fragments.py fetching the wrong (truncated,
        # non-existent) URL for such a footnote and reporting a false
        # HTTP error/mismatch on an otherwise-correct citation.
        body = ('"a quote," [Politics (Aristotle)]'
                '(https://en.wikipedia.org/wiki/Politics_(Aristotle)).')
        result = tf.footnote_citation(body)
        self.assertIsNotNone(result)
        url, title, quote = result
        self.assertEqual(url, "https://en.wikipedia.org/wiki/Politics_(Aristotle)")
        self.assertEqual(title, "Politics (Aristotle)")

    def test_parse_unquoted_reason_matches_trailing_comment(self):
        body = ("[Council Watch](https://www.councilwatch.com.au), Council Watch. "
                "<!-- unquoted: bot-blocked: site returns 403 to automated fetches -->")
        result = tf.parse_unquoted_reason(body)
        self.assertEqual(result, ("bot-blocked", "site returns 403 to automated fetches"))

    def test_parse_unquoted_reason_none_when_absent(self):
        body = "[About](https://example.org/about), Example Org."
        self.assertIsNone(tf.parse_unquoted_reason(body))

    def test_parse_unquoted_reason_does_not_confuse_footnote_citation(self):
        # A trailing unquoted: comment must not itself be picked up as a
        # verbatim quote by footnote_citation() — it carries no quote
        # characters, so the two parsers stay independent on the same line.
        body = ("[About](https://example.org/about), Example Org. "
                "<!-- unquoted: legacy: predates this convention -->")
        self.assertIsNone(tf.footnote_citation(body))
        self.assertIsNotNone(tf.parse_unquoted_reason(body))

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


class CitationOnlyLinksTests(unittest.TestCase):
    """citation_only_links()/iter_citation_only_footnotes() — the bare-item
    counterpart of footnote_citation()/iter_footnote_citations() for a
    footnote with no verbatim quote. See hooks/citation_export.py's
    module docstring for why this exists: such a footnote used to have
    zero representation in citations.json."""

    def test_extracts_url_and_title_when_no_quote(self):
        body = "[About](https://example.org/about), Example Org, accessed 2026."
        result = tf.citation_only_links(body)
        self.assertEqual(result, [("https://example.org/about", "About")])

    def test_empty_when_footnote_citation_already_matches(self):
        # Has a quote — footnote_citation() owns this case, not this one.
        body = '"founded in 2015," [About](https://example.org/about).'
        self.assertEqual(tf.citation_only_links(body), [])

    def test_multiple_links_yields_one_pair_per_link(self):
        # No quote exists to mispair, so unlike footnote_citation()'s
        # "exactly one link" rule (which is about quote-pairing), a
        # multi-source citation-only footnote isn't ambiguous — it's
        # just two ordinary citations, each gets represented.
        body = "[First](https://a.example.org) and [Second](https://b.example.org)."
        result = tf.citation_only_links(body)
        self.assertEqual(result, [
            ("https://a.example.org", "First"),
            ("https://b.example.org", "Second"),
        ])

    def test_empty_with_zero_links(self):
        body = "A citation with no link at all, just prose."
        self.assertEqual(tf.citation_only_links(body), [])

    def test_non_http_link_excluded(self):
        body = "[ref](mailto:info@example.org)."
        self.assertEqual(tf.citation_only_links(body), [])

    def test_non_http_link_excluded_alongside_a_valid_one(self):
        body = "[Web](https://example.org/about) and [Email](mailto:info@example.org)."
        self.assertEqual(tf.citation_only_links(body), [("https://example.org/about", "Web")])

    def test_iter_citation_only_footnotes_yields_unquoted_footnotes_only(self):
        source = "\n".join([
            "Some prose.",
            '[^quoted]: "founded in 2015," [About](https://example.org/about).',
            "[^plain]: [Council Watch](https://www.councilwatch.com.au), "
            "Council Watch. <!-- unquoted: legacy: n/a -->",
            "[^multi]: [First](https://a.example.org) and "
            "[Second](https://b.example.org). <!-- unquoted: multi-source: two links -->",
        ])
        results = list(tf.iter_citation_only_footnotes(source))
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0], ("plain", "https://www.councilwatch.com.au", "Council Watch"))
        self.assertEqual(results[1], ("multi", "https://a.example.org", "First"))
        self.assertEqual(results[2], ("multi", "https://b.example.org", "Second"))


class HtmlToTextTests(unittest.TestCase):
    """html_to_text() is shared between check_fragments.py's live-fetch
    path and import_manual_dump.py's browser-snapshot path — a quote must
    verify identically against either, so these tests pin down its exact
    output shape rather than just "some text comes out"."""

    def test_strips_tags_and_collapses_whitespace(self):
        html_src = "<html><body><p>Hello   <b>world</b>.</p></body></html>"
        self.assertEqual(tf.html_to_text(html_src), "Hello world.")

    def test_block_tags_become_paragraph_breaks(self):
        html_src = "<div>First paragraph.</div><div>Second paragraph.</div>"
        text = tf.html_to_text(html_src)
        # Adjacent open/close block-tag boundaries can each contribute their
        # own \n\n (harmless — paragraph_text()/paragraph_hash() only need
        # rfind/find on "\n\n", not exactly one), so assert the paragraph
        # break and content rather than pinning the exact run of newlines.
        self.assertIn("\n\n", text)
        before, after = text.split("\n\n", 1)
        self.assertEqual(before.strip(), "First paragraph.")
        self.assertTrue(after.strip().endswith("Second paragraph."))

    def test_drops_script_and_style_bodies(self):
        html_src = ("<p>Visible text.</p>"
                   "<script>var x = 'founded in 2015';</script>"
                   "<style>.a { color: red; }</style>")
        text = tf.html_to_text(html_src)
        self.assertIn("Visible text.", text)
        self.assertNotIn("founded in 2015", text)

    def test_unescapes_entities(self):
        html_src = "<p>2015&#8211;2016 &amp; beyond</p>"
        self.assertEqual(tf.html_to_text(html_src), "2015–2016 & beyond")

    def test_no_stray_space_before_punctuation_at_tag_boundary(self):
        html_src = "<p>Written by <a href=\"/x\">Jane Wright</a>, an activist.</p>"
        self.assertEqual(tf.html_to_text(html_src),
                         "Written by Jane Wright, an activist.")

    def test_same_output_as_a_live_fetch_would_produce(self):
        # Regression guard for the refactor that moved this out of
        # check_fragments.py's _fetch_page_text() into this shared
        # function — a live fetch and a manually-saved snapshot of
        # identical markup must extract to identical text, or a quote
        # could verify against one path and mismatch against the other
        # for no reason but a diverging extractor.
        html_src = "<article><h1>Title</h1><p>Founded in 2015 by activists.</p></article>"
        text = tf.html_to_text(html_src)
        self.assertIn("Title", text)
        self.assertIn("Founded in 2015 by activists.", text)
        self.assertIn("\n\n", text)


class LoadArchiveInfoTests(unittest.TestCase):
    """load_archive_info()/load_archive_urls() read the committed evidence
    cache's archive_url/url_status fields — used at render time by
    hooks/org_events.py, hooks/footnote_fragments.py, and
    hooks/citation_export.py to add archive links and, once url_status is
    dead/unfit, swap which link renders as primary."""

    def setUp(self):
        self._orig_path = tf.STATE_PATH
        self.addCleanup(self._restore_path)

    def _restore_path(self):
        tf.STATE_PATH = self._orig_path

    def _write_cache(self, tmp_path, data):
        import json
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        tf.STATE_PATH = tmp_path

    def test_missing_cache_file_returns_empty(self):
        tf.STATE_PATH = "/nonexistent/path/does-not-exist.json"
        self.assertEqual(tf.load_archive_info(), {})
        self.assertEqual(tf.load_archive_urls(), {})

    def test_entry_with_only_archive_url(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        self.addCleanup(lambda: os.remove(path))
        self._write_cache(path, {
            "https://example.org/a": {"archive_url": "https://web.archive.org/web/20260101000000/https://example.org/a"},
        })
        info = tf.load_archive_info()
        self.assertEqual(
            info["https://example.org/a"]["archive_url"],
            "https://web.archive.org/web/20260101000000/https://example.org/a",
        )
        self.assertIsNone(info["https://example.org/a"]["url_status"])
        self.assertEqual(
            tf.load_archive_urls()["https://example.org/a"],
            "https://web.archive.org/web/20260101000000/https://example.org/a",
        )

    def test_entry_with_url_status_but_no_archive(self):
        # A citation can be flagged dead before any snapshot is recorded —
        # load_archive_info() must still surface it (rendering logic
        # decides what to do when archive_url is absent).
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        self.addCleanup(lambda: os.remove(path))
        self._write_cache(path, {
            "https://example.org/b": {"url_status": "dead"},
        })
        info = tf.load_archive_info()
        self.assertEqual(info["https://example.org/b"]["url_status"], "dead")
        self.assertIsNone(info["https://example.org/b"]["archive_url"])
        # load_archive_urls() only surfaces entries with an actual archive_url
        self.assertNotIn("https://example.org/b", tf.load_archive_urls())

    def test_entry_with_neither_field_is_excluded(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        self.addCleanup(lambda: os.remove(path))
        self._write_cache(path, {
            "https://example.org/c": {"checked": "2026-08-22", "document_sha256": "abc"},
        })
        info = tf.load_archive_info()
        self.assertNotIn("https://example.org/c", info)

    def test_non_dict_entries_are_skipped(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        self.addCleanup(lambda: os.remove(path))
        self._write_cache(path, {"https://example.org/d": "not-a-dict"})
        self.assertEqual(tf.load_archive_info(), {})

    def test_corrupt_json_returns_empty(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("{not valid json")
            path = f.name
        self.addCleanup(lambda: os.remove(path))
        tf.STATE_PATH = path
        self.assertEqual(tf.load_archive_info(), {})


class CoinsContextTests(unittest.TestCase):
    """coins_context()/coins_span_html() — the COinS <span class="Z3988">
    Zotero/EndNote/RefWorks scan any webpage for. See Appendix E of
    internal-heartbeat/machine-verifiable-citation.md."""

    def test_no_url_returns_none(self):
        self.assertIsNone(tf.coins_context(None))
        self.assertIsNone(tf.coins_context(""))

    def test_minimal_context_has_required_keys_only(self):
        ctx = tf.coins_context("https://example.org/x")
        self.assertIn("ctx_ver=Z39.88-2004", ctx)
        self.assertIn("rft_val_fmt=info%3Aofi%2Ffmt%3Akev%3Amtx%3Ajournal", ctx)
        self.assertIn("rft.genre=unknown", ctx)
        self.assertIn("rft_id=https%3A%2F%2Fexample.org%2Fx", ctx)
        self.assertNotIn("rft.atitle", ctx)
        self.assertNotIn("rft.date", ctx)
        self.assertNotIn("evidence_sha256", ctx)

    def test_title_and_date_are_kev_encoded_matching_mediawiki_style(self):
        # Cross-checked against a real Z3988 span fetched from a live
        # Wikipedia citations page — same key set, same percent-encoding
        # (spaces as '+', unicode as %XX), same rft_val_fmt/genre.
        ctx = tf.coins_context(
            "http://www.abs.gov.au/x?y",
            title="Local Government Areas – Alphabetic",
            cite_date="2008-09-26",
        )
        self.assertIn(
            "rft.atitle=Local+Government+Areas+%E2%80%93+Alphabetic", ctx)
        self.assertIn("rft.date=2008-09-26", ctx)
        self.assertIn("rft_id=http%3A%2F%2Fwww.abs.gov.au%2Fx%3Fy", ctx)

    def test_evidence_id_is_truncated_to_prefix(self):
        full_hash = "a" * 64
        ctx = tf.coins_context("https://example.org/x", evidence_id=full_hash)
        self.assertIn("evidence_sha256=" + "a" * tf.EVIDENCE_SHA256_PREFIX_LEN, ctx)
        self.assertNotIn(full_hash, ctx)

    def test_span_html_escapes_ampersand_for_the_attribute(self):
        html_out = tf.coins_span_html("https://example.org/x")
        self.assertIn('class="Z3988"', html_out)
        self.assertIn("&amp;", html_out)
        # The attribute value itself must not contain a bare, unescaped &
        # between the title="..." quotes (that would be invalid HTML).
        start = html_out.index('title="') + len('title="')
        end = html_out.index('"', start)
        attr = html_out[start:end]
        self.assertNotIn("& ", attr)  # sanity: no raw '&' survived escaping
        self.assertIn("&amp;rft_val_fmt", attr)

    def test_span_html_empty_string_when_no_url(self):
        self.assertEqual(tf.coins_span_html(None), "")
        self.assertEqual(tf.coins_span_html(""), "")


if __name__ == "__main__":
    unittest.main()
