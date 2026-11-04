"""Region-level primitive detection and snapping (phase 2, stream A).

Chain-level primitive fitting (fit.py) only sees *closed* chains. A shape whose outline is
split by junctions (a shape lying on top of other shapes, a box outline fragmented by JPEG
into several colour regions, a connector line touching a box) is fitted chain by chain, so
it loses its primitive identity and its straight edges carry extra junction vertices.

Here the samples of all chains of a region's outer loop are concatenated and the whole
loop is tested against primitive models (ellipse / circle / rect / rounded rect / polygon).
On success every chain of the loop is replaced by the exact piece of the primitive outline
between its (projected) end points, and the junction vertices are moved onto the outline for
all incident chains. Neighbouring regions therefore use exactly the same geometry (no gaps,
cut-consistent), and the region itself can be emitted as a native element.

Outline representation: closed list of pieces in clockwise screen order (region on the right):
  ('L', p0, p1)                         straight segment
  ('E', c, a, b, rot, th0, th1)         elliptical arc, parametric angle th0 -> th1 (th1 > th0)
"""
from __future__ import annotations

import math

import numpy as np

from .fit import (_arclen, _is_cw, _line_fit, choose_closed_primitive, detect_corners, reverse_geom, robust_err,
                  rrect_geom)


# ------------------------------------------------------------------ outline model

class Outline:
    def __init__(self, pieces, step=0.1):
        self.pieces = pieces
        pts, par, idx = [], [], []
        s0 = 0.0
        self.starts = []
        self.tables = []                    # per piece: (cumulative length array, param array)
        for k, pc in enumerate(pieces):
            if pc[0] == "L":
                p0, p1 = np.asarray(pc[1], float), np.asarray(pc[2], float)
                L = float(np.hypot(*(p1 - p0)))
                m = max(2, int(math.ceil(L / step)) + 1)
                u = np.linspace(0, 1, m)
                P = p0[None] + u[:, None] * (p1 - p0)[None]
                cum = u * L
                prm = u
            else:
                th = np.linspace(pc[5], pc[6], max(8, int(math.ceil(_arc_len_est(pc) / step)) + 1))
                P = _ell_pts(pc, th)
                d = np.sqrt((np.diff(P, axis=0) ** 2).sum(1))
                cum = np.concatenate([[0.0], np.cumsum(d)])
                prm = th
            self.starts.append(s0)
            self.tables.append((cum, prm))
            pts.append(P)
            par.append(s0 + cum)
            idx.append(np.full(len(P), k))
            s0 += cum[-1]
        self.length = s0
        self.P = np.vstack(pts)
        self.S = np.concatenate(par)
        self.K = np.concatenate(idx)

    def point(self, s):
        s = s % self.length
        k = int(np.searchsorted(self.starts, s, side="right") - 1)
        return self._piece_point(k, s - self.starts[k])

    def _piece_point(self, k, ds):
        pc = self.pieces[k]
        cum, prm = self.tables[k]
        if pc[0] == "L":
            p0, p1 = np.asarray(pc[1], float), np.asarray(pc[2], float)
            L = cum[-1]
            u = 0.0 if L <= 0 else min(max(ds / L, 0.0), 1.0)
            return p0 + u * (p1 - p0)
        th = float(np.interp(ds, cum, prm))
        return _ell_pts(pc, np.array([th]))[0]

    def _piece_param(self, k, ds):
        cum, prm = self.tables[k]
        return float(np.interp(ds, cum, prm))

    def project(self, p):
        """Arclength parameter of the outline point nearest to p, and its distance."""
        d = ((self.P - np.asarray(p, float)[None]) ** 2).sum(1)
        i = int(np.argmin(d))
        k = int(self.K[i])
        pc = self.pieces[k]
        s = float(self.S[i])
        if pc[0] == "L":                    # exact projection on the segment
            p0, p1 = np.asarray(pc[1], float), np.asarray(pc[2], float)
            v = p1 - p0
            L2 = float((v * v).sum())
            u = 0.0 if L2 <= 0 else min(max(float(((np.asarray(p) - p0) * v).sum()) / L2, 0.0), 1.0)
            s = self.starts[k] + u * math.sqrt(L2)
        return s % self.length, math.sqrt(float(d[i]))

    def dist(self, Q):
        """Approximate distance of points Q to the outline (dense sampling, chunked)."""
        out = np.empty(len(Q))
        for a in range(0, len(Q), 512):
            d = ((Q[a:a + 512, None, :] - self.P[None]) ** 2).sum(-1)
            out[a:a + 512] = np.sqrt(d.min(1))
        return out

    def segs_between(self, s0, s1, full=False):
        """Geometry dict following the outline clockwise from s0 to s1."""
        Lt = self.length
        s0 %= Lt
        span = (s1 - s0) % Lt
        if full or (span < 1e-9 and full):
            span = Lt
        start = self.point(s0)
        segs = []
        s = s0
        remaining = span
        k = int(np.searchsorted(self.starts, s, side="right") - 1)
        guard = 0
        while remaining > 1e-9 and guard < 4 * len(self.pieces) + 4:
            guard += 1
            pc_len = self.tables[k][0][-1]
            local = s - self.starts[k]
            take = min(remaining, pc_len - local)
            if take > 1e-9:
                end_local = local + take
                endp = self._piece_point(k, end_local)
                pc = self.pieces[k]
                if pc[0] == "L":
                    segs.append(("L", (float(endp[0]), float(endp[1]))))
                else:
                    t0 = self._piece_param(k, local)
                    t1 = self._piece_param(k, end_local)
                    dth = t1 - t0
                    if dth > 1.9 * math.pi:     # SVG arcs cannot be (nearly) full: split in two
                        tm = t0 + dth / 2
                        pm = _ell_pts(pc, np.array([tm]))[0]
                        segs.append(("A", pc[2], pc[3], math.degrees(pc[4]), 0, 1, (float(pm[0]), float(pm[1]))))
                        dth /= 2
                    segs.append(("A", pc[2], pc[3], math.degrees(pc[4]), int(dth > math.pi), 1,
                                 (float(endp[0]), float(endp[1]))))
                remaining -= take
                s = (s + take) % Lt
            k = (k + 1) % len(self.pieces)
            if take <= 1e-9:
                s = self.starts[k]
        if not segs:
            segs.append(("L", (float(start[0]), float(start[1]))))
        return {"start": (float(start[0]), float(start[1])), "segs": segs}


def _ell_pts(pc, th):
    c, a, b, rot = pc[1], pc[2], pc[3], pc[4]
    cr, sr = math.cos(rot), math.sin(rot)
    x, y = a * np.cos(th), b * np.sin(th)
    return np.column_stack([c[0] + x * cr - y * sr, c[1] + x * sr + y * cr])


def _arc_len_est(pc):
    a, b = pc[2], pc[3]
    return max(a, b) * abs(pc[6] - pc[5])


def outline_from_prim(prim):
    """Clockwise outline pieces for a primitive dict (circle / ellipse / rect / polygon)."""
    t = prim["type"]
    if t in ("circle", "ellipse"):
        if t == "circle":
            a = b = prim["r"]
            rot = 0.0
        else:
            a, b, rot = prim["rx"], prim["ry"], math.radians(prim.get("angle", 0.0))
        return Outline([("E", (prim["cx"], prim["cy"]), a, b, rot, 0.0, 2 * math.pi)])
    if t == "rect":
        cx, cy, w, h, r = prim["cx"], prim["cy"], prim["w"], prim["h"], prim.get("r", 0.0)
        ang = math.radians(prim.get("angle", 0.0))
        c, s = math.cos(ang), math.sin(ang)

        def T(x, y):
            return (cx + x * c - y * s, cy + x * s + y * c)
        hw, hh = w / 2, h / 2
        if r < 0.05:
            pts = [T(-hw, -hh), T(hw, -hh), T(hw, hh), T(-hw, hh)]
            return Outline([("L", pts[i], pts[(i + 1) % 4]) for i in range(4)])
        pieces = []
        # top edge, top-right arc, right edge, bottom-right arc, ... (clockwise on screen)
        corners = [((hw - r, -hh + r), -math.pi / 2), ((hw - r, hh - r), 0.0),
                   ((-hw + r, hh - r), math.pi / 2), ((-hw + r, -hh + r), math.pi)]
        edges = [((-hw + r, -hh), (hw - r, -hh)), ((hw, -hh + r), (hw, hh - r)),
                 ((hw - r, hh), (-hw + r, hh)), ((-hw, hh - r), (-hw, -hh + r))]
        for (e0, e1), (cc, th0) in zip(edges, corners):
            if math.hypot(e1[0] - e0[0], e1[1] - e0[1]) > 1e-6:
                pieces.append(("L", T(*e0), T(*e1)))
            pieces.append(("E", T(*cc), r, r, ang, th0, th0 + math.pi / 2))
        return Outline(pieces)
    if t == "polygon":
        pts = [tuple(p) for p in prim["points"]]
        return Outline([("L", pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))])
    raise ValueError(t)


# ------------------------------------------------------------------ polygon model

def _seg_dist(Q, a, b):
    v = b - a
    L2 = float((v * v).sum())
    if L2 <= 1e-12:
        return np.sqrt(((Q - a) ** 2).sum(1))
    u = np.clip(((Q - a) * v).sum(1) / L2, 0, 1)
    return np.sqrt(((Q - (a + u[:, None] * v)) ** 2).sum(1))


def polygon_dist(Q, V):
    d = np.full(len(Q), np.inf)
    for i in range(len(V)):
        d = np.minimum(d, _seg_dist(Q, V[i], V[(i + 1) % len(V)]))
    return d


def _run_line(S, a, b, tol, trim):
    n = len(S)
    idx = np.arange(a, b if b > a else b + n) % n
    P = S[idx]
    if len(P) > 2 * trim + 2:
        P = P[trim:len(P) - trim]
    if len(P) < 2:
        return None
    c, d = _line_fit(P)
    res = np.abs((P[:, 0] - c[0]) * d[1] - (P[:, 1] - c[1]) * d[0])
    if robust_err(res) > tol:
        return None
    return c, d


def _poly_from_corners(S, cs, tol, trim=2, cache=None):
    """Polygon whose edges are TLS lines through the runs between corner indices cs. (V, err) or None.

    cache: optional dict memoising the per-run line fits (keyed by run end points); the greedy vertex
    removal in fit_polygon re-evaluates the same runs O(corners^2) times."""
    m = len(cs)
    if m < 3:
        return None
    lines = []
    for i in range(m):
        key = (cs[i], cs[(i + 1) % m])
        if cache is not None and key in cache:
            ln = cache[key]
        else:
            ln = _run_line(S, key[0], key[1], tol, trim)
            if cache is not None:
                cache[key] = ln
        if ln is None:
            return None
        lines.append(ln)
    V = []
    for i in range(m):
        (c0, d0), (c1, d1) = lines[i - 1], lines[i]
        den = d0[0] * d1[1] - d0[1] * d1[0]
        if abs(den) < 1e-6:
            return None
        t = ((c1[0] - c0[0]) * d1[1] - (c1[1] - c0[1]) * d1[0]) / den
        V.append(c0 + t * d0)
    V = np.array(V)
    return V, robust_err(polygon_dist(S, V))


def fit_polygon(S, opts, max_vertices=16):
    """Straight-edged closed polygon through samples S (closed, region on the right).

    Corners are detected with a permissive angle; vertices are line-line intersections of TLS
    lines through the corner-to-corner runs. Model selection: vertices are removed greedily while
    the polygon still explains the samples (robust error <= prim_tol, increase <= 0.1 px), so
    spurious corners (junction bumps, blurred tips) disappear. Returns (vertices (k,2), error) or None."""
    n = len(S)
    if n < 12:
        return None
    per = _arclen(S, True)[1]
    k = min(opts.get("corner_scale", 3.0), max(1.0, per / 16.0))
    cs = detect_corners(S, True, opts.get("poly_corner_angle", 25.0), k)
    if len(cs) < 3 or len(cs) > 2 * max_vertices:
        return None
    tol = opts.get("prim_tol", 0.75)
    cs = list(cs)

    dcache = {}

    def run_dir(a, b):
        if (a, b) in dcache:
            return dcache[a, b]
        idx = np.arange(a, b if b > a else b + n) % n
        P = S[idx]
        if len(P) >= 3:
            r = _line_fit(P)[1]
        else:
            d = S[b % n] - S[a]
            L = math.hypot(*d)
            r = d / L if L > 1e-9 else np.array([1.0, 0.0])
        dcache[a, b] = r
        return r
    # 1) merge nearly collinear neighbouring runs (staircase noise on diagonal edges)
    while len(cs) > 3:
        dirs = [run_dir(cs[i], cs[(i + 1) % len(cs)]) for i in range(len(cs))]
        angs = [math.degrees(math.acos(min(1.0, abs(float(dirs[i - 1] @ dirs[i]))))) for i in range(len(cs))]
        i = int(np.argmin(angs))
        if angs[i] >= 15.0:
            break
        del cs[i]
    # 2) greedy vertex removal while the polygon still explains the samples
    cache = {}
    cur = _poly_from_corners(S, cs, tol, cache=cache)
    if cur is None and len(cs) > 8:
        return None                      # not a polygon (cost guard: greedy search is O(corners^2))
    while len(cs) > 3:
        best = None
        for i in range(len(cs)):
            cand = cs[:i] + cs[i + 1:]
            r = _poly_from_corners(S, cand, tol, cache=cache)
            if r is not None and (best is None or r[1] < best[1][1]):
                best = (cand, r)
        if best is None:
            break
        if cur is None or best[1][1] <= min(tol, cur[1] + 0.1):
            cs, cur = best
        else:
            break
    if cur is None or len(cs) > max_vertices:
        return None
    V, err = cur
    if err > tol:
        return None
    for i in range(len(V)):
        if math.hypot(*(V[i] - S[cs[i]])) > max(3.0, 0.15 * per / len(V)):
            return None
    el = np.sqrt(((np.roll(V, -1, 0) - V) ** 2).sum(1))
    if el.min() < 3.0:
        return None
    if _is_cw(V) != _is_cw(S):
        return None
    try:
        from shapely.geometry import Polygon
        if not Polygon(V).is_valid:
            return None
    except Exception:
        pass
    return V, err


def _solidity(S):
    from scipy.spatial import ConvexHull
    x, y = S[:, 0], S[:, 1]
    area = abs(0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y)))
    try:
        hull = ConvexHull(S).volume
    except Exception:
        return 0.0
    return area / hull if hull > 0 else 0.0


def choose_loop_primitive(S, opts):
    """Primitive model selection for a closed loop of samples. Returns (prim, err) or None."""
    cands = []
    # cost gate: ellipses and (rounded) rectangles are convex
    res = choose_closed_primitive(S, opts) if _solidity(S) >= 0.9 else None
    if res is not None:
        prim, _, err = res
        cands.append((err, 0, prim))
    if opts.get("prim_polygons", True):
        pg = fit_polygon(S, opts)
        if pg is not None:
            V, err = pg
            if not (len(V) == 4 and cands and cands[0][2]["type"] == "rect"):
                # complexity penalty per vertex (a fine polygon must not replace a circle / rect)
                cands.append((err + 0.02 * len(V), 1, {"type": "polygon", "points": [tuple(map(float, v)) for v in V]}))
    if not cands:
        return None
    err, _, prim = min(cands, key=lambda c: (c[0], c[1]))
    return prim, err


# ------------------------------------------------------------------ region loops

def loop_samples(chains, loop):
    """Concatenate the fitting samples of a loop's chains in loop orientation (no duplicates)."""
    parts = []
    for cid, rev in loop:
        S = chains[cid].samples
        if S is None:
            return None
        if rev:
            S = S[::-1]
        parts.append(S[:-1] if len(loop) > 1 else S)
    return np.vstack(parts)


def _vkey(p):
    return (int(round(p[0])), int(round(p[1])))


def _flatten(g, n=6):
    pts = [np.asarray(g["start"], float)]
    cur = pts[0]
    for s in g["segs"]:
        end = np.asarray(s[-1], float)
        if s[0] == "C":
            c1, c2 = np.asarray(s[1]), np.asarray(s[2])
            for t in np.linspace(0, 1, n + 1)[1:]:
                mt = 1 - t
                pts.append(mt ** 3 * cur + 3 * mt * mt * t * c1 + 3 * mt * t * t * c2 + t ** 3 * end)
        else:
            for t in np.linspace(0, 1, n + 1)[1:]:      # arcs: chord points are enough for a tolerance check
                pts.append(cur + t * (end - cur))
        cur = end
    return np.array(pts)


def _move_end(g, at_start, newp):
    newp = (float(newp[0]), float(newp[1]))
    segs = list(g["segs"])
    if at_start:
        old = np.asarray(g["start"], float)
        dl = np.asarray(newp) - old
        if segs and segs[0][0] == "C":
            c1 = tuple(np.asarray(segs[0][1]) + dl)
            segs[0] = ("C", c1, segs[0][2], segs[0][3])
        return {"start": newp, "segs": segs}
    last = segs[-1]
    old = np.asarray(last[-1], float)
    dl = np.asarray(newp) - old
    if last[0] == "C":
        segs[-1] = ("C", last[1], tuple(np.asarray(last[2]) + dl), newp)
    else:
        segs[-1] = last[:-1] + (newp,)
    return {"start": g["start"], "segs": segs}


def sharpen_blurred_rect(prim, rid, ctx, opts):
    """Sharp vs rounded corners in the presence of blur (scale-aware model selection).

    The iso-contour of a blurred *sharp* corner is rounded with radius ~1.9 sigma, so a small fitted
    radius is no evidence of a rounded design corner. If the fitted radius is below
    `blur_sharp_ratio` x the measured edge spread of the same rectangle and the sharp model is
    acceptable, the sharp rectangle is returned instead."""
    ratio = opts.get("blur_sharp_ratio", 0.0)
    alt = prim.get("alt_sharp")
    if not ratio or prim.get("type") != "rect" or prim.get("r", 0.0) <= 0 or alt is None or ctx is None:
        return prim
    if alt.get("err", 1e9) > opts.get("prim_tol", 0.75) + 0.15:
        return prim
    sg = edge_blur_sigma(prim, rid, ctx)
    if sg is None or prim["r"] >= ratio * sg[0]:
        return prim
    q = {"type": "rect", **{k: alt[k] for k in ("cx", "cy", "w", "h", "angle")}, "r": 0.0, "err": alt["err"],
         "err0": alt["err"]}
    if abs(q["angle"]) < 0.75:
        q["angle"] = 0.0
    return q


def snap_region_primitives(regions, chains, opts, drawn, shape=None, ctx=None):
    """Detect primitives on multi-chain outer loops and snap the loop's chains to them.

    Returns {region id: prim dict}. Chains of accepted loops get .snapped=True and new geometry;
    chains touching a moved junction get their end points moved accordingly."""
    min_len = opts.get("region_prim_min_len", 24)
    validate = opts.get("geom_repair", False)
    fcache = {}
    max_shift = opts.get("region_prim_max_shift", 1.5)
    out = {}
    # incident open-chain ends per junction vertex
    inc = {}
    for cid, c in enumerate(chains):
        if c.closed or c.geom is None:
            continue
        inc.setdefault(_vkey(c.pts[0]), []).append((cid, True))
        inc.setdefault(_vkey(c.pts[-1]), []).append((cid, False))
    moved = {}                           # vertex key -> new position
    cand = [r for r in regions if r.label >= 0 and drawn[r.rid] and r.loops and r.area >= 30]
    cand.sort(key=lambda r: -r.area)
    for r in cand:
        loop = r.loops[r.outer]
        if len(loop) == 1:
            c = chains[loop[0][0]]
            if c.prim is not None and c.prim.get("type") == "rect" and c.prim.get("r", 0) > 0 and ctx is not None:
                q = sharpen_blurred_rect(c.prim, r.rid, ctx, opts)
                if q is not c.prim:
                    g = rrect_geom(q)
                    c.geom = g if _is_cw(c.samples) else reverse_geom(g)
                    c.prim = q
                continue
            if c.prim is not None or not opts.get("prim_polygons", True) or c.samples is None or len(c.samples) < 12:
                continue
            if c.snapped:
                continue
            S = c.samples[::-1] if loop[0][1] else c.samples
            pg = fit_polygon(S, opts)
            if pg is None:
                continue
            V, _ = pg
            prim = {"type": "polygon", "points": [tuple(map(float, v)) for v in V]}
            g = {"start": prim["points"][0], "segs": [("L", p) for p in prim["points"][1:] + prim["points"][:1]]}
            c.geom = reverse_geom(g) if loop[0][1] else g
            c.snapped = True
            out[r.rid] = prim
            continue
        if any(chains[cid].geom is None for cid, _ in loop) or len({cid for cid, _ in loop}) != len(loop):
            continue
        S = loop_samples(chains, loop)
        if S is None or len(S) < min_len:
            continue
        if shape is not None and (S.min() <= 0.5 or (S[:, 0] >= shape[1] - 0.5).any() or (S[:, 1] >= shape[0] - 0.5).any()):
            continue                    # clipped by the canvas: not a primitive
        res = choose_loop_primitive(S, opts)
        if res is None:
            continue
        prim, err = res
        if ctx is not None:
            prim = sharpen_blurred_rect(prim, r.rid, ctx, opts)
        ol = outline_from_prim(prim)
        # junction vertices of the loop (start of every chain in loop orientation)
        verts = []
        for cid, rev in loop:
            c = chains[cid]
            verts.append(c.pts[-1] if rev else c.pts[0])
        params, newpos, ok = [], [], True
        for v in verts:
            key = _vkey(v)
            if key in moved:
                s, d = ol.project(moved[key])
                if d > 0.35:
                    ok = False
                    break
                params.append(s)
                newpos.append(moved[key])
            else:
                s, d = ol.project(v)
                if d > max_shift:
                    ok = False
                    break
                params.append(s)
                newpos.append(ol.point(s))
        if not ok:
            continue
        # cyclic order of the junctions along the outline must match the loop order (one turn)
        m = len(params)
        tot = sum((params[(i + 1) % m] - params[i]) % ol.length for i in range(m))
        if abs(tot - ol.length) > 1e-3 * ol.length + 1e-6:
            continue
        new_geoms = {}
        for i, (cid, rev) in enumerate(loop):
            c = chains[cid]
            s0, s1 = params[i], params[(i + 1) % m]
            g = ol.segs_between(s0, s1)
            # exact shared end points (moved junction positions)
            g = _move_end(_move_end(g, True, newpos[i]), False, newpos[(i + 1) % m])
            if rev:
                g = reverse_geom(g)
            if c.snapped:                       # already snapped by a neighbour primitive: must agree
                A = _flatten(c.geom)
                if ol.dist(A).max() > 0.35:
                    ok = False
                    break
                continue
            new_geoms[cid] = g
        if not ok:
            continue
        # tentative application (kept only if no neighbouring outline starts to self-cross)
        loop_cids = {cid for cid, _ in loop}
        changes = dict(new_geoms)
        new_moved = {}
        for v, p in zip(verts, newpos):
            key = _vkey(v)
            if key in moved or key in new_moved:
                continue
            new_moved[key] = p
            for cid, at_start in inc.get(key, []):
                if cid in loop_cids:
                    continue
                c = chains[cid]
                changes[cid] = _move_end(changes.get(cid, c.geom), at_start, p)
        if validate and not _snap_keeps_valid(changes, set(new_geoms), chains, regions, drawn, fcache):
            continue
        for cid, g in changes.items():
            chains[cid].geom = g
        for cid in new_geoms:
            chains[cid].snapped = True
        moved.update(new_moved)
        out[r.rid] = prim
    return out


def _snap_keeps_valid(changes, protected, chains, regions, drawn, fcache):
    """True if no outline of a region touching the changed chains turns from simple into self-crossing."""
    from .validity import _ring_ok, flatten_geom, split_pinches

    def fl(cid, g):
        hit = fcache.get(cid)
        if hit is not None and hit[0] is g:
            return hit[1]
        P = flatten_geom(g)
        fcache[cid] = (g, P)
        return P
    rids = set()
    for cid in changes:
        c = chains[cid]
        for rr in (c.left, c.right):
            if rr >= 0 and drawn[rr]:
                rids.add(rr)

    def ring(loop, geoms):
        parts = []
        for cid, rev in loop:
            g = geoms.get(cid)
            P = flatten_geom(g) if g is not None else fl(cid, chains[cid].geom)
            if rev:
                P = P[::-1]
            parts.append(P[:-1] if len(loop) > 1 else P)
        return np.vstack(parts)
    for rr in rids:
        for lp in regions[rr].loops:
            if not any(cid in changes for cid, _ in lp):
                continue
            for sub in split_pinches(lp, chains):
                if not any(cid in changes for cid, _ in sub):
                    continue
                if any(chains[cid].geom is None for cid, _ in sub):
                    continue
                if _ring_ok(ring(sub, {})) and not _ring_ok(ring(sub, changes)):
                    if _is_sliver(regions[rr], chains):
                        continue                 # a thin AA/JPEG sliver along the shape: its valid parts are emitted
                    if not _repairable(sub, changes, protected, chains, ring):
                        return False
    return True


def _is_sliver(region, chains, max_thickness=2.0, max_area=30):
    """Small or thin region (mean thickness = area / half perimeter of the lattice outline)."""
    if region.area <= max_area:
        return True
    per = 0.0
    for lp in region.loops:
        for cid, _ in lp:
            per += len(chains[cid].pts) - 1
    return per > 0 and region.area / (0.5 * per) < max_thickness


def _repairable(sub, changes, protected, chains, ring):
    """Would the loop be simple again if its ordinary (non-primitive) crossing chains became raw polylines?
    (That is what the validity repair does later; only crossings among exact primitive edges are fatal.)"""
    from types import SimpleNamespace

    from .validity import _culprits, _polyline_geom, _ring_ok, flatten_geom
    geoms = dict(changes)
    cul = _culprits(sub, lambda cid: flatten_geom(geoms.get(cid, chains[cid].geom)))
    cand = [cid for cid, _ in sub] if cul is None else list(cul)
    fixed = False
    for cid in cand:
        c = chains[cid]
        if c.snapped or c.prim is not None or cid in protected:
            continue
        tmp = SimpleNamespace(pts=c.pts, closed=c.closed, samples=c.samples, geom=geoms.get(cid, c.geom))
        geoms[cid] = _polyline_geom(tmp, raw=True)
        fixed = True
    return fixed and _ring_ok(ring(sub, geoms))


# ------------------------------------------------------------------ blur-invariant corner radius

def corner_radius_mass(prim, rid, ctx, depth=3.0):
    """Corner radius of a (rounded) rectangle from anti-aliased coverage, independent of blur.

    Blur rounds the iso-contour of a sharp corner (apparent radius ~1.9 sigma), so the radius of
    the fitted boundary is biased. Coverage *mass* is preserved by blur instead: per unit edge
    length the inside of a blurred straight edge misses k = sum(1 - alpha) (measured on the four
    edges, away from the corners); an L x L corner window of a corner with radius r misses
    2 L k - k^2 + (1 - pi/4) r^2. Coverage alpha = unmixing of the (OKLab) pixel between the
    region colour and its outer neighbour colour. Returns (radius, n_corners_used) or None.
    """
    R, rl, lab, pal = ctx["R"], ctx["region_label"], ctx["lab"], ctx["pal_lab"]
    H, W = R.shape
    cx, cy, w, h = prim["cx"], prim["cy"], prim["w"], prim["h"]
    ang = math.radians(prim.get("angle", 0.0))
    hw, hh = w / 2, h / 2
    r_fit = prim.get("r", 0.0)
    L = max(5.0, 1.5 * r_fit + 3.0)
    if min(hw, hh) < L + 2:
        L = min(hw, hh) - 2
    if L < 3:
        return None
    c, s = math.cos(ang), math.sin(ang)
    x0, x1 = int(max(0, math.floor(cx - hw * abs(c) - hh * abs(s) - 3))), int(min(W, math.ceil(cx + hw * abs(c) + hh * abs(s) + 3)))
    y0, y1 = int(max(0, math.floor(cy - hw * abs(s) - hh * abs(c) - 3))), int(min(H, math.ceil(cy + hw * abs(s) + hh * abs(c) + 3)))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1]
    px, py = xx + 0.5 - cx, yy + 0.5 - cy
    u = px * c + py * s                   # rect-local coordinates of pixel centres
    v = -px * s + py * c
    Rw = R[y0:y1, x0:x1]
    inside_lbl = rl[rid]
    # outside neighbour colour: dominant region label in a thin ring just outside the rect
    ring = (np.maximum(np.abs(u) - hw, np.abs(v) - hh) > 0.6) & (np.maximum(np.abs(u) - hw, np.abs(v) - hh) < 1.6)
    if not ring.any():
        return None
    lab_ring = rl[Rw[ring]]
    lab_ring = lab_ring[lab_ring >= 0]
    if len(lab_ring) == 0:
        return None
    vals, cnt = np.unique(lab_ring, return_counts=True)
    out_lbl = int(vals[np.argmax(cnt)])
    if out_lbl == inside_lbl or inside_lbl < 0:
        return None
    ca, cb = pal[out_lbl], pal[inside_lbl]
    dcol = cb - ca
    L2 = float((dcol * dcol).sum())
    if L2 < 0.05 ** 2:
        return None
    alpha = np.clip(((lab[y0:y1, x0:x1] - ca) * dcol).sum(-1) / L2, 0.0, 1.0)
    # ignore pixels of unrelated regions (holes / text inside the box): only the region and its outside label
    use = (rl[Rw] == inside_lbl) | (rl[Rw] == out_lbl)
    du, dv = hw - np.abs(u), hh - np.abs(v)   # distance inside from the nearest vertical / horizontal edge
    miss = (1.0 - alpha) * use
    # edge leakage per unit length (strips along the 4 edges, away from the corners)
    ks = []
    for dd, along, half in ((du, dv, hh), (dv, du, hw)):
        strip = (dd >= -0.5) & (dd < depth) & (along > L + 1.0)
        n_len = 2 * 2 * max(half - L - 1.0, 0.0)          # two edges of this orientation
        if n_len >= 4:
            ks.append(float(miss[strip].sum()) / n_len)
    if not ks:
        return None
    k = float(np.mean(ks))
    # corner windows [0, L]^2 (from the edge lines inwards), one per quadrant
    rs = []
    win = (du >= -0.5) & (dv >= -0.5) & (du < L) & (dv < L)
    for su in (-1, 1):
        for sv in (-1, 1):
            q = win & (np.sign(u) == su) & (np.sign(v) == sv)
            if q.sum() < 0.5 * L * L:
                continue
            if (~use[q]).mean() > 0.1:
                continue                       # something else sits in this corner
            D = float(miss[q].sum())
            Lu = L + 0.5
            r2 = (D - 2 * Lu * k + k * k) / (1 - math.pi / 4)
            rs.append(math.sqrt(max(r2, 0.0)))
    if len(rs) < 2:
        return None
    return float(np.median(rs)), len(rs)


def edge_blur_sigma(prim, rid, ctx, margin=None):
    """Edge spread (Gaussian sigma, px) of a rect's straight sides from the anti-aliased profile.

    Mean coverage profile across the four sides (bilinear OKLab samples unmixed between the
    region colour and the dominant outside colour) fitted with Phi((d - d0) / sigma)."""
    from scipy.ndimage import map_coordinates
    from scipy.special import ndtr
    R, rl, lab, pal = ctx["R"], ctx["region_label"], ctx["lab"], ctx["pal_lab"]
    cx, cy, w, h = prim["cx"], prim["cy"], prim["w"], prim["h"]
    ang = math.radians(prim.get("angle", 0.0))
    hw, hh = w / 2, h / 2
    r = prim.get("r", 0.0)
    m = margin if margin is not None else r + 3.0
    c, s = math.cos(ang), math.sin(ang)
    ds = np.linspace(-1.5, 1.5, 13)
    rows = []
    # sides: (point on side as function of t, outward normal) in local coords
    sides = []
    for sx in (-1, 1):
        L = hh - m
        if L > 2:
            t = np.arange(-L, L, 1.0)
            sides.append((np.column_stack([np.full_like(t, sx * hw), t]), np.array([sx, 0.0])))
    for sy in (-1, 1):
        L = hw - m
        if L > 2:
            t = np.arange(-L, L, 1.0)
            sides.append((np.column_stack([t, np.full_like(t, sy * hh)]), np.array([0.0, sy])))
    if not sides:
        return None
    inside = rl[rid]
    prof = []
    for P, nrm in sides:
        # local -> image (pixel centre convention: lab[y, x] sampled at (y - 0.5, x - 0.5))
        Q = P[:, None, :] + ds[None, :, None] * nrm[None, None, :]       # (n, k, 2), +d = outside
        X = cx + Q[..., 0] * c - Q[..., 1] * s
        Y = cy + Q[..., 0] * s + Q[..., 1] * c
        Xo = cx + (P[:, 0] + 2.0 * nrm[0]) * c - (P[:, 1] + 2.0 * nrm[1]) * s
        Yo = cy + (P[:, 0] + 2.0 * nrm[0]) * s + (P[:, 1] + 2.0 * nrm[1]) * c
        xi = np.clip(np.floor(Xo).astype(int), 0, R.shape[1] - 1)
        yi = np.clip(np.floor(Yo).astype(int), 0, R.shape[0] - 1)
        outl = rl[R[yi, xi]]
        vals, cnt = np.unique(outl[outl >= 0], return_counts=True)
        if len(vals) == 0:
            continue
        ol = int(vals[np.argmax(cnt)])
        if ol == inside:
            continue
        ca, cb = pal[ol], pal[inside]
        dcol = cb - ca
        L2 = float(dcol @ dcol)
        if L2 < 0.05 ** 2:
            continue
        smp = np.stack([map_coordinates(lab[..., k], [Y.ravel() - 0.5, X.ravel() - 0.5], order=1, mode="nearest")
                        for k in range(3)], -1).reshape(X.shape + (3,))
        a = np.clip(((smp - ca) * dcol).sum(-1) / L2, 0, 1)
        ok = outl == ol
        if ok.sum() >= 3:
            prof.append(a[ok])
    if not prof:
        return None
    A = np.vstack(prof)
    y = 1.0 - np.median(A, axis=0)                     # outside coverage rising with d
    best = None
    for sg in np.linspace(0.15, 2.5, 48):
        for d0 in np.linspace(-0.8, 0.8, 33):
            e = float(((ndtr((ds - d0) / sg) - y) ** 2).sum())
            if best is None or e < best[0]:
                best = (e, sg, d0)
    return best[1], best[2]
