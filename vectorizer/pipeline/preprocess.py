"""Edge-preserving pre-filtering (W1)."""
from __future__ import annotations

import numpy as np


def sigma_filter(lab: np.ndarray, t: float = 0.04, iters: int = 1) -> np.ndarray:
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
