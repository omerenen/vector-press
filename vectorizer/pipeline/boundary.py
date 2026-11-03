"""Shared boundary graph on the pixel-crack lattice (W5).

Regions = 4-connected components of the label map. Every boundary between two
regions (or a region and the image border) is a *chain* of crack edges between
junction vertices (degree >= 3) or a closed loop. Each chain is fitted exactly
once and reused (reversed) by both adjacent regions, so shared borders can never
drift apart -> no hairline gaps/slivers by construction.

Coordinates: lattice vertex (x, y) is the top-left corner of pixel (row y, col x).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

OUTSIDE = -1


@dataclass
class Chain:
    pts: np.ndarray          # (N, 2) float lattice vertices (x, y), N >= 2; closed => pts[0] == pts[-1]
    left: int                # region on the left when walking pts forward (screen coords, y down)
    right: int               # region on the right
    closed: bool
    geom: list = None        # fitted segments, filled by fitting stage
    prim: dict = None        # primitive description if the whole closed chain is a primitive


@dataclass
class Region:
    rid: int
    label: int               # palette index, -1 = transparent
    area: int
    loops: list = field(default_factory=list)   # list of [(chain_id, reversed), ...]
    loop_area: list = field(default_factory=list)
    outer: int = -1          # index into loops of the outer boundary
    fill_holes: bool = True


def label_regions(lbl):
    """4-connected components of equal labels (including transparent -1), one C pass.

    Returns (R, labels_of_region) with region ids 0..n-1."""
    from skimage.measure import label as sklabel
    C = sklabel(lbl.astype(np.int32), background=-(2 ** 30), connectivity=1)
    n = int(C.max())
    R = (C - 1).astype(np.int32)
    region_label = np.zeros(n, np.int32)
    region_label[R.ravel()] = lbl.ravel()
    return R, region_label


def build_graph(R):
    """Trace all boundary chains. Returns list[Chain]."""
    H, W = R.shape
    P = np.full((H + 2, W + 2), OUTSIDE, np.int32)
    P[1:-1, 1:-1] = R
    up, dn = P[0:H + 1, 1:W + 1], P[1:H + 2, 1:W + 1]
    hact = up != dn                      # (H+1, W): crack from vertex (x,y) to (x+1,y)
    lf, rt = P[1:H + 1, 0:W + 1], P[1:H + 1, 1:W + 2]
    vact = lf != rt                      # (H, W+1): crack from vertex (x,y) to (x,y+1)
    deg = np.zeros((H + 1, W + 1), np.int8)
    deg[:, :W] += hact
    deg[:, 1:] += hact
    deg[:H, :] += vact
    deg[1:, :] += vact
    W1 = W + 1
    hl = hact.ravel().tolist()
    vl = vact.ravel().tolist()
    hvis = bytearray(len(hl))
    vvis = bytearray(len(vl))
    junction = (deg >= 3).ravel().tolist()
    upl = up.ravel().tolist()
    dnl = dn.ravel().tolist()
    lfl = lf.ravel().tolist()
    rtl = rt.ravel().tolist()

    def side_regions(kind, idx, dx, dy):
        # returns (left, right) for walking along crack `idx` in direction (dx, dy)
        if kind == 0:  # horizontal
            a, b = upl[idx], dnl[idx]          # above, below
            return (a, b) if dx > 0 else (b, a)
        a, b = lfl[idx], rtl[idx]              # left pixel, right pixel
        return (b, a) if dy > 0 else (a, b)

    def step(x, y):
        """Yield unvisited active cracks at vertex (x, y): (kind, idx, nx, ny)."""
        out = []
        if x < W:
            i = y * W + x
            if hl[i] and not hvis[i]:
                out.append((0, i, x + 1, y))
        if x > 0:
            i = y * W + x - 1
            if hl[i] and not hvis[i]:
                out.append((0, i, x - 1, y))
        if y < H:
            i = y * W1 + x
            if vl[i] and not vvis[i]:
                out.append((1, i, x, y + 1))
        if y > 0:
            i = (y - 1) * W1 + x
            if vl[i] and not vvis[i]:
                out.append((1, i, x, y - 1))
        return out

    chains = []

    def trace(x0, y0, kind, idx, x1, y1):
        if kind == 0:
            hvis[idx] = 1
        else:
            vvis[idx] = 1
        left, right = side_regions(kind, idx, x1 - x0, y1 - y0)
        xs, ys = [x0, x1], [y0, y1]
        x, y = x1, y1
        while not junction[y * W1 + x] and not (x == x0 and y == y0):
            nb = step(x, y)
            if not nb:
                break
            k, i, nx, ny = nb[0]
            if k == 0:
                hvis[i] = 1
            else:
                vvis[i] = 1
            xs.append(nx)
            ys.append(ny)
            x, y = nx, ny
        pts = np.column_stack([np.array(xs, np.float64), np.array(ys, np.float64)])
        closed = (x == x0 and y == y0) and not junction[y0 * W1 + x0]
        chains.append(Chain(pts, left, right, closed))

    # chains starting at junctions
    jy, jx = np.nonzero(deg >= 3)
    for y0, x0 in zip(jy.tolist(), jx.tolist()):
        for k, i, nx, ny in step(x0, y0):
            if (hvis[i] if k == 0 else vvis[i]):
                continue
            trace(x0, y0, k, i, nx, ny)
    # remaining closed loops (no junction); start at a straight segment midpoint vertex
    for kind, arr in ((0, hact), (1, vact)):
        rem = np.nonzero(arr.ravel())[0]
        for i in rem.tolist():
            if (hvis[i] if kind == 0 else vvis[i]):
                continue
            if kind == 0:
                y0, x0 = divmod(i, W)
                trace(x0, y0, 0, i, x0 + 1, y0)
            else:
                y0, x0 = divmod(i, W1)
                trace(x0, y0, 1, i, x0, y0 + 1)
    return chains


def _shoelace(pts):
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1]))


def assemble_regions(chains, region_label, R):
    """Group chains into oriented loops per region (region on the right of every loop)."""
    n = len(region_label)
    areas = np.bincount(R.ravel(), minlength=n)
    regions = [Region(i, int(region_label[i]), int(areas[i])) for i in range(n)]
    # per region: departures at vertices: key (x,y) -> list of (cid, rev)
    dep = [dict() for _ in range(n)]
    for cid, c in enumerate(chains):
        for reg, rev in ((c.right, False), (c.left, True)):
            if reg < 0:
                continue
            if c.closed:
                regions[reg].loops.append([(cid, rev)])
                continue
            p = c.pts[-1] if rev else c.pts[0]
            dep[reg].setdefault((int(p[0]), int(p[1])), []).append((cid, rev))

    def first_dir(cid, rev):
        p = chains[cid].pts
        d = (p[-2] - p[-1]) if rev else (p[1] - p[0])
        return int(d[0]), int(d[1])

    def last(cid, rev):
        p = chains[cid].pts
        if rev:
            return p[0], p[0] - p[1]
        return p[-1], p[-1] - p[-2]

    for reg in range(n):
        d = dep[reg]
        while d:
            key = next(iter(d))
            lst = d[key]
            first = lst.pop()
            if not lst:
                del d[key]
            loop = [first]
            cur = first
            start = key
            for _guard in range(10000000):
                end, din = last(*cur)
                k = (int(end[0]), int(end[1]))
                options = list(d.get(k, []))
                if k == start:
                    options.append(first)
                if not options:
                    break
                dx, dy = int(din[0]), int(din[1])
                rightv, leftv = (-dy, dx), (dy, -dx)
                best, bscore = None, 9
                for cc in options:
                    fd = first_dir(*cc)
                    s = 0 if fd == rightv else (1 if fd == (dx, dy) else (2 if fd == leftv else 3))
                    if s < bscore:
                        best, bscore = cc, s
                if best is first and k == start:
                    break
                d[k].remove(best)
                if not d[k]:
                    del d[k]
                loop.append(best)
                cur = best
            regions[reg].loops.append(loop)
    for r in regions:
        r.loop_area = []
        for loop in r.loops:
            a = 0.0
            for cid, rev in loop:
                p = chains[cid].pts
                a += -_shoelace(p) if rev else _shoelace(p)
            r.loop_area.append(a)
        if r.loops:
            r.outer = int(np.argmax(r.loop_area))
    return regions

