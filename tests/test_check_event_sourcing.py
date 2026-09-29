#!/usr/bin/env python3
"""Tests for util/check_event_sourcing.py's thin-history coverage report.

The thin-history line is informational (never affects the exit code): active
orgs with THIN_HISTORY_MAX_EVENTS or fewer events have history timelines too
sparse to tell their story, and nothing else in the toolchain surfaces that
gap — per-event verification (check_fragments.py) can only check the events
that already exist. These tests pin down which orgs get flagged: active with
≤1 event yes; active with 2+ no; inactive with ≤1 no; zero-event orgs stay on
the pre-existing "no events" line instead.

Offline — fixture org pages are written to a tempdir and ORGS_DIR is
monkeypatched, so the real docs/ tree is never touched. Run with:

    python -m unittest discover tests
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import check_event_sourcing as ces  # noqa: E402


ORG_TEMPLATE = """---
title: {title}
type: ngo
status: {status}
country: France
website: https://example.org
summary: A test org.
events:
{events_yaml}---

Body text here.
"""

ONE_EVENT = """- date: '2020-01-01'
  title: Something happened
  url: https://example.org/specific-page
  note: The site states the event happened.
"""

SECOND_EVENT = """- date: '2021-01-01'
  title: Something else happened
  url: https://example.org/another-page
  note: The site states the other event happened.
"""


def write_org(directory, slug, status="active", events_yaml=""):
    path = os.path.join(directory, slug + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ORG_TEMPLATE.format(
            title=slug.replace("-", " ").title(),
            status=status,
            events_yaml=events_yaml,
        ))
    return path


class ThinHistoryReportTests(unittest.TestCase):
    def run_main(self, orgs_dir):
        """Run check_event_sourcing.main() against a fixture dir, returning
        (stdout_text, exit_code)."""
        stdout = io.StringIO()
        with mock.patch.object(ces, "ORGS_DIR", orgs_dir), \
             mock.patch.object(sys, "argv", ["check_event_sourcing.py"]), \
             contextlib.redirect_stdout(stdout):
            try:
                ces.main()
                code = 0
            except SystemExit as e:
                code = e.code or 0
        return stdout.getvalue(), code

    def test_active_org_with_one_event_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_org(tmp, "thin-org", status="active", events_yaml=ONE_EVENT)
            out, code = self.run_main(tmp)
        self.assertIn("thin history, info only): 1", out)
        self.assertEqual(code, 0)

    def test_active_org_with_two_events_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_org(tmp, "rich-org", status="active",
                      events_yaml=ONE_EVENT + SECOND_EVENT)
            out, code = self.run_main(tmp)
        self.assertNotIn("thin history", out)
        self.assertEqual(code, 0)

    def test_inactive_org_with_one_event_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_org(tmp, "dormant-org", status="inactive",
                      events_yaml=ONE_EVENT)
            out, code = self.run_main(tmp)
        self.assertNotIn("thin history", out)
        self.assertEqual(code, 0)

    def test_zero_event_org_stays_on_no_events_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_org(tmp, "empty-org", status="active", events_yaml="")
            out, code = self.run_main(tmp)
        self.assertIn("Orgs with no events (info only): 1", out)
        self.assertNotIn("thin history", out)
        self.assertEqual(code, 0)

    def test_counts_across_orgs(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_org(tmp, "thin-a", status="active", events_yaml=ONE_EVENT)
            write_org(tmp, "thin-b", status="active", events_yaml=ONE_EVENT)
            write_org(tmp, "rich-org", status="active",
                      events_yaml=ONE_EVENT + SECOND_EVENT)
            out, _ = self.run_main(tmp)
        self.assertIn("thin history, info only): 2", out)


def announce_event(value, notable="true"):
    return f"""- date: '2030-01-01'
  title: A flagship summit
  url: https://example.org/summit
  note: The site announces the summit.
  notable: {notable}
  announce_days: {value}
"""


class AnnounceDaysTests(unittest.TestCase):
    """announce_days (hooks/news_export.py) is validated here, because the
    hook falls back to the default notice without a word on a bad value."""

    run_main = ThinHistoryReportTests.run_main

    def check(self, events_yaml):
        with tempfile.TemporaryDirectory() as tmp:
            write_org(tmp, "org", events_yaml=events_yaml)
            return self.run_main(tmp)

    def test_valid_value_on_a_major_event_passes(self):
        out, code = self.check(announce_event(90))
        self.assertEqual(code, 0)
        self.assertNotIn("ANNOUNCE", out)

    def test_invalid_values_fail_the_build(self):
        for bad in ("0", "400", "'90'", "true", "2.5"):
            with self.subTest(value=bad):
                out, code = self.check(announce_event(bad))
                self.assertEqual(code, 1)
                self.assertIn("BAD ANNOUNCE", out)

    def test_on_a_notable_event_it_is_flagged_as_ignored_not_failed(self):
        out, code = self.check(announce_event(90, notable="medium"))
        self.assertEqual(code, 0)
        self.assertIn("ANNOUNCE IGNORED", out)


if __name__ == "__main__":
    unittest.main()
