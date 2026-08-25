"""Tests for util/merge_citation_state.py — the resolver the probe cron uses
when its citation-state.json commit collides with a moved `main`.

The failure this guards against is not hypothetical: 9 of the first 10
scheduled runs of .github/workflows/heartbeat-probes.yml died on exactly this
conflict and threw away hours of verification work, which is why no citation
in the repo had ever recorded an archive_url. The one rule that matters is
that neither side's evidence may be dropped — `-X ours`, `-X theirs` and
`--force` are all wrong answers, so these tests mostly pin down "nothing is
lost" rather than any particular ordering.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import merge_citation_state as mcs  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO_ROOT, "util", "merge_citation_state.py")


def ev(quote, verified=True, checked=None, **extra):
    item = {"id": "id-" + quote.replace(" ", "-"), "quote": quote,
            "verified": verified}
    if checked:
        item["checked"] = checked
    item.update(extra)
    return item


class MergeEvidenceTests(unittest.TestCase):
    def _merge(self, ours, theirs):
        merged, _ = mcs.merge_states(ours, theirs, warn=lambda m: None)
        return merged

    def test_union_of_urls_from_both_sides(self):
        merged = self._merge({"https://a/": {"evidence": [ev("a")]}},
                             {"https://b/": {"evidence": [ev("b")]}})
        self.assertEqual(set(merged), {"https://a/", "https://b/"})

    def test_union_of_quotes_on_a_shared_url(self):
        # The exact shape of the cron conflict: both sides verified different
        # quotes on the same page during overlapping runs.
        merged = self._merge(
            {"https://x/": {"evidence": [ev("first")]}},
            {"https://x/": {"evidence": [ev("second")]}})
        quotes = {e["quote"] for e in merged["https://x/"]["evidence"]}
        self.assertEqual(quotes, {"first", "second"})

    def test_newer_verdict_wins_a_collision(self):
        merged = self._merge(
            {"https://x/": {"evidence": [ev("q", verified=False, checked="2026-01-01")]}},
            {"https://x/": {"evidence": [ev("q", verified=True, checked="2026-06-01")]}})
        item = merged["https://x/"]["evidence"][0]
        self.assertTrue(item["verified"])
        self.assertEqual(item["checked"], "2026-06-01")

    def test_dated_item_beats_undated_one(self):
        # Undated entries predate per-quote stamping, so they are strictly older.
        merged = self._merge(
            {"https://x/": {"evidence": [ev("q", verified=False)]}},
            {"https://x/": {"evidence": [ev("q", verified=True, checked="2026-06-01")]}})
        self.assertTrue(merged["https://x/"]["evidence"][0]["verified"])

    def test_nothing_is_ever_dropped(self):
        ours = {"https://x/": {"evidence": [ev("a"), ev("b")]},
                "https://y/": {"evidence": [ev("c")]}}
        theirs = {"https://x/": {"evidence": [ev("b"), ev("d")]},
                  "https://z/": {"evidence": [ev("e")]}}
        merged = self._merge(ours, theirs)
        all_quotes = {e["quote"] for v in merged.values() for e in v["evidence"]}
        self.assertEqual(all_quotes, {"a", "b", "c", "d", "e"})


class MergeUrlFieldTests(unittest.TestCase):
    def _merge(self, ours, theirs, warn=None):
        merged, _ = mcs.merge_states(ours, theirs, warn=warn or (lambda m: None))
        return merged["https://x/"]

    def test_fetch_state_comes_from_the_newer_side_as_a_unit(self):
        # An etag belongs to the body whose hash sits next to it; mixing them
        # would yield a validator that doesn't match its own document.
        out = self._merge(
            {"https://x/": {"checked": "2026-01-01", "etag": "old",
                            "document_sha256": "aaa"}},
            {"https://x/": {"checked": "2026-06-01", "etag": "new",
                            "document_sha256": "bbb"}})
        self.assertEqual((out["etag"], out["document_sha256"]), ("new", "bbb"))

    def test_archive_url_survives_from_the_older_side(self):
        # The regression that motivated the whole fix: an archive snapshot
        # recorded by one run must not vanish because the other fetched later.
        out = self._merge(
            {"https://x/": {"checked": "2026-01-01",
                            "archive_url": "https://web.archive.org/snap"}},
            {"https://x/": {"checked": "2026-06-01"}})
        self.assertEqual(out["archive_url"], "https://web.archive.org/snap")

    def test_url_status_survives_from_the_older_side(self):
        out = self._merge(
            {"https://x/": {"checked": "2026-01-01", "url_status": "dead"}},
            {"https://x/": {"checked": "2026-06-01"}})
        self.assertEqual(out["url_status"], "dead")

    def test_cleared_blocked_flag_on_the_newer_side_wins(self):
        # A successful fetch clears `blocked`; the newer side is the truth.
        out = self._merge(
            {"https://x/": {"checked": "2026-01-01", "blocked": "HTTP_403",
                            "blocked_since": "2026-01-01"}},
            {"https://x/": {"checked": "2026-06-01"}})
        self.assertNotIn("blocked", out)

    def test_conflicting_url_status_is_reported_not_silently_dropped(self):
        seen = []
        self._merge(
            {"https://x/": {"checked": "2026-01-01", "url_status": "dead"}},
            {"https://x/": {"checked": "2026-06-01", "url_status": "unfit"}},
            warn=seen.append)
        self.assertTrue(any("url_status" in m for m in seen))


class MergeCliTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def _write(self, name, obj):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        return path

    def test_cli_writes_merged_output(self):
        a = self._write("a.json", {"https://x/": {"evidence": [ev("one")]}})
        b = self._write("b.json", {"https://x/": {"evidence": [ev("two")]}})
        out = os.path.join(self.tmpdir, "merged.json")
        r = subprocess.run([sys.executable, SCRIPT, a, b, "--out", out],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as f:
            merged = json.load(f)
        self.assertEqual({e["quote"] for e in merged["https://x/"]["evidence"]},
                         {"one", "two"})

    def test_check_mode_writes_nothing(self):
        a = self._write("a.json", {"https://x/": {"evidence": [ev("one")]}})
        b = self._write("b.json", {"https://x/": {"evidence": [ev("two")]}})
        out = os.path.join(self.tmpdir, "nope.json")
        r = subprocess.run([sys.executable, SCRIPT, a, b, "--check", "--out", out],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(out))


class RebaseConflictEndToEndTests(unittest.TestCase):
    """Reproduce the actual cron failure in a throwaway git repo and prove the
    resolution path recovers both sides' work."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.repo = os.path.join(self.tmpdir, "repo")
        os.makedirs(os.path.join(self.repo, "docs", "data"))
        self.state = os.path.join("docs", "data", "citation-state.json")
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "t")

    def _git(self, *args, check=True):
        r = subprocess.run(("git",) + args, cwd=self.repo,
                           capture_output=True, text=True)
        if check and r.returncode != 0:
            self.fail("git %s failed: %s%s" % (" ".join(args), r.stdout, r.stderr))
        return r

    def _write_state(self, obj):
        with open(os.path.join(self.repo, self.state), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, sort_keys=True)

    def _read_state(self):
        with open(os.path.join(self.repo, self.state), encoding="utf-8") as f:
            return json.load(f)

    def test_conflicting_state_commits_resolve_without_losing_evidence(self):
        # Common ancestor.
        self._write_state({"https://x/": {"checked": "2026-01-01",
                                          "evidence": [ev("base", checked="2026-01-01")]}})
        self._git("add", "-A"); self._git("commit", "-qm", "base")

        # main moves: someone records a quote by hand.
        self._write_state({"https://x/": {"checked": "2026-02-01",
                                          "evidence": [ev("base", checked="2026-01-01"),
                                                       ev("from-main", checked="2026-02-01")]}})
        self._git("add", "-A"); self._git("commit", "-qm", "main edit")
        self._git("branch", "-f", "upstream")

        # The cron's own commit, made from the older base — the real scenario.
        self._git("checkout", "-q", "-b", "cron", "HEAD~1")
        self._write_state({"https://x/": {"checked": "2026-03-01",
                                          "archive_url": "https://web.archive.org/snap",
                                          "evidence": [ev("base", checked="2026-01-01"),
                                                       ev("from-cron", checked="2026-03-01")]}})
        self._git("add", "-A"); self._git("commit", "-qm", "cron probe")

        # Rebase must conflict — that's the bug being reproduced.
        r = self._git("rebase", "upstream", check=False)
        self.assertNotEqual(r.returncode, 0, "expected the rebase to conflict")
        conflicts = self._git("diff", "--name-only", "--diff-filter=U").stdout.split()
        self.assertEqual(conflicts, [self.state])

        # The workflow's resolution path.
        for stage, name in ((":2:", "ours"), (":3:", "theirs")):
            blob = self._git("show", stage + self.state).stdout
            with open(os.path.join(self.tmpdir, name + ".json"), "w",
                      encoding="utf-8") as f:
                f.write(blob)
        r = subprocess.run(
            [sys.executable, SCRIPT,
             os.path.join(self.tmpdir, "ours.json"),
             os.path.join(self.tmpdir, "theirs.json"),
             "--out", os.path.join(self.repo, self.state)],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self._git("add", self.state)
        env = dict(os.environ, GIT_EDITOR="true")
        r = subprocess.run(("git", "rebase", "--continue"), cwd=self.repo,
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        # Both sides' work survives, including the archive_url that the old
        # rebase-and-die path threw away every week.
        merged = self._read_state()["https://x/"]
        self.assertEqual({e["quote"] for e in merged["evidence"]},
                         {"base", "from-main", "from-cron"})
        self.assertEqual(merged["archive_url"], "https://web.archive.org/snap")
        self.assertEqual(merged["checked"], "2026-03-01")


if __name__ == "__main__":
    unittest.main()
