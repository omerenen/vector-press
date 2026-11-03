"""Region-adjacency-graph merging for textured art (phase 2, stream B).

Piecewise-constant Mumford-Shah / Potts region merging (Koepfler, Lopez & Morel 1994, "A multiscale algorithm for
image segmentation by variational method"): the energy

    E = sum_regions sum_pixels |c(p) - mean_region|^2  +  lam * total boundary length

is decreased greedily by merging adjacent regions. Merging regions i, j changes the data term by
n_i n_j / (n_i + n_j) |mu_i - mu_j|^2 and removes their shared boundary l_ij, so a merge is beneficial when

    r_ij = n_i n_j / (n_i + n_j) |mu_i - mu_j|^2 / (lam * l_ij) < 1.

Unlike a fixed speckle-area threshold this is scale aware: tiny texture fragments surrounded by other fragments merge
(their colour cost is tiny compared with their long boundaries), while long thin high-contrast lines and large
regions with distinct colours survive. Boundary length is also what the SVG pays for (nodes / bytes).

The merge is run in vectorised rounds (numpy, no Python loop over regions): every region picks its cheapest
neighbour; within each nearest-neighbour tree only depth-1 stars around a stable receiver are merged per round
(approximates the strictly greedy order, which is what makes the result deterministic and order independent).
"""
from __future__ import annotations

import numpy as np

from .boundary import label_regions


def region_edges(R):
    """Unique 4-adjacency edges (a < b) between region ids >= 0 with their shared boundary length in px."""
    keys = []
    n = int(R.max()) + 1 if R.size else 0
    for a, b in ((R[:, :-1], R[:, 1:]), (R[:-1], R[1:])):
        m = (a != b) & (a >= 0) & (b >= 0)
        if m.any():
            x, y = a[m].astype(np.int64), b[m].astype(np.int64)
            keys.append(np.minimum(x, y) * n + np.maximum(x, y))
    if not keys:
        z = np.zeros(0, np.int64)
        return z, z, np.zeros(0, np.float64)
    uk, cnt = np.unique(np.concatenate(keys), return_counts=True)
    return uk // n, uk % n, cnt.astype(np.float64)


def _region_stats(R, lab, n):
    """(area, colour sums (n,3), sum of squared colour norms) per region id; channel planes, no copies of the
    whole image when every pixel is valid."""
    r = R.ravel()
    ok = r >= 0
    full = bool(ok.all())
    if not full:
        r = r[ok]
    area = np.bincount(r, minlength=n).astype(np.float64)
    S = np.empty((n, 3))
    Q = np.zeros(n)
    for c in range(3):
        ch = lab[..., c].ravel()
        if not full:
            ch = ch[ok]
        ch = ch.astype(np.float64)
        S[:, c] = np.bincount(r, weights=ch, minlength=n)
        Q += np.bincount(r, weights=ch * ch, minlength=n)
    return area, S, Q


AFFINE_RIDGE = 1e-4      # slope penalty in (x/1024)^2 units: regions below ~10x10 px stay (nearly) constant


def _stats_const(R, lab, n):
    area, S, Q = _region_stats(R, lab, n)
    return np.column_stack([area, S, Q])


def _obj_const(st):
    """Sum of squared errors of the best constant colour (st = [n, Sc(3), Q])."""
    n = np.maximum(st[:, 0], 1e-12)
    return st[:, 4] - (st[:, 1:4] ** 2).sum(1) / n


def _stats_affine(R, lab, n, H, W):
    r = R.ravel()
    ok = r >= 0
    r = r[ok]
    yy, xx = np.divmod(np.nonzero(ok)[0], W)
    x = (xx + 0.5) / 1024.0
    y = (yy + 0.5) / 1024.0
    c = lab.reshape(-1, 3)[ok].astype(np.float64)
    cols = [np.ones_like(x), x, y, x * x, x * y, y * y]
    for ch in range(3):
        cols.append(c[:, ch])
    for ch in range(3):
        cols.append(x * c[:, ch])
    for ch in range(3):
        cols.append(y * c[:, ch])
    cols.append((c * c).sum(1))
    return np.stack([np.bincount(r, weights=v, minlength=n) for v in cols], 1)


def _affine_solve(st, ridge=AFFINE_RIDGE):
    """Ridge-regularised affine colour fit c = c0 + gx x + gy y per channel. st rows: [n, sx, sy, sxx, sxy, syy,
    sc(3), sxc(3), syc(3), scc]. Returns (objective (SSE + penalty), coefficients (m, 3 [1,x,y], 3 channels))."""
    m = len(st)
    A = np.empty((m, 3, 3))
    A[:, 0, 0] = st[:, 0]
    A[:, 0, 1] = A[:, 1, 0] = st[:, 1]
    A[:, 0, 2] = A[:, 2, 0] = st[:, 2]
    A[:, 1, 1] = st[:, 3] + ridge
    A[:, 1, 2] = A[:, 2, 1] = st[:, 4]
    A[:, 2, 2] = st[:, 5] + ridge
    A[:, 0, 0] += 1e-12
    B = np.stack([st[:, 6:9], st[:, 9:12], st[:, 12:15]], 1)            # (m, 3 basis, 3 channels)
    X = np.linalg.solve(A, B)
    obj = st[:, 15] - (B * X).sum((1, 2))
    return np.maximum(obj, 0.0), X


def _obj_affine(st):
    return _affine_solve(st)[0]


def ms_merge(R, lab, lam, max_rounds=400, edge_weight=None, model="const", return_stats=False):
    """Greedy Mumford-Shah merging of the regions of R (ids 0..n-1, -1 = excluded).

    lam: boundary price (OKLab^2 per px of boundary). edge_weight: optional per-edge factor (same order as
    region_edges(R)) multiplying the boundary price. model: "const" (piecewise-constant colour) or "affine"
    (piecewise-affine colour, i.e. every region may be a linear ramp -> smooth shading is not cut into bands).
    Returns (Rnew with ids 0..m-1, info) (+ final per-region statistics if return_stats).
    """
    n = int(R.max()) + 1 if (R >= 0).any() else 0
    if n <= 1:
        out = (R, {"rounds": 0, "n0": n, "n1": n})
        return out + (None,) if return_stats else out
    if model == "affine":
        H, W = R.shape
        st = _stats_affine(R, lab, n, H, W)
        obj = _obj_affine
    else:
        st = _stats_const(R, lab, n)
        obj = _obj_const
    area = st[:, 0]
    a, b, L = region_edges(R)
    w = np.ones_like(L) if edge_weight is None else edge_weight.astype(np.float64)
    parent = np.arange(n)
    rounds = 0
    node_obj = obj(st)
    for rounds in range(1, max_rounds + 1):
        if len(a) == 0:
            break
        if model == "affine":
            dE = obj(st[a] + st[b]) - node_obj[a] - node_obj[b]
        else:
            mu = st[:, 1:4] / np.maximum(area, 1)[:, None]
            na, nb = area[a], area[b]
            dE = na * nb / (na + nb) * ((mu[a] - mu[b]) ** 2).sum(1)
        r = np.maximum(dE, 0.0) / (lam * L * w)
        # best neighbour per node
        src = np.concatenate([a, b])
        dst = np.concatenate([b, a])
        rr = np.concatenate([r, r])
        o = np.lexsort((dst, rr, src))
        src_o = src[o]
        first = np.ones(len(o), bool)
        first[1:] = src_o[1:] != src_o[:-1]
        nodes = src_o[first]
        best = np.full(n, -1, np.int64)
        bestr = np.full(n, np.inf)
        best[nodes] = dst[o][first]
        bestr[nodes] = rr[o][first]
        cand = bestr < 1.0
        if not cand.any():
            break
        bb = np.where(best >= 0, best, 0)
        mutual = cand & (best >= 0) & (best[bb] == np.arange(n))
        # in a mutual pair the smaller region (tie: larger id) moves; the other one receives
        bigger = (area > area[bb]) | ((area == area[bb]) & (np.arange(n) < bb))
        out = cand & ~(mutual & bigger)
        move = out & ~out[bb]
        if not move.any():
            break
        tgt = np.arange(n)
        tgt[move] = best[move]
        # apply merges (targets do not move this round -> one level)
        mv = np.nonzero(move)[0]
        np.add.at(st, tgt[mv], st[mv])
        st[mv] = 0
        area = st[:, 0]
        parent[mv] = tgt[mv]
        recv = np.unique(tgt[mv])
        node_obj[mv] = 0
        node_obj[recv] = obj(st[recv])
        # relabel edges, combine duplicates
        a2, b2 = tgt[a], tgt[b]
        keep = a2 != b2
        a2, b2, L2, w2 = a2[keep], b2[keep], L[keep], w[keep]
        lo, hi = np.minimum(a2, b2), np.maximum(a2, b2)
        key = lo * n + hi
        uk, inv = np.unique(key, return_inverse=True)
        L = np.bincount(inv, weights=L2)
        w = np.bincount(inv, weights=w2 * L2) / np.maximum(L, 1e-9)    # length-weighted mean factor
        a, b = uk // n, uk % n
    # resolve parents
    root = parent.copy()
    while True:
        nr = root[root]
        if np.array_equal(nr, root):
            break
        root = nr
    ids = np.unique(root[area[root] > 0]) if n else root
    remap = np.full(n, -1, np.int64)
    remap[ids] = np.arange(len(ids))
    Rn = np.where(R >= 0, remap[root[np.maximum(R, 0)]], -1).astype(np.int32)
    info = {"rounds": rounds, "n0": n, "n1": len(ids)}
    if return_stats:
        return Rn, info, st[ids]
    return Rn, info


def region_means(Rn, lab):
    n = int(Rn.max()) + 1 if (Rn >= 0).any() else 0
    area, S, _ = _region_stats(Rn, lab, n)
    return (S / np.maximum(area, 1)[:, None]).astype(np.float32), area


def snap_colors(lbl, pal, tol):
    """Greedy colour snapping: labels whose colours lie within tol (OKLab) of a heavier label's colour take that
    label (fewer distinct paints; adjacent regions with snapped colours merge). Returns (lbl, pal)."""
    K = len(pal)
    if K < 2:
        return lbl, pal
    w = np.bincount(lbl[lbl >= 0], minlength=K).astype(np.float64)
    bs = tol
    q = np.floor(pal / bs).astype(np.int64)
    order = np.argsort(-w)
    target = np.arange(K)
    from collections import defaultdict
    grid = defaultdict(list)
    for k in order.tolist():
        cell = tuple(q[k])
        best, bd = -1, tol * tol
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ()):
                        d = float(((pal[k] - pal[j]) ** 2).sum())
                        if d < bd:
                            best, bd = j, d
        if best >= 0:
            target[k] = best
        else:
            grid[cell].append(k)
    newl = np.where(lbl >= 0, target[np.maximum(lbl, 0)], lbl).astype(np.int32)
    return newl, pal


def reduce_paints(lbl, pal, k, iters=8):
    """Map the region colours to at most k paints (area-weighted k-means in OKLab, farthest-point init).
    Adjacent regions that get the same paint merge. Returns (lbl, pal) with labels into the k paints."""
    K = len(pal)
    if K <= k:
        return lbl, pal
    w = np.bincount(lbl[lbl >= 0], minlength=K).astype(np.float64)
    P = pal.astype(np.float64)
    c = [int(np.argmax(w))]
    d = ((P - P[c[0]]) ** 2).sum(1)
    for _ in range(1, k):
        j = int(np.argmax(d * np.sqrt(w)))         # far and heavy
        c.append(j)
        d = np.minimum(d, ((P - P[j]) ** 2).sum(1))
    C = P[c].copy()
    for _ in range(iters):
        a = ((P[:, None] - C[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            m = a == j
            if w[m].sum() > 0:
                C[j] = (P[m] * w[m, None]).sum(0) / w[m].sum()
    a = ((P[:, None] - C[None]) ** 2).sum(-1).argmin(1)
    newl = np.where(lbl >= 0, a[np.maximum(lbl, 0)], lbl).astype(np.int32)
    return newl, C.astype(np.float32)
