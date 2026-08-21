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
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import manual_dump as md  # noqa: E402


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
        imported_dir = os.path.join(snapshots_dir, "imported")
        for name, value in [("DUMP_DIR", dump_dir), ("REQUESTS_PATH", requests_path),
                            ("SNAPSHOTS_DIR", snapshots_dir), ("IMPORTED_DIR", imported_dir)]:
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
    """Firefox/Chrome/IE-Edge all stamp this comment as the first line of
    a page saved via 'Save Page As' (either HTML-only or complete)."""

    def test_extracts_the_url(self):
        html_src = "<!-- saved from url=(0034)https://example.org/some/page -->\n<html></html>"
        self.assertEqual(md.parse_saved_from_url(html_src), "https://example.org/some/page")

    def test_returns_none_without_the_comment(self):
        self.assertIsNone(md.parse_saved_from_url("<html><body>hello</body></html>"))

    def test_only_scans_the_first_2kb(self):
        padding = "x" * 3000
        html_src = "<!-- padding: " + padding + " -->\n<!-- saved from url=(0022)https://example.org/x -->"
        self.assertIsNone(md.parse_saved_from_url(html_src))


if __name__ == "__main__":
    unittest.main()
