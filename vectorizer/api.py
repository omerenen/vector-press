"""Public API: vectorize(image, preset="auto", mode="fast", **options) -> Result."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .imageio import ImageLike, load_rgba
from .pipeline.assemble import build_elements
from .pipeline.color import oklab_to_rgb8
from .pipeline.gradients import apply_gradients
from .pipeline.quantize import quantize
from .pipeline.svgout import svg_document
from .pipeline.trace import vtracer_trace
from .pipeline.classify import classify
from .presets import TYPE_TO_PRESET, preset_options

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
    line_tls=0.45,           # straight-line test tolerance on TLS fit (px)
    thin_lines="ridge",      # "ridge": rescue sub-pixel lines; "both": + bridge diagonal saddles (off: +33% bytes)
    gradients=True,          # fit linear/radial gradients to banded colour ramps (W6)
    grad_tol=0.03,           # max OKLab RMS residual for an accepted gradient
    slivers=True,
    merge_frac=0.6,          # palette colours closer than merge_frac*color_radius are merged            # remove thin AA/JPEG bands whose colour mixes their neighbours
    mix_suppress=False,      # drop palette colours explainable as AA mixtures (line_art/diagram presets)
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
    H, W = rgba.shape[:2]
    stats = {"width": W, "height": H, "mode": mode}
    opts = dict(DEFAULTS)
    if preset == "auto":
        t = time.perf_counter()
        itype, feats = classify(rgba) if H > 0 and W > 0 else ("icon", {})
        timings["classify"] = time.perf_counter() - t
        stats["image_type"] = itype
        preset = TYPE_TO_PRESET[itype]
    else:
        stats["image_type"] = None
    opts.update(preset_options(preset))
    stats["preset"] = preset
    opts.update({k: v for k, v in options.items() if v is not None})
    if H == 0 or W == 0:
        return Result(svg_document(max(W, 1), max(H, 1), ""), stats)
    if opts["engine"] == "vtracer_raw":
        t = time.perf_counter()
        svg = vtracer_trace(rgba)
        timings["vtracer"] = time.perf_counter() - t
    else:
        t = time.perf_counter()
        lbl, pal_rgb, pal_lab, qinfo = quantize(rgba[..., :3], rgba[..., 3], radius=opts["color_radius"],
                                                max_colors=opts["max_colors"], min_area=opts["min_area"],
                                                thin_lines=opts["thin_lines"], mix_suppress=opts["mix_suppress"],
                                                slivers=opts["slivers"], merge_frac=opts["merge_frac"])
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
            label_fill, defs = None, []
            if opts["gradients"]:
                t = time.perf_counter()
                lbl, pal_lab, label_fill, defs = apply_gradients(rgba[..., :3], lbl, pal_lab, opts)
                pal_rgb = oklab_to_rgb8(pal_lab)
                timings["gradients"] = time.perf_counter() - t
                stats["n_gradients"] = len(defs)
            els, est = build_elements(lbl, pal_rgb, opts, timings, label_fill=label_fill)
            stats.update(est)
            body = (f"<defs>{''.join(defs)}</defs>" if defs else "") + "".join(els)
            svg = svg_document(W, H, body)
    timings["total"] = time.perf_counter() - t_all
    stats["timings"] = timings
    stats["bytes"] = len(svg.encode())
    return Result(svg, stats)
