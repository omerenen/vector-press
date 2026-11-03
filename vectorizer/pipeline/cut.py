"""Cut-file post-processing of the label map (vinyl / laser / Cricut).

  enforce_min_feature: features thinner than `min_px` are removed per colour layer (morphological opening with a disk
                       of diameter min_px); removed pixels go to the nearest surviving label; islands smaller than a
                       disk of that diameter are merged into their surroundings.
  silhouette:          two-level map: background (dominant border label) vs everything else.
  background_label:    label covering most of the image border.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi


def background_label(lbl):
    b = np.concatenate([lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]])
    b = b[b >= 0]
    if len(b) == 0:
        return -1
    return int(np.bincount(b).argmax())


def enforce_min_feature(lbl, min_px, pal_lab=None):
    if min_px < 1.5:
        return lbl
    r = max(1, int(round(min_px / 2)))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disk = xx * xx + yy * yy <= r * r
    out = np.full(lbl.shape, -2, np.int32)
    out[lbl == -1] = -1
    for k in np.unique(lbl):
        if k < 0:
            continue
        m = lbl == k
        sl = ndi.find_objects(m.astype(np.int32))[0]
        y0, y1 = max(0, sl[0].start - r - 1), min(lbl.shape[0], sl[0].stop + r + 1)
        x0, x1 = max(0, sl[1].start - r - 1), min(lbl.shape[1], sl[1].stop + r + 1)
        sub = m[y0:y1, x0:x1]
        op = ndi.binary_opening(sub, structure=disk)
        o = out[y0:y1, x0:x1]
        o[op] = k
    unknown = out == -2
    if unknown.any():
        known = ~unknown & (out >= 0)
        if known.any():
            _, (iy, ix) = ndi.distance_transform_edt(~known, return_indices=True)
            out[unknown] = out[iy[unknown], ix[unknown]]
        else:
            out[unknown] = lbl[unknown]
    from .quantize import merge_small_regions
    pal = pal_lab if pal_lab is not None else np.zeros((int(out.max()) + 1, 3), np.float32)
    return merge_small_regions(out, pal, int(np.ceil(np.pi * r * r)))


def silhouette(lbl, pal_lab):
    bg = background_label(lbl)
    fg = (lbl >= 0) & (lbl != bg)
    out = np.where(lbl < 0, -1, np.where(fg, 1, 0)).astype(np.int32)
    # foreground colour: darkest foreground palette entry (fallback black)
    if fg.any():
        ks = np.unique(lbl[fg])
        dark = pal_lab[ks[np.argmin(pal_lab[ks, 0])]]
    else:
        dark = np.array([0.0, 0.0, 0.0], np.float32)
    bgc = pal_lab[bg] if bg >= 0 else np.array([1.0, 0.0, 0.0], np.float32)
    return out, np.array([bgc, dark], np.float32)
