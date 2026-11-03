"""Evaluation metrics for raster->SVG vectorisation.

All raster metrics compare RGB images composited over white (uint8).
See eval/README section in EXPERIMENTS.md for definitions and the composite.
"""
from __future__ import annotations

import gzip
import math
import re
import xml.etree.ElementTree as ET

import numpy as np
from scipy import ndimage as ndi
from skimage import color as skcolor
from skimage.feature import canny
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

# ----------------------------------------------------------------- raster

def to_gray(rgb):
    rgb = rgb.astype(np.float64)
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def ssim(a, b):
    return float(structural_similarity(a, b, channel_axis=2, data_range=255))


def psnr(a, b):
    if np.array_equal(a, b):
        return 60.0
    return float(min(60.0, peak_signal_noise_ratio(a, b, data_range=255)))


def gmsd(a, b):
    """Gradient Magnitude Similarity Deviation (Xue et al. 2014). Lower is better."""
    def prep(x):
        g = to_gray(x)
        g = ndi.uniform_filter(g, 2)[::2, ::2] if min(g.shape) >= 8 else g
        return g
    ga, gb = prep(a), prep(b)
    hx = np.array([[1, 0, -1], [1, 0, -1], [1, 0, -1]], np.float64) / 3.0
    hy = hx.T

    def gm(g):
        return np.sqrt(ndi.convolve(g, hx, mode="nearest") ** 2 + ndi.convolve(g, hy, mode="nearest") ** 2)
    ma, mb = gm(ga), gm(gb)
    c = 170.0
    gms = (2 * ma * mb + c) / (ma ** 2 + mb ** 2 + c)
    return float(np.std(gms))


def msssim(a, b, scales=4):
    """Multi-scale SSIM on luminance (Wang et al. 2003), renormalised weights."""
    w = np.array([0.0448, 0.2856, 0.3001, 0.2363, 0.1333])[:scales]
    w = w / w.sum()
    ga, gb = to_gray(a), to_gray(b)
    vals = []
    for s in range(scales):
        if min(ga.shape) < 7:
            break
        _, S = structural_similarity(ga, gb, data_range=255, full=True)
        vals.append(max(1e-6, float(S.mean())))
        ga = ndi.uniform_filter(ga, 2)[::2, ::2]
        gb = ndi.uniform_filter(gb, 2)[::2, ::2]
    w = w[: len(vals)] / w[: len(vals)].sum()
    return float(np.prod(np.array(vals) ** w))


def delta_e(a, b):
    la = skcolor.rgb2lab(a)
    lb = skcolor.rgb2lab(b)
    de = skcolor.deltaE_ciede2000(la, lb)
    return float(de.mean()), float(np.percentile(de, 95))


def edge_f(a, b, tol=1.5, sigma=1.0):
    ea = canny(to_gray(a), sigma=sigma, low_threshold=10, high_threshold=30)
    eb = canny(to_gray(b), sigma=sigma, low_threshold=10, high_threshold=30)
    na, nb = ea.sum(), eb.sum()
    if na == 0 and nb == 0:
        return 1.0
    if na == 0 or nb == 0:
        return 0.0
    da = ndi.distance_transform_edt(~ea)
    db = ndi.distance_transform_edt(~eb)
    prec = float((da[eb] <= tol).mean())  # output edges near reference edges
    rec = float((db[ea] <= tol).mean())
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)


_lpips_model = None
_lpips_failed = False


def lpips_dist(a, b):
    """LPIPS(alex) if torch + lpips + backbone weights are available, else None."""
    global _lpips_model, _lpips_failed
    if _lpips_failed:
        return None
    try:
        if _lpips_model is None:
            import torch  # noqa: F401
            import lpips
            _lpips_model = lpips.LPIPS(net="alex", verbose=False)
        import torch
        ta = torch.from_numpy(a.astype(np.float32) / 127.5 - 1).permute(2, 0, 1)[None]
        tb = torch.from_numpy(b.astype(np.float32) / 127.5 - 1).permute(2, 0, 1)[None]
        with torch.no_grad():
            return float(_lpips_model(ta, tb).item())
    except Exception:
        _lpips_failed = True
        return None


# ----------------------------------------------------------------- high-res geometry

def lab(rgb):
    return skcolor.rgb2lab(rgb)


def edge_deviation(gt4, out4, scale):
    """Mean boundary deviation in 1x pixels: mismatching area / GT boundary length.

    gt4/out4 are RGB renders at `scale`x. Mismatch = Lab distance > 15.
    """
    la, lb = lab(gt4), lab(out4)
    mism = np.linalg.norm(la - lb, axis=2) > 15
    # boundary: pixels where GT colour changes notably between neighbours
    gx = np.linalg.norm(np.diff(la, axis=1), axis=2) > 15
    gy = np.linalg.norm(np.diff(la, axis=0), axis=2) > 15
    blen = gx.sum() + gy.sum()
    if blen == 0:
        return 0.0, float(mism.mean())
    bmask = np.zeros(mism.shape, bool)
    bmask[:, 1:] |= gx
    bmask[:, :-1] |= gx
    bmask[1:, :] |= gy
    bmask[:-1, :] |= gy
    # only count mismatches within 3 px (1x) of a GT boundary: geometry, not interior colour
    band = ndi.distance_transform_edt(~bmask) <= 3 * scale
    return float((mism & band).sum() / blen / scale), float(mism.mean())


def gap_pixels(out4_rgba, opaque_mask4, erode=6):
    """Pixels (at hi-res) inside opaque GT area not fully covered by the output."""
    m = ndi.binary_erosion(opaque_mask4, iterations=erode) if erode else opaque_mask4
    holes = (out4_rgba[..., 3] < 250) & m
    return int(holes.sum())


def _harris_color(rgb, sigma):
    x = rgb.astype(np.float64) / 255.0
    Ixx = np.zeros(x.shape[:2])
    Iyy = np.zeros(x.shape[:2])
    Ixy = np.zeros(x.shape[:2])
    for c in range(3):
        gx = ndi.sobel(x[..., c], axis=1)
        gy = ndi.sobel(x[..., c], axis=0)
        Ixx += gx * gx
        Iyy += gy * gy
        Ixy += gx * gy
    Ixx = ndi.gaussian_filter(Ixx, sigma)
    Iyy = ndi.gaussian_filter(Iyy, sigma)
    Ixy = ndi.gaussian_filter(Ixy, sigma)
    det = Ixx * Iyy - Ixy ** 2
    tr = Ixx + Iyy
    return det - 0.05 * tr ** 2


def corner_metrics(gt4, out4, corners, scale, radius=1.5):
    """Corner recall (output has a strong corner within `radius` px) and mean position error."""
    if not corners:
        return None, None
    sig = 0.6 * scale
    rg = _harris_color(gt4, sig)
    ro = _harris_color(out4, sig)
    H, W = rg.shape
    R = int(math.ceil(radius * scale))
    found, errs = 0, []
    n = 0
    for (x, y) in corners:
        cx, cy = int(round(x * scale)), int(round(y * scale))
        if cx < R or cy < R or cx >= W - R or cy >= H - R:
            continue
        g = rg[cy - R:cy + R + 1, cx - R:cx + R + 1]
        gmax = g.max()
        if gmax <= 1e-6:
            continue  # not actually a visible corner in GT (e.g. same colour both sides)
        n += 1
        o = ro[cy - R:cy + R + 1, cx - R:cx + R + 1]
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
        disk = (xx ** 2 + yy ** 2) <= R * R
        o = np.where(disk, o, -np.inf)
        if o.max() >= 0.5 * gmax:
            found += 1
            iy, ix = np.unravel_index(np.argmax(o), o.shape)
            errs.append(math.hypot(ix - R, iy - R) / scale)
    if n == 0:
        return None, None
    return found / n, (float(np.mean(errs)) if errs else None)


# ----------------------------------------------------------------- SVG structure

_NUM = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
_CMD_RE = re.compile(r"([MmZzLlHhVvCcSsQqTtAa])|(" + _NUM + ")")
_ARGC = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def parse_path(d):
    """Return list of (CMD_upper, abs_points list) segments with absolute coords.

    Points: for L/M end point; for C [(c1),(c2),(p)]; for A the end point.
    """
    toks = _CMD_RE.findall(d)
    segs = []
    cmd = None
    args = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)

    def flush(c, a):
        nonlocal cur, start
        C = c.upper()
        rel = c.islower()
        n = _ARGC[C]
        if C == "Z":
            segs.append(("Z", [start]))
            cur = start
            return
        if n == 0 or len(a) < n:
            return
        i = 0
        first = True
        while i + n <= len(a):
            v = a[i:i + n]
            i += n
            if C == "M":
                p = (v[0] + cur[0], v[1] + cur[1]) if rel else (v[0], v[1])
                if first:
                    segs.append(("M", [p]))
                    start = p
                else:
                    segs.append(("L", [p]))
                cur = p
            elif C == "L" or C == "T":
                p = (v[0] + cur[0], v[1] + cur[1]) if rel else (v[0], v[1])
                segs.append(("L" if C == "L" else "T", [p]))
                cur = p
            elif C == "H":
                p = (v[0] + (cur[0] if rel else 0), cur[1])
                segs.append(("L", [p]))
                cur = p
            elif C == "V":
                p = (cur[0], v[0] + (cur[1] if rel else 0))
                segs.append(("L", [p]))
                cur = p
            elif C in ("C", "S", "Q"):
                pts = [(v[k] + (cur[0] if rel else 0), v[k + 1] + (cur[1] if rel else 0)) for k in range(0, n, 2)]
                segs.append((C, pts))
                cur = pts[-1]
            elif C == "A":
                p = (v[5] + (cur[0] if rel else 0), v[6] + (cur[1] if rel else 0))
                segs.append(("A", [p, tuple(v[:5])]))
                cur = p
            first = False
    for c, num in toks:
        if c:
            if cmd is not None:
                flush(cmd, args)
            cmd, args = c, []
            if c in "Zz":
                flush(c, [])
                cmd = None
        else:
            args.append(float(num))
    if cmd is not None:
        flush(cmd, args)
    return segs


def _parse_transform(t):
    """Return 3x3 matrix for translate/rotate/scale/matrix transforms."""
    M = np.eye(3)
    if not t:
        return M
    for name, argstr in re.findall(r"(\w+)\s*\(([^)]*)\)", t):
        a = [float(x) for x in re.findall(_NUM, argstr)]
        T = np.eye(3)
        if name == "translate":
            T[0, 2] = a[0]
            T[1, 2] = a[1] if len(a) > 1 else 0
        elif name == "scale":
            T[0, 0] = a[0]
            T[1, 1] = a[1] if len(a) > 1 else a[0]
        elif name == "rotate":
            r = math.radians(a[0])
            c, s = math.cos(r), math.sin(r)
            R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
            if len(a) == 3:
                cx, cy = a[1], a[2]
                T1 = np.array([[1, 0, cx], [0, 1, cy], [0, 0, 1]])
                T2 = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]])
                R = T1 @ R @ T2
            T = R
        elif name == "matrix" and len(a) == 6:
            T = np.array([[a[0], a[2], a[4]], [a[1], a[3], a[5]], [0, 0, 1]])
        M = M @ T
    return M


def svg_elements(svg):
    """Yield (tag, attrib, matrix) for drawable elements (flattening <g> transforms)."""
    root = ET.fromstring(svg)
    out = []

    def walk(el, M):
        tag = el.tag.split("}")[-1]
        Mi = M @ _parse_transform(el.attrib.get("transform"))
        if tag in ("path", "circle", "ellipse", "rect", "polygon", "polyline", "line"):
            out.append((tag, el.attrib, Mi))
        for ch in el:
            if ch.tag.split("}")[-1] in ("defs", "linearGradient", "radialGradient", "clipPath", "mask"):
                continue
            walk(ch, Mi)
    walk(root, np.eye(3))
    return out


def structure_stats(svg):
    els = svg_elements(svg)
    nodes = 0
    nprim = 0
    for tag, at, _ in els:
        if tag == "path":
            nodes += sum(1 for s in parse_path(at.get("d", "")) if s[0] != "M")
        elif tag in ("circle", "ellipse"):
            nodes += 4
            nprim += 1
        elif tag == "rect":
            nodes += 8 if at.get("rx") or at.get("ry") else 4
            nprim += 1
        elif tag in ("polygon", "polyline"):
            nodes += len(re.findall(_NUM, at.get("points", ""))) // 2
        elif tag == "line":
            nodes += 1
    raw = svg.encode()
    return {"n_paths": len(els), "n_nodes": int(nodes), "n_primitives": nprim,
            "bytes": len(raw), "gz_bytes": len(gzip.compress(raw, 9))}


def _apply(M, x, y):
    v = M @ np.array([x, y, 1.0])
    return float(v[0]), float(v[1])


def primitive_recovery(svg, prims, sx=1.0, sy=1.0, ox=0.0, oy=0.0, tol=1.5):
    """Fraction of GT primitives represented by a matching native primitive (or exact polygon path).

    sx, sy: output user units -> GT pixel scale (output viewBox may differ).
    """
    if not prims:
        return None, {}
    els = svg_elements(svg)
    # fold the viewBox scale/offset into every element matrix (user units -> GT pixels)
    V = np.array([[sx, 0, ox], [0, sy, oy], [0, 0, 1.0]])
    els = [(t, a, V @ Mx) for t, a, Mx in els]
    sx = sy = 1.0
    cands = []  # (kind, data)
    for tag, at, M in els:
        def g(k, d=0.0):
            try:
                return float(re.findall(_NUM, at.get(k, str(d)))[0])
            except Exception:
                return d
        if tag in ("circle", "ellipse"):
            cx, cy = _apply(M, g("cx"), g("cy"))
            if tag == "circle":
                rx = ry = g("r")
            else:
                rx, ry = g("rx"), g("ry")
            # axis scale from matrix
            ax = math.hypot(M[0, 0], M[1, 0])
            ay = math.hypot(M[0, 1], M[1, 1])
            ang = math.degrees(math.atan2(M[1, 0], M[0, 0]))
            cands.append(("ellipse", (cx * sx, cy * sy, rx * ax * sx, ry * ay * sy, ang)))
        elif tag == "rect":
            x, y, w, h = g("x"), g("y"), g("width"), g("height")
            rr = g("rx", g("ry", 0.0))
            pts = [_apply(M, *p) for p in [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]]
            cands.append(("rect", ([(px * sx, py * sy) for px, py in pts], rr * math.hypot(M[0, 0], M[1, 0]))))
        elif tag in ("path", "polygon"):
            polys = []
            if tag == "path":
                # every straight-edged closed subpath is a candidate polygon (same-colour regions
                # may be merged into one path element)
                cur, ok = [], True
                for c, p in parse_path(at.get("d", "")) + [("M", [(0.0, 0.0)])]:
                    if c == "M":
                        if cur and ok:
                            polys.append(cur)
                        cur, ok = [p[0]], True
                    elif c == "L":
                        cur.append(p[0])
                    elif c == "Z":
                        pass
                    else:
                        ok = False
            else:
                v = [float(x) for x in re.findall(_NUM, at.get("points", ""))]
                polys.append(list(zip(v[0::2], v[1::2])))
            for pts in polys:
                if len(pts) >= 2 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-6:
                    pts = pts[:-1]
                if len(pts) < 3:
                    continue
                pts = [_apply(M, *p) for p in pts]
                cands.append(("poly", [(px * sx, py * sy) for px, py in pts]))

    def match_poly(gt_pts, out_pts):
        if len(gt_pts) != len(out_pts):
            return False
        for p in gt_pts:
            if min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in out_pts) > tol:
                return False
        return True

    rec = 0
    per_type = {}
    for p in prims:
        t = p["type"]
        ok = False
        if t in ("circle", "ellipse"):
            for k, c in cands:
                if k != "ellipse":
                    continue
                cx, cy, rx, ry, ang = c
                if math.hypot(cx - p["cx"], cy - p["cy"]) > tol:
                    continue
                rt = max(tol, 0.03 * max(p["rx"], p["ry"]))
                if t == "circle" or abs(p["rx"] - p["ry"]) <= rt:
                    # (near-)circle: orientation is undefined, compare radii only
                    ok = abs(rx - p["rx"]) <= rt and abs(ry - p["ry"]) <= rt
                else:
                    da = (ang - p.get("angle", 0.0)) % 180
                    if (abs(rx - p["rx"]) <= rt and abs(ry - p["ry"]) <= rt and min(da, 180 - da) < 3) or \
                       (abs(rx - p["ry"]) <= rt and abs(ry - p["rx"]) <= rt and abs(da - 90) < 3):
                        ok = True
                if ok:
                    break
        elif t in ("rect", "roundrect"):
            a = math.radians(p.get("angle", 0.0))
            cx, cy = p["cx"], p["cy"]
            # stroked shapes: the outer or inner edge of the outline is an equally faithful target
            offs = [0.0] + ([p["sw"] / 2, -p["sw"] / 2] if p.get("sw") else [])
            for off in offs:
                w, h = p["w"] + 2 * off, p["h"] + 2 * off
                r0 = max(0.0, p.get("r", 0.0) + off) if p.get("r", 0.0) > 0 else 0.0
                base = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
                gpts = [(cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)) for x, y in base]
                for k, c in cands:
                    if k == "rect":
                        pts, rr = c
                        if match_poly(gpts, pts) and abs(rr - r0) <= max(tol, 0.1 * r0):
                            ok = True
                            break
                    elif k == "poly" and t == "rect" and match_poly(gpts, c):
                        ok = True
                        break
                if ok:
                    break
        elif t in ("polygon", "star", "triangle"):
            for k, c in cands:
                if k == "poly" and match_poly(p["points"], c):
                    ok = True
                    break
                if k == "rect" and len(p["points"]) == 4 and match_poly(p["points"], c[0]):
                    ok = True
                    break
        rec += ok
        a = per_type.setdefault(t, [0, 0])
        a[0] += ok
        a[1] += 1
    return rec / len(prims), per_type


def svg_valid(svg):
    try:
        ET.fromstring(svg)
        return True
    except Exception:
        return False


# ----------------------------------------------------------------- composite

def is_vector(svg):
    """False if the SVG embeds raster data (<image>, data: URIs) or foreign content - such output
    would trivially score high on raster metrics without being a vectorisation."""
    low = svg.lower()
    return not ("<image" in low or "data:image" in low or "<foreignobject" in low)


def composite(m):
    """Single score in [0,1]; weights documented in EXPERIMENTS.md (E-metrics). Non-vector output scores 0."""
    if m.get("is_vector") is False:
        return 0.0
    fid = (0.25 * m["ssim"] + 0.15 * min(m["psnr"], 40) / 40 + 0.20 * (1 - min(m["de_mean"], 20) / 20)
           + 0.20 * m["edge_f"] + 0.20 * (1 - min(m["gmsd"], 0.35) / 0.35))
    compact = 1 - float(np.clip(math.log10(max(m["gz_bytes"], 1000) / 1000) / 3, 0, 1))
    if m.get("edge_dev") is not None:
        geo = 1 - min(m["edge_dev"], 3.0) / 3.0
        return 0.75 * fid + 0.15 * geo + 0.10 * compact
    return 0.90 * fid + 0.10 * compact
