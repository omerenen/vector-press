"""Heuristic image-type classifier (W7).

Features are computed on a <=256 px thumbnail (cheap, resolution independent).
Types: icon / logo (flat, few colours), flat_illustration, line_art, diagram,
gradient (smooth colour ramps), photo (continuous tone / texture).
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from .color import rgb8_to_oklab


def features(rgba: np.ndarray) -> dict:
    H, W = rgba.shape[:2]
    s = 256.0 / max(H, W)
    im = Image.fromarray(rgba, "RGBA")
    if s < 1:
        im = im.resize((max(1, int(W * s)), max(1, int(H * s))), Image.BILINEAR)
    from PIL import ImageFilter
    a = np.asarray(im)
    alpha = a[..., 3] >= 128
    # 3x3 median suppresses noise / JPEG ringing so "smooth" means real colour ramps
    rgbm = np.asarray(Image.fromarray(np.ascontiguousarray(a[..., :3])).filter(ImageFilter.MedianFilter(3)))
    a = np.dstack([rgbm, a[..., 3]])
    if alpha.sum() < 16:
        return {"empty": True}
    rgb = a[..., :3]
    lab = rgb8_to_oklab(rgb)
    # local contrast (max OKLab distance to 4-neighbours), only between opaque pixels
    d = np.zeros(alpha.shape, np.float32)
    dx = np.sqrt(((lab[:, 1:] - lab[:, :-1]) ** 2).sum(-1)) * (alpha[:, 1:] & alpha[:, :-1])
    dy = np.sqrt(((lab[1:] - lab[:-1]) ** 2).sum(-1)) * (alpha[1:] & alpha[:-1])
    d[:, 1:] = np.maximum(d[:, 1:], dx)
    d[:, :-1] = np.maximum(d[:, :-1], dx)
    d[1:] = np.maximum(d[1:], dy)
    d[:-1] = np.maximum(d[:-1], dy)
    dv = d[alpha]
    q = (rgb[alpha] >> 4).astype(np.int32)
    key = (q[:, 0] << 8) | (q[:, 1] << 4) | q[:, 2]
    cnt = np.sort(np.bincount(key, minlength=4096))[::-1].astype(np.float64)
    cs = np.cumsum(cnt) / cnt.sum()
    f = {
        "c90": int(np.searchsorted(cs, 0.90) + 1),
        "c99": int(np.searchsorted(cs, 0.99) + 1),
        "top1": float(cs[0]),
        "flat": float((dv < 0.004).mean()),
        "smooth": float(((dv >= 0.004) & (dv < 0.03)).mean()),
        "edge": float((dv >= 0.1).mean()),
        "chroma": float(np.sqrt(lab[alpha][:, 1] ** 2 + lab[alpha][:, 2] ** 2).mean()),
        "transparent": float(1 - alpha.mean()),
    }
    # "inkiness": share of non-background pixels that are near strong edges (thin strokes)
    bgk = int(np.argmax(np.bincount(key, minlength=4096)))
    nonbg = key != bgk
    f["ink"] = float(nonbg.mean())
    f["ink_edge"] = float(((dv >= 0.05) & nonbg).sum() / max(1, nonbg.sum()))
    return f


def classify(rgba: np.ndarray) -> tuple[str, dict]:
    """Return (image_type, features). image_type in
    {icon, logo, line_art, gradient, photo} (flat illustrations are reported as "logo").

    Rules = depth-3 decision tree fitted on the *dev* split features (grouped into the four
    preset families flat / lines / gradient / photo), thresholds rounded; see EXPERIMENTS.md.
    """
    f = features(rgba)
    if f.get("empty"):
        return "icon", f
    if f["ink_edge"] <= 0.41:
        if f["c90"] > 13.5:
            return ("gradient" if f["flat"] > 0.53 else "photo"), f
        return ("icon" if f["c90"] <= 4 and f["top1"] > 0.5 else "logo"), f
    if f["ink"] <= 0.27:
        return "line_art", f
    return "logo", f
