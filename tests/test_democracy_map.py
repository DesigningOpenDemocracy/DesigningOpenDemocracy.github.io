#!/usr/bin/env python3
"""Regression tests for hooks/democracy_map.py.

The hook decides which orgs the home page's Democracy Map shows, and three
templates act on that decision: home.html places the pins, organisation.html
and organisations.html render "Show on map" links to them. A link rendered
for an org the map left out opens the map on nothing, and nothing says why,
so the rule is pinned here and the templates are checked for using the
shared test rather than a copy of the condition.

Offline, stdlib-only apart from jinja2 (already installed). Run with:

    python -m unittest discover tests
"""

import os
import sys
import unittest

import jinja2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

import democracy_map as dm  # noqa: E402

OVERRIDES = os.path.join(os.path.dirname(__file__), "..", "docs", "overrides")

ON_MAP = {"status": "active", "location": {"latitude": -37.8, "longitude": 144.9}}


class IsOnMapTests(unittest.TestCase):
    def test_active_with_coordinates(self):
        self.assertTrue(dm.is_on_map(ON_MAP))

    def test_inactive_is_left_off(self):
        self.assertFalse(dm.is_on_map({**ON_MAP, "status": "inactive"}))

    def test_missing_or_partial_location_is_left_off(self):
        self.assertFalse(dm.is_on_map({"status": "active"}))
        self.assertFalse(dm.is_on_map({"status": "active", "location": None}))
        self.assertFalse(dm.is_on_map({"status": "active", "location": {"latitude": -37.8}}))
        self.assertFalse(dm.is_on_map({"status": "active", "location": {"name": "Melbourne"}}))

    def test_empty_meta(self):
        self.assertFalse(dm.is_on_map({}))
        self.assertFalse(dm.is_on_map(None))


class OnEnvTests(unittest.TestCase):
    def test_registers_test_and_filter(self):
        env = dm.on_env(jinja2.Environment(), {}, None)
        tmpl = env.from_string(
            "{% if meta is on_democracy_map %}{{ 'bank-australia' | democracy_map_url }}{% endif %}"
        )
        self.assertEqual(tmpl.render(meta=ON_MAP), "/?org=bank-australia")
        self.assertEqual(tmpl.render(meta={"status": "inactive"}), "")

    def test_no_stray_event_handlers(self):
        # MkDocs registers every module-level on_<name> function in a hook
        # file as a handler for event <name>, and an unknown event name
        # fails the whole build (the first draft named the helper on_map).
        handlers = [n for n in dir(dm) if n.startswith("on_") and callable(getattr(dm, n))]
        self.assertEqual(handlers, ["on_env"])


class TemplatesShareTheRuleTests(unittest.TestCase):
    def test_each_template_uses_the_shared_test(self):
        for name in ("home.html", "organisation.html", "organisations.html"):
            with open(os.path.join(OVERRIDES, name), encoding="utf-8") as f:
                self.assertIn("is on_democracy_map", f.read(), name)


if __name__ == "__main__":
    unittest.main()
