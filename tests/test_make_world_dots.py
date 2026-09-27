#!/usr/bin/env python3
"""Tests for util/make_world_dots.py, the generator behind the home page's
Democracy Map teaser outline.

The outline is committed output, so a wrong dot never fails a build; it just
draws a coastline in the wrong place. Two things are worth pinning: the
TopoJSON decoding and point-in-polygon test on synthetic shapes, and the one
contract that spans files — home.html's SVG viewBox must cover exactly the
latitude band the script draws, or the real org dots land offset from the
land they sit on.

Offline and stdlib-only. Run with:

    python -m unittest discover tests
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "util"))

import make_world_dots as mwd  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), "..")

SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
HOLE = [(4, 4), (6, 4), (6, 6), (4, 6), (4, 4)]


class DecodeTests(unittest.TestCase):
    def test_delta_decoding_and_transform(self):
        topo = {
            "transform": {"scale": [0.5, 2], "translate": [-10, 5]},
            "arcs": [[[0, 0], [2, 1], [2, -1]]],
        }
        self.assertEqual(mwd.decode_arcs(topo), [[(-10, 5), (-9, 7), (-8, 5)]])

    def test_ring_stitches_reversed_arcs_without_repeating_joints(self):
        arcs = [[(0, 0), (1, 0)], [(1, 1), (1, 0)]]
        # ~1 is arc 1 reversed: (1, 0) -> (1, 1); the shared (1, 0) appears once.
        self.assertEqual(mwd.ring([0, ~1], arcs), [(0, 0), (1, 0), (1, 1)])


class OnLandTests(unittest.TestCase):
    def test_inside_outside_and_hole(self):
        polys = [[SQUARE, HOLE]]
        self.assertTrue(mwd.on_land(2, 2, polys))
        self.assertFalse(mwd.on_land(15, 5, polys))
        self.assertFalse(mwd.on_land(5, 5, polys))  # in the hole = water


class DotPathTests(unittest.TestCase):
    def test_rows_start_absolute_then_move_relative(self):
        old = (mwd.LAT_TOP, mwd.LAT_BOTTOM)
        mwd.LAT_TOP, mwd.LAT_BOTTOM = 10, 0
        try:
            d = mwd.dot_path([[SQUARE]], 5)
        finally:
            mwd.LAT_TOP, mwd.LAT_BOTTOM = old
        # Grid points at lat 7.5 and 2.5 fall in the square at lon 2.5 and
        # 7.5 only; y is -latitude.
        self.assertEqual(d, "M2.5 -7.5h0m5 0h0M2.5 -2.5h0m5 0h0")


class TeaserViewBoxTests(unittest.TestCase):
    def test_home_viewbox_matches_the_generated_band(self):
        with open(os.path.join(REPO, "docs", "overrides", "home.html"), encoding="utf-8") as f:
            m = re.search(r'viewBox="(-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+)"', f.read())
        self.assertIsNotNone(m, "home.html teaser SVG viewBox not found")
        x, y, w, h = (float(v) for v in m.groups())
        self.assertEqual((x, w), (-180, 360))
        self.assertEqual(y, -mwd.LAT_TOP)
        self.assertEqual(h, mwd.LAT_TOP - mwd.LAT_BOTTOM)

    def test_committed_outline_stays_inside_the_band(self):
        path = os.path.join(REPO, "docs", "overrides", "partials", "world-land-dots.html")
        with open(path, encoding="utf-8") as f:
            d = re.search(r' d="([^"]+)"', f.read()).group(1)
        ys = [float(y) for y in re.findall(r"M-?[\d.]+ (-?[\d.]+)", d)]
        self.assertGreater(len(ys), 20)
        self.assertTrue(all(-mwd.LAT_TOP <= y <= -mwd.LAT_BOTTOM for y in ys))


if __name__ == "__main__":
    unittest.main()
