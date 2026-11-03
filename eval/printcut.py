"""Print / cut-readiness metrics for an SVG (format-agnostic: works for our output and VTracer's).

Physical scale: the SVG is assumed to be produced at `width_mm` (default 100 mm = 10 cm) wide.
  open_subpaths        filled subpaths that are not explicitly closed (Z) and whose end != start
  self_intersections   subpaths whose flattened outline is not simple (cutters choke on these)
  overlap_ratio        sum of the (exact, shapely) areas of all filled shapes / area of their union - 1 (0 = pure cutout);
                       the union area comes from a crisp 800-px render (resolution about +-0.5 %)
  n_colors             distinct fill paints (a gradient counts as one paint)
  tiny_islands         connected same-colour components with equivalent diameter < min_mm (0.5 mm) - weeding nightmare
  thin_features        connected components thinner than min_mm somewhere (2*max distance < min_mm) or with
                       > 20 % of their area in parts thinner than min_mm
  n_nodes              path segments (from eval.metrics.structure_stats)
Raster-based parts render the SVG with crisp edges at `ppm` px/mm (default 8 px/mm -> 800 px at 10 cm).
"""
from __future__ import annotations

import math
import re

import numpy as np
from scipy import ndimage as ndi

from eval.metrics import _NUM, parse_path, svg_elements

_FILL_RE = re.compile(r"fill\s*[:=]\s*\"?([^\";]+)")


def _flatten_subpaths(d, M, n_curve=8):
    """Path data -> list of (points (k,2) after transform, closed_flag)."""
    out = []
    cur = []
    closed = False
    last = (0.0, 0.0)
    for c, p in parse_path(d):
        if c == "M":
            if len(cur) >= 2:
                out.append((cur, closed))
            cur = [p[0]]
            closed = False
            last = p[0]
        elif c in ("L", "T"):
            cur.append(p[0])
            last = p[0]
        elif c in ("C", "S", "Q"):
            pts = [last] + list(p)
            if c == "Q":
                q0, q1, q2 = pts
                for t in np.linspace(0, 1, n_curve + 1)[1:]:
                    cur.append(((1 - t) ** 2 * q0[0] + 2 * (1 - t) * t * q1[0] + t * t * q2[0],
                                (1 - t) ** 2 * q0[1] + 2 * (1 - t) * t * q1[1] + t * t * q2[1]))
            elif c == "C":
                b0, b1, b2, b3 = pts
                for t in np.linspace(0, 1, n_curve + 1)[1:]:
                    mt = 1 - t
                    cur.append((mt ** 3 * b0[0] + 3 * mt * mt * t * b1[0] + 3 * mt * t * t * b2[0] + t ** 3 * b3[0],
                                mt ** 3 * b0[1] + 3 * mt * mt * t * b1[1] + 3 * mt * t * t * b2[1] + t ** 3 * b3[1]))
            else:  # S approximated by its end point chain
                cur.append(p[-1])
            last = p[-1]
        elif c == "A":
            end, (rx, ry, rot, large, sweep) = p[0], p[1]
            cur.extend(_arc_points(last, end, rx, ry, rot, large, sweep, 16))
            last = end
        elif c == "Z":
            closed = True
            if cur:
                last = cur[0]
    if len(cur) >= 2:
        out.append((cur, closed))
    res = []
    for pts, cl in out:
        P = np.array(pts, float)
        P = (np.c_[P, np.ones(len(P))] @ M.T)[:, :2]
        res.append((P, cl))
    return res


def _arc_points(p0, p1, rx, ry, rot, large, sweep, n):
    """SVG endpoint arc -> points (centre parameterisation, F.6.5 of the SVG spec)."""
    x1, y1 = p0
    x2, y2 = p1
    rx, ry = abs(rx), abs(ry)
    if rx < 1e-9 or ry < 1e-9:
        return [p1]
    phi = math.radians(rot)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    co = math.sqrt(max(0.0, num / den)) if den > 0 else 0.0
    if large == sweep:
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(u, v):
        return math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])
    t1 = ang((1, 0), ((x1p - cxp) / rx, (y1p - cyp) / ry))
    dt = ang(((x1p - cxp) / rx, (y1p - cyp) / ry), ((-x1p - cxp) / rx, (-y1p - cyp) / ry))
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    pts = []
    for k in range(1, n + 1):
        t = t1 + dt * k / n
        pts.append((cx + rx * math.cos(t) * cp - ry * math.sin(t) * sp, cy + rx * math.cos(t) * sp + ry * math.sin(t) * cp))
    return pts


def _element_subpaths(tag, at, M):
    def g(k, d=0.0):
        try:
            return float(re.findall(_NUM, at.get(k, str(d)))[0])
        except Exception:
            return d
    if tag == "path":
        return _flatten_subpaths(at.get("d", ""), M)
    if tag in ("circle", "ellipse"):
        cx, cy = g("cx"), g("cy")
        rx = ry = g("r") if tag == "circle" else 0
        if tag == "ellipse":
            rx, ry = g("rx"), g("ry")
        t = np.linspace(0, 2 * np.pi, 48, endpoint=False)
        P = np.c_[cx + rx * np.cos(t), cy + ry * np.sin(t), np.ones(48)] @ M.T
        return [(P[:, :2], True)]
    if tag == "rect":
        x, y, w, h = g("x"), g("y"), g("width"), g("height")
        P = np.array([[x, y, 1], [x + w, y, 1], [x + w, y + h, 1], [x, y + h, 1]]) @ M.T
        return [(P[:, :2], True)]
    if tag in ("polygon", "polyline"):
        v = [float(x) for x in re.findall(_NUM, at.get("points", ""))]
        P = np.c_[np.array(v[0::2]), np.array(v[1::2]), np.ones(len(v) // 2)] @ M.T
        return [(P[:, :2], tag == "polygon")]
    return []


def _is_filled(at):
    f = at.get("fill")
    st = at.get("style", "")
    if f is None and "fill:" in st:
        f = st.split("fill:")[1].split(";")[0].strip()
    return f != "none"


def geometry_metrics(svg, scale_to_mm, vb_w=None):
    from shapely.geometry import Polygon
    from shapely.validation import make_valid
    open_sp = selfx = 0
    n_sub = 0
    areas = 0.0
    geoms = []
    paints = set()
    for tag, at, M in svg_elements(svg):
        if not _is_filled(at):
            continue
        paints.add(at.get("fill", "#000"))
        sps = _element_subpaths(tag, at, M)
        polys = []
        for P, closed in sps:
            n_sub += 1
            if len(P) < 3:
                continue
            if not closed and np.hypot(*(P[0] - P[-1])) > 1e-6:
                open_sp += 1
            ring = Polygon(P * scale_to_mm)
            if not ring.exterior.is_simple:
                selfx += 1
            polys.append(ring)
        if not polys:
            continue
        # even-odd composition of the subpaths (nonzero == even-odd for properly oriented, non-overlapping rings)
        g = None
        for p in polys:
            try:
                p = make_valid(p).buffer(0)
                g = p if g is None else g.symmetric_difference(p, grid_size=1e-6)
            except Exception:           # GEOS topology failure on degenerate input: skip this ring
                continue
        if g is not None and not g.is_empty:
            areas += g.area
            geoms.append(g)
    # union area = covered area of a crisp render (exact polygon union is slow / fragile on 10^4 paths)
    union = 0.0
    if geoms:
        import io
        import resvg_py
        from PIL import Image
        Wr = 800
        png = resvg_py.svg_to_bytes(svg_string=svg, width=Wr, shape_rendering="crisp_edges", skip_system_fonts=True)
        a = np.asarray(Image.open(io.BytesIO(bytes(png))).convert("RGBA"))[..., 3]
        mm_per_px = (vb_w * scale_to_mm) / a.shape[1]
        union = float((a >= 128).sum()) * mm_per_px * mm_per_px
    return {"open_subpaths": open_sp, "self_intersections": selfx, "n_subpaths": n_sub,
            "overlap_ratio": float(areas / union - 1.0) if union > 0 else (float("nan") if union != union else 0.0),
            "n_colors": len(paints)}


def _layers(svg):
    """Split a stacked SVG into one SVG per fill paint (cut layer): (paint, svg_with_only_that_layer_in_black)."""
    import xml.etree.ElementTree as ET
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root = ET.fromstring(svg)
    els = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("path", "circle", "ellipse", "rect", "polygon"):
            if el.attrib.get("fill") == "none":
                continue
            els.append(el)
    paints = {}
    for el in els:
        paints.setdefault(el.attrib.get("fill", "#000"), []).append(el)
    head = {k: v for k, v in root.attrib.items()}
    out = []
    for paint, group in paints.items():
        body = ""
        for el in group:
            at = dict(el.attrib)
            for k in ("fill", "fill-opacity", "stroke", "stroke-width", "opacity", "style"):
                at.pop(k, None)
            tag = el.tag.split("}")[-1]
            body += f"<{tag} " + " ".join(f'{k}="{v}"' for k, v in at.items()) + ' fill="#000"/>'
        attrs = " ".join(f'{k}="{v}"' for k, v in head.items() if not k.startswith("{"))
        out.append((paint, f'<svg xmlns="http://www.w3.org/2000/svg" {attrs}>{body}</svg>'))
    return out


def raster_metrics(svg, W, H, width_mm=100.0, ppm=8.0, min_mm=0.5, max_layers=64):
    """Per cut layer (fill paint): tiny islands and too-thin features at the physical scale."""
    import io
    import resvg_py
    from PIL import Image
    from skimage.measure import label as sklabel
    Wr = int(round(width_mm * ppm))
    Hr = max(1, int(round(Wr * H / W)))
    min_px = min_mm * ppm
    tiny = thin = ncomp = 0
    thin_area_tot = 0.0
    layers = _layers(svg)
    approx = len(layers) > max_layers
    if approx:
        # too many paints (e.g. photo-like output): one crisp render, visible region of each colour = its layer
        png = resvg_py.svg_to_bytes(svg_string=svg, width=Wr, height=Hr, shape_rendering="crisp_edges",
                                    skip_system_fonts=True)
        a = np.asarray(Image.open(io.BytesIO(bytes(png))).convert("RGBA"))
        key = (a[..., 0].astype(np.int64) << 16) | (a[..., 1].astype(np.int64) << 8) | a[..., 2]
        key[a[..., 3] < 128] = -1
        C = sklabel(key, background=-1, connectivity=1)
        n = int(C.max())
        area = np.bincount(C.ravel(), minlength=n + 1)[1:].astype(np.float64)
        eqd = 2 * np.sqrt(area / np.pi)
        bnd = np.zeros(C.shape, bool)
        bnd[:, 1:] |= C[:, 1:] != C[:, :-1]
        bnd[:, :-1] |= C[:, 1:] != C[:, :-1]
        bnd[1:] |= C[1:] != C[:-1]
        bnd[:-1] |= C[1:] != C[:-1]
        dt = ndi.distance_transform_edt(~bnd) + 0.5
        mx = np.asarray(ndi.maximum(dt, labels=C, index=np.arange(1, n + 1))) if n else np.zeros(0)
        big = eqd >= min_px
        return {"tiny_islands": int((eqd < min_px).sum()), "thin_features": int((big & (2 * mx < min_px)).sum()),
                "n_components": n, "thin_area_mm2": float("nan"), "layers_approx": True}
    for paint, lsvg in layers:
        try:
            png = resvg_py.svg_to_bytes(svg_string=lsvg, width=Wr, height=Hr, shape_rendering="crisp_edges",
                                        skip_system_fonts=True)
        except Exception:
            continue
        m = np.asarray(Image.open(io.BytesIO(bytes(png))).convert("RGBA"))[..., 3] >= 128
        if not m.any():
            continue
        ys, xs = np.nonzero(m)
        pad = int(min_px) + 2
        m = np.pad(m[ys.min():ys.max() + 1, xs.min():xs.max() + 1], pad)
        C = sklabel(m, connectivity=1)
        n = int(C.max())
        ncomp += n
        area = np.bincount(C.ravel(), minlength=n + 1)[1:].astype(np.float64)
        eqd = 2 * np.sqrt(area / np.pi)
        tiny += int((eqd < min_px).sum())
        dt = ndi.distance_transform_edt(m)
        mx = np.asarray(ndi.maximum(dt, labels=C, index=np.arange(1, n + 1)))
        # parts thinner than min_mm: pixels removed by an opening with a disk of diameter min_mm
        r = max(1, int(round(min_px / 2)))
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        disk = xx * xx + yy * yy <= r * r
        opened = ndi.binary_opening(m, structure=disk)
        thin_px = m & ~opened
        ta = np.bincount(C.ravel(), weights=thin_px.ravel().astype(float), minlength=n + 1)[1:]
        big = eqd >= min_px
        thin += int((big & ((2 * mx < min_px) | (ta / np.maximum(area, 1) > 0.2))).sum())
        thin_area_tot += float(thin_px.sum())
    return {"tiny_islands": tiny, "thin_features": thin, "n_components": ncomp,
            "thin_area_mm2": thin_area_tot / (ppm * ppm)}


def printcut_metrics(svg, W, H, width_mm=100.0, min_mm=0.5):
    from eval.metrics import structure_stats
    import xml.etree.ElementTree as ET
    root = ET.fromstring(svg)
    vb = root.attrib.get("viewBox")
    vw = float(re.split(r"[ ,]+", vb.strip())[2]) if vb else float(W)
    m = geometry_metrics(svg, width_mm / vw, vb_w=vw)
    m.update(raster_metrics(svg, W, H, width_mm=width_mm, min_mm=min_mm))
    m["n_nodes"] = structure_stats(svg)["n_nodes"]
    return m
