#!/usr/bin/env python3
"""Regression tests for hooks/citation_export.py's on_pre_build(): the
CSL-JSON citations.json export, and specifically that archive/
archive_location/url-status are a fresh *projection* of
docs/data/citation-evidence.json on every build, never carried
forward from citations.json's own previous output.

That's the fix for the drift risk recorded in internal-heartbeat/
2026-08-22-citation-archival-design-decisions.md: before this, two
independent, uncoordinated things could each write archive data for the
same URL (check_fragments.py's evidence cache, and a separate
citations_tool.py --archive path writing straight into citations.json).
Making citations.json a read-only projection of the evidence cache for
these three fields removes that risk by construction — this file tests
that the projection actually happens, and that stale data from a prior
citations.json build never survives once the evidence cache disagrees.

Offline — no network, no real repo files touched (DOCS_DIR/OUT_PATH and
the archive cache path are all monkeypatched to a tempdir). Run with:

    python -m unittest discover tests
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import citation_export as ce  # noqa: E402
import text_fragment as tf  # noqa: E402


ORG_MD = """---
title: Test Org
type: ngo
status: active
country: France
website: https://example.org
summary: A test org.
events:
- date: '2020-01-01'
  title: Founded
  url: https://example.org/founding
  quote: The organisation was founded in 2020 by a group of volunteers.
  proof_level: high
---

Body text here.
"""


class OnPreBuildArchiveProjectionTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

        docs_dir = os.path.join(self.tmpdir, "docs")
        orgs_dir = os.path.join(docs_dir, "organisations")
        os.makedirs(orgs_dir)
        with open(os.path.join(orgs_dir, "test-org.md"), "w", encoding="utf-8") as f:
            f.write(ORG_MD)

        self._orig_docs_dir = ce.DOCS_DIR
        self._orig_out_path = ce.OUT_PATH
        self._orig_archive_cache_path = tf.EVIDENCE_PATH
        ce.DOCS_DIR = docs_dir
        ce.OUT_PATH = os.path.join(docs_dir, "data", "citations.json")
        self.addCleanup(self._restore)

    def _restore(self):
        ce.DOCS_DIR = self._orig_docs_dir
        ce.OUT_PATH = self._orig_out_path
        tf.EVIDENCE_PATH = self._orig_archive_cache_path

    def _set_archive_cache(self, data):
        path = os.path.join(self.tmpdir, "evidence-cache.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        tf.EVIDENCE_PATH = path

    def _read_citations(self):
        with open(ce.OUT_PATH, encoding="utf-8") as f:
            return json.load(f)

    def test_no_evidence_cache_entry_leaves_archive_fields_absent(self):
        self._set_archive_cache({})
        ce.on_pre_build(None)
        cites = self._read_citations()
        self.assertEqual(len(cites), 1)
        self.assertNotIn("archive", cites[0])
        self.assertNotIn("archive_location", cites[0])
        self.assertNotIn("url-status", cites[0])

    def test_archive_url_projected_onto_citation(self):
        self._set_archive_cache({
            "https://example.org/founding": {
                "archive_url": "https://web.archive.org/web/20260101000000/https://example.org/founding",
            },
        })
        ce.on_pre_build(None)
        cites = self._read_citations()
        self.assertEqual(cites[0]["archive"], "Internet Archive Wayback Machine")
        self.assertEqual(
            cites[0]["archive_location"],
            "https://web.archive.org/web/20260101000000/https://example.org/founding",
        )
        self.assertNotIn("url-status", cites[0])

    def test_url_status_projected_onto_citation(self):
        self._set_archive_cache({
            "https://example.org/founding": {
                "archive_url": "https://web.archive.org/web/20260101000000/https://example.org/founding",
                "url_status": "dead",
            },
        })
        ce.on_pre_build(None)
        cites = self._read_citations()
        self.assertEqual(cites[0]["url-status"], "dead")

    def test_stale_prior_output_does_not_survive_when_cache_disagrees(self):
        # Simulate a citations.json left over from before this URL's
        # archive was ever recorded, or from a since-invalidated capture —
        # the projection must reflect the CURRENT evidence cache, not
        # whatever this file said last time it was built.
        os.makedirs(os.path.dirname(ce.OUT_PATH), exist_ok=True)
        with open(ce.OUT_PATH, "w", encoding="utf-8") as f:
            json.dump([{
                "id": "deadbeef",
                "type": "webpage",
                "URL": "https://example.org/founding",
                "title": "stale title",
                "archive": "Internet Archive Wayback Machine",
                "archive_location": "https://web.archive.org/web/19990101000000/https://example.org/founding",
                "url-status": "dead",
                "evidence": [],
            }], f)

        self._set_archive_cache({})  # evidence cache now has nothing recorded
        ce.on_pre_build(None)
        cites = self._read_citations()
        self.assertEqual(len(cites), 1)
        self.assertNotIn("archive", cites[0])
        self.assertNotIn("archive_location", cites[0])
        self.assertNotIn("url-status", cites[0])

    def test_accessed_field_still_carried_forward_separately(self):
        # accessed is written by citations_tool.py --augment, run against
        # citations.json directly — a different, still-valid mechanism
        # that this change must not disturb.
        os.makedirs(os.path.dirname(ce.OUT_PATH), exist_ok=True)
        with open(ce.OUT_PATH, "w", encoding="utf-8") as f:
            json.dump([{
                "id": "deadbeef",
                "type": "webpage",
                "URL": "https://example.org/founding",
                "title": "Founded",
                "accessed": {"date-parts": [[2026, 1, 1]]},
                "evidence": [],
            }], f)
        self._set_archive_cache({})
        ce.on_pre_build(None)
        cites = self._read_citations()
        self.assertEqual(cites[0]["accessed"], {"date-parts": [[2026, 1, 1]]})

    def test_evidence_id_is_full_untruncated_sha256_of_quote(self):
        # See internal-heartbeat/machine-verifiable-citation.md's "Evidence
        # id length": evidence[].id is the full 64-char digest, never
        # truncated in citations.json — truncation (if any) only happens
        # at the COinS embedding site, not in this stored record.
        self._set_archive_cache({})
        ce.on_pre_build(None)
        cites = self._read_citations()
        quote = "The organisation was founded in 2020 by a group of volunteers."
        expected_id = hashlib.sha256(tf.normalize_ws(quote).encode("utf-8")).hexdigest()
        self.assertEqual(len(cites[0]["evidence"]), 1)
        self.assertEqual(cites[0]["evidence"][0]["id"], expected_id)
        self.assertEqual(len(expected_id), 64)

    def test_url_level_id_is_full_untruncated_sha256(self):
        # Consistency fix: this id used to be md5(url)[:8], and briefly
        # sha256(url)[:12]. Both mixed a truncation decision into stored
        # data that has no byte-budget reason for one — the same
        # reasoning that keeps evidence[].id full-length applies here.
        # Truncating for a shorter display/citation key is a render-time
        # choice, not baked into the file.
        self._set_archive_cache({})
        ce.on_pre_build(None)
        cites = self._read_citations()
        expected_id = hashlib.sha256(
            "https://example.org/founding".encode("utf-8")
        ).hexdigest()
        self.assertEqual(cites[0]["id"], expected_id)
        self.assertEqual(len(cites[0]["id"]), 64)

    def test_evidence_id_is_stable_across_rebuilds_with_no_state_carried(self):
        # A hash-derived id must reproduce identically from source on every
        # build with zero persisted state — unlike a UUID, which would need
        # an id registry to stay stable (see the same doc section for why
        # that reintroduces the two-writers-can-disagree problem this
        # citation-archival redesign already removed once).
        self._set_archive_cache({})
        ce.on_pre_build(None)
        first_id = self._read_citations()[0]["evidence"][0]["id"]
        ce.on_pre_build(None)
        second_id = self._read_citations()[0]["evidence"][0]["id"]
        self.assertEqual(first_id, second_id)


if __name__ == "__main__":
    unittest.main()
