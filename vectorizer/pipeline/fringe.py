"""Edge-fringe clean-up on the quantised label map (phase 2, stream C).

Failure class (diagnosed on degraded flat art: JPEG ringing, chroma subsampling, sharpening halos, colour-shifted
re-encodes): along an edge between two flat colours the palette contains one or two extra colours that only exist as
1-2 px bands hugging the edge ("halo" on the light side, darker "rim" on the dark side).  They are not mixtures of the
two sides (they overshoot), so the AA sliver removal keeps them; when two such bands are adjacent each band's main
neighbour is the other band, so the mixture test fails twice.  The bands are fragmented into dozens of tiny
components, every flat shape gets a ragged, jagged outline and the node count explodes.

Two clean-up models (selected with the ``fringe`` option):
  * "halo"   - component level: a thin component (mean thickness < max_thick px) whose colour is within ``near``
               (OKLab) of an adjacent label is an overshoot band of that label; its pixels are re-assigned.
  * "colour" - palette level: a colour whose pixels (almost) never form an interior (3x3 erosion) and which is within
               ``near`` of an adjacent colour is an edge-only colour; all its pixels are re-assigned.
Pixels are re-assigned to the most similar (OKLab, per pixel) label among their non-fringe 8-neighbours, growing
inwards from the band borders.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

_OFFS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _refill(lbl, unknown, lab, pal, max_iter=12, reach=3):
    """Re-assign the pixels in `unknown` to the most similar known (>=0) label found within `reach` px
    (8-connected); pixels with no such label grow from their 8-neighbours."""
    lbl = lbl.copy()
    H, W = lbl.shape
    cur = np.where(unknown, -2, lbl)
    pal = np.asarray(pal, np.float32)
    ys, xs = np.nonzero(unknown)
    if len(ys) == 0:
        return lbl
    y0, y1 = max(0, ys.min() - reach), min(H, ys.max() + reach + 1)
    x0, x1 = max(0, xs.min() - reach), min(W, xs.max() + reach + 1)
    sub = cur[y0:y1, x0:x1]
    U = sub == -2
    zone = ndi.binary_dilation(U, structure=np.ones((3, 3), bool), iterations=reach)
    cands = np.unique(sub[zone & (sub >= 0)])
    best_d = np.full(U.shape, np.inf, np.float32)
    best_l = np.full(U.shape, -2, np.int32)
    labsub = lab[y0:y1, x0:x1]
    for k in cands.tolist():
        nk = ndi.binary_dilation(sub == k, structure=np.ones((3, 3), bool), iterations=reach) & U
        if not nk.any():
            continue
        d = ((labsub[nk] - pal[k]) ** 2).sum(-1)
        bd = best_d[nk]
        better = d < bd
        bd[better] = d[better]
        best_d[nk] = bd
        bl = best_l[nk]
        bl[better] = k
        best_l[nk] = bl
    sub[U & (best_l >= 0)] = best_l[U & (best_l >= 0)]
    cur[y0:y1, x0:x1] = sub
    for _ in range(max_iter):
        U = cur == -2
        if not U.any():
            break
        P = np.pad(cur, 1, constant_values=-3)
        best_d = np.full((H, W), np.inf, np.float32)
        best_l = np.full((H, W), -2, np.int32)
        for dy, dx in _OFFS:
            c = P[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
            ok = U & (c >= 0)
            if not ok.any():
                continue
            d = ((lab[ok] - pal[c[ok]]) ** 2).sum(-1)
            bd = best_d[ok]
            better = d < bd
            idx = np.nonzero(ok)
            sel = (idx[0][better], idx[1][better])
            best_d[sel] = d[better]
            best_l[sel] = c[ok][better]
        grow = U & (best_l >= 0)
        if not grow.any():
            break
        cur[grow] = best_l[grow]
    left = cur == -2
    cur[left] = lbl[left]                 # unreachable (e.g. only transparent neighbours): keep
    return cur.astype(np.int32)


def _component_stats(lbl):
    from .boundary import label_regions
    R, rl = label_regions(lbl)
    n = len(rl)
    area = np.bincount(R.ravel(), minlength=n).astype(np.float64)
    per = np.zeros(n, np.float64)
    pairs = []
    for a, b in ((R[:, 1:], R[:, :-1]), (R[1:, :], R[:-1, :])):
        m = a != b
        ra, rb = a[m], b[m]
        per += np.bincount(ra, minlength=n) + np.bincount(rb, minlength=n)
        pairs.append(np.stack([ra, rb], 1))
        pairs.append(np.stack([rb, ra], 1))
    pairs = np.concatenate(pairs).astype(np.int64) if pairs else np.zeros((0, 2), np.int64)
    return R, rl, area, per, pairs


def halo_mask(lbl, pal, near=0.09, max_thick=1.6, max_area_frac=0.01, min_contact=2):
    """Thin components whose colour is within `near` of an adjacent *non-thin* component (the surface the band
    overshoots).  Requiring a stable partner avoids erasing pairs of thin features (e.g. two dark line colours)."""
    H, W = lbl.shape
    R, rl, area, per, pairs = _component_stats(lbl)
    thick = 2 * area / np.maximum(per, 1)
    cand = (thick < max_thick) & (area < max_area_frac * H * W) & (rl >= 0)
    if not cand.any() or len(pairs) == 0:
        return np.zeros_like(lbl, bool)
    a, b = pairs[:, 0], pairs[:, 1]
    pairs = pairs[cand[a] & ~cand[b] & (rl[b] >= 0) & (rl[b] != rl[a])]
    if len(pairs) == 0:
        return np.zeros_like(lbl, bool)
    n = len(rl)
    key = pairs[:, 0] * n + pairs[:, 1]
    u, cnt = np.unique(key, return_counts=True)
    comp, nb = u // n, u % n
    keep = cnt >= min_contact
    comp, nb = comp[keep], nb[keep]
    pal = np.asarray(pal, np.float32)
    d = np.sqrt(((pal[rl[comp]] - pal[rl[nb]]) ** 2).sum(-1))
    marked = np.zeros(n, bool)
    marked[comp[d < near]] = True
    return marked[R]


def edge_only_mask(lbl, pal, near=0.09, interior_max=0.05, max_area_frac=0.05):
    H, W = lbl.shape
    st8 = np.ones((3, 3), bool)
    st4 = ndi.generate_binary_structure(2, 1)
    pal = np.asarray(pal, np.float32)
    out = np.zeros_like(lbl, bool)
    for k in np.unique(lbl[lbl >= 0]).tolist():
        m = lbl == k
        n = int(m.sum())
        if n == 0 or n > max_area_frac * H * W:
            continue
        inner = ndi.binary_erosion(m, structure=st8, border_value=1)
        if inner.sum() > interior_max * n:
            continue
        ring = ndi.binary_dilation(m, structure=st4) & ~m
        nb = np.unique(lbl[ring])
        nb = nb[nb >= 0]
        if len(nb) == 0:
            continue
        d = np.sqrt(((pal[nb] - pal[k]) ** 2).sum(-1))
        if d.min() < near:
            out |= m
    return out


def clean_fringe(lbl, lab, pal, method="halo", near=0.09, passes=2):
    """Return (labels, n_pixels_reassigned). `pal` is the OKLab palette; unused colours are left in the palette."""
    if not method:
        return lbl, 0
    total = 0
    for _ in range(passes):
        if method == "halo":
            m = halo_mask(lbl, pal, near=near)
        elif method == "colour":
            m = edge_only_mask(lbl, pal, near=near)
        elif method == "both":
            m = halo_mask(lbl, pal, near=near) | edge_only_mask(lbl, pal, near=near)
        else:
            raise ValueError(f"unknown fringe method {method!r}")
        if not m.any():
            break
        new = _refill(lbl, m, lab, pal)
        changed = int((new != lbl).sum())
        lbl = new
        total += changed
        if changed == 0:
            break
    return lbl, total
