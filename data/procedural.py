"""Procedural flat-design scene generator with exact ground truth.

Every scene is an SVG (pixel coordinates, viewBox = canvas) plus metadata:
  primitives: list of fully visible primitive shapes (circle / ellipse / rect /
              roundrect / polygon / star) with exact parameters
  corners:    list of (x, y) sharp vertices (interior angle < 150 deg) of fully
              visible shapes
Scene kinds: shapes (flat_illustration), diagram, gradient, line_art.
"""
from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass, field


@dataclass
class Scene:
    svg: str
    width: int
    height: int
    kind: str
    primitives: list = field(default_factory=list)
    corners: list = field(default_factory=list)


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, round(c)))) for c in rgb)


def _palette(rng: random.Random, n: int):
    """Distinct, design-like colours (spread in hue, varied lightness)."""
    base_h = rng.random()
    cols = []
    for i in range(n):
        h = (base_h + i / n + rng.uniform(-0.04, 0.04)) % 1.0
        s = rng.uniform(0.45, 0.95)
        v = rng.uniform(0.45, 0.98)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        cols.append(_hex((r * 255, g * 255, b * 255)))
    rng.shuffle(cols)
    return cols


def _f(x):
    return f"{x:.3f}".rstrip("0").rstrip(".")


def _bbox_overlap(a, b, pad=2.0):
    return not (a[2] + pad < b[0] or b[2] + pad < a[0] or a[3] + pad < b[1] or b[3] + pad < a[1])


def _poly_corners(pts, max_angle=150.0):
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        v1 = (p0[0] - p1[0], p0[1] - p1[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        if n1 < 1e-6 or n2 < 1e-6:
            continue
        c = max(-1, min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        if math.degrees(math.acos(c)) < max_angle:
            out.append((p1[0], p1[1]))
    return out


def _rot(pts, cx, cy, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in pts]


def _make_shape(rng: random.Random, W, H, kind=None, fill="#000"):
    """Return (svg_element, bbox, primitive_meta, corner_list)."""
    kinds = ["circle", "ellipse", "rect", "roundrect", "polygon", "star", "triangle", "blob"]
    kind = kind or rng.choice(kinds)
    S = min(W, H)
    cx, cy = rng.uniform(0.1, 0.9) * W, rng.uniform(0.1, 0.9) * H
    if kind == "circle":
        r = rng.uniform(0.05, 0.22) * S
        el = f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="{fill}"/>'
        return el, (cx - r, cy - r, cx + r, cy + r), {"type": "circle", "cx": cx, "cy": cy, "rx": r, "ry": r, "angle": 0.0}, []
    if kind == "ellipse":
        rx, ry = rng.uniform(0.06, 0.25) * S, rng.uniform(0.04, 0.18) * S
        ang = rng.choice([0.0, rng.uniform(0, 180)])
        el = (f'<ellipse cx="{_f(cx)}" cy="{_f(cy)}" rx="{_f(rx)}" ry="{_f(ry)}" fill="{fill}"'
              + (f' transform="rotate({_f(ang)} {_f(cx)} {_f(cy)})"' if ang else "") + "/>")
        R = max(rx, ry)
        return el, (cx - R, cy - R, cx + R, cy + R), {"type": "ellipse", "cx": cx, "cy": cy, "rx": rx, "ry": ry, "angle": ang}, []
    if kind in ("rect", "roundrect"):
        w, h = rng.uniform(0.08, 0.4) * W, rng.uniform(0.06, 0.35) * H
        x, y = cx - w / 2, cy - h / 2
        ang = 0.0 if rng.random() < 0.7 else rng.uniform(-40, 40)
        rr = 0.0
        if kind == "roundrect":
            rr = rng.uniform(0.08, 0.3) * min(w, h)
        el = (f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}"'
              + (f' rx="{_f(rr)}"' if rr else "") + f' fill="{fill}"'
              + (f' transform="rotate({_f(ang)} {_f(cx)} {_f(cy)})"' if ang else "") + "/>")
        pts = _rot([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], cx, cy, math.radians(ang))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        meta = {"type": kind, "cx": cx, "cy": cy, "w": w, "h": h, "r": rr, "angle": ang}
        return el, (min(xs), min(ys), max(xs), max(ys)), meta, ([] if rr else pts)
    if kind in ("polygon", "star", "triangle"):
        r = rng.uniform(0.06, 0.22) * S
        ang0 = rng.uniform(0, 2 * math.pi)
        if kind == "triangle":
            n, pts = 3, [(cx + r * math.cos(ang0 + 2 * math.pi * i / 3), cy + r * math.sin(ang0 + 2 * math.pi * i / 3)) for i in range(3)]
        elif kind == "polygon":
            n = rng.randint(4, 8)
            pts = [(cx + r * math.cos(ang0 + 2 * math.pi * i / n), cy + r * math.sin(ang0 + 2 * math.pi * i / n)) for i in range(n)]
        else:
            n = rng.randint(5, 8)
            ri = r * rng.uniform(0.4, 0.6)
            pts = []
            for i in range(2 * n):
                rad = r if i % 2 == 0 else ri
                a = ang0 + math.pi * i / n
                pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
        d = "M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in pts) + " Z"
        el = f'<path d="{d}" fill="{fill}"/>'
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        meta = {"type": kind, "points": pts}
        return el, (min(xs), min(ys), max(xs), max(ys)), meta, _poly_corners(pts)
    # smooth blob: closed Catmull-Rom through random radial points
    r = rng.uniform(0.07, 0.2) * S
    n = rng.randint(5, 8)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n + rng.uniform(-0.2, 0.2)
        rad = r * rng.uniform(0.6, 1.0)
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    d = f"M{_f(pts[0][0])} {_f(pts[0][1])}"
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{_f(c1[0])} {_f(c1[1])} {_f(c2[0])} {_f(c2[1])} {_f(p2[0])} {_f(p2[1])}"
    el = f'<path d="{d} Z" fill="{fill}"/>'
    return el, (cx - r * 1.2, cy - r * 1.2, cx + r * 1.2, cy + r * 1.2), {"type": "blob"}, []


def _finish(rng, W, H, kind, bg, items, extra_defs=""):
    """items: list of (el, bbox, meta, corners) in z-order. Compute visibility."""
    prims, corners = [], []
    for i, (el, bb, meta, cs) in enumerate(items):
        if bb[0] < 1 or bb[1] < 1 or bb[2] > W - 1 or bb[3] > H - 1:
            continue  # clipped by canvas
        if any(_bbox_overlap(bb, items[j][1]) for j in range(i + 1, len(items))):
            continue  # possibly occluded by a later shape
        if meta and meta.get("type") not in (None, "blob"):
            m = dict(meta)
            m["fill"] = re_fill(el)
            prims.append(m)
        corners.extend(cs)
    body = "".join(it[0] for it in items)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
           + (f"<defs>{extra_defs}</defs>" if extra_defs else "")
           + (f'<rect width="{W}" height="{H}" fill="{bg}"/>' if bg else "") + body + "</svg>")
    return Scene(svg, W, H, kind, prims, [(float(x), float(y)) for x, y in corners])


def re_fill(el: str):
    i = el.find('fill="')
    return el[i + 6: el.find('"', i + 6)] if i >= 0 else None


def gen_shapes(rng: random.Random, W: int, H: int) -> Scene:
    ncol = rng.randint(3, 8)
    pal = _palette(rng, ncol + 1)
    bg = pal[0] if rng.random() < 0.6 else rng.choice(["#ffffff", "#f4f1ea", "#1d1f2b"])
    items = []
    for _ in range(rng.randint(4, 12)):
        items.append(_make_shape(rng, W, H, fill=rng.choice(pal[1:])))
    return _finish(rng, W, H, "shapes", bg, items)


def gen_diagram(rng: random.Random, W: int, H: int) -> Scene:
    pal = _palette(rng, 5)
    bg = rng.choice(["#ffffff", "#fafafa", "#f5f7fb"])
    stroke = rng.choice(["#222222", "#333a45", "#1f3b73"])
    sw = rng.uniform(1.5, 3.5)
    items = []
    n = rng.randint(3, 7)
    boxes = []
    tries = 0
    while len(boxes) < n and tries < 200:
        tries += 1
        w, h = rng.uniform(0.15, 0.3) * W, rng.uniform(0.1, 0.18) * H
        x, y = rng.uniform(0.04, 0.96) * W - w / 2, rng.uniform(0.04, 0.96) * H - h / 2
        bb = (x - 6, y - 6, x + w + 6, y + h + 6)
        if bb[0] < 2 or bb[1] < 2 or bb[2] > W - 2 or bb[3] > H - 2:
            continue
        if any(_bbox_overlap(bb, b, pad=12) for b in boxes):
            continue
        boxes.append(bb)
    lines = []
    for i in range(len(boxes) - 1):
        a, b = boxes[i], boxes[i + 1]
        ax, ay = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
        bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        lines.append(f'<line x1="{_f(ax)}" y1="{_f(ay)}" x2="{_f(bx)}" y2="{_f(by)}" stroke="{stroke}" stroke-width="{_f(sw)}"/>')
        # arrow head at 60% of the way
        t = 0.6
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        ang = math.atan2(by - ay, bx - ax)
        L = 4 * sw + 4
        tri = [(px, py), (px - L * math.cos(ang - 0.4), py - L * math.sin(ang - 0.4)),
               (px - L * math.cos(ang + 0.4), py - L * math.sin(ang + 0.4))]
        lines.append(f'<path d="M{_f(tri[0][0])} {_f(tri[0][1])} L{_f(tri[1][0])} {_f(tri[1][1])} L{_f(tri[2][0])} {_f(tri[2][1])} Z" fill="{stroke}"/>')
    shapes = []
    for (x0, y0, x1, y1) in boxes:
        x, y, w, h = x0 + 6, y0 + 6, x1 - x0 - 12, y1 - y0 - 12
        fill = rng.choice(pal + ["#ffffff"])
        rr = rng.choice([0.0, 0.0, rng.uniform(4, 0.3 * min(w, h))])
        el = (f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}"' + (f' rx="{_f(rr)}"' if rr else "")
              + f' fill="{fill}" stroke="{stroke}" stroke-width="{_f(sw)}"/>')
        # text-like glyph bars
        nl = rng.randint(1, 3)
        txt = ""
        lh = h / (nl + 1)
        for k in range(nl):
            tw = w * rng.uniform(0.35, 0.75)
            th = max(2.0, lh * 0.35)
            tx = x + (w - tw) / 2
            ty = y + lh * (k + 1) - th / 2
            # split into word-like chunks
            cur = tx
            while cur < tx + tw - 2:
                ww = min(rng.uniform(0.08, 0.25) * w, tx + tw - cur)
                txt += f'<rect x="{_f(cur)}" y="{_f(ty)}" width="{_f(ww)}" height="{_f(th)}" fill="{stroke}"/>'
                cur += ww + max(2.0, th * 0.8)
        meta = {"type": "roundrect" if rr else "rect", "cx": x + w / 2, "cy": y + h / 2, "w": w, "h": h, "r": rr, "angle": 0.0, "stroked": True}
        corners = [] if rr else [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        shapes.append((el + txt, (x0, y0, x1, y1), meta, corners))
    # lines are drawn below boxes (z-order), so boxes stay fully visible
    items = [(l, (0, 0, 0, 0), None, []) for l in lines] + shapes
    sc = _finish(rng, W, H, "diagram", bg, [it for it in items if it[2] is not None])
    body = "".join(lines) + "".join(s[0] for s in shapes)
    sc.svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
              f'<rect width="{W}" height="{H}" fill="{bg}"/>{body}</svg>')
    return sc


def gen_gradient(rng: random.Random, W: int, H: int) -> Scene:
    pal = _palette(rng, 6)
    defs = ""
    gid = 0

    def lin(c1, c2):
        nonlocal defs, gid
        gid += 1
        a = rng.uniform(0, 2 * math.pi)
        x1, y1 = 0.5 - 0.5 * math.cos(a), 0.5 - 0.5 * math.sin(a)
        x2, y2 = 0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)
        defs += (f'<linearGradient id="g{gid}" x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}">'
                 f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>')
        return f"url(#g{gid})"

    def rad(c1, c2):
        nonlocal defs, gid
        gid += 1
        defs += (f'<radialGradient id="g{gid}" cx="{_f(rng.uniform(0.3, 0.7))}" cy="{_f(rng.uniform(0.3, 0.7))}" r="{_f(rng.uniform(0.5, 0.8))}">'
                 f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></radialGradient>')
        return f"url(#g{gid})"

    bgfill = lin(pal[0], pal[1]) if rng.random() < 0.6 else rng.choice(["#ffffff", pal[0]])
    items = []
    for _ in range(rng.randint(2, 6)):
        r = rng.random()
        fill = lin(*rng.sample(pal, 2)) if r < 0.4 else (rad(*rng.sample(pal, 2)) if r < 0.7 else rng.choice(pal))
        items.append(_make_shape(rng, W, H, kind=rng.choice(["circle", "ellipse", "rect", "roundrect", "blob", "polygon"]), fill=fill))
    sc = _finish(rng, W, H, "gradient", None, items, extra_defs=defs)
    sc.svg = sc.svg.replace("</defs>", f"</defs><rect width=\"{W}\" height=\"{H}\" fill=\"{bgfill}\"/>", 1)
    sc.primitives = [p for p in sc.primitives if not str(p.get("fill", "")).startswith("url(")]
    return sc


def gen_line_art(rng: random.Random, W: int, H: int) -> Scene:
    ink = rng.choice(["#111111", "#202733", "#3b2a1a", "#0b2d5c"])
    bg = rng.choice(["#ffffff", "#fbf8f1", "#f3f3f3"])
    sw = rng.uniform(1.2, 4.5)
    els = []
    S = min(W, H)
    for _ in range(rng.randint(4, 9)):
        t = rng.random()
        if t < 0.45:  # smooth curve
            pts = [(rng.uniform(0.05, 0.95) * W, rng.uniform(0.05, 0.95) * H) for _ in range(rng.randint(3, 5))]
            d = f"M{_f(pts[0][0])} {_f(pts[0][1])}"
            for i in range(1, len(pts)):
                p0 = pts[i - 1]
                p1 = pts[i]
                c1 = (p0[0] + rng.uniform(-0.12, 0.12) * S, p0[1] + rng.uniform(-0.12, 0.12) * S)
                c2 = (p1[0] + rng.uniform(-0.12, 0.12) * S, p1[1] + rng.uniform(-0.12, 0.12) * S)
                d += f" C{_f(c1[0])} {_f(c1[1])} {_f(c2[0])} {_f(c2[1])} {_f(p1[0])} {_f(p1[1])}"
        elif t < 0.65:  # polyline with sharp corners
            pts = [(rng.uniform(0.05, 0.95) * W, rng.uniform(0.05, 0.95) * H) for _ in range(rng.randint(3, 6))]
            d = "M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in pts)
        elif t < 0.85:  # circle outline
            cx, cy, r = rng.uniform(0.15, 0.85) * W, rng.uniform(0.15, 0.85) * H, rng.uniform(0.04, 0.15) * S
            els.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="none" stroke="{ink}" stroke-width="{_f(sw)}"/>')
            continue
        else:  # hatching
            x0, y0 = rng.uniform(0.1, 0.7) * W, rng.uniform(0.1, 0.7) * H
            L = rng.uniform(0.1, 0.25) * S
            gap = rng.uniform(3, 8) + sw
            d = ""
            for k in range(rng.randint(3, 7)):
                d += f"M{_f(x0 + k * gap)} {_f(y0)} L{_f(x0 + k * gap + L * 0.4)} {_f(y0 + L)} "
        w = sw * rng.uniform(0.7, 1.3)
        els.append(f'<path d="{d}" fill="none" stroke="{ink}" stroke-width="{_f(w)}" stroke-linecap="round" stroke-linejoin="round"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
           f'<rect width="{W}" height="{H}" fill="{bg}"/>' + "".join(els) + "</svg>")
    return Scene(svg, W, H, "line_art", [], [])


GENERATORS = {"shapes": gen_shapes, "diagram": gen_diagram, "gradient": gen_gradient, "line_art": gen_line_art}
