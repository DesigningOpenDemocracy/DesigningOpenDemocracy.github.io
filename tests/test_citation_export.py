#!/usr/bin/env python3
"""Regression tests for hooks/citation_export.py's on_pre_build(): the
CSL-JSON citations.json export, and specifically that archive/
archive_location/url-status are a fresh *projection* of
docs/data/citation-state.json on every build, never carried
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


class _ExportFixture(unittest.TestCase):
    """Shared tempdir fixture: one org page with one quoted event, with
    DOCS_DIR/OUT_PATH and the evidence-cache path all redirected away
    from the real repo. Holds no tests of its own, so subclassing it
    doesn't re-run another class's cases."""

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
        self._orig_archive_cache_path = tf.STATE_PATH
        ce.DOCS_DIR = docs_dir
        ce.OUT_PATH = os.path.join(docs_dir, "data", "citations.json")
        self.addCleanup(self._restore)

    def _restore(self):
        ce.DOCS_DIR = self._orig_docs_dir
        ce.OUT_PATH = self._orig_out_path
        tf.STATE_PATH = self._orig_archive_cache_path

    def _set_archive_cache(self, data):
        path = os.path.join(self.tmpdir, "evidence-cache.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        tf.STATE_PATH = path

    def _read_citations(self):
        with open(ce.OUT_PATH, encoding="utf-8") as f:
            return json.load(f)


class OnPreBuildArchiveProjectionTests(_ExportFixture):

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

    def test_convergence_sha256_always_present_even_when_identical_to_id(self):
        # See internal-heartbeat/machine-verifiable-citation.md's "id vs
        # the sha256 field": always emitted, never omitted as a
        # "redundant" duplicate when id is already content-derived — a
        # uniform schema beats saving a few bytes, so consumers never
        # need conditional presence-checking logic. A wrapper object
        # (matching evidence[].context's own shape), not a flat field
        # or a purpose-based name like "convergence-id" — the wrapper
        # names what's hashed and why, sha256 inside it says how.
        self._set_archive_cache({})
        ce.on_pre_build(None)
        cites = self._read_citations()
        self.assertEqual(cites[0]["convergence"]["sha256"], cites[0]["id"])
        self.assertEqual(
            cites[0]["evidence"][0]["convergence"]["sha256"],
            cites[0]["evidence"][0]["id"],
        )

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


class VerificationProjectionTests(_ExportFixture):
    """status/last-verified/verified-by/context are projected fresh from
    citation-state.json on every build, exactly like the archive
    fields — they used to carry forward from citations.json's own prior
    output, a structurally dead branch that left them populated on zero
    entries. See "Signal map" in internal-heartbeat/
    machine-verifiable-citation.md.

    Uses the shared _ExportFixture (same org page, same one quote).
    """

    QUOTE = "The organisation was founded in 2020 by a group of volunteers."

    def _ev_key(self):
        return hashlib.sha256(
            tf.normalize_ws(self.QUOTE).encode("utf-8")
        ).hexdigest()

    def _only_evidence(self):
        return self._read_citations()[0]["evidence"][0]

    def test_match_projected_with_bot_identity(self):
        self._set_archive_cache({
            "https://example.org/founding": {
                "evidence": [{"id": self._ev_key(), "verified": True}],
                "checked": "2026-08-22",
            },
        })
        ce.on_pre_build(None)
        ev = self._only_evidence()
        self.assertEqual(ev["status"], "MATCH")
        self.assertEqual(ev["last-verified"], "2026-08-22")
        self.assertEqual(ev["verified-by"], ce.BOT_IDENTITY)

    def test_mismatch_projected(self):
        self._set_archive_cache({
            "https://example.org/founding": {
                "evidence": [{"id": self._ev_key(), "verified": False}],
                "checked": "2026-08-22",
            },
        })
        ce.on_pre_build(None)
        self.assertEqual(self._only_evidence()["status"], "MISMATCH")

    def test_manual_verification_omits_verified_by(self):
        # A human's browser reached a page the bot cannot. Real
        # verification, different provenance — the spec reads an absent
        # verified-by as "human claim", so it must not be stamped with
        # the bot's identity.
        self._set_archive_cache({
            "https://example.org/founding": {
                "evidence": [{"id": self._ev_key(), "manual_verified": True}],
                "manual_checked": "2026-08-20",
            },
        })
        ce.on_pre_build(None)
        ev = self._only_evidence()
        self.assertEqual(ev["status"], "MATCH")
        self.assertEqual(ev["last-verified"], "2026-08-20")
        self.assertNotIn("verified-by", ev)

    def test_automated_verdict_wins_over_manual(self):
        self._set_archive_cache({
            "https://example.org/founding": {
                "evidence": [{"id": self._ev_key(), "verified": True,
                              "manual_verified": False}],
                "checked": "2026-08-22",
                "manual_checked": "2026-08-01",
            },
        })
        ce.on_pre_build(None)
        ev = self._only_evidence()
        self.assertEqual(ev["status"], "MATCH")
        self.assertEqual(ev["verified-by"], ce.BOT_IDENTITY)

    def test_context_projects_sha256_prefix_suffix_but_not_text(self):
        # context ships sha256 plus the TextQuoteSelector prefix/suffix
        # anchors (which let a verifier pin which occurrence of a repeated
        # sentence a citation means), but not the bulky paragraph text —
        # that's republishing other organisations' prose a verifier
        # recomputes from the page it fetches anyway.
        self._set_archive_cache({
            "https://example.org/founding": {
                "evidence": [{
                    "id": self._ev_key(),
                    "verified": True,
                    "context": {
                        "sha256": "abc123",
                        "text": "a whole paragraph of someone else's prose",
                        "prefix": "before",
                        "suffix": "after",
                    },
                }],
                "checked": "2026-08-22",
            },
        })
        ce.on_pre_build(None)
        ev = self._only_evidence()
        self.assertEqual(
            ev["context"],
            {"sha256": "abc123", "prefix": "before", "suffix": "after"},
        )

    def test_context_without_prefix_suffix_keeps_sha256_only(self):
        # A context entry lacking prefix/suffix (older cache shape, or a
        # quote at the very start of a page) still projects its hash alone.
        self._set_archive_cache({
            "https://example.org/founding": {
                "evidence": [{
                    "id": self._ev_key(),
                    "verified": True,
                    "context": {"sha256": "abc123"},
                }],
                "checked": "2026-08-22",
            },
        })
        ce.on_pre_build(None)
        self.assertEqual(self._only_evidence()["context"], {"sha256": "abc123"})

    def test_document_sha256_projected_at_item_level(self):
        # Resource-level integrity — the one signal-map cell that was
        # unbuilt. Sibling to archive/url-status, not nested under
        # convergence (identity) or evidence[].context (claim-level).
        self._set_archive_cache({
            "https://example.org/founding": {
                "document_sha256": "deadbeef" * 8,
            },
        })
        ce.on_pre_build(None)
        cite = self._read_citations()[0]
        self.assertEqual(cite["document"], {"sha256": "deadbeef" * 8})

    def test_document_sha256_absent_when_not_yet_fetched(self):
        self._set_archive_cache({})
        ce.on_pre_build(None)
        self.assertNotIn("document", self._read_citations()[0])

    def test_nothing_recorded_leaves_all_verification_fields_absent(self):
        # Absent means "not yet verified" per the spec — an honest gap,
        # not something to paper over with a default.
        self._set_archive_cache({})
        ce.on_pre_build(None)
        ev = self._only_evidence()
        for field in ("status", "last-verified", "verified-by", "context"):
            self.assertNotIn(field, ev)

    def test_stale_prior_output_does_not_survive(self):
        # The regression that motivated this: these fields must come
        # from the evidence cache, never from citations.json's own
        # previous build.
        os.makedirs(os.path.dirname(ce.OUT_PATH), exist_ok=True)
        with open(ce.OUT_PATH, "w", encoding="utf-8") as f:
            json.dump([{
                "id": "stale", "type": "webpage",
                "URL": "https://example.org/founding", "title": "stale",
                "evidence": [{"quote": self.QUOTE, "status": "MATCH",
                              "verified-by": "ghost/9.9",
                              "last-verified": "1999-01-01"}],
            }], f)
        self._set_archive_cache({})
        ce.on_pre_build(None)
        ev = self._only_evidence()
        self.assertNotIn("status", ev)
        self.assertNotIn("verified-by", ev)


class CitationOnlyFootnoteTests(_ExportFixture):
    """A citation-only footnote (no verbatim quote) now gets a bare
    CSL-JSON item — id/convergence/type/URL/title, evidence: [] —
    instead of no representation in citations.json at all. See this
    file's module docstring and util/text_fragment.py's
    citation_only_link()/iter_citation_only_footnotes()."""

    CITATION_ONLY_MD = """---
title: Another Org
type: ngo
status: active
country: France
website: https://example.org
summary: Another test org.
---

Some prose with a citation.[^plain]

[^plain]: [Council Watch](https://www.councilwatch.com.au), Council Watch website footer. <!-- unquoted: legacy: n/a -->
"""

    def _write_extra_org(self, content):
        orgs_dir = os.path.join(self.tmpdir, "docs", "organisations")
        with open(os.path.join(orgs_dir, "extra-org.md"), "w", encoding="utf-8") as f:
            f.write(content)

    def test_citation_only_footnote_gets_bare_item(self):
        self._write_extra_org(self.CITATION_ONLY_MD)
        self._set_archive_cache({})
        ce.on_pre_build(None)
        cites = self._read_citations()
        by_url = {c["URL"]: c for c in cites}
        self.assertIn("https://www.councilwatch.com.au", by_url)
        cite = by_url["https://www.councilwatch.com.au"]
        self.assertEqual(cite["title"], "Council Watch")
        self.assertEqual(cite["evidence"], [])
        self.assertIn("id", cite)
        self.assertIn("convergence", cite)

    def test_multi_source_footnote_is_not_exported(self):
        md = self.CITATION_ONLY_MD.replace(
            "[^plain]: [Council Watch](https://www.councilwatch.com.au), "
            "Council Watch website footer. <!-- unquoted: legacy: n/a -->",
            "[^plain]: [First](https://a.example.org) and "
            "[Second](https://b.example.org), two sources. "
            "<!-- unquoted: multi-source: two links -->",
        )
        self._write_extra_org(md)
        self._set_archive_cache({})
        ce.on_pre_build(None)
        cites = self._read_citations()
        urls = {c["URL"] for c in cites}
        self.assertNotIn("https://a.example.org", urls)
        self.assertNotIn("https://b.example.org", urls)

    def test_citation_only_and_quoted_citation_of_same_url_merge(self):
        # The fixture org (ORG_MD) already cites this exact URL WITH a
        # quote via its event. A second, citation-only mention of the
        # same URL elsewhere must not create a duplicate bare entry —
        # one citation entry per URL, real evidence intact.
        md = self.CITATION_ONLY_MD.replace(
            "https://www.councilwatch.com.au", "https://example.org/founding")
        self._write_extra_org(md)
        self._set_archive_cache({})
        ce.on_pre_build(None)
        cites = self._read_citations()
        urls = [c["URL"] for c in cites]
        self.assertEqual(urls.count("https://example.org/founding"), 1)
        cite = next(c for c in cites if c["URL"] == "https://example.org/founding")
        self.assertEqual(len(cite["evidence"]), 1)


if __name__ == "__main__":
    unittest.main()
