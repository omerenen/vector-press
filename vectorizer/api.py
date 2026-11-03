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
    min_area_scale=1.0,      # multiplier on the automatic speckle size
    fit_tol=0.6,             # Bezier fit tolerance (px)
    line_tol=0.65,           # straight-line snapping tolerance (px)
    corner_angle=55.0,       # corner sharpness threshold (deg)
    corner_scale=3.0,        # arm length (px) of the corner detector
    smooth_sigma=1.0,        # boundary smoothing before curve fitting (samples)
    primitives=True,         # emit circle/ellipse/rect for closed boundaries that fit them
    prim_tol=0.75,           # primitive acceptance error (px, robust)
    precision=2,             # decimals in the SVG output
    vtracer_params=None,     # dict of VTracer parameters for engine="vtracer_raw"
    max_side=2048,           # larger inputs are processed at this size (SVG keeps the original size)
    upscale=1,               # process at this factor (bicubic) - used by mode="max"
    upscale_scaled=("corner_scale", "seam_width"),  # px-unit options rescaled when upscaling
    seam_width=1.0,          # width of the under-stroke along shared borders (removes AA seams)
    line_tls=0.45,           # straight-line test tolerance on TLS fit (px)
    sagitta_tol=0.25,        # staircase-vs-curve test: max parabola sagitta for a straight line (px), 0 = off
    thin_lines="ridge",      # "ridge": rescue sub-pixel lines; "both": + bridge diagonal saddles (off: +33% bytes)
    denoise=1,               # edge-preserving sigma-filter iterations before quantisation (W1)
    centerline=False,        # trace thin regions as stroked centre lines (W8)
    subpixel=True,           # move boundary samples to the anti-aliasing implied edge position
    gradients=True,          # fit linear/radial gradients to banded colour ramps (W6)
    grad_tol=0.03,           # max OKLab RMS residual for an accepted gradient
    slivers=True,            # remove thin AA/JPEG bands whose colour mixes their neighbours
    merge_frac=0.6,          # palette colours closer than merge_frac*color_radius are merged
    mix_suppress=False,      # drop palette colours explainable as AA mixtures (line_art/diagram presets)
)


# mode="max": process at 2x (only px-scale of the corner detector is adapted, so the fits are effectively
# twice as tight); measured gains on icon/logo/line_art/diagram, losses on gradients -> not applied there.
MAX_MODE = dict(upscale=2)
MAX_MODE_PRESETS = {"icon", "logo", "flat_illustration", "line_art", "diagram"}
_PX_DEFAULTS = dict(corner_scale=3.0, seam_width=1.0)


@dataclass
class Result:
    svg: str
    stats: dict = field(default_factory=dict)

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.svg)


USER_OPTIONS = ("colors", "detail", "corner_sharpness", "primitives", "gradients", "centerline")


def _map_user_options(options: dict) -> dict:
    """Translate the documented user-facing knobs into internal parameters."""
    o = dict(options)
    colors = o.pop("colors", None)
    if colors not in (None, "auto"):
        o.setdefault("max_colors", max(1, int(colors)))
    detail = o.pop("detail", None)
    if detail is not None:
        d = float(min(max(detail, 0.0), 1.0))          # 0 = coarse, 1 = fine; 0.5 = defaults
        o.setdefault("fit_tol", 0.6 * (2.0 ** (1.0 - 2.0 * d)))
        o.setdefault("color_radius", 0.045 * (1.6 ** (1.0 - 2.0 * d)))
        o.setdefault("min_area_scale", 2.0 ** (2.0 - 4.0 * d))
    cs = o.pop("corner_sharpness", None)
    if cs is not None:
        c = float(min(max(cs, 0.0), 1.0))
        o.setdefault("corner_angle", 80.0 - 50.0 * c)  # 0.5 -> 55 deg (default)
    return o


def vectorize(image: ImageLike, preset: str = "auto", mode: str = "fast", **options) -> Result:
    """Vectorise a raster image.

    image:  bytes, file path, PIL.Image or numpy array (H,W[,C]).
    preset: "auto" (classifier) or one of vectorizer.presets.PRESETS.
    mode:   "fast" (default) or "max" (slower, see README).
    options (user-facing): colors (int|"auto"), detail (0..1), corner_sharpness (0..1),
             primitives (bool), gradients (bool), centerline (bool); any internal key of DEFAULTS.
    Returns Result(svg, stats) with stats: image_type, preset, timings per stage, sizes, counts.
    """
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
    if mode == "max":
        if preset in MAX_MODE_PRESETS:
            opts.update(MAX_MODE)
    elif mode != "fast":
        raise ValueError("mode must be 'fast' or 'max'")
    opts.update({k: v for k, v in _map_user_options(options).items() if v is not None})
    unknown = set(opts) - set(DEFAULTS)
    if unknown:
        raise TypeError(f"unknown option(s): {sorted(unknown)}")
    if H == 0 or W == 0:
        return Result(svg_document(max(W, 1), max(H, 1), ""), stats)
    W0, H0 = W, H
    if opts["max_side"] and max(H, W) > opts["max_side"]:
        from PIL import Image as _Image
        sc = opts["max_side"] / max(H, W)
        W, H = max(1, int(round(W * sc))), max(1, int(round(H * sc)))
        rgba = np.asarray(_Image.fromarray(rgba, "RGBA").resize((W, H), _Image.LANCZOS))
        stats["processed_size"] = [W, H]
    if opts["upscale"] and opts["upscale"] > 1 and opts["engine"] == "graph":
        from PIL import Image as _Image
        f = float(opts["upscale"])
        if max(H, W) * f <= opts["max_side"]:
            W, H = int(round(W * f)), int(round(H * f))
            rgba = np.asarray(_Image.fromarray(rgba, "RGBA").resize((W, H), _Image.BICUBIC))
            stats["processed_size"] = [W, H]
            # pixel-unit tolerances are defined at input resolution
            for k in opts["upscale_scaled"]:
                opts[k] = opts.get(k, _PX_DEFAULTS.get(k)) * f
            if opts["upscale_scaled"]:
                opts["min_area_scale"] = opts["min_area_scale"] * f * f
    if opts["engine"] == "vtracer_raw":
        t = time.perf_counter()
        svg = vtracer_trace(rgba, **(opts["vtracer_params"] or {}))
        timings["vtracer"] = time.perf_counter() - t
    else:
        t = time.perf_counter()
        lbl, pal_rgb, pal_lab, qinfo, lab = quantize(rgba[..., :3], rgba[..., 3], radius=opts["color_radius"],
                                                max_colors=opts["max_colors"], min_area=opts["min_area"],
                                                min_area_scale=opts["min_area_scale"],
                                                thin_lines=opts["thin_lines"], mix_suppress=opts["mix_suppress"],
                                                slivers=opts["slivers"], merge_frac=opts["merge_frac"],
                                                denoise=opts["denoise"])
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
            ctx = {"lab": lab, "pal_lab": pal_lab, "skip_labels": set(label_fill or {})} if opts["subpixel"] else None
            els, est = build_elements(lbl, pal_rgb, opts, timings, label_fill=label_fill, ctx=ctx)
            stats.update(est)
            body = (f"<defs>{''.join(defs)}</defs>" if defs else "") + "".join(els)
            svg = svg_document(W, H, body, out_size=(W0, H0))
    if (W, H) != (W0, H0) and opts["engine"] != "graph":
        import re as _re
        svg = _re.sub(r'<svg([^>]*?)width="[^"]*" height="[^"]*"', 
                      lambda m: f'<svg{m.group(1)}viewBox="0 0 {W} {H}" width="{W0}" height="{H0}"', svg, count=1)
    stats["width"], stats["height"] = W0, H0
    timings["total"] = time.perf_counter() - t_all
    stats["timings"] = timings
    stats["bytes"] = len(svg.encode())
    return Result(svg, stats)
