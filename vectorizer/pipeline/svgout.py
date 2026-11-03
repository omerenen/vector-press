"""SVG serialisation of fitted geometry (W10: precision control, compact commands)."""
from __future__ import annotations


def fmt(v, prec):
    s = f"{v:.{prec}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    if s in ("-0", "-", ""):
        s = "0"
    return s


def _pt(p, prec):
    return fmt(p[0], prec) + " " + fmt(p[1], prec)


def _join(tokens):
    """Join numbers minimising separators (a leading '-' or '.' needs no space)."""
    out = []
    prev = ""
    for t in tokens:
        if out and not (t[0] == "-" or (t[0] == "." and "." in prev) or prev[-1:].isalpha() or t[0].isalpha()):
            out.append(" ")
        out.append(t)
        prev = t
    return "".join(out)


def geom_to_tokens(geom, prec, move=True, rel=True, close=False):
    """Tokens for a geometry dict; relative commands for compactness."""
    toks = []
    x0, y0 = geom["start"]
    # quantise the current point exactly as written so relative offsets don't drift
    q = 10 ** prec

    def r(v):
        return round(v * q) / q
    cx, cy = r(x0), r(y0)
    if move:
        toks += ["M", fmt(cx, prec), fmt(cy, prec)]
    last_cmd = None
    segs = geom["segs"]
    if close and segs and segs[-1][0] == "L":
        segs = segs[:-1]                 # the closing line is drawn by "z"
        close = False
    nseg = len(segs)
    for si, s in enumerate(segs):
        k = s[0]
        if close and si == nseg - 1:
            # last segment of a closed loop in absolute coordinates: its end point parses to exactly the
            # start point (relative offsets accumulate float noise -> spurious "self-intersections")
            rel = False
        ex, ey = r(s[-1][0]), r(s[-1][1])
        if k == "L":
            dx, dy = ex - cx, ey - cy
            if rel:
                if abs(dy) < 0.5 / q and abs(dx) >= 0.5 / q:
                    cmd, args = "h", [fmt(dx, prec)]
                elif abs(dx) < 0.5 / q and abs(dy) >= 0.5 / q:
                    cmd, args = "v", [fmt(dy, prec)]
                elif abs(dx) < 0.5 / q and abs(dy) < 0.5 / q:
                    continue
                else:
                    cmd, args = "l", [fmt(dx, prec), fmt(dy, prec)]
            else:
                cmd, args = "L", [fmt(ex, prec), fmt(ey, prec)]
        elif k == "C":
            c1 = (r(s[1][0]), r(s[1][1]))
            c2 = (r(s[2][0]), r(s[2][1]))
            if rel:
                cmd = "c"
                args = [fmt(c1[0] - cx, prec), fmt(c1[1] - cy, prec), fmt(c2[0] - cx, prec), fmt(c2[1] - cy, prec),
                        fmt(ex - cx, prec), fmt(ey - cy, prec)]
            else:
                cmd = "C"
                args = [fmt(c1[0], prec), fmt(c1[1], prec), fmt(c2[0], prec), fmt(c2[1], prec), fmt(ex, prec), fmt(ey, prec)]
        elif k == "A":
            _, rx, ry, rot, large, sweep, _e = s
            cmd = "a" if rel else "A"
            ex2, ey2 = (ex - cx, ey - cy) if rel else (ex, ey)
            args = [fmt(rx, prec), fmt(ry, prec), fmt(rot, 1), str(int(large)), str(int(sweep)),
                    fmt(ex2, prec), fmt(ey2, prec)]
        else:
            continue
        if cmd != last_cmd or cmd in ("M", "m"):
            toks.append(cmd)
        toks += args
        last_cmd = cmd
        cx, cy = ex, ey
    return toks


def loop_d(geoms, prec, exact_close=False):
    toks = []
    for i, g in enumerate(geoms):
        toks += geom_to_tokens(g, prec, move=(i == 0), close=exact_close and i == len(geoms) - 1)
    toks.append("z")
    return toks


def svg_document(width, height, body, background=None, out_size=None):
    bg = f'<rect width="{width}" height="{height}" fill="{background}"/>' if background else ""
    ow, oh = out_size if out_size else (width, height)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{ow}" height="{oh}">{bg}{body}</svg>')
