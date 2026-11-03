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
    r = R.ravel()
    ok = r >= 0
    r = r[ok]
    px = lab.reshape(-1, 3)[ok].astype(np.float64)
    area = np.bincount(r, minlength=n).astype(np.float64)
    S = np.stack([np.bincount(r, weights=px[:, c], minlength=n) for c in range(3)], 1)
    Q = np.bincount(r, weights=(px * px).sum(1), minlength=n)
    return area, S, Q


def ms_merge(R, lab, lam, max_rounds=400, edge_weight=None, protect=None):
    """Greedy Mumford-Shah merging of the regions of R (ids 0..n-1, -1 = excluded).

    lam: boundary price (OKLab^2 per px of boundary). edge_weight: optional per-edge factor (same order as
    region_edges(R)) multiplying the boundary price (e.g. < 1 for strong image edges -> harder to merge).
    Returns (Rnew with ids 0..m-1, info).
    """
    n = int(R.max()) + 1 if (R >= 0).any() else 0
    if n <= 1:
        return R, {"rounds": 0, "n0": n, "n1": n}
    area, S, Q = _region_stats(R, lab, n)
    a, b, L = region_edges(R)
    w = np.ones_like(L) if edge_weight is None else edge_weight.astype(np.float64)
    parent = np.arange(n)
    alive_n = n
    rounds = 0
    for rounds in range(1, max_rounds + 1):
        if len(a) == 0:
            break
        mu = S / np.maximum(area, 1)[:, None]
        d2 = ((mu[a] - mu[b]) ** 2).sum(1)
        na, nb = area[a], area[b]
        r = na * nb / (na + nb) * d2 / (lam * L * w)
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
        np.add.at(area, tgt[mv], area[mv])
        np.add.at(S, tgt[mv], S[mv])
        np.add.at(Q, tgt[mv], Q[mv])
        area[mv] = 0
        parent[mv] = tgt[mv]
        alive_n -= len(mv)
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
    return Rn, {"rounds": rounds, "n0": n, "n1": len(ids)}


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
