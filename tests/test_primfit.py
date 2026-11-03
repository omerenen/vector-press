"""Region-level primitive detection / snapping (phase 2, stream A)."""
import math

import numpy as np
from PIL import Image, ImageDraw

from vectorizer.pipeline.boundary import assemble_regions, build_graph, label_regions
from vectorizer.pipeline.fit import ellipse_dist, fit_chain, fit_rounded_rect, reverse_geom
from vectorizer.pipeline.primfit import (Outline, fit_polygon, outline_from_prim, polygon_dist,
                                         snap_region_primitives)

OPTS = {"region_prims": True, "rect_refine": True}


def _graph(lbl):
    R, rl = label_regions(np.asarray(lbl).astype(np.int32))
    chains = build_graph(R)
    regions = assemble_regions(chains, rl, R)
    for c in chains:
        fit_chain(c, OPTS)
    drawn = np.array([r.label >= 0 for r in regions])
    return R, rl, chains, regions, drawn


def _region_of_label(regions, label):
    return [r for r in regions if r.label == label][0]


def _end(g):
    return np.asarray(g["segs"][-1][-1], float)


def test_ellipse_dist_exact():
    rng = np.random.default_rng(1)
    e = (3.0, -2.0, 40.0, 7.0, 0.7)
    P = rng.uniform(-60, 60, (300, 2))
    t = np.linspace(0, 2 * math.pi, 200000, endpoint=False)
    cx, cy, a, b, th = e
    E = np.column_stack([cx + a * np.cos(t) * math.cos(th) - b * np.sin(t) * math.sin(th),
                         cy + a * np.cos(t) * math.sin(th) + b * np.sin(t) * math.cos(th)])
    d0 = np.sqrt(((P[:, None] - E[None, ::50]) ** 2).sum(-1)).min(1)   # coarse brute force (upper bound)
    d1 = ellipse_dist(P, e)
    assert (d1 <= d0 + 1e-9).all() and (d0 - d1).max() < 0.05


def test_rect_on_split_background_becomes_rect_and_shares_geometry():
    # background split in two colours: the rectangle's outline has 2 junctions -> 2+ chains
    lbl = np.zeros((80, 120), np.int32)
    lbl[:, 60:] = 1
    lbl[20:50, 30:90] = 2
    R, rl, chains, regions, drawn = _graph(lbl)
    reg = _region_of_label(regions, 2)
    assert len(reg.loops[reg.outer]) >= 2
    prims = snap_region_primitives(regions, chains, OPTS, drawn, shape=lbl.shape)
    p = prims[reg.rid]
    assert p["type"] == "rect" and p["r"] == 0 and abs(p["angle"]) < 1e-9
    assert abs(p["w"] - 60) < 0.1 and abs(p["h"] - 30) < 0.1 and abs(p["cx"] - 60) < 0.1 and abs(p["cy"] - 35) < 0.1
    # every chain of the loop now lies on the rectangle outline, end points shared by all incident chains
    ol = outline_from_prim(p)
    for cid, _ in reg.loops[reg.outer]:
        g = chains[cid].geom
        pts = np.array([g["start"]] + [s[-1] for s in g["segs"]])
        assert ol.dist(pts).max() < 0.02
    ends = {}
    for c in chains:
        if c.closed:
            continue
        for p0, key in ((np.asarray(c.geom["start"]), tuple(c.pts[0])), (_end(c.geom), tuple(c.pts[-1]))):
            ends.setdefault(key, []).append(p0)
    for key, ps in ends.items():
        ps = np.array(ps)
        assert np.abs(ps - ps[0]).max() < 1e-9, key


def test_triangle_over_two_colours_becomes_polygon():
    im = Image.new("L", (120, 100), 0)
    d = ImageDraw.Draw(im)
    d.rectangle((60, 0, 119, 99), fill=1)
    d.polygon([(20, 80), (60, 15), (100, 85)], fill=2)
    R, rl, chains, regions, drawn = _graph(np.asarray(im))
    reg = _region_of_label(regions, 2)
    assert len(reg.loops[reg.outer]) >= 2
    prims = snap_region_primitives(regions, chains, OPTS, drawn, shape=R.shape)
    p = prims[reg.rid]
    assert p["type"] == "polygon" and len(p["points"]) == 3
    for v in [(20.5, 80.5), (60.5, 15.5), (100.5, 85.5)]:
        assert min(math.hypot(v[0] - q[0], v[1] - q[1]) for q in p["points"]) < 1.5


def test_circle_over_two_colours_becomes_circle():
    im = Image.new("L", (140, 140), 0)
    d = ImageDraw.Draw(im)
    d.rectangle((70, 0, 139, 139), fill=1)
    d.ellipse((30, 30, 110, 110), fill=2)
    R, rl, chains, regions, drawn = _graph(np.asarray(im))
    reg = _region_of_label(regions, 2)
    prims = snap_region_primitives(regions, chains, OPTS, drawn, shape=R.shape)
    p = prims[reg.rid]
    assert p["type"] == "circle" and abs(p["r"] - 40.5) < 0.5 and abs(p["cx"] - 70.5) < 0.5


def test_outline_segs_between_follows_rounded_rect():
    ol = outline_from_prim({"type": "rect", "cx": 50, "cy": 40, "w": 60, "h": 30, "r": 8, "angle": 20})
    s0, s1 = 0.3 * ol.length, 0.95 * ol.length
    g = ol.segs_between(s0, s1)
    assert np.allclose(g["start"], ol.point(s0)) and np.allclose(g["segs"][-1][-1], ol.point(s1))
    # reverse + full loop consistency
    g2 = reverse_geom(g)
    assert np.allclose(g2["start"], ol.point(s1))
    full = ol.segs_between(0.0, 0.0, full=True)
    assert np.allclose(full["start"], full["segs"][-1][-1])


def test_fit_polygon_star():
    pts = []
    for i in range(10):
        rad = 40 if i % 2 == 0 else 18
        a = -math.pi / 2 + math.pi * i / 5
        pts.append((60 + rad * math.cos(a), 60 + rad * math.sin(a)))
    im = Image.new("L", (120, 120), 0)
    ImageDraw.Draw(im).polygon(pts, fill=1)
    R, rl, chains, regions, drawn = _graph(np.asarray(im))
    reg = _region_of_label(regions, 1)
    S = chains[reg.loops[reg.outer][0][0]].samples
    if reg.loops[reg.outer][0][1]:
        S = S[::-1]
    res = fit_polygon(S, {})
    assert res is not None and len(res[0]) == 10
    assert polygon_dist(np.array(pts) + 0.5, res[0]).max() < 2.0


def test_robust_rect_refine_ignores_bump():
    # rectangle boundary samples with a 2-px bump on one side: refined fit stays on the true sides
    xs = np.arange(10.5, 70.5, 1.0)
    ys = np.arange(20.5, 50.5, 1.0)
    P = np.vstack([np.column_stack([xs, np.full_like(xs, 20.0)]), np.column_stack([np.full_like(ys, 70.0), ys]),
                   np.column_stack([xs[::-1], np.full_like(xs, 50.0)]), np.column_stack([np.full_like(ys, 10.0), ys[::-1]])])
    P[5:8, 1] -= 2.0
    r = fit_rounded_rect(P, 1.05, axis_aligned=True, refine=True)
    assert r is not None
    q = r.get("sharp", r)
    assert abs(q["cy"] - 35.0) < 0.15 and abs(q["h"] - 30.0) < 0.3
