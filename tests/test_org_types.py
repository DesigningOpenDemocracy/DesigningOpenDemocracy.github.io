#!/usr/bin/env python3
"""Regression tests for hooks/org_types.py.

The hook groups free-text org `type:` values into the categories the
Democracy Map's type filter offers (and whose icon the Landscape pages show).
The failure worth pinning is the one that motivated it: a type value nobody
listed doesn't break anything, it just quietly lands in "Other" — which is
how every `ngo`, `network` and `think-tank` org ended up with the generic 🏛️
before this hook existed, with nothing to say so. CorpusCoverageTests turns
that into a test failure: add the new value to a category in CATEGORIES.

Offline, stdlib-only apart from pyyaml and jinja2 (both already installed).
Run with:

    python -m unittest discover tests
"""

import glob
import os
import sys
import unittest

import jinja2
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

import org_types as ot  # noqa: E402

ORGS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "organisations")


def _frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---"):
        return {}
    return yaml.safe_load(text.split("---", 2)[1]) or {}


class NormalizeTypeTests(unittest.TestCase):
    def test_spelling_variants_fold_together(self):
        for raw in ("civic tech", "civic_tech", "Civic-Tech", " civic  tech "):
            self.assertEqual(ot.normalize_type(raw), "civic-tech", raw)

    def test_empty_and_missing(self):
        self.assertEqual(ot.normalize_type(None), "")
        self.assertEqual(ot.normalize_type(""), "")


class CategoryForTests(unittest.TestCase):
    def test_known_types(self):
        self.assertEqual(ot.category_for("ngo")["key"], "civil-society")
        self.assertEqual(ot.category_for("political_party")["key"], "political")
        self.assertEqual(ot.category_for("civic tech")["key"], "civic-tech")

    def test_unknown_and_missing_fall_back_to_other(self):
        self.assertIs(ot.category_for("something-new"), ot.OTHER)
        self.assertIs(ot.category_for(None), ot.OTHER)


class CategoryTableTests(unittest.TestCase):
    def test_keys_unique(self):
        keys = [c["key"] for c in ot.ALL_CATEGORIES]
        self.assertEqual(len(keys), len(set(keys)))

    def test_each_type_listed_once(self):
        # _BY_TYPE is a dict comprehension, so a type listed under two
        # categories would silently belong to whichever comes last.
        seen = {}
        for c in ot.CATEGORIES:
            for t in c["types"]:
                self.assertNotIn(t, seen, f"{t!r} is in both {seen.get(t)} and {c['key']}")
                seen[t] = c["key"]

    def test_listed_types_are_already_normalized(self):
        # Lookups normalize the org's value first, so an entry written in any
        # other form (`civic_tech`) could never match anything.
        for c in ot.CATEGORIES:
            for t in c["types"]:
                self.assertEqual(ot.normalize_type(t), t, f"{c['key']}: {t!r}")


class CorpusCoverageTests(unittest.TestCase):
    def test_every_org_type_has_a_category(self):
        unlisted = {}
        for path in glob.glob(os.path.join(ORGS_DIR, "*.md")):
            if os.path.basename(path) == "index.md":
                continue
            org_type = _frontmatter(path).get("type")
            if org_type and ot.category_for(org_type) is ot.OTHER:
                unlisted.setdefault(org_type, []).append(os.path.basename(path))
        self.assertEqual(
            unlisted, {},
            "org type(s) not in any category in hooks/org_types.py CATEGORIES — "
            "add each to the category it belongs in (or a new one)",
        )


class OnEnvTests(unittest.TestCase):
    def test_registers_what_the_templates_use(self):
        env = ot.on_env(jinja2.Environment(), {}, None)
        self.assertEqual(env.from_string("{{ 'ngo' | org_type_icon }}").render(), "🌐")
        self.assertEqual(env.from_string("{{ 'ngo' | org_type_category }}").render(), "civil-society")
        self.assertEqual(
            [c["key"] for c in env.globals["org_type_categories"]],
            [c["key"] for c in ot.ALL_CATEGORIES],
        )


if __name__ == "__main__":
    unittest.main()
