"""Centerline tracing for thin strokes (W8).

A region qualifies if it is thin everywhere (max distance-transform value <= max_half_width)
and long compared to its width. Its skeleton is traced into polylines (junction / end
pixels are nodes), short spurs are pruned, each polyline is smoothed and fitted with the
generic line/Bezier fitter and emitted as an SVG stroke whose width is estimated from
the distance transform along the skeleton. Every converted region is verified by
rendering its strokes and comparing with the region mask (IoU); otherwise the region
keeps its filled outline.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage as ndi

from .fit import _smooth, detect_corners, fit_piece
from .svgout import _join, fmt, geom_to_tokens

_NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _trace_skeleton(sk):
    """Return list of polylines (lists of (y, x)) covering all skeleton pixels."""
    H, W = sk.shape
    P = np.pad(sk, 1)
    nbc = sum(np.roll(np.roll(P, -dy, 0), -dx, 1) for dy, dx in _NB)[1:-1, 1:-1] * sk
    node = sk & (nbc != 2)
    pix = set(zip(*np.nonzero(sk)))
    nodes = set(zip(*np.nonzero(node)))
    visited_edges = set()
    lines = []

    def nbrs(p):
        y, x = p
        return [(y + dy, x + dx) for dy, dx in _NB if (y + dy, x + dx) in pix]

    def walk(start, nxt):
        path = [start, nxt]
        visited_edges.add((start, nxt))
        visited_edges.add((nxt, start))
        prev, cur = start, nxt
        while cur not in nodes:
            cand = [q for q in nbrs(cur) if q != prev and (cur, q) not in visited_edges]
            if not cand:
                break
            # prefer 4-neighbours to avoid diagonal shortcuts
            cand.sort(key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))
            q = cand[0]
            visited_edges.add((cur, q))
            visited_edges.add((q, cur))
            path.append(q)
            prev, cur = cur, q
            if cur == start:
                break
        return path

    for s in nodes:
        for q in nbrs(s):
            if (s, q) not in visited_edges:
                lines.append(walk(s, q))
    # closed loops without nodes
    rest = pix - set(p for line in lines for p in line)
    while rest:
        s = rest.pop()
        nb = nbrs(s)
        if not nb:
            continue
        line = walk(s, nb[0])
        rest -= set(line)
        lines.append(line)
    return lines, nodes


def region_strokes(mask, opts, prec=2):
    """Return (path tokens, stats) for a thin region mask, or (None, reason)."""
    from skimage.morphology import skeletonize
    dt = ndi.distance_transform_edt(mask)
    maxhw = opts.get("max_stroke_halfwidth", 5.0)
    if dt.max() > maxhw:
        return None, "thick"
    sk = skeletonize(mask)
    if sk.sum() < 3:
        return None, "tiny"
    lines, nodes = _trace_skeleton(sk)
    # stroke width: area / skeleton length is robust; dt-based width for reference
    total_len = 0.0
    polys = []
    for line in lines:
        P = np.array([(x + 0.5, y + 0.5) for y, x in line], np.float64)
        if len(P) >= 2:
            L = float(np.sqrt(((P[1:] - P[:-1]) ** 2).sum(1)).sum())
        else:
            L = 0.0
        polys.append((P, L, line))
        total_len += L
    if total_len < 4:
        return None, "short"
    width = mask.sum() / total_len
    # prune spurs: end-to-node branches shorter than the stroke width
    keep = []
    for P, L, line in polys:
        ends = [line[0] in nodes and len(_nb8(line[0], sk)) == 1, line[-1] in nodes and len(_nb8(line[-1], sk)) == 1]
        if (ends[0] or ends[1]) and not (ends[0] and ends[1]) and L < 1.2 * width:
            continue
        keep.append(P)
    toks = []
    tol = opts.get("fit_tol", 0.6)
    for P in keep:
        if len(P) < 2:
            continue
        closed = len(P) > 3 and np.hypot(*(P[0] - P[-1])) < 1.5
        Q = _smooth(P, 1.0, False)
        cs = detect_corners(Q, False, opts.get("corner_angle", 55.0), 3.0)
        br = [0] + cs + [len(Q) - 1]
        segs = []
        for a, b in zip(br[:-1], br[1:]):
            if b > a:
                segs += fit_piece(Q[a:b + 1], tol, opts.get("line_tol", 0.65), 0.0)
        toks += geom_to_tokens({"start": tuple(Q[0]), "segs": segs}, prec, move=True)
        if closed:
            toks.append("z")
    return toks, {"width": float(width)}


def _nb8(p, sk):
    y, x = p
    H, W = sk.shape
    return [(y + dy, x + dx) for dy, dx in _NB if 0 <= y + dy < H and 0 <= x + dx < W and sk[y + dy, x + dx]]


def centerline_regions(R, rl, regions, palette_rgb, opts, label_fill=None):
    """Try to convert thin regions to strokes. Returns ({rid}, [svg elements])."""
    from .color import hex_color
    from ..render import render_svg
    H, W = R.shape
    prec = int(opts.get("precision", 2))
    objs = ndi.find_objects(R + 1)
    # background = largest drawn region; never converted
    drawn = [r for r in regions if r.label >= 0]
    if len(drawn) < 2:
        return set(), []
    bg = max(drawn, key=lambda r: r.area).rid
    converted, elements = set(), []
    min_area = opts.get("centerline_min_area", 12)
    for r in drawn:
        if r.rid == bg or r.area < min_area or (label_fill and r.label in label_fill):
            continue
        sl = objs[r.rid]
        if sl is None:
            continue
        y0, y1 = max(0, sl[0].start - 2), min(H, sl[0].stop + 2)
        x0, x1 = max(0, sl[1].start - 2), min(W, sl[1].stop + 2)
        m = R[y0:y1, x0:x1] == r.rid
        # quick thinness test: mean thickness
        per = (m[:, 1:] != m[:, :-1]).sum() + (m[1:] != m[:-1]).sum()
        if 2 * m.sum() / max(per, 1) > opts.get("max_stroke_halfwidth", 5.0) * 1.2:
            continue
        toks, info = region_strokes(m, opts, prec)
        if toks is None:
            continue
        w = info["width"]
        col = hex_color(palette_rgb[r.label])
        # shift to image coordinates
        d = _join(toks)
        el = (f'<path fill="none" stroke="{col}" stroke-width="{fmt(w, 2)}" stroke-linecap="round" '
              f'stroke-linejoin="round" transform="translate({x0} {y0})" d="{d}"/>')
        # verify
        hh, ww = m.shape
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ww} {hh}" width="{ww}" height="{hh}">'
               f'<path fill="none" stroke="#000" stroke-width="{fmt(w, 2)}" stroke-linecap="round" stroke-linejoin="round" d="{d}"/></svg>')
        try:
            ren = render_svg(svg, ww, hh)[..., 3] >= 128
        except Exception:
            continue
        inter = (ren & m).sum()
        union = (ren | m).sum()
        iou = inter / max(union, 1)
        if iou < opts.get("centerline_iou", 0.75):
            continue
        converted.add(r.rid)
        elements.append(el)
    return converted, elements
