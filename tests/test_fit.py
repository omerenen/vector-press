import math

import numpy as np
from PIL import Image, ImageDraw

from vectorizer.pipeline.boundary import build_graph, label_regions
from vectorizer.pipeline.fit import (chain_samples, detect_corners, ellipse_dist, fit_chain, fit_cubic, fit_ellipse,
                                     reverse_geom)


def _closed_chain(img):
    R, rl = label_regions(np.asarray(img).astype(np.int32))
    ch = build_graph(R)
    return [c for c in ch if c.closed and c.left >= 0 and c.right >= 0][0]


def test_fit_ellipse_recovers_circle_subpixel():
    t = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    P = np.column_stack([50.3 + 20.7 * np.cos(t), 40.1 + 20.7 * np.sin(t)])
    P += np.random.default_rng(0).normal(0, 0.2, P.shape)
    cx, cy, a, b, th = fit_ellipse(P)
    assert abs(cx - 50.3) < 0.1 and abs(cy - 40.1) < 0.1
    assert abs(a - 20.7) < 0.1 and abs(b - 20.7) < 0.1


def test_rasterised_circle_becomes_circle_primitive_within_half_pixel():
    im = Image.new("L", (128, 128), 0)
    ImageDraw.Draw(im).ellipse((20, 30, 100, 110), fill=1)   # centre (60.5, 70.5), r = 40.5
    c = _closed_chain(im)
    fit_chain(c, {})
    assert c.prim is not None and c.prim["type"] == "circle"
    assert abs(c.prim["cx"] - 60.5) < 0.5 and abs(c.prim["cy"] - 70.5) < 0.5
    assert abs(c.prim["r"] - 40.5) < 0.5


def test_sharp_rectangle_is_exact():
    im = Image.new("L", (100, 100), 0)
    ImageDraw.Draw(im).rectangle((10, 20, 69, 49), fill=1)
    c = _closed_chain(im)
    fit_chain(c, {})
    p = c.prim
    assert p["type"] == "rect" and p["r"] == 0 and p["angle"] == 0
    assert abs(p["w"] - 60) < 1e-6 and abs(p["h"] - 30) < 1e-6
    assert abs(p["cx"] - 40) < 1e-6 and abs(p["cy"] - 35) < 1e-6


def test_rounded_rectangle_radius():
    im = Image.new("L", (140, 140), 0)
    ImageDraw.Draw(im).rounded_rectangle((20, 30, 100, 90), radius=12, fill=1)
    c = _closed_chain(im)
    fit_chain(c, {})
    assert c.prim["type"] == "rect" and abs(c.prim["r"] - 12.5) < 1.0


def test_triangle_corners_detected_and_lines():
    im = Image.new("L", (100, 100), 0)
    ImageDraw.Draw(im).polygon([(20, 60), (70, 30), (80, 85)], fill=1)
    c = _closed_chain(im)
    S = chain_samples(c.pts, True)
    cs = detect_corners(S, True)
    assert len(cs) == 3
    fit_chain(c, {})
    assert c.prim is None
    assert [s[0] for s in c.geom["segs"]] == ["L", "L", "L"]
    verts = [c.geom["start"]] + [s[-1] for s in c.geom["segs"]]
    for v in [(20.5, 60.5), (70.5, 30.5), (80.5, 85.5)]:  # pixel-centre polygon, +-1 px for rasterisation
        assert min(math.hypot(v[0] - p[0], v[1] - p[1]) for p in verts) < 1.5


def test_smooth_curve_has_no_corners():
    t = np.linspace(0, 2 * np.pi, 300, endpoint=False)
    P = np.column_stack([50 + 30 * np.cos(t), 50 + 18 * np.sin(t)])
    assert detect_corners(P, True) == []


def test_fit_cubic_error_bound():
    t = np.linspace(0, 1, 60)
    P = np.column_stack([t * 100, 30 * np.sin(t * np.pi)])
    t1 = (P[1] - P[0]) / np.linalg.norm(P[1] - P[0])
    t2 = (P[-2] - P[-1]) / np.linalg.norm(P[-2] - P[-1])
    curves = fit_cubic(P, t1, t2, 0.3)
    # sample curves densely and check every input point is near the result
    pts = []
    for c in curves:
        u = np.linspace(0, 1, 200)[:, None]
        pts.append((1 - u) ** 3 * c[0] + 3 * (1 - u) ** 2 * u * c[1] + 3 * (1 - u) * u ** 2 * c[2] + u ** 3 * c[3])
    Q = np.vstack(pts)
    d = np.sqrt(((P[:, None] - Q[None]) ** 2).sum(-1)).min(1)
    assert d.max() < 0.35


def test_reverse_geom_roundtrip():
    g = {"start": (0, 0), "segs": [("L", (1, 0)), ("C", (2, 0), (2, 1), (2, 2)), ("A", 3, 3, 0, 0, 1, (0, 5))]}
    r = reverse_geom(g)
    assert r["start"] == (0, 5)
    assert r["segs"][0][0] == "A" and r["segs"][0][5] == 0 and r["segs"][0][-1] == (2, 2)
    assert r["segs"][1] == ("C", (2, 1), (2, 0), (1, 0))
    assert reverse_geom(r) == g


def test_ellipse_dist_zero_on_ellipse():
    e = (10.0, 20.0, 8.0, 4.0, 0.3)
    t = np.linspace(0, 2 * np.pi, 50)
    P = np.column_stack([10 + 8 * np.cos(t) * np.cos(0.3) - 4 * np.sin(t) * np.sin(0.3),
                         20 + 8 * np.cos(t) * np.sin(0.3) + 4 * np.sin(t) * np.cos(0.3)])
    assert ellipse_dist(P, e).max() < 0.05
