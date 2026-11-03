"""Label map -> shared boundary graph -> fitted geometry -> SVG elements.

Drawing model ("stacked with filled holes"):
  * regions are drawn in decreasing order of their outer-loop area, so a region is
    always drawn before every region nested in it;
  * a region's holes are *filled* (omitted) when they contain no transparent pixels:
    the nested regions are painted on top, so their shared border needs no
    anti-aliasing seam handling and the path data is emitted only once;
  * side-by-side neighbours (border on the outer loop of the lower region) get a
    thin "seam" stroke in the lower region's colour along exactly the shared chain,
    which removes background bleed-through (conflation artefacts) without moving
    any visible edge.
"""
from __future__ import annotations

import math
import time

import numpy as np
from scipy import ndimage as ndi

from .boundary import assemble_regions, build_graph, label_regions
from .color import hex_color
from .fit import fit_chain, reverse_geom
from .svgout import _join, fmt, geom_to_tokens, loop_d


def _decide_fill_holes(regions, R, lbl):
    trans = lbl < 0
    if not trans.any():
        return
    objs = None
    for r in regions:
        if r.label < 0 or len(r.loops) <= 1:
            continue
        if objs is None:
            objs = ndi.find_objects(R + 1)
        sl = objs[r.rid]
        if sl is None:
            continue
        m = R[sl] == r.rid
        inside = ndi.binary_fill_holes(m) & ~m
        if (inside & trans[sl]).any():
            r.fill_holes = False


def build_elements(lbl, palette_rgb, opts, timings=None, region_extra=None):
    """Return (list of SVG element strings, stats)."""
    timings = timings if timings is not None else {}
    prec = int(opts.get("precision", 2))
    t = time.perf_counter()
    R, rl = label_regions(lbl)
    chains = build_graph(R)
    regions = assemble_regions(chains, rl, R)
    timings["graph"] = time.perf_counter() - t
    t = time.perf_counter()
    drawn = np.array([r.label >= 0 for r in regions], bool)
    for c in chains:
        if (c.left >= 0 and drawn[c.left]) or (c.right >= 0 and drawn[c.right]):
            fit_chain(c, opts)
    timings["fit"] = time.perf_counter() - t
    t = time.perf_counter()
    _decide_fill_holes(regions, R, lbl)
    order = sorted([r for r in regions if r.label >= 0 and r.loops],
                   key=lambda r: (-r.loop_area[r.outer], r.rid))
    rank = {r.rid: i for i, r in enumerate(order)}
    rev_cache = {}

    def oriented(cid, rev):
        g = chains[cid].geom
        if not rev:
            return g
        if cid not in rev_cache:
            rev_cache[cid] = reverse_geom(g)
        return rev_cache[cid]

    seam_w = opts.get("seam_width", 1.0)
    elements = []
    n_prims = 0
    for r in order:
        col = hex_color(palette_rgb[r.label])
        loops = [r.outer] + ([] if r.fill_holes else [i for i in range(len(r.loops)) if i != r.outer])
        extra = region_extra.get(r.rid) if region_extra else None
        fill_attr = f'fill="{col}"' if extra is None else extra
        outer = r.loops[r.outer]
        prim = chains[outer[0][0]].prim if len(outer) == 1 else None
        if len(loops) == 1 and prim is not None and opts.get("primitives", True):
            elements.append(_prim_element(prim, fill_attr, prec))
            n_prims += 1
        else:
            toks = []
            for li in loops:
                toks += loop_d([oriented(cid, rev) for cid, rev in r.loops[li]], prec)
            rule = ' fill-rule="evenodd"' if len(loops) > 1 else ""
            elements.append(f'<path {fill_attr}{rule} d="{_join(toks)}"/>')
        # seams: chains on our outer loop (or unfilled holes) shared with a later-drawn region
        if seam_w > 0:
            stoks = []
            for li in loops:
                for cid, rev in r.loops[li]:
                    c = chains[cid]
                    other = c.left if not rev else c.right
                    if other < 0 or not drawn[other] or rank.get(other, -1) < rank[r.rid]:
                        continue
                    stoks += geom_to_tokens(oriented(cid, rev), prec, move=True)
            if stoks:
                scol = col if extra is None else _extra_color(extra, col)
                elements.append(f'<path fill="none" stroke="{scol}" stroke-width="{fmt(seam_w, 2)}" d="{_join(stoks)}"/>')
    timings["assemble"] = time.perf_counter() - t
    stats = {"n_regions": len(order), "n_chains": len(chains), "n_primitives": n_prims}
    return elements, stats


def _extra_color(extra, default):
    i = extra.find('data-seam="')
    if i < 0:
        return default
    return extra[i + 11: extra.find('"', i + 11)]


def _prim_element(p, fill_attr, prec):
    f = lambda v: fmt(v, prec)  # noqa: E731
    if p["type"] == "circle":
        return f'<circle {fill_attr} cx="{f(p["cx"])}" cy="{f(p["cy"])}" r="{f(p["r"])}"/>'
    if p["type"] == "ellipse":
        rot = ""
        ang = p["angle"] % 180
        if abs(ang) > 0.05 and abs(ang - 180) > 0.05:
            rot = f' transform="rotate({fmt(ang, 2)} {f(p["cx"])} {f(p["cy"])})"'
        return f'<ellipse {fill_attr} cx="{f(p["cx"])}" cy="{f(p["cy"])}" rx="{f(p["rx"])}" ry="{f(p["ry"])}"{rot}/>'
    if p["type"] == "rect":
        x, y = p["cx"] - p["w"] / 2, p["cy"] - p["h"] / 2
        rot = f' transform="rotate({fmt(p["angle"], 2)} {f(p["cx"])} {f(p["cy"])})"' if p["angle"] else ""
        rx = f' rx="{f(p["r"])}"' if p["r"] > 0 else ""
        return f'<rect {fill_attr} x="{f(x)}" y="{f(y)}" width="{f(p["w"])}" height="{f(p["h"])}"{rx}{rot}/>'
    raise ValueError(p["type"])
