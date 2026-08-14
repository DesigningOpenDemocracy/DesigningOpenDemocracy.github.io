#!/usr/bin/env python3
"""Regression tests for util/report_tracking_issue.py.

Offline: build_issue_body/is_actionable are pure and tested directly;
sync_issue's GitHub API calls are exercised against a mocked
requests.Session so no network call is ever made. Run with:

    python -m unittest discover tests
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import report_tracking_issue as rti  # noqa: E402


class LoadReportTests(unittest.TestCase):

    def test_none_path_returns_none(self):
        self.assertIsNone(rti.load_report(None))

    def test_missing_file_returns_none(self):
        self.assertIsNone(rti.load_report("/nonexistent/path/report.json"))

    def test_valid_json_round_trips(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"counts": {"bad": 1}}, f)
            path = f.name
        self.addCleanup(os.unlink, path)
        self.assertEqual(rti.load_report(path), {"counts": {"bad": 1}})

    def test_corrupt_json_returns_none(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not valid json")
            path = f.name
        self.addCleanup(os.unlink, path)
        self.assertIsNone(rti.load_report(path))


class IsActionableTests(unittest.TestCase):

    def test_all_empty_is_not_actionable(self):
        self.assertFalse(rti.is_actionable({}, {}))

    def test_mismatches_are_actionable(self):
        self.assertTrue(rti.is_actionable({"mismatches": [{"source": "x"}]}, {}))

    def test_ambiguous_are_actionable(self):
        self.assertTrue(rti.is_actionable({"ambiguous": [{"source": "x"}]}, {}))

    def test_fetch_errors_are_actionable(self):
        self.assertTrue(rti.is_actionable({"fetch_errors": [{"source": "x"}]}, {}))

    def test_dead_urls_are_actionable(self):
        self.assertTrue(rti.is_actionable({}, {"dead": [{"org": "x"}]}))

    def test_errored_urls_are_actionable(self):
        self.assertTrue(rti.is_actionable({}, {"errored": [{"org": "x"}]}))

    def test_blocked_and_redirected_alone_are_not_actionable(self):
        # Informational-only categories — a bot-block false positive or a
        # citation that redirected shouldn't by itself keep the tracking
        # issue open.
        self.assertFalse(rti.is_actionable({}, {"blocked": [{"org": "x"}],
                                                  "redirected": [{"org": "y"}]}))

    def test_missing_report_is_always_actionable_even_if_empty(self):
        # A crashed check step must never look identical to "all clear".
        self.assertTrue(rti.is_actionable({}, {}, fragments_missing=True))
        self.assertTrue(rti.is_actionable({}, {}, urls_missing=True))


class BuildIssueBodyTests(unittest.TestCase):

    def test_all_clean_says_nothing_to_do(self):
        body = rti.build_issue_body({}, {}, "2026-08-21")
        self.assertIn("Nothing to do", body)
        self.assertNotIn("Needs attention", body)
        self.assertIn(rti.MARKER, body)
        self.assertIn("2026-08-21", body)

    def test_mismatches_render_under_needs_attention_with_count(self):
        fragments = {"mismatches": [
            {"source": "g0v [2020-01-01] Founded", "url": "https://g0v.tw", "evidence": "founding text"},
        ]}
        body = rti.build_issue_body(fragments, {}, "2026-08-21")
        self.assertIn("## Needs attention", body)
        self.assertIn("Quote mismatches (1)", body)
        self.assertIn("g0v [2020-01-01] Founded", body)
        self.assertIn("founding text", body)
        self.assertNotIn("Nothing to do", body)

    def test_dead_urls_render_with_status(self):
        urls = {"dead": [
            {"org": "example-org", "date": "2020-01-01", "event": "Launch",
             "url": "https://example.org/gone", "status": 404},
        ]}
        body = rti.build_issue_body({}, urls, "2026-08-21")
        self.assertIn("Dead citation URLs (1)", body)
        self.assertIn("404", body)

    def test_blocked_and_redirected_render_under_informational_only(self):
        urls = {
            "blocked": [{"org": "x", "date": "2020-01-01", "event": "E",
                         "url": "https://x.org", "status": 403}],
            "redirected": [{"org": "y", "date": "2020-01-01", "event": "F",
                            "url": "https://y.org/old", "final_url": "https://y.org/new"}],
        }
        body = rti.build_issue_body({}, urls, "2026-08-21")
        self.assertIn("## Informational (not gating this issue's open/closed state)", body)
        self.assertNotIn("## Needs attention", body)
        # "Nothing to do" only applies when there's truly nothing anywhere
        self.assertNotIn("Nothing to do", body)

    def test_missing_report_renders_warning(self):
        body = rti.build_issue_body({}, {}, "2026-08-21", fragments_missing=True)
        self.assertIn("check_fragments.py", body)
        self.assertIn("may have failed", body)
        self.assertNotIn("Nothing to do", body)

    def test_large_section_is_capped_with_a_more_note(self):
        # Regression / robustness: a transient outage could flag hundreds
        # of fetch errors in one run. Uncapped, the issue body could blow
        # past GitHub's ~65KB limit and the PATCH/POST itself would fail
        # — exactly the week this tracking issue matters most. The
        # section must cap the rendered list while still reporting the
        # true total count in the header.
        fragments = {"mismatches": [
            {"source": f"org-{i} [2020-01-01] Event", "url": f"https://example.org/{i}",
             "evidence": "some evidence text"}
            for i in range(40)
        ]}
        body = rti.build_issue_body(fragments, {}, "2026-08-21")
        self.assertIn("Quote mismatches (40)", body)
        self.assertIn("and 15 more", body)
        self.assertLess(len(body), 20_000)  # nowhere near GitHub's ~65KB cap

    def test_ambiguous_and_fetch_errors_have_their_own_sections(self):
        fragments = {
            "ambiguous": [{"source": "a [2020-01-01] X", "url": "https://a.org", "evidence": "dup text"}],
            "fetch_errors": [{"source": "b [2020-01-01] Y", "url": "https://b.org", "error": "HTTP_500"}],
        }
        body = rti.build_issue_body(fragments, {}, "2026-08-21")
        self.assertIn("Ambiguous quotes", body)
        self.assertIn("Fetch errors (1)", body)
        self.assertIn("HTTP_500", body)


class SyncIssueTests(unittest.TestCase):

    def _session(self, existing_issues):
        session = MagicMock()
        get_resp = MagicMock()
        get_resp.json.return_value = existing_issues
        get_resp.raise_for_status.return_value = None
        session.get.return_value = get_resp

        patch_resp = MagicMock()
        patch_resp.raise_for_status.return_value = None
        session.patch.return_value = patch_resp

        post_resp = MagicMock()
        post_resp.raise_for_status.return_value = None
        session.post.return_value = post_resp
        return session

    def test_creates_when_actionable_and_no_existing_issue(self):
        session = self._session([])
        result = rti.sync_issue(session, "https://api.github.com/repos/o/r", "body text", True)
        self.assertEqual(result, "created")
        session.post.assert_called_once()
        self.assertEqual(session.post.call_args.kwargs["json"]["title"], rti.TITLE)
        session.patch.assert_not_called()

    def test_updates_existing_open_issue_when_actionable(self):
        existing = [{"title": rti.TITLE, "number": 42, "state": "open"}]
        session = self._session(existing)
        result = rti.sync_issue(session, "https://api.github.com/repos/o/r", "new body", True)
        self.assertEqual(result, "updated")
        session.patch.assert_called_once()
        args, kwargs = session.patch.call_args
        self.assertIn("/issues/42", args[0])
        self.assertEqual(kwargs["json"], {"body": "new body"})
        session.post.assert_not_called()

    def test_reopens_closed_issue_when_actionable_again(self):
        existing = [{"title": rti.TITLE, "number": 42, "state": "closed"}]
        session = self._session(existing)
        result = rti.sync_issue(session, "https://api.github.com/repos/o/r", "new body", True)
        self.assertEqual(result, "reopened")
        session.patch.assert_called_once()
        self.assertEqual(session.patch.call_args.kwargs["json"],
                         {"state": "open", "body": "new body"})

    def test_closes_open_issue_when_no_longer_actionable(self):
        existing = [{"title": rti.TITLE, "number": 42, "state": "open"}]
        session = self._session(existing)
        result = rti.sync_issue(session, "https://api.github.com/repos/o/r", "clean body", False)
        self.assertEqual(result, "closed")
        session.patch.assert_called_once()
        self.assertEqual(session.patch.call_args.kwargs["json"],
                         {"state": "closed", "body": "clean body"})

    def test_noop_when_not_actionable_and_no_existing_issue(self):
        # Must never create an issue just to immediately have nothing to
        # say in it.
        session = self._session([])
        result = rti.sync_issue(session, "https://api.github.com/repos/o/r", "clean body", False)
        self.assertEqual(result, "noop-clean")
        session.post.assert_not_called()
        session.patch.assert_not_called()

    def test_noop_when_not_actionable_and_issue_already_closed(self):
        # Zero write calls on a clean week where the issue is already
        # closed — the whole point of the "don't annoy GitHub" design.
        existing = [{"title": rti.TITLE, "number": 42, "state": "closed"}]
        session = self._session(existing)
        result = rti.sync_issue(session, "https://api.github.com/repos/o/r", "clean body", False)
        self.assertEqual(result, "noop-clean")
        session.post.assert_not_called()
        session.patch.assert_not_called()

    def test_finds_issue_by_exact_title_ignoring_pull_requests(self):
        existing = [
            {"title": "Some other issue", "number": 1, "state": "open"},
            {"title": rti.TITLE, "number": 2, "state": "open", "pull_request": {}},
            {"title": rti.TITLE, "number": 3, "state": "open"},
        ]
        session = self._session(existing)
        found = rti.find_existing_issue(session, "https://api.github.com/repos/o/r")
        self.assertEqual(found["number"], 3)

    def test_single_get_call_per_sync(self):
        session = self._session([])
        rti.sync_issue(session, "https://api.github.com/repos/o/r", "body", True)
        session.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
