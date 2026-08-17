#!/usr/bin/env python3
"""Regression tests for the raw-text frontmatter surgery in
util/check_rss.py's update_activity_source(), util/scrape_news.py's
write_checked_only(), and util/review_orgs.py's write_manual_activity().

These functions edit org frontmatter by splicing lines rather than doing a
full YAML re-serialization (see util/frontmatter_io.py's module docstring
for why: it avoids reformatting parts of the file the write didn't touch).
That approach is inherently easy to get subtly wrong, and it was: the
2026-08-17 automated activity probe (commit 934ccd2) landed duplicate
activity.sitemap and activity.scrape.hint keys on live org pages — caught
only because it broke util/reorder_frontmatter.py --check in CI on an
unrelated PR. Auditing the other scripts sharing this pattern
(util/frontmatter_io.py's docstring names check_rss.py, scrape_news.py,
record_dod.py, review_orgs.py) turned up the same silent-drop bug in
review_orgs.py's write_manual_activity() — a brand-new activity.manual
entry (the very first manual review for an org) never got written
whenever activity: was followed by a top-level key such as last_checked:,
which is nearly always. record_dod.py's write_dod_activity() already used
a correctly-scoped `inserted` flag and needed no fix. These tests pin all
of it down so it can't silently recur.

Offline, no network calls. Run with:

    python -m unittest discover tests
"""

import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import check_rss  # noqa: E402
import review_orgs  # noqa: E402
import scrape_news  # noqa: E402


def count_keys(text, key):
    """Count occurrences of `key:` as its own YAML key line (any indent)."""
    return len(re.findall(rf"^\s*{re.escape(key)}\s*:", text, re.MULTILINE))


class UpdateActivitySourceTests(unittest.TestCase):
    """util/check_rss.py's update_activity_source()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        check_rss.TODAY = "2026-08-17"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, body):
        path = os.path.join(self.tmpdir, "org.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n" + body + "---\nBody text.\n")
        return path

    def test_replacing_existing_source_before_last_checked_does_not_duplicate(self):
        # Regression for designing-open-democracy.md: a source sub-block
        # (sitemap:) that is immediately followed by the frontmatter's next
        # top-level key (last_checked:) got its replacement lines inserted
        # twice, because in_this_source stayed True after the block was
        # already replaced, so the boundary check one line later fired a
        # second insert.
        path = self._write(
            "title: Designing Open Democracy\n"
            "activity:\n"
            "  manual:\n"
            "    date: 2026-01-01\n"
            "    note: Manual note\n"
            "  sitemap:\n"
            "    date: 2026-08-01\n"
            '    note: "Page last modified (from sitemap)"\n'
            "    url: https://example.org/sitemap.xml\n"
            "    checked: 2026-08-01\n"
            "last_checked: '2026-08-09'\n"
        )
        ok = check_rss.update_activity_source(
            path, "2026-08-17", "Page last modified (from sitemap)",
            "https://example.org/sitemap.xml", method="sitemap",
        )
        self.assertTrue(ok)
        out = open(path, encoding="utf-8").read()
        self.assertEqual(count_keys(out, "sitemap"), 1)
        self.assertEqual(out.count("2026-08-17"), 2)  # date: and checked:
        self.assertTrue(out.rstrip("\n").endswith("last_checked: '2026-08-09'\n---\nBody text."))

    def test_replacing_existing_source_at_end_of_activity_block(self):
        # The same replacement, but activity: is the last frontmatter key
        # (no boundary line follows it) — the other code path through the
        # same function; must not duplicate either.
        path = self._write(
            "title: Some Org\n"
            "activity:\n"
            "  sitemap:\n"
            "    date: 2026-08-01\n"
            '    note: "Page last modified (from sitemap)"\n'
            "    url: https://example.org/sitemap.xml\n"
            "    checked: 2026-08-01\n"
        )
        ok = check_rss.update_activity_source(
            path, "2026-08-17", "Page last modified (from sitemap)",
            "https://example.org/sitemap.xml", method="sitemap",
        )
        self.assertTrue(ok)
        out = open(path, encoding="utf-8").read()
        self.assertEqual(count_keys(out, "sitemap"), 1)

    def test_adding_new_source_before_last_checked(self):
        path = self._write(
            "title: Some Org\n"
            "activity:\n"
            "  manual:\n"
            "    date: 2026-01-01\n"
            "    note: Manual note\n"
            "last_checked: '2026-08-09'\n"
        )
        ok = check_rss.update_activity_source(
            path, "2026-08-17", "Page last modified (from sitemap)",
            "https://example.org/sitemap.xml", method="sitemap",
        )
        self.assertTrue(ok)
        out = open(path, encoding="utf-8").read()
        self.assertEqual(count_keys(out, "sitemap"), 1)
        self.assertEqual(count_keys(out, "manual"), 1)


class WriteCheckedOnlyTests(unittest.TestCase):
    """util/scrape_news.py's write_checked_only()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        scrape_news.TODAY = "2026-08-17"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, field_order):
        lines = {
            "note": "    note: News page found, no machine-readable date",
            "hint": "    hint: no_markup",
            "checked": "    checked: 2026-08-08",
        }
        body = (
            "title: g0v\n"
            "activity:\n"
            "  scrape:\n"
            + "\n".join(lines[k] for k in field_order) + "\n"
            "last_checked: '2026-05-30'\n"
        )
        path = os.path.join(self.tmpdir, "org.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n" + body + "---\nBody text.\n")
        return path

    def test_no_duplicate_hint_regardless_of_existing_field_order(self):
        # Regression for g0v.md: when the existing sub-block had checked:
        # before hint: (field order is not fixed — it depends on when each
        # field was first written), the checked: handler pre-emptively
        # inserted a new hint: line, and the hint: handler then blindly
        # re-emitted the old one on top of it instead of dropping it.
        import itertools
        for perm in itertools.permutations(["note", "hint", "checked"]):
            with self.subTest(order=perm):
                path = self._write(perm)
                ok = scrape_news.write_checked_only(path, "scrape", hint="no_markup")
                self.assertTrue(ok)
                out = open(path, encoding="utf-8").read()
                self.assertEqual(count_keys(out, "hint"), 1, out)
                self.assertEqual(count_keys(out, "checked"), 1, out)
                self.assertEqual(count_keys(out, "note"), 1, out)

    def test_adds_hint_and_checked_when_only_note_exists(self):
        path = self._write(["note"])
        ok = scrape_news.write_checked_only(path, "scrape", hint="no_markup")
        self.assertTrue(ok)
        out = open(path, encoding="utf-8").read()
        self.assertEqual(count_keys(out, "hint"), 1)
        self.assertEqual(count_keys(out, "checked"), 1)


class WriteManualActivityTests(unittest.TestCase):
    """util/review_orgs.py's write_manual_activity()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, body):
        path = os.path.join(self.tmpdir, "org.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n" + body + "---\nBody text.\n")
        return path

    def test_brand_new_source_before_last_checked_is_not_silently_dropped(self):
        # Regression: activity.manual had never appeared for this org, so
        # in_this_source was never set True, and the boundary-insert branch
        # was gated on `in_this_source and not inserted` — silently
        # skipping the write whenever activity: was followed by a
        # top-level key (last_checked: — the common case).
        path = self._write(
            "title: Some Org\n"
            "activity:\n"
            "  rss:\n"
            "    date: 2026-01-01\n"
            "    note: some rss note\n"
            "    checked: 2026-01-01\n"
            "last_checked: '2026-08-09'\n"
        )
        ok = review_orgs.write_manual_activity(path, "2026-08-17", "First manual review")
        self.assertTrue(ok)
        out = open(path, encoding="utf-8").read()
        self.assertEqual(count_keys(out, "manual"), 1, out)
        self.assertIn("First manual review", out)

    def test_brand_new_source_when_activity_is_last_key(self):
        path = self._write(
            "title: Some Org\n"
            "activity:\n"
            "  rss:\n"
            "    date: 2026-01-01\n"
            "    note: some rss note\n"
            "    checked: 2026-01-01\n"
        )
        ok = review_orgs.write_manual_activity(path, "2026-08-17", "First manual review")
        self.assertTrue(ok)
        out = open(path, encoding="utf-8").read()
        self.assertEqual(count_keys(out, "manual"), 1, out)

    def test_replacing_existing_source_before_last_checked_does_not_duplicate(self):
        path = self._write(
            "title: Some Org\n"
            "activity:\n"
            "  manual:\n"
            "    date: 2026-08-01\n"
            "    note: Old manual note\n"
            "    checked: 2026-08-01\n"
            "last_checked: '2026-08-09'\n"
        )
        ok = review_orgs.write_manual_activity(path, "2026-08-17", "New manual note")
        self.assertTrue(ok)
        out = open(path, encoding="utf-8").read()
        self.assertEqual(count_keys(out, "manual"), 1, out)
        self.assertIn("New manual note", out)
        self.assertNotIn("Old manual note", out)


if __name__ == "__main__":
    unittest.main()
