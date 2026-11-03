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

import time

import numpy as np
from scipy import ndimage as ndi

from .boundary import assemble_regions, build_graph, label_regions
from .color import hex_color
from .fit import fit_chain, reverse_geom
from .svgout import _join, fmt, geom_to_tokens, loop_d


def _containment(regions, R, lbl, semi=None):
    """Decide hole filling and nesting depth (number of enclosing drawn regions).

    Holes are not filled if they contain transparent pixels or semi-transparent regions."""
    trans = lbl < 0
    if semi is not None and semi.any():
        trans = trans | semi[R]
    depth = np.zeros(len(regions), np.int32)
    objs = None
    for r in sorted(regions, key=lambda r: -(r.loop_area[r.outer] if r.loops else 0)):
        if r.label < 0 or len(r.loops) <= 1:
            continue
        if objs is None:
            objs = ndi.find_objects(R + 1)
        sl = objs[r.rid]
        if sl is None:
            continue
        m = R[sl] == r.rid
        inside = ndi.binary_fill_holes(m) & ~m
        if not inside.any():
            continue
        if (inside & trans[sl]).any():
            r.fill_holes = False
        ids = np.unique(R[sl][inside])
        depth[ids] = np.maximum(depth[ids], depth[r.rid] + 1)
    return depth


def build_elements(lbl, palette_rgb, opts, timings=None, label_fill=None, ctx=None, alpha=None):
    """Return (list of SVG element strings, stats).

    label_fill: optional {label: (fill_attr_string, seam_paint)} overrides (e.g. gradients).
    """
    timings = timings if timings is not None else {}
    prec = int(opts.get("precision", 2))
    t = time.perf_counter()
    R, rl = label_regions(lbl)
    chains = build_graph(R)
    regions = assemble_regions(chains, rl, R)
    timings["graph"] = time.perf_counter() - t
    t = time.perf_counter()
    drawn = np.array([r.label >= 0 for r in regions], bool)
    if ctx is not None:
        from .fit import subpixel_field
        ctx = dict(ctx, R=R, region_label=rl)
        ctx["field"] = subpixel_field(ctx)
    for c in chains:
        if (c.left >= 0 and drawn[c.left]) or (c.right >= 0 and drawn[c.right]):
            fit_chain(c, opts, ctx)
    timings["fit"] = time.perf_counter() - t
    t = time.perf_counter()
    # region opacity from the input alpha (median over the region); < 0.98 -> fill-opacity
    opacity = np.ones(len(regions))
    if alpha is not None and (alpha[lbl >= 0] < 250).any():
        from scipy import ndimage as _ndi
        idx = np.arange(len(regions))
        a16 = alpha.astype(np.int16)
        P = np.pad(a16, 1, mode="edge")
        var = np.maximum.reduce([np.abs(P[1:-1, 2:] - a16), np.abs(P[1:-1, :-2] - a16),
                                 np.abs(P[2:, 1:-1] - a16), np.abs(P[:-2, 1:-1] - a16)])
        flat = (var <= 10) & (alpha < 250)
        # only genuinely translucent regions (mostly flat partial alpha), not anti-aliasing bands
        frac = np.bincount(R.ravel(), weights=flat.ravel().astype(np.float64), minlength=len(regions)) / \
            np.maximum(np.bincount(R.ravel(), minlength=len(regions)), 1)
        med = _ndi.median(np.where(flat, alpha, 255).astype(np.float64), labels=R + 1, index=idx + 1)
        opacity = np.clip(np.asarray(med, np.float64) / 255.0, 0, 1)
        opacity[(opacity >= 0.98) | (frac < 0.5)] = 1.0
    semi = opacity < 1.0
    depth = _containment(regions, R, lbl, semi)
    converted, stroke_els = set(), []
    if opts.get("centerline"):
        from .centerline import centerline_regions
        tc = time.perf_counter()
        converted, stroke_els = centerline_regions(R, rl, regions, palette_rgb, opts, label_fill)
        timings["centerline"] = time.perf_counter() - tc
        for rid in converted:
            drawn[rid] = False
    order = sorted([r for r in regions if r.label >= 0 and r.loops and r.rid not in converted],
                   key=lambda r: (depth[r.rid], -r.loop_area[r.outer], r.rid))
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
    level_start = 0
    while level_start < len(order):
        d = depth[order[level_start].rid]
        level_end = level_start
        while level_end < len(order) and depth[order[level_end].rid] == d:
            level_end += 1
        seams = {}      # colour -> tokens
        fills = {}      # key -> [attr, tokens]   (insertion ordered)
        singles = []    # primitive / special elements
        for r in order[level_start:level_end]:
            if label_fill and r.label in label_fill:
                fill_attr, col = label_fill[r.label]
            else:
                col = hex_color(palette_rgb[r.label])
                fill_attr = f'fill="{col}"'
            if semi[r.rid]:
                fill_attr += f' fill-opacity="{opacity[r.rid]:.3f}"'
            loops = [r.outer] + ([] if r.fill_holes else [i for i in range(len(r.loops)) if i != r.outer])
            outer = r.loops[r.outer]
            prim = chains[outer[0][0]].prim if len(outer) == 1 else None
            if len(loops) == 1 and prim is not None and opts.get("primitives", True):
                singles.append(_prim_element(prim, fill_attr, prec))
                n_prims += 1
            else:
                toks = []
                for li in loops:
                    toks += loop_d([oriented(cid, rev) for cid, rev in r.loops[li]], prec)
                fills.setdefault(fill_attr, [fill_attr, []])[1].extend(toks)
            if seam_w > 0 and not semi[r.rid]:
                for li in loops:
                    for cid, rev in r.loops[li]:
                        c = chains[cid]
                        other = c.left if not rev else c.right
                        if other < 0 or not drawn[other] or semi[other]:
                            continue
                        do = depth[other]
                        if do < d:
                            continue                       # container is below us: it handles (or fills) the seam
                        if do == d and other < r.rid:
                            continue                       # same level: emit each shared chain once
                        if do > d and r.fill_holes and li != r.outer:
                            continue                       # nested region over our filled hole: no seam needed
                        seams.setdefault(col, []).extend(geom_to_tokens(oriented(cid, rev), prec, move=True))
        for col, toks in seams.items():
            elements.append(f'<path fill="none" stroke="{col}" stroke-width="{fmt(seam_w, 2)}" '
                            f'stroke-linecap="round" stroke-linejoin="round" d="{_join(toks)}"/>')
        for attr, toks in fills.values():
            elements.append(f'<path {attr} d="{_join(toks)}"/>')
        elements.extend(singles)
        level_start = level_end
    elements.extend(stroke_els)
    timings["assemble"] = time.perf_counter() - t
    stats = {"n_regions": len(order), "n_chains": len(chains), "n_primitives": n_prims, "n_strokes": len(stroke_els)}
    return elements, stats


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
