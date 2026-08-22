#!/usr/bin/env python3
"""Regression tests for util/pagecache.py — the local reading copies of
cited pages written through by check_fragments.py at fetch time — and for
the fetch-path hooks in check_fragments._fetch_page_text() that populate it.

Offline, no network. Isolates all file I/O to a tempdir by patching the
module's path constants (same approach as test_manual_dump.py), so these
tests never touch the real (gitignored) .pagecache/ directory at the repo
root. The fetch-hook tests stub requests.get and robots_allowed rather than
hitting any site. Run with:

    python -m unittest discover tests
"""

import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import pagecache as pc  # noqa: E402


class PageCacheIsolationMixin:
    """Redirects pagecache's path constants into a fresh tempdir for the
    duration of each test, and restores enabled=True (a prior test may have
    flipped it off — module state, so it leaks between tests otherwise)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        cache_dir = os.path.join(self.tmpdir, ".pagecache")
        index_path = os.path.join(cache_dir, "index.json")
        for name, value in [("PAGECACHE_DIR", cache_dir), ("INDEX_PATH", index_path)]:
            patcher = mock.patch.object(pc, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        enabled_patcher = mock.patch.object(pc, "enabled", True)
        enabled_patcher.start()
        self.addCleanup(enabled_patcher.stop)
        self.cache_dir = cache_dir
        self.index_path = index_path


class StoreGetTests(PageCacheIsolationMixin, unittest.TestCase):

    def test_roundtrip_stores_text_and_index_metadata(self):
        pc.store("https://example.org/report", "The assembly voted on 3 May 2026.")
        text, meta = pc.get("https://example.org/report")
        self.assertEqual(text, "The assembly voted on 3 May 2026.")
        self.assertEqual(meta["url"], "https://example.org/report")
        self.assertEqual(meta["checked"], date.today().isoformat())
        self.assertEqual(meta["chars"], len(text))
        # sha256 is of the stored text, verifiable independently
        self.assertEqual(meta["sha256"],
                         hashlib.sha256(text.encode("utf-8")).hexdigest())

    def test_overwrite_replaces_text_and_updates_meta(self):
        pc.store("https://example.org/report", "old body")
        pc.store("https://example.org/report", "new, longer body")
        text, meta = pc.get("https://example.org/report")
        self.assertEqual(text, "new, longer body")
        self.assertEqual(meta["chars"], len("new, longer body"))

    def test_disabled_flag_is_a_full_no_op(self):
        pc.enabled = False
        pc.store("https://example.org/report", "should not be written")
        self.assertFalse(os.path.exists(self.cache_dir))
        self.assertIsNone(pc.get("https://example.org/report"))

    def test_empty_text_is_never_stored(self):
        pc.store("https://example.org/empty", "")
        self.assertIsNone(pc.get("https://example.org/empty"))
        # ...and no stray zero-byte file either
        self.assertFalse(os.path.exists(self.cache_dir))


class CorruptionToleranceTests(PageCacheIsolationMixin, unittest.TestCase):
    """index.json is a catalog over plain .txt files — the files are the
    data, so a mangled index must degrade gracefully, not take the store
    (or the verification run writing through it) down."""

    def test_mangled_index_loads_as_empty_and_store_recovers(self):
        pc.store("https://example.org/a", "body a")
        with open(self.index_path, "w") as f:
            f.write("{not json at all")
        self.assertIsNone(pc.get("https://example.org/a"))  # catalog lost...
        pc.store("https://example.org/b", "body b")          # ...but writable
        text, _meta = pc.get("https://example.org/b")
        self.assertEqual(text, "body b")

    def test_index_entry_without_its_txt_file_reads_as_absent(self):
        pc.store("https://example.org/orphan", "text whose file vanishes")
        key = pc.key_for("https://example.org/orphan")
        os.remove(os.path.join(self.cache_dir, key + ".txt"))
        self.assertIsNone(pc.get("https://example.org/orphan"))


class MatchingEntriesTests(PageCacheIsolationMixin, unittest.TestCase):

    def test_substring_filter_case_insensitive_newest_first(self):
        pc.store("https://example.org/G0v-summit", "x" * 10)
        pc.store("https://example.org/adrindia-about", "y" * 20)
        hits = [e["url"] for e in pc.matching_entries("G0V")]
        self.assertEqual(hits, ["https://example.org/G0v-summit"])
        all_urls = [e["url"] for e in pc.matching_entries("")]
        self.assertEqual(len(all_urls), 2)

    def test_same_day_entries_keep_a_stable_order(self):
        for i in range(5):
            pc.store(f"https://example.org/page-{i}", f"text {i}")
        urls = [e["url"] for e in pc.matching_entries("")]
        self.assertEqual(sorted(urls), sorted(f"https://example.org/page-{i}" for i in range(5)))


class FetchHookTests(unittest.TestCase):
    """check_fragments._fetch_page_text() must write through on every full-
    body success path — this is what makes the archive populate without any
    separate 'please snapshot' step. Network is mocked; nothing is hit."""

    HTML = "<html><head><title>t</title></head><body><p>The council was founded in 2019.</p></body></html>"

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        import check_fragments as cf
        self.cf = cf
        for name, value in [("PAGECACHE_DIR", self.tmpdir),
                            ("INDEX_PATH", os.path.join(self.tmpdir, "index.json"))]:
            patcher = mock.patch.object(cf.pagecache, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        enabled_patcher = mock.patch.object(cf.pagecache, "enabled", True)
        enabled_patcher.start()
        self.addCleanup(enabled_patcher.stop)

    class FakeResponse:
        status_code = 200
        headers = {}
        text = ""  # set per-test below
        content = b""
        encoding = None  # _fetch_page_text consults this for charset handling

        def raise_for_status(self):
            pass

    def test_html_fetch_writes_through(self):
        resp = self.FakeResponse()
        resp.text = self.HTML
        resp.content = self.HTML.encode("utf-8")
        with mock.patch.object(self.cf, "robots_allowed", return_value=True), \
             mock.patch.object(self.cf.requests, "get", return_value=resp):
            text, r, error = self.cf._fetch_page_text(
                "https://example.org/about", {"User-Agent": "test"})
        self.assertIsNone(error)
        self.assertIn("founded in 2019", text)
        stored, meta = pc.get("https://example.org/about")
        self.assertEqual(stored, text)  # identical pipeline output, byte for byte

    def test_no_page_cache_leaves_nothing_behind(self):
        pc.enabled = False
        resp = self.FakeResponse()
        resp.text = self.HTML
        resp.content = self.HTML.encode("utf-8")
        with mock.patch.object(self.cf, "robots_allowed", return_value=True), \
             mock.patch.object(self.cf.requests, "get", return_value=resp):
            text, r, error = self.cf._fetch_page_text(
                "https://example.org/about", {"User-Agent": "test"})
        self.assertIsNone(error)  # fetch itself unaffected by the opt-out
        self.assertIsNone(pc.get("https://example.org/about"))
        self.assertEqual(os.listdir(self.tmpdir), [])  # not even the directory


class OfflineModeTests(unittest.TestCase):
    """check_evidence(from_pagecache=True) — the --offline cite-adjustment
    path: answers from stored copies only, no network, no evidence-cache
    mutation, no manual-dump queueing, and it deliberately bypasses the
    sticky-blocked cache (a blocked live fetch can still have a stored copy)."""

    QUOTE = "The council was founded in 2019."
    PAGE = ("Intro paragraph. " + QUOTE + " It has since grown. " + QUOTE +
            " Closing paragraph.")

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        import check_fragments as cf
        self.cf = cf
        for name, value in [("PAGECACHE_DIR", self.tmpdir),
                            ("INDEX_PATH", os.path.join(self.tmpdir, "index.json"))]:
            patcher = mock.patch.object(cf.pagecache, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        enabled_patcher = mock.patch.object(cf.pagecache, "enabled", True)
        enabled_patcher.start()
        self.addCleanup(enabled_patcher.stop)
        queue_patcher = mock.patch.object(cf.manual_dump, "queue_request")
        self.queue_request = queue_patcher.start()
        self.addCleanup(queue_patcher.stop)

    def test_good_match_against_stored_copy(self):
        pc.store("https://example.org/about", "Lead. " + self.QUOTE + " More text.")
        cache = {}
        result, unchanged, error, ambiguous, hint, page_text = self.cf.check_evidence(
            "https://example.org/about", self.QUOTE, cache, use_cache=True,
            from_pagecache=True)
        self.assertEqual(result, "good")
        self.assertFalse(unchanged)  # not an evidence-cache answer at all
        self.assertIsNone(error)
        self.assertEqual(page_text, "Lead. " + self.QUOTE + " More text.")
        # The whole point of --offline: zero writes to official state.
        self.assertEqual(cache, {})
        self.queue_request.assert_not_called()

    def test_ambiguous_detected_offline(self):
        pc.store("https://example.org/about", self.PAGE)  # quote occurs twice
        result, _u, _e, ambiguous, _h, _t = self.cf.check_evidence(
            "https://example.org/about", self.QUOTE, {}, from_pagecache=True)
        self.assertEqual(result, "good")
        self.assertTrue(ambiguous)

    def test_mismatch_returns_bad_with_hint(self):
        pc.store("https://example.org/about",
                 "The council was founded in 2020, not 2019.")
        result, _u, error, _a, hint, _t = self.cf.check_evidence(
            "https://example.org/about", self.QUOTE, {}, from_pagecache=True)
        self.assertEqual(result, "bad")
        self.assertIsNone(error)
        self.assertIsNotNone(hint)  # fuzzy diagnostic for the adjuster

    def test_missing_copy_reports_not_cached_without_touching_cache(self):
        result, _u, error, _a, _h, page_text = self.cf.check_evidence(
            "https://example.org/never-fetched", "anything", {}, from_pagecache=True)
        self.assertIsNone(result)
        self.assertEqual(error, "NOT_CACHED")
        self.assertIsNone(page_text)

    def test_blocked_url_is_still_checkable_from_its_copy(self):
        pc.store("https://example.org/blocked", "Body text with " + self.QUOTE)
        blocked_cache = {"https://example.org/blocked":
                         {"blocked": "HTTP_403", "blocked_since": "2026-01-01"}}
        result, unchanged, error, _a, _h, _t = self.cf.check_evidence(
            "https://example.org/blocked", self.QUOTE, blocked_cache,
            use_cache=True, from_pagecache=True)
        self.assertEqual(result, "good")     # answered from the copy...
        self.assertFalse(unchanged)          # ...not the sticky-block path
        self.assertIsNone(error)
        self.assertIn("blocked", blocked_cache["https://example.org/blocked"])
        self.queue_request.assert_not_called()  # no human work queued offline


if __name__ == "__main__":
    unittest.main()
