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
    """Fit linear, circular-radial and elliptical-radial gradients to pixels.

    xy: (n,2) pixel centres, rgb: (n,3) float 0..255. Returns (kind, params, stops, rms_lab, pred_lab)
    of the best model or None.
    """
    n = len(xy)
    lab_true = rgb8_to_oklab(rgb)
    res = []
    A = np.column_stack([np.ones(n), xy])
    coef, *_ = np.linalg.lstsq(A, rgb, rcond=None)
    G = coef[1:].T
    _, _, vt = np.linalg.svd(G)
    d = vt[0]

    def score(tn):
        st = _profile_stops(tn, rgb)
        pred = rgb8_to_oklab(_eval_stops(tn, st))
        err = np.sqrt(((pred - lab_true) ** 2).sum(-1))
        return st, float(np.sqrt((err ** 2).mean())), err

    t = xy @ d
    t0, t1 = t.min(), t.max()
    if t1 - t0 > 1e-6:
        st, rms, err = score((t - t0) / (t1 - t0))
        ctr = xy.mean(0)
        off = ctr - d * (ctr @ d)
        res.append(("linear", (d * t0 + off, d * t1 + off), st, rms, err))
    # elliptical / circular radial from a quadratic luminance model
    L = lab_true[:, 0]
    x, y = xy[:, 0] - xy[:, 0].mean(), xy[:, 1] - xy[:, 1].mean()
    Q = np.column_stack([np.ones(n), x, y, x * x, y * y, x * y])
    q, *_ = np.linalg.lstsq(Q, L, rcond=None)
    Mq = np.array([[q[3], q[5] / 2], [q[5] / 2, q[4]]])
    ev = np.linalg.eigvalsh(Mq)
    if np.all(ev > 1e-12) or np.all(ev < -1e-12):
        try:
            c = -0.5 * np.linalg.solve(Mq, q[1:3])
        except np.linalg.LinAlgError:
            c = None
        if c is not None:
            cx, cy = c + xy.mean(0)
            lo, hi = xy.min(0), xy.max(0)
            span = hi - lo
            if lo[0] - span[0] <= cx <= hi[0] + span[0] and lo[1] - span[1] <= cy <= hi[1] + span[1]:
                M = Mq / np.sign(ev[0])
                w, V = np.linalg.eigh(M)
                ratio = float(np.sqrt(w.max() / w.min()))
                dxy = xy - [cx, cy]
                for kind in (("radial",) if ratio < 1.05 else ("radial", "eradial")):
                    if kind == "radial":
                        r = np.sqrt((dxy ** 2).sum(1))
                        R = r.max()
                        if R > 1:
                            st, rms, err = score(r / R)
                            res.append(("radial", (np.array([cx, cy]), R), st, rms, err))
                    else:
                        u = dxy @ V                                    # principal axes
                        r = np.sqrt(w[0] * u[:, 0] ** 2 + w[1] * u[:, 1] ** 2)
                        R = r.max()
                        if R > 1e-9:
                            ax = R / np.sqrt(w)                        # semi-axes at t = 1
                            ang = float(np.degrees(np.arctan2(V[1, 0], V[0, 0])))
                            st, rms, err = score(r / R)
                            res.append(("eradial", (np.array([cx, cy]), ax, ang), st, rms, err))
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
    if kind == "eradial":
        (cx, cy), (a, b), ang = params
        return (f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="1" '
                f'gradientTransform="translate({fmt(cx, prec)} {fmt(cy, prec)}) rotate({fmt(ang, 2)}) '
                f'scale({fmt(a, prec)} {fmt(b, prec)})">{st}</radialGradient>')
    (cx, cy), R = params
    return (f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{fmt(cx, prec)}" cy="{fmt(cy, prec)}" '
            f'r="{fmt(R, prec)}">{st}</radialGradient>')


def affine_fills(lab, lbl, pal_lab, exclude, lam, cost, prec=2, gid0=0, max_t=None):
    """Per-region linear gradients from a piecewise-affine colour model (segment="ms", seg_model="affine").

    For every label k (one region per label in the ms engine) the ridge-regularised affine OKLab fit is computed from
    pixel moments; if it lowers the squared error by more than cost*lam (the price of ~cost px of boundary, i.e. the
    bytes of a gradient definition) the region is filled with a linearGradient along its dominant colour-change
    direction, spanning the region's extent. Returns ({label: (fill_attr, seam_paint)}, defs)."""
    from .segment import _affine_solve
    H, W = lbl.shape
    K = len(pal_lab)
    ok = lbl.ravel() >= 0
    if K == 0 or not ok.any():
        return {}, []
    r = lbl.ravel()[ok]
    idx = np.nonzero(ok)[0]
    yy, xx = np.divmod(idx, W)
    x = (xx + 0.5) / 1024.0
    y = (yy + 0.5) / 1024.0
    c = lab.reshape(-1, 3)[ok].astype(np.float64)
    cols = [np.ones_like(x), x, y, x * x, x * y, y * y] + [c[:, i] for i in range(3)] + \
        [x * c[:, i] for i in range(3)] + [y * c[:, i] for i in range(3)] + [(c * c).sum(1)]
    st = np.stack([np.bincount(r, weights=v, minlength=K) for v in cols], 1)
    n = np.maximum(st[:, 0], 1e-12)
    sse_c = st[:, 15] - (st[:, 6:9] ** 2).sum(1) / n
    obj, X = _affine_solve(st)
    gain = sse_c - obj
    cand = np.nonzero((gain > cost * lam) & (st[:, 0] >= 16))[0]
    cand = np.array([k for k in cand.tolist() if k not in exclude], np.int64)
    if len(cand) == 0:
        return {}, []
    G = X[:, 1:3, :]                                        # (K, 2 [x, y], 3 channels): OKLab per 1024 px
    # dominant direction: top right-singular... (2x3 -> principal 2-vector of G G^T)
    M = np.einsum("kic,kjc->kij", G, G)
    tr = M[:, 0, 0] + M[:, 1, 1]
    det = M[:, 0, 0] * M[:, 1, 1] - M[:, 0, 1] ** 2
    l1 = tr / 2 + np.sqrt(np.maximum(tr * tr / 4 - det, 0))
    dx = np.where(np.abs(M[:, 0, 1]) > 1e-15, M[:, 0, 1], np.where(M[:, 0, 0] >= M[:, 1, 1], 1.0, 0.0))
    dy = np.where(np.abs(M[:, 0, 1]) > 1e-15, l1 - M[:, 0, 0], np.where(M[:, 0, 0] >= M[:, 1, 1], 0.0, 1.0))
    nn = np.sqrt(dx * dx + dy * dy) + 1e-30
    dx, dy = dx / nn, dy / nn
    # extent of each region along its direction (px)
    proj = (xx + 0.5) * dx[r] + (yy + 0.5) * dy[r]
    smin = np.full(K, np.inf)
    smax = np.full(K, -np.inf)
    np.minimum.at(smin, r, proj)
    np.maximum.at(smax, r, proj)
    mx, my = st[:, 1] / n * 1024.0, st[:, 2] / n * 1024.0            # centroid (px)
    fills, defs = {}, []
    from .svgout import fmt
    for k in cand.tolist():
        s0, s1 = smin[k], smax[k]
        if not np.isfinite(s0) or s1 - s0 < 2:
            continue
        mc = mx[k] * dx[k] + my[k] * dy[k]
        p0 = np.array([mx[k] + (s0 - mc) * dx[k], my[k] + (s0 - mc) * dy[k]])
        p1 = np.array([mx[k] + (s1 - mc) * dx[k], my[k] + (s1 - mc) * dy[k]])
        ts = np.linspace(0.0, 1.0, 3)
        pts = p0[None] + ts[:, None] * (p1 - p0)[None]
        labs = X[k, 0][None] + (pts[:, :1] / 1024.0) * X[k, 1][None] + (pts[:, 1:] / 1024.0) * X[k, 2][None]
        rgbs = oklab_to_rgb8(labs.astype(np.float32))
        # midpoint stop only if sRGB-linear interpolation of the ends misses the OKLab ramp
        mid_err = np.abs(rgbs[1] - 0.5 * (rgbs[0] + rgbs[2])).max()
        stops = [(0.0, rgbs[0]), (0.5, rgbs[1]), (1.0, rgbs[2])] if mid_err > 2.0 else [(0.0, rgbs[0]), (1.0, rgbs[2])]
        gid = f"a{gid0 + len(defs) + 1}"
        defs.append(gradient_defs(gid, "linear", (p0, p1), stops, prec))
        fills[k] = (f'fill="url(#{gid})"', f"url(#{gid})")
    return fills, defs


def apply_gradients(rgb, lbl, pal_lab, opts):
    """Detect banded ramps and replace them by gradient-filled regions.

    Returns (lbl_new, pal_lab_new, label_fill {label: (fill_attr, seam_paint)}, defs list).
    """
    from .boundary import label_regions
    H, W = lbl.shape
    if not (lbl >= 0).any() or len(pal_lab) == 0:
        return lbl, pal_lab, {}, []
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
        fit = None
        for _it in range(4):
            if len(regs) < 1 or area[regs].sum() < opts.get("grad_min_area", 64):
                break
            mask = np.isin(R, regs)
            ys, xs = yy[mask], xx[mask]
            if len(ys) > 40000:
                sel = np.sort(np.random.default_rng(0).choice(len(ys), 40000, replace=False))
            else:
                sel = np.arange(len(ys))
            xy = np.column_stack([xs[sel] + 0.5, ys[sel] + 0.5]).astype(np.float64)
            cols = rgbf[ys[sel], xs[sel]]
            f = fit_group(xy, cols)
            if f is None:
                break
            band = pal_lab[lbl[ys[sel], xs[sel]]]
            rms_band = float(np.sqrt(((band - rgb8_to_oklab(cols)) ** 2).sum(-1).mean()))
            if f[3] <= tol and f[3] <= opts.get("grad_vs_band", 1.1) * rms_band:
                fit = f
                break
            # drop member regions that the model explains badly, then refit
            rid = R[ys[sel], xs[sel]]
            err = f[4]
            per = np.array([err[rid == r].mean() if (rid == r).any() else 0.0 for r in regs])
            keep = per <= max(tol, np.median(per) * 1.5)
            if keep.all() or keep.sum() == 0:
                break
            regs = regs[keep]
        if fit is None or len(regs) < opts.get("grad_min_bands", 2):
            continue
        kind, params, stops, rms, _err = fit
        gcount += 1
        gid = f"g{gcount}"
        defs.append(gradient_defs(gid, kind, params, stops, int(opts.get("precision", 2))))
        newl = len(pal_new)
        pal_new.append(rgb8_to_oklab(np.mean([s[1] for s in stops], axis=0)[None])[0])
        lbl_new[mask] = newl
        fills[newl] = (f'fill="url(#{gid})"', f"url(#{gid})")
    return lbl_new, np.array(pal_new, np.float32), fills, defs


def apply_gradients_ms(rgb, lbl, pal_lab, opts):
    """segment="ms": soft-group gradients (banded ramps) first, then per-region affine gradients (seg_model="affine")."""
    lbl, pal_lab, fills, defs = apply_gradients(rgb, lbl, pal_lab, opts)
    if opts.get("seg_model") == "affine":
        H, W = lbl.shape
        lam = opts.get("seg_lambda", 0.01) * np.sqrt(H * W) / 1024.0
        f2, d2 = affine_fills(rgb8_to_oklab(rgb), lbl, pal_lab, set(fills), lam, opts.get("seg_grad_cost", 60.0),
                              int(opts.get("precision", 2)), gid0=0)
        fills.update(f2)
        defs = defs + d2
    return lbl, pal_lab, fills, defs
