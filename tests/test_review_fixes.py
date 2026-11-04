"""Regression tests for the phase-2 independent review (REVIEW_PHASE2.md): colour cap, optional shapely, cut."""
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np

from vectorizer import vectorize


def _fills(svg):
    return set(re.findall(r'fill="(#[0-9a-fA-F]{3,6})"', svg))


def _scene():
    rng = np.random.default_rng(0)
    img = np.full((96, 128, 3), 245, np.uint8)
    yy, xx = np.mgrid[:96, :128]
    cols = [(200, 30, 30), (30, 120, 200), (40, 170, 60), (240, 200, 20), (120, 40, 160), (20, 20, 20)]
    for i, c in enumerate(cols):
        cy, cx = 20 + (i // 3) * 50, 22 + (i % 3) * 42
        img[(yy - cy) ** 2 + (xx - cx) ** 2 < 15 ** 2] = c
    img = np.clip(img.astype(int) + rng.integers(-4, 5, img.shape), 0, 255).astype(np.uint8)
    return img


def test_explicit_colors_is_a_cap():
    img = _scene()
    for n in (2, 4):
        svg = vectorize(img, colors=n).svg
        assert len(_fills(svg)) <= n, (n, _fills(svg))


def test_cut_small_design_drops_background_and_is_opaque():
    img = np.full((200, 200, 4), 255, np.uint8)
    img[95:105, 95:105, :3] = (200, 20, 20)          # 0.25 % of the canvas
    img[:10, :10, 3] = 128                             # translucent corner must not produce fill-opacity
    svg = vectorize(img, preset="cut").svg
    ET.fromstring(svg)
    fills = _fills(svg)
    assert "#fff" not in fills and "#ffffff" not in fills, fills
    assert "opacity" not in svg


def test_cut_merges_near_identical_paints():
    img = np.full((120, 120, 3), 255, np.uint8)
    img[10:60, 10:60] = (0, 0, 0)
    img[60:110, 60:110] = (2, 3, 3)                    # visually identical black
    img[10:60, 60:110] = (200, 30, 30)
    svg = vectorize(img, preset="cut").svg
    assert len(_fills(svg)) == 2, _fills(svg)


def test_runs_without_shapely():
    code = r"""
import builtins, xml.etree.ElementTree as ET, numpy as np
real = builtins.__import__
def imp(name, *a, **k):
    if name == 'shapely' or name.startswith('shapely.'):
        raise ImportError('blocked')
    return real(name, *a, **k)
builtins.__import__ = imp
from vectorizer import vectorize
img = np.full((64, 64, 3), 255, np.uint8); img[16:48, 16:48] = (200, 30, 30)
for p in ('auto', 'print', 'cut'):
    r = vectorize(img, preset=p); ET.fromstring(r.svg)
    assert r.stats.get('geom_repair', '').startswith('unavailable'), r.stats
print('ok')
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0 and "ok" in out.stdout, out.stderr[-2000:]
