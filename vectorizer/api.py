"""Public API: vectorize(image, preset="auto", mode="fast", **options) -> Result."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .imageio import ImageLike, load_rgba
from .pipeline.assemble import build_elements
from .pipeline.quantize import quantize
from .pipeline.svgout import svg_document
from .pipeline.trace import vtracer_trace

DEFAULTS = dict(
    engine="graph",          # "graph" (shared boundary graph) | "vtracer" (palette-cleaned VTracer) | "vtracer_raw"
    color_radius=0.045,      # OKLab merge radius for palette extraction (smaller = more colours)
    max_colors=64,
    min_area=None,           # speckle size in px (None = auto from image size)
    fit_tol=0.6,             # Bezier fit tolerance (px)
    line_tol=0.65,           # straight-line snapping tolerance (px)
    corner_angle=55.0,       # corner sharpness threshold (deg)
    smooth_sigma=1.0,
    primitives=True,
    prim_tol=0.75,
    precision=2,
    seam_width=1.0,
)


@dataclass
class Result:
    svg: str
    stats: dict = field(default_factory=dict)

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.svg)


def vectorize(image: ImageLike, preset: str = "auto", mode: str = "fast", **options) -> Result:
    t_all = time.perf_counter()
    timings = {}
    t = time.perf_counter()
    rgba = load_rgba(image)
    timings["load"] = time.perf_counter() - t
    opts = dict(DEFAULTS)
    opts.update({k: v for k, v in options.items() if v is not None})
    H, W = rgba.shape[:2]
    stats = {"width": W, "height": H, "preset": preset, "mode": mode}
    if H == 0 or W == 0:
        return Result(svg_document(max(W, 1), max(H, 1), ""), stats)
    if opts["engine"] == "vtracer_raw":
        t = time.perf_counter()
        svg = vtracer_trace(rgba)
        timings["vtracer"] = time.perf_counter() - t
    else:
        t = time.perf_counter()
        lbl, pal_rgb, pal_lab, qinfo = quantize(rgba[..., :3], rgba[..., 3], radius=opts["color_radius"],
                                                max_colors=opts["max_colors"], min_area=opts["min_area"])
        timings["quantize"] = time.perf_counter() - t
        stats.update(qinfo)
        if opts["engine"] == "vtracer":
            t = time.perf_counter()
            img = np.zeros((H, W, 4), np.uint8)
            m = lbl >= 0
            img[m, :3] = np.clip(pal_rgb[lbl[m]] + 0.5, 0, 255).astype(np.uint8)
            img[m, 3] = 255
            svg = vtracer_trace(img, filter_speckle=1, color_precision=8, layer_difference=1)
            timings["vtracer"] = time.perf_counter() - t
        else:
            els, est = build_elements(lbl, pal_rgb, opts, timings)
            stats.update(est)
            svg = svg_document(W, H, "".join(els))
    timings["total"] = time.perf_counter() - t_all
    stats["timings"] = timings
    stats["bytes"] = len(svg.encode())
    return Result(svg, stats)
