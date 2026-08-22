#!/usr/bin/env python3
"""Regression tests for util/manual_dump.py — the request-queue and
browser-snapshot-parsing helpers for the manual page-dump workflow.

Offline, no network. Isolates all file I/O to a tempdir by patching the
module's path constants, so these tests never touch the real (gitignored)
manual-dump/ directory at the repo root. Run with:

    python -m unittest discover tests
"""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import manual_dump as md  # noqa: E402
import import_manual_dump as imd  # noqa: E402

try:
    import pdfminer  # noqa: F401
    HAS_PDFMINER = True
except ImportError:
    HAS_PDFMINER = False


def minimal_pdf(text):
    """Builds a small but structurally valid one-page PDF containing text,
    xref table included — enough for pdfminer to extract it back."""
    stream = ("BT /F1 12 Tf 72 720 Td (%s) Tj ET" % text).encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += (b"trailer\n<< /Size " + str(len(objs) + 1).encode()
            + b" /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF")
    return out


class ManualDumpPathIsolationMixin:
    """Redirects manual_dump's path constants into a fresh tempdir for
    the duration of each test, so queue_request/dequeue_request never
    touch the real repo-root manual-dump/ directory."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        dump_dir = os.path.join(self.tmpdir, "manual-dump")
        requests_path = os.path.join(dump_dir, "requests.txt")
        snapshots_dir = os.path.join(dump_dir, "snapshots")
        # imported/ is a sibling of snapshots/, not a child — see
        # manual_dump.IMPORTED_DIR for why.
        imported_dir = os.path.join(dump_dir, "imported")
        for name, value in [("DUMP_DIR", dump_dir), ("REQUESTS_PATH", requests_path),
                            ("SNAPSHOTS_DIR", snapshots_dir), ("IMPORTED_DIR", imported_dir),
                            ("URL_MAP_PATH", os.path.join(snapshots_dir, "url-map.txt")),
                            ("IMPORT_MAP_PATH", os.path.join(dump_dir, "import.json"))]:
            patcher = mock.patch.object(md, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.requests_path = requests_path


class QueueRequestTests(ManualDumpPathIsolationMixin, unittest.TestCase):

    def test_creates_the_file_and_writes_the_url(self):
        md.queue_request("https://example.org/paper")
        with open(self.requests_path) as f:
            self.assertEqual(f.read(), "https://example.org/paper\n")

    def test_appends_a_second_distinct_url(self):
        md.queue_request("https://example.org/paper")
        md.queue_request("https://example.org/other")
        with open(self.requests_path) as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["https://example.org/paper", "https://example.org/other"])

    def test_deduplicates_the_same_url(self):
        md.queue_request("https://example.org/paper")
        md.queue_request("https://example.org/paper")
        with open(self.requests_path) as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["https://example.org/paper"])

    def test_never_raises_if_the_directory_cannot_be_created(self):
        # queue_request is a best-effort convenience nudge, not something
        # that should ever break a verification run.
        with mock.patch.object(md.os, "makedirs", side_effect=OSError("no space")):
            md.queue_request("https://example.org/paper")  # must not raise


class DequeueRequestTests(ManualDumpPathIsolationMixin, unittest.TestCase):

    def test_removes_the_matching_url(self):
        md.queue_request("https://example.org/paper")
        md.queue_request("https://example.org/other")
        md.dequeue_request("https://example.org/paper")
        with open(self.requests_path) as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["https://example.org/other"])

    def test_noop_when_url_not_present(self):
        md.queue_request("https://example.org/paper")
        md.dequeue_request("https://example.org/nowhere")
        with open(self.requests_path) as f:
            lines = f.read().splitlines()
        self.assertEqual(lines, ["https://example.org/paper"])

    def test_noop_when_file_does_not_exist(self):
        md.dequeue_request("https://example.org/paper")  # must not raise
        self.assertFalse(os.path.exists(self.requests_path))


class ParseSavedFromUrlTests(unittest.TestCase):
    """Firefox/Chrome/IE-Edge historically stamp this comment as the first
    line of a page saved via 'Save Page As' — though current versions have
    become unreliable about it, hence the meta/map fallbacks."""

    def test_extracts_the_url(self):
        html_src = "<!-- saved from url=(0034)https://example.org/some/page -->\n<html></html>"
        self.assertEqual(md.parse_saved_from_url(html_src), "https://example.org/some/page")

    def test_returns_none_without_the_comment(self):
        self.assertIsNone(md.parse_saved_from_url("<html><body>hello</body></html>"))

    def test_only_scans_the_first_2kb(self):
        padding = "x" * 3000
        html_src = "<!-- padding: " + padding + " -->\n<!-- saved from url=(0022)https://example.org/x -->"
        self.assertIsNone(md.parse_saved_from_url(html_src))


class ParseMetaUrlTests(unittest.TestCase):
    """Fallback recovery for unstamped saves: the page's own canonical /
    og:url declaration. Regression-anchored on real saves: Medium pages
    carry both tags; climateassembly.uk declares a scheme-less og:url."""

    def test_prefers_canonical_over_og_url(self):
        html_src = ('<meta property="og:url" content="https://example.org/og">'
                    '<link rel="canonical" href="https://example.org/canonical">')
        self.assertEqual(md.parse_meta_url(html_src), "https://example.org/canonical")

    def test_falls_back_to_og_url_without_canonical(self):
        html_src = '<meta property="og:url" content="https://example.org/only-og">'
        self.assertEqual(md.parse_meta_url(html_src), "https://example.org/only-og")

    def test_returns_none_when_neither_present(self):
        self.assertIsNone(md.parse_meta_url("<html><head><title>x</title></head></html>"))

    def test_normalises_protocol_relative_url(self):
        html_src = '<link rel="canonical" href="//cdn.example.org/page">'
        self.assertEqual(md.parse_meta_url(html_src), "https://cdn.example.org/page")

    def test_normalises_scheme_less_www_url(self):
        # Real case: climateassembly.uk's og:url is literally
        # 'www.climateassembly.uk/about/' with no scheme.
        html_src = '<meta property="og:url" content="www.climateassembly.uk/about/">'
        self.assertEqual(md.parse_meta_url(html_src), "https://www.climateassembly.uk/about/")

    def test_leaves_other_relative_forms_alone(self):
        # A bare path can't be attributed to a host — returned as-is so the
        # resulting citation mismatch surfaces as NO MATCH, not a wrong match.
        html_src = '<link rel="canonical" href="/about/">'
        self.assertEqual(md.parse_meta_url(html_src), "/about/")


class LoadUrlMapTests(ManualDumpPathIsolationMixin, unittest.TestCase):
    """The human-maintained filename → URL sidecar. Authoritative over
    stamps and meta tags because it's deliberate human intent."""

    def write_map(self, text):
        os.makedirs(md.SNAPSHOTS_DIR, exist_ok=True)
        with open(md.URL_MAP_PATH, "w", encoding="utf-8") as f:
            f.write(text)

    def test_parses_filename_with_spaces_and_url(self):
        self.write_map("My Saved Page.html https://example.org/page\n")
        self.assertEqual(md.load_url_map(), {"My Saved Page.html": "https://example.org/page"})

    def test_takes_last_whitespace_run_as_separator(self):
        self.write_map("A   B.html\thttps://example.org/x\n")
        self.assertEqual(md.load_url_map(), {"A   B.html": "https://example.org/x"})

    def test_ignores_comments_blanks_and_malformed_lines(self):
        self.write_map("# a comment\n\njust-one-token\nok.html https://example.org/y\n")
        self.assertEqual(md.load_url_map(), {"ok.html": "https://example.org/y"})

    def test_empty_when_file_missing(self):
        self.assertEqual(md.load_url_map(), {})

    def test_custom_path_argument(self):
        custom = os.path.join(self.tmpdir, "elsewhere.txt")
        with open(custom, "w", encoding="utf-8") as f:
            f.write("x.html https://example.org/z\n")
        self.assertEqual(md.load_url_map(path=custom), {"x.html": "https://example.org/z"})


class RebuildImportMapTests(ManualDumpPathIsolationMixin, unittest.TestCase):
    """Reconstructing the import manifest from imported/ contents — used to
    backfill entries created before the manifest existed, or regenerate a
    lost one. Verdict counts come from the shared evidence cache, keyed by
    the re-recovered URL."""

    STAMPED = '<!-- saved from url=(0021)https://example.org/a -->\n<html>page a</html>'
    UNSTAMPED = ('<html><head><link rel="canonical" '
                 'href="https://example.org/b"></head><body>page b</body></html>')
    CACHE = {
        "https://example.org/a": {"manual_verified": {"h1": True, "h2": False},
                                  "manual_checked": "2026-08-22"},
        "https://example.org/b": {"manual_verified": {"h3": True},
                                  "manual_checked": "2026-08-21"},
    }

    def setUp(self):
        super().setUp()
        os.makedirs(md.IMPORTED_DIR)

    def test_recovers_urls_and_counts_verdicts(self):
        with open(os.path.join(md.IMPORTED_DIR, "a.html"), "w") as f:
            f.write(self.STAMPED)
        with open(os.path.join(md.IMPORTED_DIR, "b.html"), "w") as f:
            f.write(self.UNSTAMPED)
        entries = imd.rebuild_import_map(self.CACHE, {})
        self.assertEqual(entries["a.html"], {
            "url": "https://example.org/a", "source": "stamp",
            "checked": "2026-08-22", "good": 1, "mismatch": 1})
        self.assertEqual(entries["b.html"], {
            "url": "https://example.org/b", "source": "meta tag",
            "checked": "2026-08-21", "good": 1, "mismatch": 0})

    def test_unrecoverable_file_listed_honestly_with_null_url(self):
        with open(os.path.join(md.IMPORTED_DIR, "mystery.html"), "w") as f:
            f.write("<html>no markers at all</html>")
        entries = imd.rebuild_import_map({}, {})
        self.assertEqual(entries["mystery.html"]["url"], None)
        self.assertEqual(entries["mystery.html"]["source"], "unknown")

    def test_companion_files_folders_get_no_entry(self):
        with open(os.path.join(md.IMPORTED_DIR, "a.html"), "w") as f:
            f.write(self.STAMPED)
        os.makedirs(os.path.join(md.IMPORTED_DIR, "a_files"))
        entries = imd.rebuild_import_map(self.CACHE, {})
        self.assertEqual(list(entries), ["a.html"])

    def test_url_map_wins_over_embedded_markers(self):
        with open(os.path.join(md.IMPORTED_DIR, "a.html"), "w") as f:
            f.write(self.STAMPED)
        entries = imd.rebuild_import_map({}, {"a.html": "https://example.org/mapped"})
        self.assertEqual(entries["a.html"]["url"], "https://example.org/mapped")
        self.assertEqual(entries["a.html"]["source"], "url-map")

    def test_empty_or_missing_imported_dir_gives_empty_map(self):
        shutil.rmtree(md.IMPORTED_DIR)
        self.assertEqual(imd.rebuild_import_map(self.CACHE, {}), {})


class LoadImportMapTests(ManualDumpPathIsolationMixin, unittest.TestCase):

    def test_roundtrips_through_save_and_load(self):
        imd.save_import_map({"a.html": {"url": "https://example.org/x"}})
        self.assertEqual(imd.load_import_map(),
                         {"a.html": {"url": "https://example.org/x"}})

    def test_missing_file_loads_as_empty(self):
        self.assertEqual(imd.load_import_map(), {})

    def test_corrupt_json_loads_as_empty(self):
        os.makedirs(md.DUMP_DIR, exist_ok=True)
        with open(md.IMPORT_MAP_PATH, "w") as f:
            f.write("{not json")
        self.assertEqual(imd.load_import_map(), {})


@unittest.skipUnless(HAS_PDFMINER, "pdfminer.six not installed")
class ImportSnapshotPdfTests(ManualDumpPathIsolationMixin, unittest.TestCase):
    """Downloaded-PDF snapshots (a browser 'Save As' of a citation URL that
    is a direct file download) import like zip docs: bytes-sniffed by %PDF-
    magic, URL recoverable only via url-map.txt, verdicts recorded under that
    URL in the shared evidence cache."""

    URL = "https://www.parliament.vic.gov.au/example/response.pdf"
    NAME = "3ab-response.pdf"
    QUOTE = "The assembly recommended reform."

    def setUp(self):
        super().setUp()
        os.makedirs(md.SNAPSHOTS_DIR, exist_ok=True)
        self.path = os.path.join(md.SNAPSHOTS_DIR, self.NAME)
        with open(self.path, "wb") as f:
            f.write(minimal_pdf(self.QUOTE))

    def _import(self, evidence, url_map=None, cache=None, dry_run=False):
        return imd.import_snapshot(
            self.path, cache if cache is not None else {},
            {self.URL: [(evidence, "post [^q]", "footnote")]},
            url_map if url_map is not None else {self.NAME: self.URL},
            {}, dry_run=dry_run)

    def test_pdf_snapshot_verifies_quote_and_records_verdict(self):
        cache = {}
        ok = self._import(self.QUOTE, cache=cache)
        self.assertTrue(ok)
        mv = cache[self.URL]["manual_verified"]
        self.assertEqual(list(mv.values()), [True])
        self.assertEqual(cache[self.URL]["manual_checked"], date.today().isoformat())

    def test_mismatching_evidence_records_false_not_failure(self):
        cache = {}
        ok = self._import("A sentence that appears nowhere in the PDF.", cache=cache)
        self.assertTrue(ok)
        self.assertEqual(list(cache[self.URL]["manual_verified"].values()), [False])

    def test_dry_run_leaves_cache_and_file_untouched(self):
        cache = {}
        ok = self._import(self.QUOTE, cache=cache, dry_run=True)
        self.assertTrue(ok)
        self.assertEqual(cache, {})
        self.assertTrue(os.path.exists(self.path))

    def test_missing_url_map_entry_skips_without_raising(self):
        ok = self._import(self.QUOTE, url_map={})
        self.assertFalse(ok)
        self.assertTrue(os.path.exists(self.path),
                        "unmatched snapshot must stay in snapshots/")

    def test_imported_file_moves_to_imported_dir(self):
        self._import(self.QUOTE)
        self.assertFalse(os.path.exists(self.path))
        self.assertTrue(os.path.exists(os.path.join(md.IMPORTED_DIR, self.NAME)))

    def test_import_seeds_pagecache_with_extracted_text(self):
        """The human-obtained copy is the best text bot-blocked/SPA URLs ever
        yield to us — it should land in .pagecache/ so later --offline quote
        work covers manually-resolved citations too."""
        with mock.patch.object(imd.pagecache, "store") as store:
            self._import(self.QUOTE)
        store.assert_called_once()
        args = store.call_args.args
        self.assertEqual(args[0], self.URL)
        self.assertIn(self.QUOTE, args[1])

    def test_dry_run_does_not_seed_pagecache(self):
        with mock.patch.object(imd.pagecache, "store") as store:
            self._import(self.QUOTE, dry_run=True)
        store.assert_not_called()


class ImportSnapshotEmptyHtmlTests(ManualDumpPathIsolationMixin, unittest.TestCase):
    """Regression: an HTML save whose extracted text is empty used to hit a
    NameError ('url' referenced before assignment) inside its own skip
    message, instead of skipping cleanly."""

    def test_empty_html_snapshot_skips_cleanly(self):
        os.makedirs(md.SNAPSHOTS_DIR, exist_ok=True)
        path = os.path.join(md.SNAPSHOTS_DIR, "blank.html")
        with open(path, "w") as f:
            f.write("<html><body></body></html>")
        ok = imd.import_snapshot(
            path, {}, {"https://example.org/x": [("q", "post [^q]", "footnote")]},
            {"blank.html": "https://example.org/x"}, {})
        self.assertFalse(ok)
        self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
