"""Palette extraction + anti-alias-aware label assignment + speckle merging (W1, W2).

Pipeline:
  1. OKLab conversion, local contrast -> "flat" pixel mask (edge / AA pixels excluded)
  2. weighted 3-D histogram of flat pixels, greedy mode seeking (largest bin first,
     absorb bins within radius) -> palette; weighted k-means refinement
  3. flat pixels -> nearest palette colour; edge pixels -> nearest colour among the
     labels of nearby flat pixels (avoids spurious in-between colours on AA borders)
  4. connected components smaller than `min_area` merged into the most similar neighbour
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from .color import oklab_to_rgb8, rgb8_to_oklab

TRANSPARENT = -1


def local_contrast(lab):
    """Max OKLab distance to 4-neighbours (per pixel)."""
    H, W, _ = lab.shape
    g = np.zeros((H, W), np.float32)
    dx = np.sqrt(((lab[:, 1:] - lab[:, :-1]) ** 2).sum(-1))
    dy = np.sqrt(((lab[1:] - lab[:-1]) ** 2).sum(-1))
    g[:, 1:] = np.maximum(g[:, 1:], dx)
    g[:, :-1] = np.maximum(g[:, :-1], dx)
    g[1:] = np.maximum(g[1:], dy)
    g[:-1] = np.maximum(g[:-1], dy)
    return g


def mixed_mask(lab, t=0.03, slack=1.2):
    """Pixels whose colour lies between two opposite neighbours (AA / blur ramps).

    For each of 4 directions with neighbours a, b of pixel p: mixed if |a-b| > t,
    |a-p| + |p-b| < slack * |a-b| and p is not (nearly) equal to a or b.
    Thin-line cores (local extrema) are therefore NOT mixed.
    """
    H, W, _ = lab.shape
    P = np.pad(lab, ((1, 1), (1, 1), (0, 0)), mode="edge")
    c = P[1:-1, 1:-1]
    out = np.zeros((H, W), bool)
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        a = P[1 - dy:1 - dy + H, 1 - dx:1 - dx + W]
        b = P[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
        ab = np.sqrt(((a - b) ** 2).sum(-1))
        ap = np.sqrt(((a - c) ** 2).sum(-1))
        pb = np.sqrt(((c - b) ** 2).sum(-1))
        out |= (ab > t) & (ap + pb < slack * ab) & (ap > 0.15 * ab) & (pb > 0.15 * ab)
    return out


def estimate_noise(lab):
    """Robust noise sigma estimate (OKLab L units) from the Laplacian (Immerkaer 1996)."""
    L = lab[..., 0].astype(np.float64)
    if min(L.shape) < 3:
        return 0.0
    k = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float64)
    r = ndi.convolve(L, k, mode="reflect")[1:-1, 1:-1]
    # kernel L2 norm is 6 -> sigma_r = 6 sigma; median(|N(0,s)|) = 0.6745 s (robust to edges)
    return float(np.median(np.abs(r)) / 0.6745 / 6.0) if r.size else 0.0


def _greedy_palette(colors, weights, radius, max_colors, min_weight):
    order = np.argsort(-weights)
    colors = colors[order]
    weights = weights[order].astype(np.float64)
    alive = np.ones(len(colors), bool)
    pal, palw = [], []
    i = 0
    n = len(colors)
    while len(pal) < max_colors:
        while i < n and not alive[i]:
            i += 1
        if i >= n:
            break
        c = colors[i]
        d = np.sqrt(((colors - c) ** 2).sum(-1))
        m = alive & (d < radius)
        w = weights[m].sum()
        alive[m] = False
        if w < min_weight:
            continue
        # mean-shift style re-centre then absorb again
        cc = (colors[m] * weights[m, None]).sum(0) / w
        pal.append(cc)
        palw.append(w)
    if not pal:
        j = int(np.argmax(weights))
        return colors[j:j + 1].astype(np.float32), weights[j:j + 1]
    return np.array(pal, np.float32), np.array(palw)


def _kmeans(colors, weights, pal, iters=4):
    for _ in range(iters):
        d = ((colors[:, None, :] - pal[None, :, :]) ** 2).sum(-1)
        a = d.argmin(1)
        newp = pal.copy()
        for k in range(len(pal)):
            m = a == k
            w = weights[m]
            if w.sum() > 0:
                newp[k] = (colors[m] * w[:, None]).sum(0) / w.sum()
        if np.allclose(newp, pal, atol=1e-4):
            pal = newp
            break
        pal = newp
    return pal


def _merge_close(pal, palw, radius):
    pal = list(pal)
    palw = list(palw)
    changed = True
    while changed and len(pal) > 1:
        changed = False
        P = np.array(pal)
        d = np.sqrt(((P[:, None] - P[None]) ** 2).sum(-1))
        np.fill_diagonal(d, np.inf)
        i, j = np.unravel_index(np.argmin(d), d.shape)
        if d[i, j] < radius:
            w = palw[i] + palw[j]
            pal[i] = (P[i] * palw[i] + P[j] * palw[j]) / w
            palw[i] = w
            del pal[j]
            del palw[j]
            changed = True
    return np.array(pal, np.float32), np.array(palw)


def extract_palette(lab, valid, radius=0.045, max_colors=64, min_frac=0.0002, min_px=8, flat_thresh=None, noise=None,
                    mix_suppress=True, keep_frac=0.01, merge_frac=0.6):
    """Return palette (K,3) OKLab, plus the flat mask used."""
    if noise is None:
        noise = estimate_noise(lab)
    ft = flat_thresh if flat_thresh is not None else max(0.03, 4.0 * noise)
    flat = ~mixed_mask(lab, ft) & valid
    if flat.sum() < max(16, 0.05 * valid.sum()):
        g = local_contrast(lab)
        thr = np.percentile(g[valid], 50) if valid.any() else 0
        flat = (g <= thr) & valid
    px = lab[flat]
    if len(px) == 0:
        px = lab[valid] if valid.any() else lab.reshape(-1, 3)
    # histogram binning (bin size ~ radius/4)
    bs = radius / 4.0
    q = np.floor(px / bs).astype(np.int32)
    q -= q.min(0)
    dims = q.max(0) + 1
    key = (q[:, 0].astype(np.int64) * dims[1] + q[:, 1]) * dims[2] + q[:, 2]
    uk, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    sums = np.zeros((len(uk), 3), np.float64)
    np.add.at(sums, inv, px)
    cols = (sums / cnt[:, None]).astype(np.float32)
    N = valid.sum()
    min_w = max(min_px, min_frac * N)
    pal, palw = _greedy_palette(cols, cnt, radius, max_colors, min_w)
    pal = _kmeans(cols, cnt.astype(np.float64), pal)
    pal, palw = _merge_close(pal, palw, radius * merge_frac)
    if mix_suppress:
        pal, palw = _suppress_mixtures(pal, palw, radius, keep_frac * N)
    return pal, flat


def _suppress_mixtures(pal, palw, radius, keep_w):
    """Drop light-weight palette colours that lie on the segment between two heavier colours.

    Such colours are produced by anti-aliasing / blur where two regions meet (e.g. grey
    plateaus where blurred black strokes cross). Heavy intermediate colours are kept.
    """
    K = len(pal)
    if K < 3:
        return pal, palw
    order = np.argsort(-palw)
    keep = np.ones(K, bool)
    for r, k in enumerate(order):
        if palw[k] >= keep_w or r < 2:
            continue
        heavier = [i for i in order[:r] if keep[i]]
        c = pal[k]
        found = False
        for ii in range(len(heavier)):
            a = pal[heavier[ii]]
            for jj in range(ii + 1, len(heavier)):
                b = pal[heavier[jj]]
                ab = b - a
                L2 = float((ab * ab).sum())
                if L2 < 1e-9:
                    continue
                t = float(((c - a) * ab).sum()) / L2
                if 0.08 < t < 0.92:
                    d = float(np.sqrt(((a + t * ab - c) ** 2).sum()))
                    if d < 0.6 * radius:
                        found = True
                        break
            if found:
                break
        if found:
            keep[k] = False
    return pal[keep], palw[keep]


def assign_labels(lab, valid, pal, flat, window=2):
    """Nearest-palette labels; non-flat pixels restricted to palette entries of nearby flat pixels."""
    H, W, _ = lab.shape
    flatlab = lab.reshape(-1, 3)
    # nearest palette for all pixels (chunked to bound memory)
    lbl = np.empty(H * W, np.int32)
    dmin = np.empty(H * W, np.float32)
    step = 1 << 18
    for s in range(0, H * W, step):
        d = ((flatlab[s:s + step, None, :] - pal[None]) ** 2).sum(-1)
        lbl[s:s + step] = d.argmin(1)
        dmin[s:s + step] = d.min(1)
    lbl = lbl.reshape(H, W)
    edge = valid & ~flat
    if window > 0 and edge.any() and flat.any():
        fl = np.where(flat, lbl, -1)
        ys, xs = np.nonzero(edge)
        best = np.full(len(ys), np.inf, np.float32)
        bestl = lbl[ys, xs].copy()
        pe = lab[ys, xs]
        pad = np.pad(fl, window, constant_values=-1)
        for dy in range(-window, window + 1):
            for dx in range(-window, window + 1):
                cand = pad[ys + window + dy, xs + window + dx]
                ok = cand >= 0
                if not ok.any():
                    continue
                c = np.where(ok, cand, 0)
                d = ((pe - pal[c]) ** 2).sum(-1)
                d = np.where(ok, d, np.inf)
                better = d < best
                best[better] = d[better]
                bestl[better] = cand[better]
        lbl[ys, xs] = bestl
    lbl[~valid] = TRANSPARENT
    return lbl


def rescue_ridges(lab, lbl, pal, valid, noise=0.0, t=0.04):
    """Thin-line rescue: pixels that differ from two similar opposite neighbours (a ridge,
    e.g. the core of a sub-pixel-wide anti-aliased line) but were assigned the neighbours'
    label are re-assigned to the palette colour that best explains them as a mixture
    p = bg + alpha (c - bg), alpha >= 0.3. (A top-hat based detector was tried and was
    worse on JPEG input: ringing got rescued as grey specks, see EXPERIMENTS.md.)"""
    H, W, _ = lab.shape
    if H < 3 or W < 3:
        return lbl
    t = max(t, 3.0 * noise)
    P = np.pad(lab, ((1, 1), (1, 1), (0, 0)), mode="edge")
    c = P[1:-1, 1:-1]
    ridge = np.zeros((H, W), bool)
    bg = np.zeros_like(lab)
    best = np.zeros((H, W), np.float32)
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        a = P[1 - dy:1 - dy + H, 1 - dx:1 - dx + W]
        b = P[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
        ab = np.sqrt(((a - b) ** 2).sum(-1))
        m = 0.5 * (a + b)
        pm = np.sqrt(((c - m) ** 2).sum(-1))
        score = pm - ab
        sel = (ab < t) & (pm > t) & (score > best)
        best = np.where(sel, score, best)
        bg[sel] = m[sel]
        ridge |= sel
    ridge &= valid & (lbl >= 0)
    if not ridge.any():
        return lbl
    ys, xs = np.nonzero(ridge)
    p = lab[ys, xs]
    g = bg[ys, xs]
    v = p - g
    D = pal[None, :, :] - g[:, None, :]                      # (n, K, 3)
    L2 = (D * D).sum(-1) + 1e-12
    alpha = (v[:, None, :] * D).sum(-1) / L2
    resid = np.sqrt(((v[:, None, :] - alpha[..., None] * D) ** 2).sum(-1))
    vn = np.sqrt((v * v).sum(-1))[:, None]
    ok = (alpha >= 0.3) & (alpha <= 1.3) & (resid < 0.45 * vn + 0.01) & (np.sqrt(L2) > 1.5 * t)
    resid = np.where(ok, resid, np.inf)
    k = resid.argmin(1)
    good = np.isfinite(resid[np.arange(len(k)), k])
    cur = lbl[ys, xs]
    gl = ((pal[None, :, :] - g[:, None, :]) ** 2).sum(-1).argmin(1)
    upd = good & (cur == gl) & (k != cur)
    lbl = lbl.copy()
    lbl[ys[upd], xs[upd]] = k[upd]
    return lbl


def bridge_saddles(lbl, lab, pal, passes=2):
    """Make thin diagonal structures 4-connected: in 2x2 saddles (A B / B A), flip the
    background pixel closest in colour to the thin label."""
    H, W = lbl.shape
    for _ in range(passes):
        A = lbl[:-1, :-1]
        B = lbl[:-1, 1:]
        C = lbl[1:, :-1]
        D = lbl[1:, 1:]
        s1 = (A == D) & (B == C) & (A != B) & (A >= 0) & (B >= 0)
        if not s1.any():
            break
        ys, xs = np.nonzero(s1)
        # local label counts in a 5x5 window decide which diagonal is the thin structure
        changed = 0
        for y, x in zip(ys.tolist(), xs.tolist()):
            a, b = lbl[y, x], lbl[y, x + 1]
            if not (lbl[y + 1, x + 1] == a and lbl[y + 1, x] == b and a != b):
                continue
            y0, y1, x0, x1 = max(0, y - 2), min(H, y + 4), max(0, x - 2), min(W, x + 4)
            win = lbl[y0:y1, x0:x1]
            na, nb = int((win == a).sum()), int((win == b).sum())
            if na == nb:
                continue
            thin, other = (a, b) if na < nb else (b, a)
            if thin == a:
                cands = [(y, x + 1), (y + 1, x)]
            else:
                cands = [(y, x), (y + 1, x + 1)]
            dists = [float(((lab[cy, cx] - pal[thin]) ** 2).sum()) for cy, cx in cands]
            cy, cx = cands[int(np.argmin(dists))]
            lbl[cy, cx] = thin
            changed += 1
        if not changed:
            break
    return lbl


def remove_slivers(lbl, lab, pal, radius=0.045, max_thick=1.6, max_area_frac=0.01):
    """Remove thin regions (mean thickness < max_thick px) whose colour is a mixture of their two
    main neighbours (AA / JPEG bands along an edge). Pixels go to the nearer neighbour colour."""
    H, W = lbl.shape
    st = ndi.generate_binary_structure(2, 1)
    comp = np.zeros(lbl.shape, np.int32)
    nxt = 0
    clab = []
    for k in np.unique(lbl):
        if k < 0:
            continue
        c, n = ndi.label(lbl == k, structure=st)
        comp[c > 0] = c[c > 0] + nxt
        clab.extend([int(k)] * n)
        nxt += n
    if nxt == 0:
        return lbl
    area = np.bincount(comp.ravel(), minlength=nxt + 1).astype(np.float64)
    per = np.zeros(nxt + 1)
    dh = comp[:, 1:] != comp[:, :-1]
    dv = comp[1:, :] != comp[:-1, :]
    np.add.at(per, comp[:, 1:][dh], 1)
    np.add.at(per, comp[:, :-1][dh], 1)
    np.add.at(per, comp[1:, :][dv], 1)
    np.add.at(per, comp[:-1, :][dv], 1)
    thick = 2 * area / np.maximum(per, 1)
    cand = np.nonzero((thick < max_thick) & (area < max_area_frac * H * W) & (area > 0))[0]
    cand = cand[cand > 0]
    if len(cand) == 0:
        return lbl
    slices = ndi.find_objects(comp)
    lbl = lbl.copy()
    for cid in cand.tolist():
        sl = slices[cid - 1]
        if sl is None:
            continue
        y0, y1 = max(0, sl[0].start - 1), min(H, sl[0].stop + 1)
        x0, x1 = max(0, sl[1].start - 1), min(W, sl[1].stop + 1)
        sub = comp[y0:y1, x0:x1] == cid
        ring = ndi.binary_dilation(sub, structure=st) & ~sub
        nb = lbl[y0:y1, x0:x1][ring]
        own = clab[cid - 1]
        nb = nb[(nb >= 0) & (nb != own)]
        if len(nb) == 0:
            continue
        u, cnt = np.unique(nb, return_counts=True)
        o = np.argsort(-cnt)
        a = int(u[o[0]])
        b = int(u[o[1]]) if len(u) > 1 else a
        c = pal[own]
        A, B = pal[a], pal[b]
        if a != b:
            ab = B - A
            L2 = float((ab * ab).sum())
            t = float(((c - A) * ab).sum()) / L2 if L2 > 1e-9 else 0.5
            d = float(np.sqrt(((A + np.clip(t, 0, 1) * ab - c) ** 2).sum()))
            mixture = -0.15 < t < 1.15 and d < radius
        else:
            mixture = float(np.sqrt(((A - c) ** 2).sum())) < 2 * radius
        if not mixture:
            continue
        ys, xs = np.nonzero(sub)
        px = lab[y0:y1, x0:x1][ys, xs]
        da = ((px - A) ** 2).sum(-1)
        db = ((px - B) ** 2).sum(-1)
        lbl[y0 + ys, x0 + xs] = np.where(da <= db, a, b)
    return lbl


def merge_small_regions(lbl, pal, min_area, passes=3, connectivity=4):
    """Merge connected components with area < min_area into the most similar adjacent label."""
    if min_area <= 1:
        return lbl
    st = ndi.generate_binary_structure(2, 1 if connectivity == 4 else 2)
    H, W = lbl.shape
    for _ in range(passes):
        changed = False
        comp = np.zeros(lbl.shape, np.int32)
        nxt = 0
        for k in np.unique(lbl):
            if k == TRANSPARENT:
                continue
            c, n = ndi.label(lbl == k, structure=st)
            comp[c > 0] = c[c > 0] + nxt
            nxt += n
        if nxt == 0:
            break
        areas = np.bincount(comp.ravel(), minlength=nxt + 1)
        small = np.nonzero((areas < min_area) & (np.arange(nxt + 1) > 0))[0]
        if len(small) == 0:
            break
        slices = ndi.find_objects(comp)
        # process small components smallest first
        small = small[np.argsort(areas[small])]
        for cid in small:
            sl = slices[cid - 1]
            if sl is None:
                continue
            y0, y1 = max(0, sl[0].start - 1), min(H, sl[0].stop + 1)
            x0, x1 = max(0, sl[1].start - 1), min(W, sl[1].stop + 1)
            sub = comp[y0:y1, x0:x1] == cid
            if not sub.any():
                continue
            ring = ndi.binary_dilation(sub, structure=st) & ~sub
            nb = lbl[y0:y1, x0:x1][ring]
            nb = nb[nb != TRANSPARENT]
            own = lbl[y0:y1, x0:x1][sub][0]
            nb = nb[nb != own]
            if len(nb) == 0:
                continue
            u, cnt = np.unique(nb, return_counts=True)
            d = np.sqrt(((pal[u] - pal[own]) ** 2).sum(-1))
            score = d - 0.002 * cnt  # prefer similar colour, then longer shared border
            tgt = u[np.argmin(score)]
            lbl[y0:y1, x0:x1][sub] = tgt
            comp[y0:y1, x0:x1][sub] = 0
            changed = True
        if not changed:
            break
    return lbl


def quantize(rgb, alpha, radius=0.045, max_colors=64, min_area=None, window=2, alpha_threshold=128,
             thin_lines=True, mix_suppress=True, slivers=True, merge_frac=0.6):
    """Return (labels HxW int32 with -1 transparent, palette_rgb (K,3) float, palette_lab, info dict)."""
    H, W, _ = rgb.shape
    lab = rgb8_to_oklab(rgb)
    valid = alpha >= alpha_threshold
    noise = estimate_noise(lab)
    pal, flat = extract_palette(lab, valid, radius=radius, max_colors=max_colors, noise=noise, mix_suppress=mix_suppress,
                                merge_frac=merge_frac)
    lbl = assign_labels(lab, valid, pal, flat, window=window)
    if thin_lines in (True, "ridge", "both"):
        lbl = rescue_ridges(lab, lbl, pal, valid, noise)
    if thin_lines in (True, "bridge", "both"):
        lbl = bridge_saddles(lbl, lab, pal)
    if min_area is None:
        min_area = int(np.clip(round(H * W / 25000), 3, 40))
    lbl = merge_small_regions(lbl, pal, min_area)
    if slivers:
        lbl = remove_slivers(lbl, lab, pal, radius)
    # drop unused palette entries, recompute colours as mean of assigned pixels (in OKLab)
    used = np.unique(lbl[lbl >= 0])
    remap = np.full(len(pal), -1, np.int32)
    remap[used] = np.arange(len(used))
    lbl = np.where(lbl >= 0, remap[np.maximum(lbl, 0)], TRANSPARENT).astype(np.int32)
    K = len(used)
    m = (lbl >= 0) & flat
    newpal = np.zeros((K, 3), np.float32)
    for k in range(K):
        mk = m & (lbl == k)
        if mk.sum() < 3:
            mk = lbl == k
        newpal[k] = np.median(lab[mk], axis=0) if mk.any() else pal[used[k]]
    info = {"noise": noise, "n_colors": K, "min_area": min_area}
    return lbl, oklab_to_rgb8(newpal), newpal, info
