"""Curve fitting for boundary chains (W3, W4).

Per chain:
  samples   = crack midpoints (+ fixed junction endpoints for open chains)
  corners   = scale-consistent turning-angle maxima (turn at scale k ~ turn at 2k)
  pieces    = corner-to-corner runs; each is a straight line if within `line_tol`,
              otherwise cubic Beziers (Schneider 1990 with Newton reparameterisation),
              G1-continuous at non-corner split points
  primitives: closed chains are tested for ellipse / circle / rectangle /
              rounded-rectangle fits before generic fitting.

Geometry representation: dict(start=(x, y), segs=[...]) with segments
  ('L', (x, y)) | ('C', (x1, y1), (x2, y2), (x, y)) | ('A', rx, ry, rot_deg, large, sweep, (x, y))
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage as ndi

# ------------------------------------------------------------------ samples / corners


def chain_samples(pts, closed):
    mids = 0.5 * (pts[:-1] + pts[1:])
    if closed:
        return mids
    return np.vstack([pts[:1], mids, pts[-1:]])


def _arclen(P, closed):
    d = np.sqrt(((P[1:] - P[:-1]) ** 2).sum(1))
    s = np.concatenate([[0.0], np.cumsum(d)])
    total = s[-1] + (math.hypot(*(P[0] - P[-1])) if closed else 0.0)
    return s, total


def turning(P, closed, L):
    """Turning angle (radians) at each sample measured with arms of arclength L."""
    n = len(P)
    s, total = _arclen(P, closed)
    if closed:
        ext = np.concatenate([s - total, s, s + total])
        Pe = np.vstack([P, P, P])
        i0 = np.searchsorted(ext, s + total - L)
        i1 = np.searchsorted(ext, s + total + L)
        i1 = np.minimum(i1, len(ext) - 1)
        a = Pe[i0] - P
        b = Pe[i1] - P
        valid = np.ones(n, bool)
    else:
        i0 = np.searchsorted(s, s - L)
        i1 = np.minimum(np.searchsorted(s, s + L), n - 1)
        a = P[i0] - P
        b = P[i1] - P
        valid = (s - L >= -1e-9) & (s + L <= s[-1] + 1e-9)
    na = np.sqrt((a ** 2).sum(1)) + 1e-12
    nb = np.sqrt((b ** 2).sum(1)) + 1e-12
    c = np.clip((a * b).sum(1) / (na * nb), -1, 1)
    t = math.pi - np.arccos(c)
    t[~valid] = 0.0
    return t


def detect_corners(P, closed, angle_deg=55.0, k=3.0, ratio=0.72):
    n = len(P)
    if n < 5:
        return []
    t1 = turning(P, closed, k)
    t2 = turning(P, closed, 2 * k)
    thr = math.radians(angle_deg)
    cand = (t1 > thr) & (t1 >= ratio * t2)
    if not cand.any():
        return []
    idx = np.nonzero(cand)[0]
    # non-maximum suppression within arclength k
    s, total = _arclen(P, closed)
    order = idx[np.argsort(-t1[idx])]
    taken = []
    for i in order.tolist():
        ok = True
        for j in taken:
            d = abs(s[i] - s[j])
            if closed:
                d = min(d, total - d)
            if d < 1.5 * k:
                ok = False
                break
        if ok:
            taken.append(i)
    if not closed:
        taken = [i for i in taken if 0 < i < n - 1]
    return sorted(taken)


# ------------------------------------------------------------------ bezier fitting

def _bez(ctrl, t):
    t = t[:, None]
    mt = 1 - t
    return (mt ** 3) * ctrl[0] + 3 * (mt ** 2) * t * ctrl[1] + 3 * mt * (t ** 2) * ctrl[2] + (t ** 3) * ctrl[3]


def _bez_d1(ctrl, t):
    t = t[:, None]
    mt = 1 - t
    return 3 * (mt ** 2) * (ctrl[1] - ctrl[0]) + 6 * mt * t * (ctrl[2] - ctrl[1]) + 3 * (t ** 2) * (ctrl[3] - ctrl[2])


def _bez_d2(ctrl, t):
    t = t[:, None]
    return 6 * (1 - t) * (ctrl[2] - 2 * ctrl[1] + ctrl[0]) + 6 * t * (ctrl[3] - 2 * ctrl[2] + ctrl[1])


def _chord_param(P):
    d = np.sqrt(((P[1:] - P[:-1]) ** 2).sum(1))
    s = np.concatenate([[0.0], np.cumsum(d)])
    return s / s[-1] if s[-1] > 0 else np.linspace(0, 1, len(P))


def _generate(P, u, t1, t2):
    p0, p3 = P[0], P[-1]
    b0 = (1 - u) ** 3
    b1 = 3 * u * (1 - u) ** 2
    b2 = 3 * u ** 2 * (1 - u)
    b3 = u ** 3
    A1 = b1[:, None] * t1
    A2 = b2[:, None] * t2
    C00 = (A1 * A1).sum()
    C01 = (A1 * A2).sum()
    C11 = (A2 * A2).sum()
    tmp = P - (b0 + b1)[:, None] * p0 - (b2 + b3)[:, None] * p3
    X0 = (A1 * tmp).sum()
    X1 = (A2 * tmp).sum()
    det = C00 * C11 - C01 * C01
    seg = math.hypot(*(p3 - p0))
    if abs(det) > 1e-12:
        a1 = (X0 * C11 - X1 * C01) / det
        a2 = (C00 * X1 - C01 * X0) / det
    else:
        a1 = a2 = seg / 3
    eps = 1e-6 * seg
    if a1 < eps or a2 < eps or a1 > 2 * seg or a2 > 2 * seg:
        a1 = a2 = seg / 3
    return np.array([p0, p0 + a1 * t1, p3 + a2 * t2, p3])


def _max_err(P, ctrl, u):
    d = ((_bez(ctrl, u) - P) ** 2).sum(1)
    i = int(np.argmax(d))
    return math.sqrt(d[i]), i


def _reparam(P, ctrl, u):
    q = _bez(ctrl, u) - P
    d1 = _bez_d1(ctrl, u)
    d2 = _bez_d2(ctrl, u)
    num = (q * d1).sum(1)
    den = (d1 * d1).sum(1) + (q * d2).sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        nu = np.where(np.abs(den) > 1e-12, u - num / den, u)
    nu = np.clip(nu, 0, 1)
    nu[0], nu[-1] = 0.0, 1.0
    return np.maximum.accumulate(nu)


def _unit(v):
    n = math.hypot(v[0], v[1])
    return v / n if n > 1e-12 else np.array([1.0, 0.0])


def _end_tangent(P, at_start, L=3.0):
    """Unit tangent at an end, pointing into the curve, estimated over arclength L."""
    Q = P if at_start else P[::-1]
    d = np.sqrt(((Q[1:] - Q[:-1]) ** 2).sum(1))
    s = np.cumsum(d)
    j = int(np.searchsorted(s, min(L, s[-1] * 0.5))) + 1
    j = min(max(j, 1), len(Q) - 1)
    return _unit(Q[j] - Q[0])


def fit_cubic(P, t1, t2, tol, depth=0):
    n = len(P)
    if n == 2 or depth > 12:
        dist = math.hypot(*(P[-1] - P[0])) / 3
        return [np.array([P[0], P[0] + t1 * dist, P[-1] + t2 * dist, P[-1]])]
    u = _chord_param(P)
    ctrl = _generate(P, u, t1, t2)
    err, idx = _max_err(P, ctrl, u)
    if err <= tol:
        return [ctrl]
    if err <= 4 * tol:
        for _ in range(6):
            u = _reparam(P, ctrl, u)
            ctrl = _generate(P, u, t1, t2)
            err, idx = _max_err(P, ctrl, u)
            if err <= tol:
                return [ctrl]
    idx = min(max(idx, 1), n - 2)
    tc = _unit(P[idx - 1] - P[idx + 1])
    return fit_cubic(P[:idx + 1], t1, tc, tol, depth + 1) + fit_cubic(P[idx:], -tc, t2, tol, depth + 1)


def _point_line_dist(P, a, b):
    d = b - a
    L = math.hypot(*d)
    if L < 1e-9:
        return np.sqrt(((P - a) ** 2).sum(1))
    return np.abs((P[:, 0] - a[0]) * d[1] - (P[:, 1] - a[1]) * d[0]) / L


def _smooth(P, sigma, closed):
    if sigma <= 0 or len(P) < 5:
        return P
    if closed:
        return ndi.gaussian_filter1d(P, sigma, axis=0, mode="wrap")
    Q = ndi.gaussian_filter1d(P, sigma, axis=0, mode="nearest")
    Q[0], Q[-1] = P[0], P[-1]
    return Q


def fit_piece(P, tol, line_tol, smooth_sigma, t_start=None, t_end=None, line_tls=0.45):
    """Fit samples between two break points. Returns list of segments (without start point)."""
    a, b = P[0], P[-1]
    if len(P) <= 3 or _point_line_dist(P, a, b).max() <= line_tol:
        return [("L", tuple(b))]
    if line_tls and line_tls > 0 and len(P) >= 6:
        # total-least-squares line through the interior (end samples may sit off a true corner)
        c, d = _line_fit(P[1:-1])
        res = np.abs((P[:, 0] - c[0]) * d[1] - (P[:, 1] - c[1]) * d[0])
        if res[1:-1].max() <= line_tls and res.max() <= 2 * line_tls:
            return [("L", tuple(b))]
    Q = _smooth(P, smooth_sigma, False)
    t1 = t_start if t_start is not None else _end_tangent(Q, True)
    t2 = t_end if t_end is not None else _end_tangent(Q, False)
    segs = []
    for c in fit_cubic(Q, t1, t2, tol):
        # degenerate cubic that is basically straight -> line
        if _point_line_dist(c[1:3], c[0], c[3]).max() < 0.15:
            segs.append(("L", tuple(c[3])))
        else:
            segs.append(("C", tuple(c[1]), tuple(c[2]), tuple(c[3])))
    return segs


def _line_fit(P):
    """Total least squares line: returns (point, unit direction)."""
    c = P.mean(0)
    u, s, vt = np.linalg.svd(P - c, full_matrices=False)
    return c, vt[0]


def _intersect(p1, d1, p2, d2):
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-6:
        return None
    t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
    return p1 + t * d1


# ------------------------------------------------------------------ primitives

def fit_ellipse(P):
    """Fitzgibbon direct least-squares ellipse. Returns (cx, cy, a, b, theta) or None."""
    x, y = P[:, 0], P[:, 1]
    mx, my = x.mean(), y.mean()
    sc = max(x.std(), y.std(), 1e-6)
    x = (x - mx) / sc
    y = (y - my) / sc
    D1 = np.column_stack([x * x, x * y, y * y])
    D2 = np.column_stack([x, y, np.ones_like(x)])
    S1, S2, S3 = D1.T @ D1, D1.T @ D2, D2.T @ D2
    try:
        T = -np.linalg.solve(S3, S2.T)
    except np.linalg.LinAlgError:
        return None
    Mm = S1 + S2 @ T
    Mm = np.array([Mm[2] / 2, -Mm[1], Mm[0] / 2])
    try:
        w, v = np.linalg.eig(Mm)
    except np.linalg.LinAlgError:
        return None
    v = np.real(v)
    cond = 4 * v[0] * v[2] - v[1] ** 2
    ok = np.nonzero(cond > 0)[0]
    if len(ok) == 0:
        return None
    a1 = v[:, ok[0]]
    A, B, C = a1
    Dd, E, F = T @ a1
    # conic: A x^2 + B xy + C y^2 + D x + E y + F = 0 (normalised coords)
    den = B * B - 4 * A * C
    if abs(den) < 1e-12:
        return None
    cx = (2 * C * Dd - B * E) / den
    cy = (2 * A * E - B * Dd) / den
    num = 2 * (A * E * E + C * Dd * Dd - B * Dd * E + den * F)
    root = math.sqrt((A - C) ** 2 + B * B)
    try:
        ra = -math.sqrt(num * (A + C + root)) / den
        rb = -math.sqrt(num * (A + C - root)) / den
    except ValueError:
        return None
    if not (np.isfinite(ra) and np.isfinite(rb)) or ra <= 0 or rb <= 0:
        return None
    if abs(B) < 1e-12:
        th = 0.0 if A < C else math.pi / 2
    else:
        th = math.atan2(C - A - root, B)
    return (cx * sc + mx, cy * sc + my, ra * sc, rb * sc, th)


def ellipse_dist(P, e, n=720):
    cx, cy, a, b, th = e
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    ct, st = math.cos(th), math.sin(th)
    ex = cx + a * np.cos(t) * ct - b * np.sin(t) * st
    ey = cy + a * np.cos(t) * st + b * np.sin(t) * ct
    E = np.column_stack([ex, ey])
    # chunked nearest distance
    out = np.empty(len(P))
    for s in range(0, len(P), 2048):
        d = ((P[s:s + 2048, None, :] - E[None]) ** 2).sum(-1)
        out[s:s + 2048] = np.sqrt(d.min(1))
    return out


def robust_err(d):
    """Primitive acceptance error: tolerant to a few noisy samples, not to real features."""
    d = np.abs(d)
    return float(max(np.percentile(d, 90), d.max() / 2.0))


def _rounded_rect_sd(Q, hw, hh, r):
    q = np.abs(Q) - np.array([hw - r, hh - r])
    outside = np.sqrt((np.maximum(q, 0) ** 2).sum(1))
    inside = np.minimum(np.maximum(q[:, 0], q[:, 1]), 0)
    return outside + inside - r


def _min_area_rect(P):
    from scipy.spatial import ConvexHull
    try:
        hull = P[ConvexHull(P).vertices]
    except Exception:
        return None
    best = None
    for i in range(len(hull)):
        e = hull[(i + 1) % len(hull)] - hull[i]
        ang = math.atan2(e[1], e[0])
        c, s = math.cos(ang), math.sin(ang)
        R = np.array([[c, s], [-s, c]])
        q = hull @ R.T
        mn, mx = q.min(0), q.max(0)
        area = (mx - mn).prod()
        if best is None or area < best[0]:
            ctr = ((mn + mx) / 2) @ R
            best = (area, ctr, (mx - mn), ang)
    return best


def fit_rounded_rect(P, tol, axis_aligned=False):
    """Return dict(cx, cy, w, h, r, angle_deg, err, err0) or None."""
    if len(P) < 8:
        return None
    if axis_aligned:
        mn, mx = P.min(0), P.max(0)
        ctr, wh, ang = (mn + mx) / 2, mx - mn, 0.0
    else:
        mar = _min_area_rect(P)
        if mar is None:
            return None
        _, ctr, wh, ang = mar
    # normalise angle to (-45, 45]
    w, h = float(wh[0]), float(wh[1])
    while ang > math.pi / 4:
        ang -= math.pi / 2
        w, h = h, w
    while ang <= -math.pi / 4:
        ang += math.pi / 2
        w, h = h, w
    c, s = math.cos(ang), math.sin(ang)
    Q = (P - ctr) @ np.array([[c, -s], [s, c]])
    hw, hh = w / 2, h / 2
    rmax = min(hw, hh)
    best = None
    for r in np.linspace(0, rmax, 41):
        e = robust_err(_rounded_rect_sd(Q, hw, hh, r))
        if best is None or e < best[1]:
            best = (r, e)
    r, e = best
    # local refine
    lo, hi = max(0, r - rmax / 40), min(rmax, r + rmax / 40)
    for r2 in np.linspace(lo, hi, 11):
        e2 = robust_err(_rounded_rect_sd(Q, hw, hh, r2))
        if e2 < e:
            r, e = r2, e2
    e0 = robust_err(_rounded_rect_sd(Q, hw, hh, 0.0))
    if min(e, e0) > tol:
        return None
    return {"cx": float(ctr[0]), "cy": float(ctr[1]), "w": w, "h": h, "r": float(r),
            "angle": math.degrees(ang), "err": float(e), "err0": e0}


def _fit_closed_primitive(chain, S, opts):
    """Model selection for a closed chain: ellipse/circle vs sharp rect vs rounded rect.

    Errors are max distances (px) of the smoothed boundary samples to the model. A sharp,
    axis-aligned rectangle gets a small preference (design prior; blur rounds small corners).
    Returns True if a primitive was assigned.
    """
    sig = opts.get("smooth_sigma", 1.0)
    ptol = opts.get("prim_tol", 0.75)
    Sm = _smooth(S, sig, True)
    cands = []
    e = fit_ellipse(Sm)
    if e is not None and min(e[2], e[3]) >= 2.5:
        d = ellipse_dist(Sm, e)
        if np.sqrt((d ** 2).mean()) <= 0.45 * ptol:
            cands.append((robust_err(d), "ellipse", e))
    rr = None
    for axis_only in (True, False):
        cand = fit_rounded_rect(S, ptol + 0.3, axis_aligned=axis_only)
        if cand is not None and (rr is None or min(cand["err"], cand["err0"]) < min(rr["err"], rr["err0"]) - 0.05):
            rr = cand
    if rr is not None:
        axis = abs(rr["angle"]) < 2.0
        small = min(rr["w"], rr["h"]) < 10
        bias = 0.15 if axis else 0.0
        tol0 = ptol + (0.3 if (axis and small) else 0.0)
        if min(rr["w"], rr["h"]) >= 2 and rr["err0"] <= tol0:
            cands.append((rr["err0"] - bias, "rect0", rr))
        if rr["r"] >= 0.75 and min(rr["w"], rr["h"]) >= 6 and rr["err"] <= ptol and rr["err"] < rr["err0"] - 0.1:
            cands.append((rr["err"], "rrect", rr))
    cands = [c for c in cands if c[0] <= ptol]
    if not cands:
        return False
    err, kind, m = min(cands, key=lambda c: c[0])
    if kind == "ellipse":
        cx, cy, a, b, th = m
        if abs(a - b) <= max(0.35, 0.015 * max(a, b)):
            r = (a + b) / 2
            m = (cx, cy, r, r, 0.0)
            chain.prim = {"type": "circle", "cx": cx, "cy": cy, "r": r}
        else:
            chain.prim = {"type": "ellipse", "cx": cx, "cy": cy, "rx": a, "ry": b, "angle": math.degrees(th)}
        chain.geom = ellipse_geom(m, _is_cw(S))
        return True
    rr = dict(m)
    if kind == "rect0":
        rr["r"] = 0.0
    if abs(rr["angle"]) < 0.75:
        rr["angle"] = 0.0
    if rr["r"] < 0.75:
        rr["r"] = 0.0
    chain.prim = {"type": "rect", **rr}
    g = rrect_geom(rr)
    if not _is_cw(S):
        g = reverse_geom(g)
    chain.geom = g
    return True


def ellipse_geom(e, ccw_region_right=True):
    """Closed path geometry for ellipse e=(cx,cy,a,b,th) as two arcs.

    Orientation: loops are stored with the region on the right; in y-down coordinates
    that is clockwise on screen == SVG sweep-flag 1.
    """
    cx, cy, a, b, th = e
    ct, st = math.cos(th), math.sin(th)
    p0 = (cx + a * ct, cy + a * st)
    p1 = (cx - a * ct, cy - a * st)
    sweep = 1 if ccw_region_right else 0
    rot = math.degrees(th)
    return {"start": p0, "segs": [("A", a, b, rot, 0, sweep, p1), ("A", a, b, rot, 0, sweep, p0)]}


def rrect_geom(rr):
    """Closed geometry (clockwise on screen) for a rounded rect dict."""
    cx, cy, w, h, r, ang = rr["cx"], rr["cy"], rr["w"], rr["h"], rr["r"], math.radians(rr["angle"])
    c, s = math.cos(ang), math.sin(ang)

    def T(x, y):
        return (cx + x * c - y * s, cy + x * s + y * c)
    hw, hh = w / 2, h / 2
    if r < 0.05:
        pts = [T(-hw, -hh), T(hw, -hh), T(hw, hh), T(-hw, hh)]
        return {"start": pts[0], "segs": [("L", pts[1]), ("L", pts[2]), ("L", pts[3]), ("L", pts[0])]}
    rot = rr["angle"]
    segs = []
    start = T(-hw + r, -hh)
    seq = [((hw - r, -hh), (hw, -hh + r)), ((hw, hh - r), (hw - r, hh)),
           ((-hw + r, hh), (-hw, hh - r)), ((-hw, -hh + r), (-hw + r, -hh))]
    for (lx, ly), (ax, ay) in seq:
        segs.append(("L", T(lx, ly)))
        segs.append(("A", r, r, rot, 0, 1, T(ax, ay)))
    return {"start": start, "segs": segs}


# ------------------------------------------------------------------ chain fitting

def fit_chain(chain, opts):
    """Populate chain.geom (and chain.prim for closed primitive chains)."""
    pts = chain.pts
    closed = chain.closed
    S = chain_samples(pts, closed)
    tol = opts.get("fit_tol", 0.6)
    line_tol = opts.get("line_tol", 0.65)
    sig = opts.get("smooth_sigma", 1.0)
    n = len(S)
    if not closed and n <= 4:
        chain.geom = {"start": tuple(pts[0]), "segs": [("L", tuple(pts[-1]))]}
        return
    if closed and opts.get("primitives", True) and n >= 12:
        if _fit_closed_primitive(chain, S, opts):
            return
    k = opts.get("corner_scale", 3.0)
    if closed:
        k = min(k, max(1.0, _arclen(S, True)[1] / 16.0))
    corners = detect_corners(S, closed, opts.get("corner_angle", 55.0), k)
    if closed:
        if not corners:
            # split smooth loop in 2 with G1 tangents
            k = [0, n // 2]
            Sm = _smooth(S, sig, True)
            tangents = {i: _unit(Sm[(i + 2) % n] - Sm[(i - 2) % n]) for i in k}
            segs = []
            for a_, b_ in ((k[0], k[1]), (k[1], n)):
                P = Sm[a_:b_ + 1] if b_ < n else np.vstack([Sm[a_:], Sm[:1]])
                segs += fit_piece(P, tol, line_tol, 0.0, tangents[a_ % n], -tangents[b_ % n])
            chain.geom = {"start": tuple(Sm[0]), "segs": segs}
            return
        r = corners[0]
        S = np.vstack([S[r:], S[:r], S[r:r + 1]])
        corners = sorted((c - r) % n for c in corners) + [n]
    else:
        corners = [0] + corners + [n - 1]
    pieces = []
    for a_, b_ in zip(corners[:-1], corners[1:]):
        P = S[a_:b_ + 1]
        pieces.append(fit_piece(P, tol, line_tol, sig, line_tls=opts.get("line_tls", 0.45)))
    # corner refinement: intersect adjacent straight pieces
    vertices = [S[c].copy() for c in corners]
    if opts.get("refine_corners", True):
        nseg = len(pieces)
        for j in range(1, nseg + (1 if closed else 0)):
            pa = pieces[j - 1]
            pb = pieces[j % nseg]
            if len(pa) == 1 and pa[0][0] == "L" and len(pb) == 1 and pb[0][0] == "L":
                A = S[corners[j - 1]:corners[j] + 1]
                jb = j % nseg
                B = S[corners[jb]:corners[jb + 1] + 1]
                if len(A) >= 4 and len(B) >= 4:
                    ca, da = _line_fit(A[1:-1] if len(A) > 4 else A)
                    cb, db = _line_fit(B[1:-1] if len(B) > 4 else B)
                    X = _intersect(ca, da, cb, db)
                    if X is not None and math.hypot(*(X - S[corners[j]])) < 1.5:
                        vertices[j] = X
                        if closed and j == nseg:
                            vertices[0] = X
        if closed:
            vertices[-1] = vertices[0]
    # endpoints of open chains are junctions: keep exact
    start = tuple(vertices[0]) if closed else tuple(pts[0])
    segs = []
    for j, pc in enumerate(pieces):
        end = tuple(vertices[j + 1]) if (closed or j + 1 < len(pieces)) else tuple(pts[-1])
        pc = list(pc)
        last = pc[-1]
        pc[-1] = (last[0],) + last[1:-1] + (end,)
        segs += pc
    chain.geom = {"start": start, "segs": segs}


def _is_cw(S):
    x, y = S[:, 0], S[:, 1]
    return (np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y)) > 0


def reverse_geom(g):
    pts = [g["start"]] + [s[-1] for s in g["segs"]]
    out = []
    for i in range(len(g["segs"]) - 1, -1, -1):
        s = g["segs"][i]
        prev = pts[i]
        if s[0] == "L":
            out.append(("L", prev))
        elif s[0] == "C":
            out.append(("C", s[2], s[1], prev))
        elif s[0] == "A":
            out.append(("A", s[1], s[2], s[3], s[4], 1 - s[5], prev))
    return {"start": pts[-1], "segs": out}
