"""SVG elliptical arc (endpoint parameterisation) -> points, after SVG 1.1 implementation notes F.6.5."""
from __future__ import annotations

import math


def arc_points(p0, p1, rx, ry, rot, large, sweep, n=16):
    """Points (excluding p0, including p1) along the SVG arc from p0 to p1."""
    x1, y1 = float(p0[0]), float(p0[1])
    x2, y2 = float(p1[0]), float(p1[1])
    rx, ry = abs(rx), abs(ry)
    if rx < 1e-9 or ry < 1e-9 or (abs(x1 - x2) < 1e-12 and abs(y1 - y2) < 1e-12):
        return [(x2, y2)]
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
    for k in range(1, n):
        t = t1 + dt * k / n
        pts.append((cx + rx * math.cos(t) * cp - ry * math.sin(t) * sp, cy + rx * math.cos(t) * sp + ry * math.sin(t) * cp))
    pts.append((x2, y2))
    return pts
