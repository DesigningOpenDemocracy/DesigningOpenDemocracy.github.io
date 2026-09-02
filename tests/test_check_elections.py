#!/usr/bin/env python3
"""Regression tests for util/check_elections.py and the election-loading
half of hooks/calendar_export.py — the curated polling days the site-wide
calendar carries alongside org events.

Offline, stdlib + pyyaml only (same bar as the rest of tests/). Run with:

    python -m unittest discover tests

The linter and the hook deliberately disagree about what a malformed entry
means: the hook SKIPS it so a typo can't take the whole site build down,
and the linter FAILS on it so the typo can't reach main unnoticed. Both
halves of that are pinned here — a bad entry that the hook silently drops
and the linter also lets through would vanish from the calendar with
nothing said, which is the failure this pairing exists to prevent.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta

import yaml

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(REPO_ROOT, "hooks"))

import calendar_export as ce  # noqa: E402

CHECKER = os.path.join(REPO_ROOT, "util", "check_elections.py")
ELECTIONS_FILE = os.path.join(REPO_ROOT, "docs", "data", "elections.yml")

FUTURE = (date.today() + timedelta(days=200)).isoformat()
PAST = (date.today() - timedelta(days=200)).isoformat()

VALID = {
    "date": FUTURE,
    "country": "AU",
    "jurisdiction": "Victoria",
    "level": "state",
    "title": "Victorian state election",
    "date_status": "fixed",
    "url": "https://example.org/vic",
    "quote": "A state general election is scheduled to be held.",
    "url_checked": date.today().isoformat(),
}


def write_elections(entries):
    """Write a throwaway elections file and return its path."""
    tmp = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8")
    yaml.safe_dump({"elections": entries}, tmp, sort_keys=False, allow_unicode=True)
    tmp.close()
    return tmp.name


def run_checker(entries):
    """Run check_elections.py over `entries`; return (exit_code, output)."""
    path = write_elections(entries)
    try:
        proc = subprocess.run(
            [sys.executable, CHECKER, "--file", path],
            capture_output=True, text=True,
        )
        return proc.returncode, proc.stdout + proc.stderr
    finally:
        os.unlink(path)


class CheckerAcceptsGoodDataTests(unittest.TestCase):

    def test_valid_entry_passes(self):
        code, out = run_checker([VALID])
        self.assertEqual(code, 0, out)

    def test_source_instead_of_url_passes(self):
        entry = {**VALID}
        del entry["url"]
        entry["source"] = "Victorian Electoral Commission election timetable, 2026"
        code, out = run_checker([entry])
        self.assertEqual(code, 0, out)

    def test_note_instead_of_quote_passes(self):
        entry = {**VALID}
        del entry["quote"]
        entry["note"] = "The commission's timetable states the polling day."
        code, out = run_checker([entry])
        self.assertEqual(code, 0, out)

    def test_the_repos_own_elections_file_passes(self):
        """The gate has to hold on the real data, not just on fixtures."""
        proc = subprocess.run(
            [sys.executable, CHECKER, "--file", ELECTIONS_FILE],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class CheckerRejectsBadDataTests(unittest.TestCase):

    def assert_fails_with(self, entry, marker):
        code, out = run_checker([entry])
        self.assertEqual(code, 1, out)
        self.assertIn(marker, out)

    def test_unsourced_entry_fails(self):
        entry = {**VALID}
        del entry["url"]
        self.assert_fails_with(entry, "NOT SOURCED")

    def test_entry_without_quote_or_note_fails(self):
        entry = {**VALID}
        del entry["quote"]
        self.assert_fails_with(entry, "NO PROOF")

    def test_unparseable_date_fails(self):
        self.assert_fails_with({**VALID, "date": "November 2026"}, "BAD DATE")

    def test_end_date_before_start_fails(self):
        entry = {**VALID, "end_date": PAST}
        self.assert_fails_with(entry, "BAD END DATE")

    def test_unknown_level_fails(self):
        self.assert_fails_with({**VALID, "level": "regional"}, "BAD LEVEL")

    def test_unknown_date_status_fails(self):
        self.assert_fails_with({**VALID, "date_status": "probably"}, "BAD DATE STATUS")

    def test_unknown_country_code_fails(self):
        """An ISO code the hook has no name for renders as the bare code with
        no flag, and names an unlabelled per-country .ics feed."""
        self.assert_fails_with({**VALID, "country": "XX"}, "BAD COUNTRY")

    def test_lowercase_country_code_fails(self):
        self.assert_fails_with({**VALID, "country": "au"}, "BAD COUNTRY")

    def test_typo_field_name_fails(self):
        """A misspelled key is silently dropped by every consumer, so the
        entry would quietly lose whatever it was meant to say."""
        entry = {**VALID}
        entry["date_stats"] = "fixed"
        self.assert_fails_with(entry, "UNKNOWN FIELD")

    def test_duplicate_entries_fail(self):
        code, out = run_checker([VALID, dict(VALID)])
        self.assertEqual(code, 1, out)
        self.assertIn("DUPLICATE", out)

    def test_missing_top_level_key_fails(self):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8")
        tmp.write("something_else: []\n")
        tmp.close()
        try:
            proc = subprocess.run([sys.executable, CHECKER, "--file", tmp.name],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("elections", proc.stdout + proc.stderr)
        finally:
            os.unlink(tmp.name)


class CheckerWarningsTests(unittest.TestCase):

    def test_past_election_warns_but_passes(self):
        """A held election is dropped by the calendar either way, so this is
        a reminder to replace it — not a build failure."""
        code, out = run_checker([{**VALID, "date": PAST}])
        self.assertEqual(code, 0, out)
        self.assertIn("PAST", out)

    def test_unfixed_date_without_a_note_warns(self):
        entry = {**VALID, "date_status": "expected"}
        code, out = run_checker([entry])
        self.assertEqual(code, 0, out)
        self.assertIn("NO DATE NOTE", out)

    def test_vague_source_warns(self):
        entry = {**VALID}
        del entry["url"]
        entry["source"] = "Wikipedia"
        code, out = run_checker([entry])
        self.assertEqual(code, 0, out)
        self.assertIn("VAGUE SOURCE", out)

    def test_stale_url_checked_warns(self):
        entry = {**VALID, "url_checked": (date.today() - timedelta(days=400)).isoformat()}
        code, out = run_checker([entry])
        self.assertEqual(code, 0, out)
        self.assertIn("STALE CHECK", out)


class HookVocabularyTests(unittest.TestCase):
    """The linter imports its vocabularies from the hook rather than keeping
    a second copy; these pin that the import path still resolves and that
    the two documented sets are what the renderer actually knows."""

    def test_checker_imports_the_hooks_vocabulary(self):
        spec = importlib.util.spec_from_file_location("check_elections", CHECKER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        hook = module._calendar_export()
        self.assertEqual(set(hook.ELECTION_LEVEL_LABELS), set(ce.ELECTION_LEVEL_LABELS))
        self.assertEqual(set(hook.ELECTION_DATE_STATUS_LABELS), set(ce.ELECTION_DATE_STATUS_LABELS))

    def test_every_level_has_a_label(self):
        for level, label in ce.ELECTION_LEVEL_LABELS.items():
            self.assertTrue(label, level)

    def test_only_a_fixed_date_renders_without_a_caveat(self):
        """Any status other than `fixed` must say so on the card and in the
        .ics SUMMARY — an unqualified date reads as a settled appointment,
        which for a "due by" deadline it flatly isn't."""
        for status, label in ce.ELECTION_DATE_STATUS_LABELS.items():
            if status == "fixed":
                self.assertEqual(label, "")
            else:
                self.assertTrue(label, status)


class HookLoaderTests(unittest.TestCase):
    """hooks/calendar_export.py's _load_elections(): what actually reaches
    the calendar. Each test points the hook at a throwaway file rather than
    the repo's real one, so these don't move when the curated data does."""

    def setUp(self):
        self._real_file = ce.ELECTIONS_FILE
        self.today = date.today()

    def tearDown(self):
        ce.ELECTIONS_FILE = self._real_file

    def load(self, entries, today=None):
        path = write_elections(entries)
        self.addCleanup(os.unlink, path)
        ce.ELECTIONS_FILE = path
        return ce._load_elections(today or self.today)

    def test_future_election_is_loaded_as_an_orgless_event(self):
        loaded = self.load([VALID])
        self.assertEqual(len(loaded), 1)
        e = loaded[0]
        self.assertEqual(e["source"], "election")
        self.assertEqual(e["type"], "election")
        self.assertIsNone(e["org_slug"])
        self.assertFalse(e["notable"])
        self.assertEqual(e["org_title"], "Victoria")

    def test_past_election_is_dropped(self):
        self.assertEqual(self.load([{**VALID, "date": PAST}]), [])

    def test_election_on_today_is_kept(self):
        """Polling day itself is the single most relevant day to show it."""
        loaded = self.load([{**VALID, "date": self.today.isoformat()}])
        self.assertEqual(len(loaded), 1)

    def test_national_election_falls_back_to_the_country_name(self):
        entry = {**VALID, "level": "national", "title": "Federal election"}
        del entry["jurisdiction"]
        self.assertEqual(self.load([entry])[0]["org_title"], "Australia")

    def test_malformed_entries_are_skipped_not_raised_on(self):
        """A typo must not take the whole site build down — check_elections.py
        is the gate that fails on it, offline and before the push."""
        bad = [
            {**VALID, "date": "sometime in November"},
            {**VALID, "level": "regional"},
            "not even a mapping",
        ]
        self.assertEqual(self.load(bad), [])

    def test_missing_file_yields_nothing(self):
        ce.ELECTIONS_FILE = os.path.join(tempfile.gettempdir(), "no-such-elections-file.yml")
        self.assertEqual(ce._load_elections(self.today), [])

    def test_date_status_carries_its_rendering_label(self):
        entry = {**VALID, "date_status": "deadline", "date_note": "Last lawful day."}
        e = self.load([entry])[0]
        self.assertEqual(e["date_status"], "deadline")
        self.assertEqual(e["date_status_label"], ce.ELECTION_DATE_STATUS_LABELS["deadline"])
        self.assertEqual(e["date_note"], "Last lawful day.")

    def test_fixed_date_carries_no_caveat_label(self):
        self.assertEqual(self.load([VALID])[0]["date_status_label"], "")


class ElectionIcsTests(unittest.TestCase):
    """The .ics is what a subscriber actually sees, with none of the page's
    badges around it — so the qualifiers have to survive into SUMMARY."""

    def write(self, events):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".ics", delete=False, encoding="utf-8")
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        ce._write_ics(events, tmp.name)
        with open(tmp.name, encoding="utf-8") as f:
            return f.read()

    def election(self, **overrides):
        path = write_elections([{**VALID, **overrides}])
        self.addCleanup(os.unlink, path)
        real, ce.ELECTIONS_FILE = ce.ELECTIONS_FILE, path
        try:
            return ce._load_elections(date.today())[0]
        finally:
            ce.ELECTIONS_FILE = real

    def test_summary_names_the_country_once(self):
        ics = self.write([self.election()])
        self.assertIn("SUMMARY:Victorian state election — Australia", ics)

    def test_summary_does_not_repeat_a_country_already_in_the_title(self):
        e = self.election(title="New Zealand general election", country="NZ", jurisdiction=None)
        self.assertIn("SUMMARY:New Zealand general election", self.write([e]))
        self.assertNotIn("— New Zealand", self.write([e]))

    def test_country_matching_is_whole_word(self):
        """"Australia" is inside "Australian": a substring test would drop the
        country from this title while keeping it on its Victorian sibling."""
        e = self.election(title="South Australian state election", jurisdiction="South Australia")
        self.assertIn("SUMMARY:South Australian state election — Australia", self.write([e]))

    def test_unfixed_date_says_so_in_the_summary(self):
        e = self.election(date_status="deadline", date_note="Last lawful day.")
        self.assertIn("(due by this date)", self.write([e]))

    def test_categories_groups_by_country_not_jurisdiction(self):
        self.assertIn("CATEGORIES:Australia", self.write([self.election()]))

    def test_org_event_summary_is_unchanged(self):
        """Elections must not disturb the existing org-event .ics shape —
        a changed UID or SUMMARY lands in every subscriber's calendar."""
        ics = self.write([{
            "date": date(2027, 3, 1), "title": "Annual forum", "org_slug": "someorg",
            "org_title": "Some Org", "url": "https://example.org",
        }])
        self.assertIn("SUMMARY:Some Org: Annual forum", ics)
        self.assertIn("CATEGORIES:Some Org", ics)


class CheckFragmentsCollectionTests(unittest.TestCase):
    """check_fragments.py picks election quotes up as a fourth evidence
    source. The path has to resolve from DOCS_DIR at call time: pinning it
    at import made every other test in tests/test_check_fragments.py fetch
    the repo's real election list into its temp tree."""

    def setUp(self):
        sys.path.insert(0, os.path.join(REPO_ROOT, "util"))
        import check_fragments
        self.cf = check_fragments
        self._docs = check_fragments.DOCS_DIR
        self.addCleanup(setattr, check_fragments, "DOCS_DIR", self._docs)

    def test_elections_are_read_from_the_current_docs_dir(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: None)
        os.makedirs(os.path.join(tmp, "data"))
        with open(os.path.join(tmp, "data", "elections.yml"), "w", encoding="utf-8") as f:
            yaml.safe_dump({"elections": [VALID]}, f, sort_keys=False)
        self.cf.DOCS_DIR = tmp
        items = self.cf.collect_election_evidence()
        self.assertEqual(len(items), 1)
        url, quote, label, kind, path = items[0]
        self.assertEqual(kind, "election")
        self.assertEqual(url, VALID["url"])
        self.assertEqual(quote, VALID["quote"])
        self.assertTrue(path.startswith(tmp))

    def test_no_elections_file_yields_nothing(self):
        self.cf.DOCS_DIR = tempfile.mkdtemp()
        self.assertEqual(self.cf.collect_election_evidence(), [])

    def test_entry_without_a_quote_is_not_collected(self):
        """An entry sourced with note: only has nothing to verify
        mechanically — it passes check_elections.py and is skipped here."""
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "data"))
        entry = {**VALID}
        del entry["quote"]
        entry["note"] = "The commission's timetable states the polling day."
        with open(os.path.join(tmp, "data", "elections.yml"), "w", encoding="utf-8") as f:
            yaml.safe_dump({"elections": [entry]}, f, sort_keys=False)
        self.cf.DOCS_DIR = tmp
        self.assertEqual(self.cf.collect_election_evidence(), [])


if __name__ == "__main__":
    unittest.main()
