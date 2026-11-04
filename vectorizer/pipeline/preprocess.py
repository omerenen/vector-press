"""Edge-preserving pre-filtering (W1)."""
from __future__ import annotations

import numpy as np


def _d2(a, b):
    """Squared distance over the last axis (size 3), without a slow small-axis reduction."""
    d = a[..., 0] - b[..., 0]
    s = d * d
    d = a[..., 1] - b[..., 1]
    s += d * d
    d = a[..., 2] - b[..., 2]
    s += d * d
    return s


def sigma_filter(lab: np.ndarray, t: float = 0.04, iters: int = 1) -> np.ndarray:
    """Lee's sigma filter (see sigma_filter_ref). Each neighbour weight is symmetric (w(p, p+d) = w(p+d, p)), so only
    4 of the 8 neighbour distances are computed; channel planes are processed separately (no small-axis reductions).
    Same result as sigma_filter_ref up to float rounding."""
    out = np.ascontiguousarray(np.moveaxis(lab.astype(np.float32), -1, 0))    # (3, H, W)
    C, H, W = out.shape
    t2 = np.float32(t * t)
    for _ in range(iters):
        P = np.pad(out, ((0, 0), (1, 1), (1, 1)), mode="edge")             # same border handling as the reference
        Hp, Wp = H + 2, W + 2
        acc = P.copy()                         # centre pixel, weight 1
        cnt = np.ones((Hp, Wp), np.float32)
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            ys0, ys1 = slice(0, Hp - dy), slice(dy, Hp)
            if dx >= 0:
                xp, xq = slice(0, Wp - dx), slice(dx, Wp)
            else:
                xp, xq = slice(-dx, Wp), slice(0, Wp + dx)
            a = P[:, ys0, xp]
            b = P[:, ys1, xq]
            d = a[0] - b[0]
            s = d * d
            d = a[1] - b[1]
            s += d * d
            d = a[2] - b[2]
            s += d * d
            w = (s < t2).astype(np.float32)
            acc[:, ys0, xp] += w * b
            cnt[ys0, xp] += w
            acc[:, ys1, xq] += w * a
            cnt[ys1, xq] += w
        out = acc[:, 1:-1, 1:-1] / cnt[1:-1, 1:-1]
    return np.ascontiguousarray(np.moveaxis(out, 0, -1))


def sigma_filter_ref(lab: np.ndarray, t: float = 0.04, iters: int = 1) -> np.ndarray:
    """Lee's sigma filter in OKLab: average each pixel with its 3x3 neighbours that are
    within distance t. Flattens JPEG/noise speckle inside regions, never blends across
    edges (neighbours across an edge differ by more than t), keeps 1-px lines."""
    out = lab.astype(np.float32)
    H, W, _ = out.shape
    for _ in range(iters):
        P = np.pad(out, ((1, 1), (1, 1), (0, 0)), mode="edge")
        acc = np.zeros_like(out)
        cnt = np.zeros((H, W, 1), np.float32)
        t2 = t * t
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nb = P[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
                w = (((nb - out) ** 2).sum(-1, keepdims=True) < t2).astype(np.float32)
                acc += w * nb
                cnt += w
        out = acc / cnt
    return out
