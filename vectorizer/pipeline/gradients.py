"""Gradient detection and fitting (W6).

Quantisation turns smooth colour ramps into bands. Bands are recognised by *soft*
boundaries: across a soft boundary the input image changes by much less than the
palette step between the two regions (no real edge). Regions connected by soft
boundaries are grouped; each group is fitted with a linear or radial SVG gradient
(multi-stop profile along the principal direction / radius). A fit is accepted only
if its colour residual is small and clearly better than the banded representation.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from .color import hex_color, oklab_to_rgb8, rgb8_to_oklab


def _uf_find(p, i):
    while p[i] != i:
        p[i] = p[p[i]]
        i = p[i]
    return i


def soft_groups(R, lab, region_lab, step_ratio=0.7, max_step=0.2, min_pairs=4, span=2, max_edge_frac=0.15):
    """Union regions whose shared boundaries are soft.

    For every pair of 4-adjacent pixels on a region boundary the input colour change is
    measured over a wider span (from `span` px before to `span` px after the boundary).
    A real (anti-aliased or blurred) edge shows its full step there; a quantisation band
    inside a smooth ramp shows much less than the palette step between the two bands.
    """
    n = len(region_lab)
    H, W = R.shape
    P = np.pad(lab, ((span, span + 1), (span, span + 1), (0, 0)), mode="edge")
    pairs, vals = [], []
    # horizontal neighbours (y, x) | (y, x+1): compare lab[y, x-span] with lab[y, x+1+span]
    a, b = R[:, :-1], R[:, 1:]
    m = (a != b) & (a >= 0) & (b >= 0)
    if m.any():
        ys, xs = np.nonzero(m)
        d = P[ys + span, xs] - P[ys + span, xs + 1 + 2 * span]
        pairs.append((a[m].astype(np.int64), b[m].astype(np.int64)))
        vals.append(np.sqrt((d ** 2).sum(-1)))
    a, b = R[:-1], R[1:]
    m = (a != b) & (a >= 0) & (b >= 0)
    if m.any():
        ys, xs = np.nonzero(m)
        d = P[ys, xs + span] - P[ys + 1 + 2 * span, xs + span]
        pairs.append((a[m].astype(np.int64), b[m].astype(np.int64)))
        vals.append(np.sqrt((d ** 2).sum(-1)))
    parent = np.arange(n)
    if not pairs:
        return parent
    ra = np.concatenate([p[0] for p in pairs])
    rb = np.concatenate([p[1] for p in pairs])
    v = np.concatenate(vals)
    lo, hi = np.minimum(ra, rb), np.maximum(ra, rb)
    key = lo * n + hi
    uk, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    ulo, uhi = uk // n, uk % n
    pal_d = np.sqrt(((region_lab[ulo] - region_lab[uhi]) ** 2).sum(-1))
    step = np.bincount(inv, weights=v) / cnt
    edge_like = np.bincount(inv, weights=(v > pal_d[inv]).astype(np.float64)) / cnt
    soft = (cnt >= min_pairs) & (pal_d < max_step) & (step < step_ratio * pal_d) & (edge_like < max_edge_frac)
    for x, y in zip(ulo[soft].tolist(), uhi[soft].tolist()):
        rx, ry = _uf_find(parent, x), _uf_find(parent, y)
        if rx != ry:
            parent[ry] = rx
    for i in range(n):
        parent[i] = _uf_find(parent, i)
    return parent


def _profile_stops(t, cols, nbins=48, tol=1.2):
    """Piecewise-linear colour profile c(t), t in [0,1], simplified to few stops (tol in RGB units)."""
    bins = np.clip((t * nbins).astype(int), 0, nbins - 1)
    cnt = np.bincount(bins, minlength=nbins)
    ok = cnt > 0
    prof = np.zeros((nbins, 3))
    for c in range(3):
        prof[:, c] = np.bincount(bins, weights=cols[:, c], minlength=nbins)
    prof[ok] /= cnt[ok, None]
    tc = (np.arange(nbins) + 0.5) / nbins
    tc, prof = tc[ok], prof[ok]
    if len(tc) < 2:
        return [(0.0, prof[0]), (1.0, prof[0])]
    # Douglas-Peucker in (t, rgb) on colour error
    keep = {0, len(tc) - 1}

    def dp(i, j):
        if j <= i + 1:
            return
        tt = (tc[i + 1:j] - tc[i]) / max(tc[j] - tc[i], 1e-9)
        interp = prof[i] + tt[:, None] * (prof[j] - prof[i])
        err = np.abs(prof[i + 1:j] - interp).max(1)
        k = int(np.argmax(err))
        if err[k] > tol * 3:
            keep.add(i + 1 + k)
            dp(i, i + 1 + k)
            dp(i + 1 + k, j)
    dp(0, len(tc) - 1)
    idx = sorted(keep)
    stops = [(float(tc[i]), prof[i]) for i in idx]
    # extend the end stops to 0 and 1
    stops[0] = (0.0, stops[0][1])
    stops[-1] = (1.0, stops[-1][1])
    return stops


def _eval_stops(t, stops):
    ts = np.array([s[0] for s in stops])
    cs = np.array([s[1] for s in stops])
    out = np.zeros((len(t), 3))
    for c in range(3):
        out[:, c] = np.interp(t, ts, cs[:, c])
    return out


def fit_group(xy, rgb):
    """Fit linear and radial gradients to pixels (xy: (n,2) pixel centres, rgb float 0..255).

    Returns (kind, params, stops, rms_lab) of the better model.
    """
    n = len(xy)
    A = np.column_stack([np.ones(n), xy])
    coef, *_ = np.linalg.lstsq(A, rgb, rcond=None)
    G = coef[1:].T                                     # (3, 2) colour gradient per channel
    u, s, vt = np.linalg.svd(G)
    d = vt[0]
    lab_true = rgb8_to_oklab(rgb)
    res = []
    # linear
    t = xy @ d
    t0, t1 = t.min(), t.max()
    if t1 - t0 > 1e-6:
        tn = (t - t0) / (t1 - t0)
        st = _profile_stops(tn, rgb)
        pred = _eval_stops(tn, st)
        rms = float(np.sqrt(((rgb8_to_oklab(pred) - lab_true) ** 2).sum(-1).mean()))
        p0 = d * t0
        p1 = d * t1
        # make points lie on the line through the region centre
        ctr = xy.mean(0)
        off = ctr - d * (ctr @ d)
        res.append(("linear", (p0 + off, p1 + off), st, rms))
    # radial: quadratic luminance model for the centre
    L = lab_true[:, 0]
    Q = np.column_stack([np.ones(n), xy, (xy ** 2).sum(1)])
    q, *_ = np.linalg.lstsq(Q, L, rcond=None)
    if abs(q[3]) > 1e-9:
        cx, cy = -q[1] / (2 * q[3]), -q[2] / (2 * q[3])
        lo, hi = xy.min(0), xy.max(0)
        span = hi - lo
        if lo[0] - span[0] <= cx <= hi[0] + span[0] and lo[1] - span[1] <= cy <= hi[1] + span[1]:
            r = np.sqrt(((xy - [cx, cy]) ** 2).sum(1))
            R = r.max()
            if R > 1:
                tn = r / R
                st = _profile_stops(tn, rgb)
                pred = _eval_stops(tn, st)
                rms = float(np.sqrt(((rgb8_to_oklab(pred) - lab_true) ** 2).sum(-1).mean()))
                res.append(("radial", (np.array([cx, cy]), R), st, rms))
    if not res:
        return None
    return min(res, key=lambda r: r[3])


def gradient_defs(gid, kind, params, stops, prec=2):
    from .svgout import fmt
    st = "".join(f'<stop offset="{fmt(o, 3)}" stop-color="{hex_color(c)}"/>' for o, c in stops)
    if kind == "linear":
        (x1, y1), (x2, y2) = params
        return (f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{fmt(x1, prec)}" y1="{fmt(y1, prec)}" '
                f'x2="{fmt(x2, prec)}" y2="{fmt(y2, prec)}">{st}</linearGradient>')
    (cx, cy), R = params
    return (f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{fmt(cx, prec)}" cy="{fmt(cy, prec)}" '
            f'r="{fmt(R, prec)}">{st}</radialGradient>')


def apply_gradients(rgb, lbl, pal_lab, opts):
    """Detect banded ramps and replace them by gradient-filled regions.

    Returns (lbl_new, pal_lab_new, label_fill {label: (fill_attr, seam_paint)}, defs list).
    """
    from .boundary import label_regions
    H, W = lbl.shape
    lab = rgb8_to_oklab(rgb)
    R, rl = label_regions(lbl)
    n = len(rl)
    drawn = rl >= 0
    # region mean colour (OKLab) from the palette
    region_lab = np.where(drawn[:, None], pal_lab[np.maximum(rl, 0)], 0.0)
    parent = soft_groups(R, lab, region_lab, step_ratio=opts.get("grad_step_ratio", 0.7))
    parent[~drawn] = np.arange(n)[~drawn]
    roots, members = np.unique(parent, return_counts=True)
    groups = roots[members >= opts.get("grad_min_bands", 2)]
    if len(groups) == 0:
        return lbl, pal_lab, {}, []
    gid_of_region = parent
    lbl_new = lbl.copy()
    pal_new = [p for p in pal_lab]
    fills = {}
    defs = []
    tol = opts.get("grad_tol", 0.03)
    area = np.bincount(R.ravel() + 1, minlength=n + 1)[1:]
    yy, xx = np.mgrid[0:H, 0:W]
    rgbf = rgb.astype(np.float64)
    gcount = 0
    for g in groups.tolist():
        regs = np.nonzero(gid_of_region == g)[0]
        if not drawn[regs].all():
            continue
        if area[regs].sum() < opts.get("grad_min_area", 64):
            continue
        mask = np.isin(R, regs)
        ys, xs = yy[mask], xx[mask]
        if len(ys) > 40000:
            sel = np.random.default_rng(0).choice(len(ys), 40000, replace=False)
        else:
            sel = slice(None)
        xy = np.column_stack([xs[sel] + 0.5, ys[sel] + 0.5]).astype(np.float64)
        cols = rgbf[ys[sel], xs[sel]]
        fit = fit_group(xy, cols)
        if fit is None:
            continue
        kind, params, stops, rms = fit
        # banded error (current palette representation)
        band = pal_lab[lbl[ys[sel], xs[sel]]]
        rms_band = float(np.sqrt(((band - rgb8_to_oklab(cols)) ** 2).sum(-1).mean()))
        if rms > tol or rms > 0.85 * rms_band:
            continue
        gcount += 1
        gid = f"g{gcount}"
        defs.append(gradient_defs(gid, kind, params, stops, int(opts.get("precision", 2))))
        newl = len(pal_new)
        pal_new.append(rgb8_to_oklab(np.mean([s[1] for s in stops], axis=0)[None])[0])
        lbl_new[mask] = newl
        fills[newl] = (f'fill="url(#{gid})"', f"url(#{gid})")
    return lbl_new, np.array(pal_new, np.float32), fills, defs
