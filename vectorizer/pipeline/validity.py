"""Geometry validity for cutting (phase 2, stream A).

Every emitted loop must be a simple ring (no self-crossings, non-zero area): plotters and cutters
choke on self-intersecting outlines. Curve fitting can violate this near junctions (a Bezier of
one chain overshoots across a neighbouring chain where two chains leave a junction at a small
angle) and on tiny regions (a 3x3 px dot whose two chains both become the same straight line).

Repair is local and keeps the shared-boundary property (a chain is changed for both regions):
the chains of an offending loop are re-emitted as polylines through their sub-pixel samples,
then (if still invalid) through the raw crack midpoints, whose polygon is simple by construction
for a 4-connected region. Loops that touch themselves at a lattice vertex (two diagonal pixels of
the same region = pinch) are split into separate simple rings at that vertex by the emitter
(`split_pinches`).
"""
from __future__ import annotations

import numpy as np

from .fit import chain_samples, reverse_geom


def flatten_geom(g, n_curve=8, n_arc=16):
    """Points along a geometry dict (start included); arcs via the SVG endpoint parameterisation."""
    from .svgarc import arc_points
    pts = [np.asarray(g["start"], float)]
    cur = pts[0]
    for s in g["segs"]:
        end = np.asarray(s[-1], float)
        if s[0] == "C":
            c1, c2 = np.asarray(s[1], float), np.asarray(s[2], float)
            t = np.linspace(0, 1, n_curve + 1)[1:, None]
            mt = 1 - t
            pts.extend(mt ** 3 * cur + 3 * mt * mt * t * c1 + 3 * mt * t * t * c2 + t ** 3 * end)
        elif s[0] == "A":
            pts.extend(arc_points(cur, end, s[1], s[2], s[3], s[4], s[5], n_arc))
        else:
            pts.append(end)
        cur = end
    return np.array(pts)


def _ring_ok(P):
    """Simple ring with positive area (P closed implicitly)."""
    from shapely.geometry import LinearRing, Polygon
    if len(P) < 3:
        return False
    # drop consecutive duplicates (zero-length segments are not crossings)
    d = np.abs(np.diff(P, axis=0)).max(1) > 1e-9
    P = np.vstack([P[:1], P[1:][d]])
    if len(P) >= 2 and np.abs(P[-1] - P[0]).max() <= 1e-9:
        P = P[:-1]
    if len(P) < 3:
        return False
    try:
        if not LinearRing(P).is_simple:
            return False
        return abs(Polygon(P).area) > 1e-3
    except Exception:
        return False


def split_pinches(loop, chains):
    """Split a loop (list of (cid, rev)) into sub-loops at vertices it visits more than once."""
    if len(loop) < 2:
        return [loop]

    def start(cid, rev):
        p = chains[cid].pts
        return (int(p[-1][0]), int(p[-1][1])) if rev else (int(p[0][0]), int(p[0][1]))
    out = []
    stack = []                          # (vertex, index in cur)
    cur = []
    seen = {}
    for item in loop:
        v = start(*item)
        if v in seen:
            i = seen[v]
            out.append(cur[i:])         # closed sub-loop from the first visit back to this vertex
            for it in cur[i:]:
                seen.pop(start(*it), None)
            cur = cur[:i]
        seen[v] = len(cur)
        cur.append(item)
    if cur:
        out.append(cur)
    return [lp for lp in out if lp]


def _polyline_geom(c, raw=False, simplify=0.25):
    pts = c.pts
    if raw or c.samples is None:
        S = chain_samples(pts, c.closed)
    else:
        S = c.samples
        if simplify and len(S) > 4:
            from shapely.geometry import LineString
            S = np.asarray(LineString(S).simplify(simplify, preserve_topology=False).coords)
    if c.closed:
        return {"start": (float(S[0][0]), float(S[0][1])),
                "segs": [("L", (float(x), float(y))) for x, y in S[1:]] + [("L", (float(S[0][0]), float(S[0][1])))]}
    # junction end points are shared with other chains: keep them exactly
    start = c.geom["start"] if c.geom is not None else (float(pts[0][0]), float(pts[0][1]))
    end = c.geom["segs"][-1][-1] if c.geom is not None else (float(pts[-1][0]), float(pts[-1][1]))
    mid = [("L", (float(x), float(y))) for x, y in S[1:-1]]
    return {"start": tuple(start), "segs": mid + [("L", tuple(end))]}


def _area(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def repair_loops(loops, chains, max_rounds=12, prec=2, refit=None, drop_area=0.5):
    """loops: list of loops (lists of (cid, rev)) that will be emitted. Returns (stats, rings).

    Chains of invalid loops are replaced by polylines (sub-pixel samples first, raw crack midpoints
    second). A changed chain can affect other loops; those are re-checked (each chain escalates at most
    three times: tighter Bezier refit (`refit(chain)` -> geometry, optional), sample polyline, raw polyline). Loops that are still invalid (e.g. a raw polyline crossing an exact,
    snapped primitive edge that deviates from the pixel lattice) are emitted as the valid polygon parts
    of their own outline (`rings`: {tuple(loop): [ring point arrays, oriented like the loop]}); zero-area
    loops get an empty list (nothing is drawn: they cover no area)."""
    flat = {}

    def fl(cid):
        if cid not in flat:
            flat[cid] = flatten_geom(chains[cid].geom)
        return flat[cid]

    def loop_pts(loop):
        parts = []
        for cid, rev in loop:
            P = fl(cid)
            if rev:
                P = P[::-1]
            parts.append(P[:-1] if len(loop) > 1 else P)
        return np.vstack(parts)

    by_chain = {}
    for li, lp in enumerate(loops):
        for cid, _ in lp:
            by_chain.setdefault(cid, []).append(li)
    level = {}                               # cid -> 0 fitted, 1 tight refit, 2 sample polyline, 3 raw polyline
    dropped = set()
    todo = list(range(len(loops)))
    stats = {"invalid_loops": 0, "repaired": 0, "unrepaired": 0}
    first = True
    for _ in range(max_rounds + 1):
        bad = []
        for li in todo:
            lp = loops[li]
            if li in dropped or any(chains[cid].geom is None for cid, _ in lp):
                continue
            P = loop_pts(lp)
            if not _ring_ok(P):
                if first and abs(_area(P)) < drop_area:
                    # collapsed tiny region (its fitted outline has no area: invisible in the output); repairing it
                    # would only add a sub-pixel island and nodes -> not emitted at all
                    dropped.add(li)
                    continue
                bad.append(li)
        if first:
            stats["invalid_loops"] = len(bad) + len(dropped)
            stats["dropped"] = len(dropped)
            first = False
        if not bad:
            break
        changed = set()
        for li in bad:
            culprits = _culprits(loops[li], fl)
            for cid, _ in loops[li]:
                if culprits is not None and cid not in culprits:
                    continue
                c = chains[cid]
                if c.snapped or c.prim is not None:
                    continue                 # exact primitive geometry: valid by construction
                lv = level.get(cid, 0)
                if refit is None and lv == 0:
                    lv = 1
                if lv >= 3:
                    continue
                if lv == 0:
                    g = refit(c)                 # tighter Bezier fit without smoothing (few extra nodes)
                    if g is None:
                        g = _polyline_geom(c)
                        lv = 1
                    c.geom = g
                else:
                    c.geom = _polyline_geom(c, raw=(lv == 2))
                level[cid] = lv + 1
                flat.pop(cid, None)
                changed.add(cid)
        if not changed:
            break
        todo = sorted({li for cid in changed for li in by_chain.get(cid, [])})
    final_bad = 0
    rings = {}
    for li in range(len(loops)):
        lp = loops[li]
        if li in dropped:
            rings[tuple(lp)] = []
            continue
        if any(chains[cid].geom is None for cid, _ in lp):
            continue
        P = loop_pts(lp)
        if not _ring_ok(P):
            final_bad += 1
            rings[tuple(lp)] = valid_parts(P, prec)
    stats["unrepaired"] = final_bad
    stats["repaired"] = stats["invalid_loops"] - final_bad - len(dropped)
    stats["valid_parts"] = len(rings)
    return stats, rings


def _culprits(loop, fl):
    """Chains of an invalid loop that take part in a crossing (pairwise / self tests); None = all
    (zero-area loops and cases the pairwise test cannot localise)."""
    from shapely.geometry import LineString, Point
    if len(loop) < 2:
        return None
    lines = []
    for cid, _ in loop:
        P = fl(cid)
        d = np.abs(np.diff(P, axis=0)).max(1) > 1e-9
        P = np.vstack([P[:1], P[1:][d]])
        lines.append(LineString(P) if len(P) >= 2 else None)
    out = set()
    for i, a in enumerate(lines):
        if a is None:
            continue
        if not a.is_simple:
            out.add(loop[i][0])
        ea = [Point(a.coords[0]), Point(a.coords[-1])]
        for j in range(i + 1, len(lines)):
            b = lines[j]
            if b is None or not a.intersects(b):
                continue
            inter = a.intersection(b)
            if inter.geom_type in ("Point", "MultiPoint"):
                pts = [inter] if inter.geom_type == "Point" else list(inter.geoms)
                eb = [Point(b.coords[0]), Point(b.coords[-1])]
                shared = [p for p in ea if any(p.distance(q) < 1e-7 for q in eb)]
                if all(any(p.distance(q) < 1e-7 for q in shared) for p in pts):
                    continue
            out.add(loop[i][0])
            out.add(loop[j][0])
    return out or None


def valid_parts(P, prec=2):
    """Valid polygon parts of a (self-crossing) ring as point rings oriented like P (exterior), holes reversed."""
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    from shapely.validation import make_valid
    x, y = P[:, 0], P[:, 1]
    sgn = 1.0 if (np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y)) >= 0 else -1.0
    try:
        from shapely import set_precision
        # valid on the output coordinate grid (written with `prec` decimals): rounding cannot re-create crossings
        g = set_precision(make_valid(Polygon(P)).buffer(0), 10.0 ** -prec)
    except Exception:
        return []
    polys = []
    stack = [g]
    min_area = 1.0                     # crossing lobes below 1 px^2 are fitting artefacts, not shape
    while stack:
        h = stack.pop()
        if h.geom_type == "Polygon":
            if h.area > 1e-3:
                polys.append(h)
        elif hasattr(h, "geoms"):
            stack.extend(h.geoms)
    if len(polys) > 1:
        polys = [p for p in polys if p.area >= min_area] or [max(polys, key=lambda p: p.area)]
    out = []
    for p in polys:
        p = orient(p, sgn)
        if not p.exterior.is_simple:
            p = orient(p.simplify(10.0 ** -prec), sgn)
        out.append(np.asarray(p.exterior.coords)[:-1])
        for it in p.interiors:
            out.append(np.asarray(it.coords)[:-1])
    return out


__all__ = ["flatten_geom", "repair_loops", "split_pinches", "reverse_geom"]
