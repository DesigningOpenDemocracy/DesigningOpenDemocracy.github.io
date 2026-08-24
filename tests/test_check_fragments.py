#!/usr/bin/env python3
"""Regression tests for the I/O-adjacent parts of util/check_fragments.py:
paragraph_hash, wikipedia_title, write_quote_fix/_write_quote_fix_yaml, and
collect_evidence's --slug filtering.

Offline — no network calls. Requires the same deps check_fragments.py itself
needs at import time (python-frontmatter, requests, pyyaml); see
util/requirements.txt. Run with:

    python -m unittest discover tests
"""

import argparse
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import check_fragments as cf  # noqa: E402


ORG_FRONTMATTER = """---
title: {title}
type: ngo
status: active
country: France
website: https://example.org
summary: A test org.
events:
{events_yaml}---

Body text here.
"""


def make_org_file(directory, slug, events_yaml, title=None):
    path = os.path.join(directory, slug + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ORG_FRONTMATTER.format(title=title or slug, events_yaml=events_yaml))
    return path


BLOG_POST_FRONTMATTER = """---
title: "{title}"
date: 2026-01-01
authors:
  - Test Author
shared_link:
{shared_link_yaml}---

Body text here.
"""


def make_blog_post_file(directory, slug, shared_link_yaml, title=None):
    path = os.path.join(directory, slug + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(BLOG_POST_FRONTMATTER.format(
            title=title or slug, shared_link_yaml=shared_link_yaml))
    return path


class ParagraphHashTests(unittest.TestCase):

    def test_returns_none_when_quote_not_found(self):
        self.assertIsNone(cf.paragraph_hash("hello world", "not present"))

    def test_returns_none_on_empty_inputs(self):
        self.assertIsNone(cf.paragraph_hash("", "quote"))
        self.assertIsNone(cf.paragraph_hash("text", ""))

    def test_same_paragraph_same_hash_regardless_of_preceding_paragraphs(self):
        # Regression for the historical offset-drift bug: a prior version
        # mixed a whitespace-normalized search with raw-text indexing,
        # landing in the wrong paragraph whenever there were enough short
        # paragraphs before the quote (each "\n\n" collapses to one space
        # under normalization, shifting the reused offset). paragraph_hash
        # must return the SAME hash for the SAME paragraph regardless of
        # how much unrelated paragraph-break-separated text precedes it.
        quote = "the org was founded in 2015 by local activists"
        page_no_preamble = "Paragraph with the org was founded in 2015 by local activists in it."
        page_with_preamble = (
            "Short.\n\nAlso short.\n\nEven shorter.\n\n"
            "Paragraph with the org was founded in 2015 by local activists in it."
        )
        hash_no_preamble = cf.paragraph_hash(page_no_preamble, quote)
        hash_with_preamble = cf.paragraph_hash(page_with_preamble, quote)
        self.assertIsNotNone(hash_no_preamble)
        self.assertEqual(hash_no_preamble, hash_with_preamble)

    def test_paragraph_boundaries_respected(self):
        quote = "founded in 2015"
        page = "Unrelated first paragraph.\n\nThe org was founded in 2015 here.\n\nUnrelated last paragraph."
        expected = cf.sha256(cf.normalize_ws("The org was founded in 2015 here."))
        self.assertEqual(cf.paragraph_hash(page, quote), expected)


class WikipediaTitleTests(unittest.TestCase):

    def test_english_article(self):
        self.assertEqual(
            cf.wikipedia_title("https://en.wikipedia.org/wiki/Democracy"),
            ("en", "Democracy"),
        )

    def test_non_english_subdomain_preserved(self):
        # Regression: this used to always query en.wikipedia.org regardless
        # of the citation's actual language subdomain, silently querying a
        # nonexistent English article for e.g. fr.wikipedia.org citations.
        self.assertEqual(
            cf.wikipedia_title("https://fr.wikipedia.org/wiki/D%C3%A9mocratie"),
            ("fr", "Démocratie"),
        )

    def test_strips_trailing_fragment(self):
        lang, title = cf.wikipedia_title("https://en.wikipedia.org/wiki/Democracy#History")
        self.assertEqual(title, "Democracy")

    def test_non_wikipedia_url_returns_none(self):
        self.assertIsNone(cf.wikipedia_title("https://example.org/wiki/Democracy"))

    def test_wikipedia_domain_without_wiki_path_returns_none(self):
        self.assertIsNone(cf.wikipedia_title("https://en.wikipedia.org/w/index.php"))


class CheckEvidenceBlockedCacheTests(unittest.TestCase):
    """A URL confirmed BLOCKED (403/429) must be skipped on later runs — no
    network call — until --no-cache forces a recheck, and must NOT stay
    stuck blocked forever once the site starts answering again. Transient
    errors (a 500, a timeout) must NOT get this sticky treatment — only
    403/429 mean "this server doesn't want scripted requests."."""

    def setUp(self):
        # check_evidence() sleeps FETCH_DELAY before a real fetch attempt —
        # only mocking _fetch_page_text still leaves that real 0.5s sleep
        # in every test that reaches it. Patch it out so this stays a fast
        # offline test, not a network test with the network call removed.
        patcher = mock.patch.object(cf.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)
        # A blocked URL now queues a manual-dump request (see
        # util/manual_dump.py) — without this patch, every test below that
        # hits a blocked path would write to the real repo's
        # manual-dump/requests.txt on disk.
        queue_patcher = mock.patch.object(cf.manual_dump, "queue_request")
        self.mock_queue_request = queue_patcher.start()
        self.addCleanup(queue_patcher.stop)

    def test_blocked_url_is_skipped_without_a_fetch(self):
        cache = {"https://example.org/paper": {"blocked": "HTTP_403", "blocked_since": "2026-01-01"}}
        with mock.patch.object(cf, "_fetch_page_text") as fake_fetch:
            result, unchanged, error, ambiguous, hint, text = cf.check_evidence(
                "https://example.org/paper", "some evidence", cache, use_cache=True)
        fake_fetch.assert_not_called()
        self.assertIsNone(result)
        self.assertTrue(unchanged)
        self.assertEqual(error, "HTTP_403")

    def test_blocked_url_queues_a_manual_dump_request(self):
        cache = {"https://example.org/paper": {"blocked": "HTTP_403", "blocked_since": "2026-01-01"}}
        with mock.patch.object(cf, "_fetch_page_text"):
            cf.check_evidence("https://example.org/paper", "some evidence", cache, use_cache=True)
        self.mock_queue_request.assert_called_once_with("https://example.org/paper")

    def test_manual_verified_good_result_is_used_instead_of_still_blocked(self):
        # A human imported a browser snapshot for this URL (see
        # util/import_manual_dump.py) that confirms this exact evidence —
        # that result must be used instead of reporting STILL BLOCKED, and
        # no fetch or manual-dump request should happen.
        ev_key = cf.sha256(cf.normalize_ws("some evidence"))
        cache = {"https://example.org/paper": {
            "blocked": "HTTP_403", "blocked_since": "2026-01-01",
            "evidence": [{"id": ev_key, "manual_verified": True}],
        }}
        with mock.patch.object(cf, "_fetch_page_text") as fake_fetch:
            result, unchanged, error, ambiguous, hint, text = cf.check_evidence(
                "https://example.org/paper", "some evidence", cache, use_cache=True)
        fake_fetch.assert_not_called()
        self.mock_queue_request.assert_not_called()
        self.assertEqual(result, "good")
        self.assertTrue(unchanged)
        self.assertIsNone(error)

    def test_manual_verified_bad_result_is_used_instead_of_still_blocked(self):
        ev_key = cf.sha256(cf.normalize_ws("some evidence"))
        cache = {"https://example.org/paper": {
            "blocked": "HTTP_403", "blocked_since": "2026-01-01",
            "evidence": [{"id": ev_key, "manual_verified": False}],
        }}
        result, unchanged, error, ambiguous, hint, text = cf.check_evidence(
            "https://example.org/paper", "some evidence", cache, use_cache=True)
        self.assertEqual(result, "bad")
        self.assertIsNone(error)

    def test_manual_verified_for_different_evidence_does_not_cover_this_one(self):
        # manual_verified is keyed per evidence string — a snapshot that
        # answered a different citation's quote must not be treated as
        # covering this one; STILL BLOCKED (and a queued request) is still
        # correct here.
        other_key = cf.sha256(cf.normalize_ws("other evidence"))
        cache = {"https://example.org/paper": {
            "blocked": "HTTP_403", "blocked_since": "2026-01-01",
            "evidence": [{"id": other_key, "manual_verified": True}],
        }}
        result, unchanged, error, ambiguous, hint, text = cf.check_evidence(
            "https://example.org/paper", "some evidence", cache, use_cache=True)
        self.assertIsNone(result)
        self.assertEqual(error, "HTTP_403")
        self.mock_queue_request.assert_called_once_with("https://example.org/paper")

    def test_fresh_403_queues_a_manual_dump_request(self):
        cache = {}
        with mock.patch.object(cf, "_fetch_page_text", return_value=(None, None, "HTTP_403")):
            cf.check_evidence("https://example.org/paper", "some evidence", cache, use_cache=True)
        self.mock_queue_request.assert_called_once_with("https://example.org/paper")

    def test_fresh_403_gets_recorded_as_blocked(self):
        cache = {}
        with mock.patch.object(cf, "_fetch_page_text", return_value=(None, None, "HTTP_403")):
            cf.check_evidence("https://example.org/paper", "some evidence", cache, use_cache=True)
        self.assertEqual(cache["https://example.org/paper"]["blocked"], "HTTP_403")
        self.assertIn("blocked_since", cache["https://example.org/paper"])

    def test_transient_error_is_not_recorded_as_blocked(self):
        cache = {}
        with mock.patch.object(cf, "_fetch_page_text", return_value=(None, None, "NETWORK_ERROR")):
            cf.check_evidence("https://example.org/paper", "some evidence", cache, use_cache=True)
        self.assertNotIn("blocked", cache.get("https://example.org/paper", {}))

    def test_no_cache_bypasses_the_blocked_skip(self):
        cache = {"https://example.org/paper": {"blocked": "HTTP_403", "blocked_since": "2026-01-01"}}
        with mock.patch.object(cf, "_fetch_page_text",
                                return_value=("some evidence appears here", mock.Mock(headers={}), None)):
            result, unchanged, error, ambiguous, hint, text = cf.check_evidence(
                "https://example.org/paper", "some evidence", cache, use_cache=False)
        self.assertIsNone(error)
        self.assertEqual(result, "good")

    def test_successful_fetch_clears_a_stale_blocked_flag(self):
        cache = {"https://example.org/paper": {"blocked": "HTTP_403", "blocked_since": "2026-01-01"}}
        with mock.patch.object(cf, "_fetch_page_text",
                                return_value=("some evidence appears here", mock.Mock(headers={}), None)):
            cf.check_evidence("https://example.org/paper", "some evidence", cache, use_cache=False)
        self.assertNotIn("blocked", cache["https://example.org/paper"])
        self.assertNotIn("blocked_since", cache["https://example.org/paper"])

    def test_no_cache_failed_recheck_does_not_destroy_prior_good_verification(self):
        # Regression test: a --no-cache run from a network-disadvantaged
        # environment (a different IP a site's bot-protection blocks, one
        # that a prior run's environment could reach fine) must not let its
        # own failed fetch wipe out a previously-successful verification's
        # "evidence" records. Confirmed happening in practice —
        # a --no-cache run overwrote real prefix/suffix/text context data
        # with a bare {"blocked": ...} stub. --no-cache means "don't use the
        # cache to SKIP the check," not "discard prior good evidence if this
        # run's fetch fails."
        cache = {
            "https://example.org/paper": {
                "etag": "abc123",
                "document_sha256": "deadbeef",
                "evidence": [{"id": "somehash", "quote": "some evidence",
                              "verified": True,
                              "context": {"prefix": "before ",
                                          "text": "some evidence",
                                          "suffix": " after"}}],
                "checked": "2026-01-01",
            }
        }
        with mock.patch.object(cf, "_fetch_page_text", return_value=(None, None, "HTTP_403")):
            result, unchanged, error, ambiguous, hint, text = cf.check_evidence(
                "https://example.org/paper", "some evidence", cache, use_cache=False)
        self.assertIsNone(result)
        self.assertEqual(error, "HTTP_403")
        entry = cache["https://example.org/paper"]
        self.assertEqual(entry["blocked"], "HTTP_403")
        # The prior good evidence must survive the failed recheck.
        self.assertEqual(entry["evidence"], [{
            "id": "somehash", "quote": "some evidence", "verified": True,
            "context": {"prefix": "before ", "text": "some evidence", "suffix": " after"}}])
        self.assertEqual(entry["document_sha256"], "deadbeef")

    def test_empty_body_is_reported_as_fetch_error_not_mismatch(self):
        # Regression: glenweyl.com returns HTTP 202 with a completely empty
        # body to DOD-Bot's plain requests.get() (almost certainly a
        # bot-challenge holding page, not real content — a browser gets the
        # actual page). _fetch_page_text() sees no HTTP error, so `error` is
        # None and `text` is "" — comparing any quote against zero
        # characters always "fails," which used to report a guaranteed,
        # uninformative MISMATCH instead of the fetch problem it actually is.
        cache = {}
        with mock.patch.object(cf, "_fetch_page_text", return_value=("", mock.Mock(headers={}), None)):
            result, unchanged, error, ambiguous, hint, text = cf.check_evidence(
                "https://example.org/paper", "some evidence", cache, use_cache=True)
        self.assertIsNone(result)
        self.assertEqual(error, "EMPTY_RESPONSE")
        self.assertNotIn("https://example.org/paper", cache)

    def test_spa_shell_shorter_than_quote_is_fetch_error_not_mismatch(self):
        # Regression: governancehubafrica.org/about is a JS-rendered SPA that
        # serves plain fetches only its title (~21 chars) while a browser
        # sees ~8,000 characters. Text shorter than the evidence string
        # cannot possibly contain it — reporting MISMATCH would assert the
        # page no longer says something we never actually saw. Same failure
        # shape as the empty-body case above, just with nav chrome attached.
        shell = "Governance Hub Africa"
        cache = {}
        with mock.patch.object(cf, "_fetch_page_text", return_value=(shell, mock.Mock(headers={}), None)):
            result, unchanged, error, ambiguous, hint, text = cf.check_evidence(
                "https://example.org/about", "a quote much longer than the shell text", cache, use_cache=True)
        self.assertIsNone(result)
        self.assertEqual(error, "PAGE_TOO_SHORT")
        self.mock_queue_request.assert_called_once_with("https://example.org/about")

    def test_manual_verified_used_when_page_text_too_short(self):
        # The manual-dump escape hatch must cover the SPA-shell shape too,
        # not just 403/429 blocks: a human's browser rendered the real page,
        # so their snapshot's verdict stands in for the unreadable fetch.
        ev_key = cf.sha256(cf.normalize_ws("a quote much longer than the shell text"))
        cache = {"https://example.org/about": {
            "evidence": [{"id": ev_key, "manual_verified": True}],
        }}
        shell = "Governance Hub Africa"
        with mock.patch.object(cf, "_fetch_page_text", return_value=(shell, mock.Mock(headers={}), None)):
            result, unchanged, error, ambiguous, hint, text = cf.check_evidence(
                "https://example.org/about", "a quote much longer than the shell text", cache, use_cache=True)
        self.assertEqual(result, "good")
        self.assertTrue(unchanged)
        self.assertIsNone(error)
        self.mock_queue_request.assert_not_called()

    def test_page_longer_than_quote_still_matches_normally(self):
        # The too-short shortcut must only trigger when containment is
        # impossible: a short-but-real page longer than the quote goes
        # through normal matching (and can legitimately MISMATCH).
        page = "a real page body that simply does not contain the claim"
        cache = {}
        with mock.patch.object(cf, "_fetch_page_text", return_value=(page, mock.Mock(headers={}), None)):
            result, unchanged, error, ambiguous, hint, text = cf.check_evidence(
                "https://example.org/paper", "an entirely different sentence", cache, use_cache=True)
        self.assertEqual(result, "bad")
        self.assertIsNone(error)
        self.mock_queue_request.assert_not_called()


class DocumentSha256Tests(unittest.TestCase):
    """document_sha256 is the resource-level integrity signal projected
    into citations.json as item-level document.sha256 — sha256 of the
    full fetched page text, unconditional. Replaced a field named
    content_hash that computed paragraph_hash(text, evidence) instead:
    the hash of whichever quote's paragraph was checked most recently,
    which meant a multi-quote URL got it overwritten by iteration order,
    not page identity, on every check. See check_evidence()'s docstring.
    """

    def setUp(self):
        patcher = mock.patch.object(cf.manual_dump, "queue_request")
        self.mock_queue_request = patcher.start()
        self.addCleanup(patcher.stop)

    def test_is_full_page_hash_not_quote_paragraph_hash(self):
        page = "Some preamble.\n\nThe claim is right here in this paragraph.\n\nSome trailer."
        quote = "The claim is right here in this paragraph."
        cache = {}
        with mock.patch.object(cf, "_fetch_page_text", return_value=(page, mock.Mock(headers={}), None)):
            cf.check_evidence("https://example.org/paper", quote, cache, use_cache=True)
        expected = cf.sha256(page)
        self.assertEqual(cache["https://example.org/paper"]["document_sha256"], expected)
        # Not the paragraph hash — a real, different value for this page.
        self.assertNotEqual(expected, cf.paragraph_hash(page, quote))

    def test_stable_across_different_quotes_on_the_same_page(self):
        # The bug this replaces: checking two different quotes against
        # the same fetched page used to leave document_sha256 (then
        # named content_hash) holding whichever quote's paragraph was
        # checked last — a value that depended on call order, not page
        # identity. It must now be identical regardless of which quote
        # triggered the check.
        page = "First paragraph with claim one.\n\nSecond paragraph with claim two."
        with mock.patch.object(cf, "_fetch_page_text", return_value=(page, mock.Mock(headers={}), None)):
            cache_a = {}
            cf.check_evidence("https://example.org/paper", "First paragraph with claim one.", cache_a, use_cache=True)
            cache_b = {}
            cf.check_evidence("https://example.org/paper", "Second paragraph with claim two.", cache_b, use_cache=True)
        self.assertEqual(
            cache_a["https://example.org/paper"]["document_sha256"],
            cache_b["https://example.org/paper"]["document_sha256"],
        )

    def test_computed_even_when_quote_not_found(self):
        # The old content_hash fell back to sha256(text) only when
        # paragraph_hash() couldn't locate the quote — an inconsistency
        # in when a whole-page hash was even available. document_sha256
        # is unconditional: present on every successful fetch regardless
        # of match result.
        page = "A real page that does not contain the claimed sentence at all."
        with mock.patch.object(cf, "_fetch_page_text", return_value=(page, mock.Mock(headers={}), None)):
            cache = {}
            result, *_ = cf.check_evidence(
                "https://example.org/paper", "a sentence nowhere on this page", cache, use_cache=True)
        self.assertEqual(result, "bad")
        self.assertEqual(cache["https://example.org/paper"]["document_sha256"], cf.sha256(page))


class FetchPageTextRobotsTests(unittest.TestCase):
    """_fetch_page_text() must honor a site's robots.txt for ordinary
    citation URLs (docs/bot.md's public promise), but must NOT gate
    Wikipedia's own REST/action API — that's designed for exactly this
    kind of programmatic access (see CLAUDE.md's "Sourcing from
    Wikipedia"), and gating it would need a robots.txt lookup against a
    path this function never actually requests directly."""

    def setUp(self):
        # These tests call the REAL _fetch_page_text() with mocked HTTP, so
        # its pagecache.store() hook would otherwise write through to the
        # real .pagecache/ at the repo root (confirmed happening: the
        # Wikipedia fixture below left a "Test" entry behind). These tests
        # are about robots gating, not the reading archive.
        patcher = mock.patch.object(cf.pagecache, "enabled", False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_disallowed_url_is_not_fetched(self):
        with mock.patch.object(cf, "robots_allowed", return_value=False) as fake_robots, \
             mock.patch.object(cf.requests, "get") as fake_get:
            text, resp, error = cf._fetch_page_text(
                "https://example.org/paper", {"User-Agent": cf.USER_AGENT})
        fake_robots.assert_called_once()
        fake_get.assert_not_called()
        self.assertIsNone(text)
        self.assertIsNone(resp)
        self.assertEqual(error, "ROBOTS_DISALLOWED")

    def test_robots_disallowed_is_in_blocked_errors(self):
        # ROBOTS_DISALLOWED must get the same sticky "don't recheck every
        # run" treatment as HTTP_403/429 — see check_evidence()'s
        # BLOCKED_ERRORS handling, already covered generically by
        # CheckEvidenceBlockedCacheTests above for the HTTP_403 case.
        self.assertIn("ROBOTS_DISALLOWED", cf.BLOCKED_ERRORS)

    def test_wikipedia_api_is_not_robots_gated(self):
        with mock.patch.object(cf, "robots_allowed") as fake_robots, \
             mock.patch.object(cf.requests, "get") as fake_get:
            fake_get.return_value = mock.Mock(
                status_code=200,
                json=lambda: {"query": {"pages": {"1": {"extract": "some text"}}}})
            text, resp, error = cf._fetch_page_text(
                "https://en.wikipedia.org/wiki/Test", {"User-Agent": cf.USER_AGENT})
        fake_robots.assert_not_called()
        self.assertEqual(text, "some text")


class FetchPageTextEncodingTests(unittest.TestCase):
    """A page serving UTF-8 bytes under an absent or Latin-1-family charset
    label must be decoded as UTF-8, not requests' RFC default for unlabelled
    text/*. Confirmed broken on climateassembly.uk: it declares no charset,
    so every curly apostrophe came back as "â€™" and its quotes
    false-MISMATCHed even though browsers rendered the page correctly."""

    UTF8_BODY = ("<html><body><p>Assembly ’quoted’ – done</p></body></html>").encode("utf-8")

    def _fetch(self, resp):
        with mock.patch.object(cf, "robots_allowed", return_value=True), \
             mock.patch.object(cf.pagecache, "enabled", False), \
             mock.patch.object(cf.requests, "get", return_value=resp):
            return cf._fetch_page_text("https://example.org/page",
                                       {"User-Agent": cf.USER_AGENT})

    def _mojibake_response(self, encoding):
        resp = mock.Mock(status_code=200, headers={}, content=self.UTF8_BODY,
                         encoding=encoding)
        # What requests' r.text would hand back if the label were trusted:
        resp.text = self.UTF8_BODY.decode("iso-8859-1")
        return resp

    def test_utf8_bytes_under_latin1_label_decode_as_utf8(self):
        text, _r, error = self._fetch(self._mojibake_response("iso-8859-1"))
        self.assertIsNone(error)
        self.assertIn("\u2019quoted\u2019 \u2013 done", text)
        self.assertNotIn("\u00e2", text)  # the mojibake tell

    def test_absent_charset_label_also_prefers_utf8(self):
        text, _r, error = self._fetch(self._mojibake_response(None))
        self.assertIsNone(error)
        self.assertIn("\u2019quoted\u2019 \u2013 done", text)

    def test_genuinely_non_utf8_page_falls_back_to_declared_decoding(self):
        latin1_src = "<html><body><p>café résumé</p></body></html>"
        raw = latin1_src.encode("windows-1252")  # 0xE9 alone — invalid UTF-8
        resp = mock.Mock(status_code=200, headers={}, content=raw,
                         encoding="windows-1252")
        resp.text = latin1_src
        text, _r, error = self._fetch(resp)
        self.assertIsNone(error)
        self.assertIn("café résumé", text)  # declared decoding used intact


def _zip_bytes(members):
    """Build an in-memory zip file with the given {name: content} members."""
    import io as _io
    import zipfile
    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in members.items():
            z.writestr(name, content)
    return buf.getvalue()


class ZipXmlExtractionTests(unittest.TestCase):
    """_extract_zip_xml_text handles citation URLs that are direct document
    downloads (.docx/.odt) — detected by the PK zip magic bytes, never by
    URL extension, since a redesigned site can serve anything at a .docx
    URL. Regression-anchored on Local Government Victoria's Local Government
    Act 2020 community-engagement principles .docx."""

    DOCX_XML = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        '<w:p><w:r><w:t>Councils must apply their</w:t><w:br/><w:t>engagement policy</w:t></w:r></w:p>'
        '<w:p><w:r><w:tab/><w:t>to decisions.</w:t></w:r></w:p>'
        '</w:body></w:document>')

    def test_docx_text_runs_joined_with_paragraph_breaks_after_text(self):
        # Breaks come after each paragraph's own runs; <w:br/> and <w:tab/>
        # render as spaces (whitespace-normalised away by verification).
        text = cf._extract_zip_xml_text(_zip_bytes({"word/document.xml": self.DOCX_XML}))
        self.assertEqual(text,
                         "Councils must apply their engagement policy\n to decisions.\n")

    def test_odt_content_xml_extracted_the_same_way(self):
        odt_xml = (
            '<office:document-content '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
            '<office:body><office:text>'
            '<text:p>Engagement principles <text:span>for councils.</text:span></text:p>'
            '</office:text></office:body></office:document-content>')
        text = cf._extract_zip_xml_text(_zip_bytes({"content.xml": odt_xml}))
        self.assertEqual(text, "Engagement principles for councils.\n")

    def test_prefers_document_xml_over_content_xml(self):
        text = cf._extract_zip_xml_text(_zip_bytes({
            "content.xml": "<p>odt side</p>",
            "word/document.xml": self.DOCX_XML}))
        self.assertIn("Councils must", text)

    def test_unknown_zip_archive_returns_none(self):
        self.assertIsNone(cf._extract_zip_xml_text(
            _zip_bytes({"some/other.xml": "<data/>"})))

    def test_corrupt_bytes_return_none(self):
        self.assertIsNone(cf._extract_zip_xml_text(b"PK\x03\x04not-really-a-zip"))

    def test_empty_zip_returns_none(self):
        self.assertIsNone(cf._extract_zip_xml_text(_zip_bytes({})))

    def _fetch(self, resp):
        with mock.patch.object(cf, "robots_allowed", return_value=True), \
             mock.patch.object(cf.pagecache, "enabled", False), \
             mock.patch.object(cf.requests, "get", return_value=resp):
            return cf._fetch_page_text("https://example.gov/doc.docx",
                                       {"User-Agent": cf.USER_AGENT})

    def test_fetch_dispatches_zip_magic_to_the_extractor(self):
        resp = mock.Mock(status_code=200, headers={},
                         content=_zip_bytes({"word/document.xml": self.DOCX_XML}))
        text, _r, error = self._fetch(resp)
        self.assertIsNone(error)
        self.assertIn("engagement policy", text)

    def test_fetch_reports_office_parse_error_for_non_document_zip(self):
        resp = mock.Mock(status_code=200, headers={},
                         content=_zip_bytes({"META-INF/x": "junk"}))
        text, _r, error = self._fetch(resp)
        self.assertIsNone(text)
        self.assertEqual(error, "OFFICE_PARSE_ERROR")


class WriteQuoteFixTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def _path(self, name="org.md"):
        return os.path.join(self.tmpdir, name)

    def test_plain_scalar_substring_replace(self):
        path = self._path()
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\ntitle: X\n---\n\nSome prose with a footnoted quote here.\n")
        old = "footnoted quote here"
        new = "footnoted quote here now"
        self.assertTrue(cf.write_quote_fix(path, old, new))
        with open(path, encoding="utf-8") as f:
            self.assertIn(new, f.read())

    def test_footnote_body_with_no_frontmatter_and_no_raw_match_refuses(self):
        # No frontmatter to fall back to, and the raw string isn't present
        # verbatim (e.g. it was YAML-escaped elsewhere) — must refuse
        # rather than guess.
        path = self._path("plain.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Just prose, no frontmatter, and no match here at all.\n")
        self.assertFalse(cf.write_quote_fix(path, "text not present", "replacement"))

    def test_yaml_fallback_rewrites_folded_scalar_quote(self):
        # A quote containing an apostrophe forces YAML to store it as a
        # single-quoted scalar with '' escaping — not verbatim in the raw
        # file text, so the plain substring replace can never find it.
        events_yaml = (
            "- date: '2020-01-01'\n"
            "  title: Founded\n"
            "  url: https://example.org/about\n"
            "  quote: 'l''été 2020: something happened'\n"
            "  note: Test event.\n"
            "  proof_level: high\n"
        )
        path = make_org_file(self.tmpdir, "test-org", events_yaml)
        old = "l'été 2020: something happened"
        new = "l'été 2020: something else happened"

        self.assertTrue(cf.write_quote_fix(path, old, new))

        with open(path, encoding="utf-8") as f:
            content = f.read()
        # `new` also contains an apostrophe, so it too is stored escaped
        # (not verbatim) — compare on the PARSED value, same as the
        # function itself does, rather than raw substring search.

        import re
        import yaml
        m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        data = yaml.safe_load(m.group(1))
        self.assertEqual(data["events"][0]["quote"], new)

        # The rewritten file must still be canonically ordered.
        import reorder_frontmatter as rf
        self.assertEqual(rf.reorder_frontmatter(m.group(1)), m.group(1))

    def test_refuses_when_quote_is_not_unique_to_one_event(self):
        # Two events sharing the exact same quote text — which one would
        # the fix apply to? Refuse rather than guess. Use a value that
        # forces the YAML fallback (an apostrophe forces a quoted scalar,
        # so the plain substring path's count==1 check can't shortcut this).
        shared = "l'été 2020: shared claim"
        events_yaml = (
            "- date: '2020-01-01'\n"
            "  title: First\n"
            "  url: https://example.org/first\n"
            "  quote: '{q}'\n"
            "  note: First event.\n"
            "  proof_level: high\n"
            "- date: '2021-01-01'\n"
            "  title: Second\n"
            "  url: https://example.org/second\n"
            "  quote: '{q}'\n"
            "  note: Second event.\n"
            "  proof_level: high\n"
        ).format(q=shared.replace("'", "''"))
        path = make_org_file(self.tmpdir, "dup-org", events_yaml)
        with open(path, encoding="utf-8") as f:
            original = f.read()

        result = cf.write_quote_fix(path, shared, "a different corrected value")

        self.assertFalse(result)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), original)  # untouched

    def test_refuses_when_existing_frontmatter_is_not_canonical(self):
        # Field order deliberately wrong (status before type) — the
        # docstring says the fallback must refuse rather than fold
        # unrelated reordering into what should be a one-line fix.
        content = (
            "---\n"
            "title: Bad Order Org\n"
            "status: active\n"
            "type: ngo\n"
            "events:\n"
            "- date: '2020-01-01'\n"
            "  title: Founded\n"
            "  url: https://example.org/about\n"
            "  quote: 'l''été 2020: something happened'\n"
            "  note: Test event.\n"
            "  proof_level: high\n"
            "---\n\nBody.\n"
        )
        path = self._path("bad-order.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        old = "l'été 2020: something happened"
        result = cf.write_quote_fix(path, old, "l'été 2020: something else")

        self.assertFalse(result)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), content)  # untouched

    def test_refuses_when_events_field_missing(self):
        path = self._path("no-events.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\ntitle: No Events Org\ntype: ngo\n---\n\nBody.\n")
        # Not found verbatim either, so both the plain and YAML paths must
        # refuse.
        self.assertFalse(cf.write_quote_fix(path, "some quote", "new quote"))


class FindSharedLinkEvidenceTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_yields_url_and_description(self):
        yaml = (
            "  url: https://example.org/paper\n"
            "  title: A Paper\n"
            "  source: Example Journal\n"
            "  description: The abstract text goes here verbatim.\n"
        )
        path = make_blog_post_file(self.tmpdir, "test-post", yaml)
        items = list(cf.find_shared_link_evidence(path))
        self.assertEqual(len(items), 1)
        url, description, source_label, yielded_path = items[0]
        self.assertEqual(url, "https://example.org/paper")
        self.assertEqual(description, "The abstract text goes here verbatim.")
        self.assertIn("A Paper", source_label)
        self.assertEqual(yielded_path, path)

    def test_no_shared_link_yields_nothing(self):
        path = self._path_no_shared_link()
        self.assertEqual(list(cf.find_shared_link_evidence(path)), [])

    def _path_no_shared_link(self):
        path = os.path.join(self.tmpdir, "no-link.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\ntitle: No Link\ndate: 2026-01-01\n---\n\nBody.\n")
        return path

    def test_shared_link_without_description_yields_nothing(self):
        yaml = "  url: https://example.org/paper\n  title: A Paper\n"
        path = make_blog_post_file(self.tmpdir, "no-desc", yaml)
        self.assertEqual(list(cf.find_shared_link_evidence(path)), [])

    def test_shared_link_without_url_yields_nothing(self):
        yaml = "  description: Some text with no url to check it against.\n"
        path = make_blog_post_file(self.tmpdir, "no-url", yaml)
        self.assertEqual(list(cf.find_shared_link_evidence(path)), [])


class WriteSharedLinkFixTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_plain_scalar_substring_replace(self):
        # The common case: a description with no special YAML characters is
        # stored verbatim, so write_quote_fix's primary path (not even the
        # shared_link-specific fallback) finds and replaces it directly.
        yaml = "  url: https://example.org/paper\n  description: Old abstract text.\n"
        path = make_blog_post_file(self.tmpdir, "plain", yaml)
        self.assertTrue(cf.write_quote_fix(path, "Old abstract text.", "New abstract text."))
        with open(path, encoding="utf-8") as f:
            self.assertIn("New abstract text.", f.read())

    def test_yaml_fallback_rewrites_quoted_scalar_description(self):
        # An apostrophe forces YAML to store the value as a single-quoted
        # scalar with '' escaping — not verbatim in the raw file text, so
        # the plain substring replace can't find it and must fall back to
        # _write_shared_link_fix_yaml.
        old = "It's the abstract's opening line"
        new = "It's the abstract's corrected opening line"
        yaml = (
            "  url: https://example.org/paper\n"
            "  title: A Paper\n"
            f"  description: '{old.replace(chr(39), chr(39) * 2)}'\n"
        )
        path = make_blog_post_file(self.tmpdir, "quoted", yaml)

        self.assertTrue(cf.write_quote_fix(path, old, new))

        post_after = None
        import frontmatter as fm
        post_after = fm.load(path)
        self.assertEqual(post_after.metadata["shared_link"]["description"], new)
        # Other shared_link fields must survive the round-trip untouched.
        self.assertEqual(post_after.metadata["shared_link"]["title"], "A Paper")

    def test_refuses_when_description_does_not_match(self):
        yaml = "  url: https://example.org/paper\n  description: Some text.\n"
        path = make_blog_post_file(self.tmpdir, "mismatch", yaml)
        with open(path, encoding="utf-8") as f:
            original = f.read()
        result = cf.write_quote_fix(path, "text that is not present anywhere", "new text")
        self.assertFalse(result)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), original)  # untouched

    def test_refuses_when_no_shared_link_field(self):
        path = os.path.join(self.tmpdir, "no-link.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\ntitle: No Link\ndate: 2026-01-01\n---\n\nBody.\n")
        self.assertFalse(cf.write_quote_fix(path, "some text", "new text"))


class CollectEvidenceSlugFilterTests(unittest.TestCase):
    """Regression test for the --slug bug: --slug a --slug b used to
    silently keep only the last flag (a plain str field, overwritten on
    each occurrence), so a multi-org run verified one org while reporting
    as if it checked both. args.slug is now a list (action="append")."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self._orig_org_dir = cf.ORG_DIR
        self._orig_docs_dir = cf.DOCS_DIR
        cf.ORG_DIR = self.tmpdir
        cf.DOCS_DIR = self.tmpdir

        one_event = (
            "- date: '2020-01-01'\n"
            "  title: Founded\n"
            "  url: https://example.org/about\n"
            "  quote: some quote text\n"
            "  note: Test event.\n"
            "  proof_level: high\n"
        )
        make_org_file(self.tmpdir, "alpha-org", one_event)
        make_org_file(self.tmpdir, "beta-org", one_event)
        make_org_file(self.tmpdir, "gamma-org", one_event)

    def tearDown(self):
        cf.ORG_DIR = self._orig_org_dir
        cf.DOCS_DIR = self._orig_docs_dir

    def _slugs_seen(self, args):
        items = cf.collect_evidence(args)
        return {source_label.split(" ", 1)[0] for _, _, source_label, kind, _ in items
                if kind == "event"}

    def _args(self, slug=None):
        return argparse.Namespace(slug=slug, events_only=True)

    def test_no_slug_filter_includes_all_orgs(self):
        self.assertEqual(
            self._slugs_seen(self._args(slug=None)),
            {"alpha-org", "beta-org", "gamma-org"},
        )

    def test_single_slug_filters_to_one_org(self):
        self.assertEqual(self._slugs_seen(self._args(slug=["alpha-org"])), {"alpha-org"})

    def test_repeated_slug_includes_every_named_org(self):
        # This is the exact regression scenario: --slug alpha-org --slug
        # gamma-org should check BOTH, not silently collapse to the last one.
        seen = self._slugs_seen(self._args(slug=["alpha-org", "gamma-org"]))
        self.assertEqual(seen, {"alpha-org", "gamma-org"})
        self.assertNotIn("beta-org", seen)


class CollectEvidenceSharedLinkTests(unittest.TestCase):
    """collect_evidence() must pick up blog posts' shared_link.description:
    under docs/blog/posts/, tagged kind='shared_link', alongside events and
    footnotes — not just org pages directly under DOCS_DIR."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self._orig_org_dir = cf.ORG_DIR
        self._orig_docs_dir = cf.DOCS_DIR
        cf.ORG_DIR = os.path.join(self.tmpdir, "organisations")
        cf.DOCS_DIR = self.tmpdir
        os.makedirs(cf.ORG_DIR, exist_ok=True)

        posts_dir = os.path.join(self.tmpdir, "blog", "posts")
        os.makedirs(posts_dir, exist_ok=True)
        make_blog_post_file(
            posts_dir, "test-post",
            "  url: https://example.org/paper\n"
            "  title: A Paper\n"
            "  description: The abstract text goes here.\n",
        )

    def tearDown(self):
        cf.ORG_DIR = self._orig_org_dir
        cf.DOCS_DIR = self._orig_docs_dir

    def test_shared_link_evidence_is_collected(self):
        args = argparse.Namespace(slug=None, events_only=False)
        items = cf.collect_evidence(args)
        shared_link_items = [i for i in items if i[3] == "shared_link"]
        self.assertEqual(len(shared_link_items), 1)
        url, description, source_label, kind, path = shared_link_items[0]
        self.assertEqual(url, "https://example.org/paper")
        self.assertEqual(description, "The abstract text goes here.")

    def test_events_only_excludes_shared_link(self):
        args = argparse.Namespace(slug=None, events_only=True)
        items = cf.collect_evidence(args)
        self.assertFalse([i for i in items if i[3] == "shared_link"])


class SetUrlStatusCliTests(unittest.TestCase):
    """--set-url-status writes/clears url_status in the evidence cache —
    the manual, never-auto-inferred liveness flag consumed by
    text_fragment.load_archive_info() and rendered by organisation.html /
    hooks/footnote_fragments.py. See internal-heartbeat/
    2026-08-22-citation-archival-design-decisions.md."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.cache_path = os.path.join(self.tmpdir, "cache.json")
        self._orig_cache_path = cf.STATE_PATH
        cf.STATE_PATH = self.cache_path
        self.addCleanup(self._restore)

    def _restore(self):
        cf.STATE_PATH = self._orig_cache_path

    def _run(self, *argv):
        with mock.patch.object(sys, "argv", ["check_fragments.py", *argv]):
            cf.main()

    def test_sets_dead_status_on_new_url(self):
        self._run("--set-url-status", "https://example.org/x", "dead")
        cache = cf.load_state()
        self.assertEqual(cache["https://example.org/x"]["url_status"], "dead")

    def test_sets_unfit_status_preserving_other_fields(self):
        cf.save_state({"https://example.org/x": {"checked": "2026-08-01"}})
        self._run("--set-url-status", "https://example.org/x", "unfit")
        cache = cf.load_state()
        self.assertEqual(cache["https://example.org/x"]["url_status"], "unfit")
        self.assertEqual(cache["https://example.org/x"]["checked"], "2026-08-01")

    def test_live_clears_the_field(self):
        cf.save_state({"https://example.org/x": {"url_status": "dead",
                                                   "checked": "2026-08-01"}})
        self._run("--set-url-status", "https://example.org/x", "live")
        cache = cf.load_state()
        self.assertNotIn("url_status", cache["https://example.org/x"])
        self.assertEqual(cache["https://example.org/x"]["checked"], "2026-08-01")

    def test_status_is_case_insensitive(self):
        self._run("--set-url-status", "https://example.org/x", "DEAD")
        cache = cf.load_state()
        self.assertEqual(cache["https://example.org/x"]["url_status"], "dead")

    def test_invalid_status_rejected(self):
        with self.assertRaises(SystemExit):
            self._run("--set-url-status", "https://example.org/x", "bogus")
        # Nothing should have been written.
        self.assertFalse(os.path.exists(self.cache_path))

    def test_offline_and_save_to_wayback_still_mutually_exclusive(self):
        # Unrelated pre-existing guard — confirm --set-url-status didn't
        # disturb argument parsing for the other flags.
        with self.assertRaises(SystemExit):
            self._run("--offline", "--save-to-wayback")


class UncheckedOnlyFilterTests(unittest.TestCase):
    """--unchecked-only skips any evidence already present in the evidence
    file's verified map, with zero network calls for it — distinct from
    the default cache-aware path, which still issues a conditional-GET
    request per URL on every run even when nothing has changed."""

    CHECKED_URL = "https://example.org/checked"
    CHECKED_QUOTE = "this quote was already verified"
    NEW_URL = "https://example.org/new"
    NEW_QUOTE = "this quote has never been checked"

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self._orig_org_dir = cf.ORG_DIR
        self._orig_docs_dir = cf.DOCS_DIR
        self._orig_evidence_path = cf.STATE_PATH
        cf.ORG_DIR = self.tmpdir
        cf.DOCS_DIR = self.tmpdir
        cf.STATE_PATH = os.path.join(self.tmpdir, "evidence.json")
        self.addCleanup(self._restore)

        make_org_file(self.tmpdir, "already-checked-org", (
            "- date: '2020-01-01'\n"
            "  title: Founded\n"
            f"  url: {self.CHECKED_URL}\n"
            f"  quote: {self.CHECKED_QUOTE}\n"
            "  proof_level: high\n"
        ))
        make_org_file(self.tmpdir, "new-org", (
            "- date: '2020-01-01'\n"
            "  title: Founded\n"
            f"  url: {self.NEW_URL}\n"
            f"  quote: {self.NEW_QUOTE}\n"
            "  proof_level: high\n"
        ))

        ev_key = cf.sha256(cf.normalize_ws(self.CHECKED_QUOTE))
        cf.save_state({self.CHECKED_URL: {
            "evidence": [{"id": ev_key, "quote": self.CHECKED_QUOTE, "verified": True}]}})

        sleep_patcher = mock.patch.object(cf.time, "sleep")
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    def _restore(self):
        cf.ORG_DIR = self._orig_org_dir
        cf.DOCS_DIR = self._orig_docs_dir
        cf.STATE_PATH = self._orig_evidence_path

    def _run(self, *argv):
        # main() always calls sys.exit() on its normal completion path
        # (0 = clean, 1 = a MISMATCH found, 2 = argparse rejected the
        # arguments) — every test here cares about that exit code, so
        # none of them should swallow it.
        with mock.patch.object(sys, "argv", ["check_fragments.py", *argv]):
            with self.assertRaises(SystemExit) as cm:
                cf.main()
            return cm.exception.code

    def _fake_fetch(self, url, headers):
        text = self.CHECKED_QUOTE if url == self.CHECKED_URL else self.NEW_QUOTE
        return (f"Some page text. {text} And more text.",
                mock.Mock(status_code=200, headers={}), None)

    def test_unchecked_only_fetches_only_the_new_url(self):
        fetched = []
        with mock.patch.object(cf, "_fetch_page_text",
                               side_effect=lambda url, headers: (
                                   fetched.append(url), self._fake_fetch(url, headers))[1]):
            exit_code = self._run("--unchecked-only")
        self.assertEqual(fetched, [self.NEW_URL])
        self.assertEqual(exit_code, 0)

    def test_without_the_flag_both_urls_are_fetched(self):
        fetched = []
        with mock.patch.object(cf, "_fetch_page_text",
                               side_effect=lambda url, headers: (
                                   fetched.append(url), self._fake_fetch(url, headers))[1]):
            exit_code = self._run()
        self.assertEqual(set(fetched), {self.CHECKED_URL, self.NEW_URL})
        self.assertEqual(exit_code, 0)

    def test_cannot_combine_with_no_cache(self):
        # argparse's parser.error() exits with code 2, distinct from the
        # 0/1 main() itself would return.
        self.assertEqual(self._run("--unchecked-only", "--no-cache"), 2)


if __name__ == "__main__":
    unittest.main()
