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
from .presets import INTENTS, TYPE_TO_PRESET, preset_options

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
    upscale_max_side=3072,   # max mode never processes more than this many px on the long side
    max_region_density=0.008,  # preset="auto": >8 regions per 1000 px (dev: flat art <= 5.7, photos 18-26) -> photo engine
    photo_route="features",  # preset="auto": "features" = classifier "photo" goes straight to the photo engine;
                             # "try" = it goes to the gradient preset and reaches the photo engine only through the
                             # region-explosion fallback (JPEG'd flat art is often classified as photo)
    noise_density=0.1,       # fallback: more regions than this per px (counted before clean-up) = pure noise -> coarse VTracer
    fit_profile="default",   # "tight": halved fit tolerances at 1x (TIGHT_FIT) for the graph-engine content presets
                             # (= the measured cause of the old max-mode gain, without 4x pixels); not for cut / 2x max
    max_presets=None,        # presets that mode="max" processes at 2x (None = MAX_MODE_PRESETS)
    photo_fallback=None,     # region-explosion fallback to the photo engine: None = only with preset "auto", True/False force
    low_alpha=24,
    cutout=False,            # cut-file geometry: real holes, no stacking overlaps, no seams, one path per colour
    drop_background=False,   # cut: remove the background colour (it is not cut / weeded)
    silhouette=False,        # cut: single-colour silhouette
    min_feature_mm=0.0,      # cut: remove features thinner than this at the physical output width
    cut_width_mm=100.0,      # cut: physical output width used for the size thresholds            # flat semi-transparent areas with alpha >= this are kept (with fill-opacity)
    seam_width=1.0,          # width of the under-stroke along shared borders (removes AA seams)
    line_tls=0.45,           # straight-line test tolerance on TLS fit (px)
    sagitta_tol=0.25,        # staircase-vs-curve test: max parabola sagitta for a straight line (px), 0 = off
    thin_lines="ridge",      # "ridge": rescue sub-pixel lines; "both": + bridge diagonal saddles (off: +33% bytes)
    denoise=1,               # edge-preserving sigma-filter iterations before quantisation (W1)
    centerline=False,        # trace thin regions as stroked centre lines (W8)
    subpixel=True,           # move boundary samples to the anti-aliasing implied edge position
    subpixel_taper=3,        # samples over which the sub-pixel shift fades in at junctions (0 = off)
    gradients=True,          # fit linear/radial gradients to banded colour ramps (W6)
    grad_tol=0.03,           # max OKLab RMS residual for an accepted gradient
    slivers=True,            # remove thin AA/JPEG bands whose colour mixes their neighbours
    merge_frac=0.6,          # palette colours closer than merge_frac*color_radius are merged
    mix_suppress=False,      # drop palette colours explainable as AA mixtures (line_art/diagram presets)
    fringe=None,             # edge-fringe clean-up after quantisation: None/"halo"/"colour"/"both"/"auto" (pipeline/fringe.py;
                             # "auto" = "halo" for the presets in FRINGE_PRESETS, off for line art: it erases thin lines)
    fringe_near=0.09,        # OKLab distance under which a thin edge band counts as an overshoot of its neighbour
)


# mode="max": process at 2x (only px-scale of the corner detector is adapted, so the fits are effectively
# twice as tight); measured gains on icon/logo/line_art/diagram, losses on gradients -> not applied there.
MAX_MODE = dict(upscale=2)
MAX_MODE_PRESETS = {"icon", "logo", "flat_illustration", "line_art", "diagram"}
FRINGE_PRESETS = {"icon", "logo", "flat_illustration"}
TIGHT_FIT = dict(fit_tol=0.3, line_tol=0.33)
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
        d = float(min(max(float(detail), 0.0), 1.0))   # 0 = coarse, 1 = fine; 0.5 = defaults
        o.setdefault("fit_tol", 0.6 * (2.0 ** (1.0 - 2.0 * d)))
        o.setdefault("color_radius", 0.045 * (1.6 ** (1.0 - 2.0 * d)))
        o.setdefault("min_area_scale", 2.0 ** (2.0 - 4.0 * d))
    cs = o.pop("corner_sharpness", None)
    if cs is not None:
        c = float(min(max(float(cs), 0.0), 1.0))
        o.setdefault("corner_angle", 80.0 - 50.0 * c)  # 0.5 -> 55 deg (default)
    return o


def _pixel_svg(rgba):
    """Exact output for tiny images: one rect per horizontal run of equal pixels."""
    from .pipeline.color import hex_color
    H, W = rgba.shape[:2]
    els = []
    for y in range(H):
        x = 0
        while x < W:
            px = rgba[y, x]
            x1 = x + 1
            while x1 < W and np.array_equal(rgba[y, x1], px):
                x1 += 1
            if px[3] > 0:
                op = f' fill-opacity="{px[3] / 255:.3f}"' if px[3] < 255 else ""
                els.append(f'<rect x="{x}" y="{y}" width="{x1 - x}" height="1" fill="{hex_color(px[:3])}"{op}/>')
            x = x1
    return svg_document(W, H, "".join(els))


def _normalise_vtracer_svg(svg, W, H, W0, H0):
    """VTracer output -> same header convention as the graph engine (viewBox, no XML prolog/comment)."""
    import re
    body = svg[svg.index(">", svg.index("<svg")) + 1:]
    body = body[: body.rindex("</svg>")]
    body = re.sub(r"\s*\n\s*", "", body)
    return svg_document(W, H, body, out_size=(W0, H0))


def _resize(rgba, W, H, resample):
    from PIL import Image as _Image
    return np.asarray(_Image.fromarray(np.ascontiguousarray(rgba), "RGBA").resize((W, H), resample))


def vectorize(image: ImageLike, preset: str = "auto", mode: str = "fast", **options) -> Result:
    """Vectorise a raster image.

    image:  bytes, file path, PIL.Image or numpy array (H,W[,C]; uint8, uint16 or float 0..1).
    preset: "auto" (classifier) or one of vectorizer.presets.PRESETS. The classifier reports
            image_type in {icon, logo, line_art, gradient, photo}; diagrams are reported as line_art
            and flat illustrations as logo/icon (they share presets).
    mode:   "fast" (default) or "max" (flat presets processed at up to 2x, slower, see README).
    options (user-facing): colors (int|"auto"), detail (0..1), corner_sharpness (0..1),
             primitives (bool), gradients (bool), centerline (bool); any internal key of DEFAULTS.
    Returns Result(svg, stats); stats always contains width, height, mode, preset, image_type,
    timings (per stage, seconds) and bytes.
    """
    from PIL import Image as _Image
    t_all = time.perf_counter()
    timings = {}
    t = time.perf_counter()
    rgba = load_rgba(image)
    timings["load"] = time.perf_counter() - t
    H, W = rgba.shape[:2]
    stats = {"width": W, "height": H, "mode": mode, "image_type": None}
    if mode not in ("fast", "max"):
        raise ValueError("mode must be 'fast' or 'max'")
    opts = dict(DEFAULTS)
    auto = preset == "auto"
    tiny = H == 0 or W == 0 or min(H, W) < 4 or H * W <= 64
    intent = None
    if preset in INTENTS:                    # "cut" / "print": content preset from the classifier + intent overrides
        intent, preset, auto = preset, "auto", True
    if auto:
        t = time.perf_counter()
        itype, feats = classify(rgba) if not tiny else ("icon", {})
        timings["classify"] = time.perf_counter() - t
        stats["image_type"] = itype
        preset = TYPE_TO_PRESET[itype]
        if preset == "photo" and options.get("photo_route", DEFAULTS["photo_route"]) == "try":
            preset = "gradient"
    opts.update(preset_options(preset))
    if intent:
        if preset in ("photo",):             # photos: posterize through the region engine for cut/print intents
            opts.update(preset_options("photo_posterize"))
        opts.update(INTENTS[intent])
        stats["intent"] = intent
        auto = False                         # cut/print never fall back to the VTracer photo engine (clean vectors)
    stats["preset"] = preset if not intent else f"{intent}:{preset}"
    max_presets = options.get("max_presets") or DEFAULTS["max_presets"] or MAX_MODE_PRESETS
    upscaled = mode == "max" and preset in max_presets
    if upscaled:
        opts.update(MAX_MODE)
    if (options.get("fit_profile", DEFAULTS["fit_profile"]) == "tight" and opts["engine"] == "graph"
            and not upscaled and intent != "cut"):
        opts.update(TIGHT_FIT)
    opts.update({k: v for k, v in _map_user_options(options).items() if v is not None})
    unknown = set(opts) - set(DEFAULTS)
    if unknown:
        raise TypeError(f"unknown option(s): {sorted(unknown)}")
    fallback = auto if opts["photo_fallback"] is None else bool(opts["photo_fallback"])
    if opts["fringe"] == "auto":
        opts["fringe"] = "halo" if preset in FRINGE_PRESETS else None

    def finish(svg):
        timings["total"] = time.perf_counter() - t_all
        stats["timings"] = timings
        stats["bytes"] = len(svg.encode())
        return Result(svg, stats)

    if tiny:
        stats["engine"] = "pixels"
        return finish(_pixel_svg(rgba) if H and W else svg_document(max(W, 1), max(H, 1), ""))
    W0, H0 = W, H
    if opts["max_side"] and max(H, W) > opts["max_side"]:
        sc = opts["max_side"] / max(H, W)
        W, H = max(1, int(round(W * sc))), max(1, int(round(H * sc)))
        rgba = _resize(rgba, W, H, _Image.LANCZOS)
        stats["processed_size"] = [W, H]
    if opts["upscale"] and opts["upscale"] > 1 and opts["engine"] == "graph":
        f = min(float(opts["upscale"]), opts["upscale_max_side"] / max(H, W))
        if f >= 1.25:
            W, H = int(round(W * f)), int(round(H * f))
            rgba = _resize(rgba, W, H, _Image.BICUBIC)
            stats["processed_size"] = [W, H]
            stats["upscale"] = round(f, 3)
            # pixel-unit tolerances are defined at input resolution
            for k in opts["upscale_scaled"]:
                opts[k] = opts.get(k, _PX_DEFAULTS.get(k)) * f
    svg = None
    if opts["engine"] == "graph":
        t = time.perf_counter()
        lbl, pal_rgb, pal_lab, qinfo, lab = quantize(rgba[..., :3], rgba[..., 3], radius=opts["color_radius"],
                                                max_colors=opts["max_colors"], min_area=opts["min_area"],
                                                min_area_scale=opts["min_area_scale"],
                                                thin_lines=opts["thin_lines"], mix_suppress=opts["mix_suppress"],
                                                slivers=opts["slivers"], merge_frac=opts["merge_frac"],
                                                denoise=opts["denoise"], low_alpha=opts["low_alpha"],
                                                bail_density=opts["max_region_density"] * 4 if fallback else None)
        timings["quantize"] = time.perf_counter() - t
        if opts["fringe"] and not qinfo.get("bailed"):
            from .pipeline.fringe import clean_fringe
            from .pipeline.boundary import label_regions
            t = time.perf_counter()
            lbl, nfr = clean_fringe(lbl, lab, pal_lab, method=opts["fringe"], near=opts["fringe_near"],
                                    min_area=max(2, int(qinfo.get("min_area") or 3)))
            if nfr:
                used = np.unique(lbl[lbl >= 0])
                remap = np.full(len(pal_lab), -1, np.int32)
                remap[used] = np.arange(len(used))
                lbl = np.where(lbl >= 0, remap[np.maximum(lbl, 0)], lbl).astype(np.int32)
                pal_lab, pal_rgb = pal_lab[used], pal_rgb[used]
                qinfo = dict(qinfo, n_colors=len(used), n_regions=int(len(label_regions(lbl)[1])), fringe_px=nfr)
            timings["fringe"] = time.perf_counter() - t
        stats.update(qinfo)
        if opts["cutout"]:
            from .pipeline import cut as _cut
            t = time.perf_counter()
            if opts["silhouette"]:
                lbl, pal_lab = _cut.silhouette(lbl, pal_lab)
                pal_rgb = oklab_to_rgb8(pal_lab)
            px_per_mm = W0 / float(opts["cut_width_mm"]) * (W / W0)
            if opts["min_feature_mm"]:
                lbl = _cut.enforce_min_feature(lbl, opts["min_feature_mm"] * px_per_mm, pal_lab)
            if opts["drop_background"]:
                bgl = _cut.background_label(lbl)
                if bgl >= 0 and (lbl == bgl).mean() < 0.95:
                    lbl = np.where(lbl == bgl, -1, lbl)
            timings["cut"] = time.perf_counter() - t
        if fallback and qinfo["n_regions"] > 300 and qinfo["n_regions"] > H * W * opts["max_region_density"]:
            # region explosion (texture / noise / star fields misclassified as flat art): photo engine
            stats["fallback"] = f"photo ({qinfo['n_regions']} regions)"
            preset = "photo"
            stats["preset"] = preset
            popts = preset_options("photo")
            opts["engine"] = "vtracer_raw"
            opts["vtracer_params"] = dict(popts["vtracer_params"])
            if qinfo["n_regions"] > opts["noise_density"] * H * W:      # pure noise: bound the output size
                opts["vtracer_params"].update(filter_speckle=8, color_precision=6, layer_difference=24)
            if max(H, W) > popts["max_side"]:
                sc = popts["max_side"] / max(H, W)
                W, H = max(1, int(round(W * sc))), max(1, int(round(H * sc)))
                rgba = _resize(rgba, W, H, _Image.LANCZOS)
                stats["processed_size"] = [W, H]
        else:
            label_fill, defs = None, []
            if opts["gradients"]:
                t = time.perf_counter()
                lbl, pal_lab, label_fill, defs = apply_gradients(rgba[..., :3], lbl, pal_lab, opts)
                pal_rgb = oklab_to_rgb8(pal_lab)
                timings["gradients"] = time.perf_counter() - t
                stats["n_gradients"] = len(defs)
            ctx = {"lab": lab, "pal_lab": pal_lab, "skip_labels": set(label_fill or {})} if opts["subpixel"] else None
            els, est = build_elements(lbl, pal_rgb, opts, timings, label_fill=label_fill, ctx=ctx,
                                      alpha=rgba[..., 3])
            stats.update(est)
            body = (f"<defs>{''.join(defs)}</defs>" if defs else "") + "".join(els)
            svg = svg_document(W, H, body, out_size=(W0, H0))
    if svg is None and opts["engine"] == "vtracer":
        t = time.perf_counter()
        lbl, pal_rgb, pal_lab, qinfo, lab = quantize(rgba[..., :3], rgba[..., 3], radius=opts["color_radius"],
                                                max_colors=opts["max_colors"], merge_frac=opts["merge_frac"])
        img = np.zeros((H, W, 4), np.uint8)
        m = lbl >= 0
        img[m, :3] = np.clip(pal_rgb[lbl[m]] + 0.5, 0, 255).astype(np.uint8)
        img[m, 3] = 255
        svg = _normalise_vtracer_svg(vtracer_trace(img, filter_speckle=1, color_precision=8, layer_difference=1),
                                     W, H, W0, H0)
        timings["vtracer"] = time.perf_counter() - t
    if svg is None:  # vtracer_raw (photo preset or fallback)
        t = time.perf_counter()
        svg = _normalise_vtracer_svg(vtracer_trace(rgba, **(opts["vtracer_params"] or {})), W, H, W0, H0)
        timings["vtracer"] = time.perf_counter() - t
    stats["engine"] = opts["engine"]
    stats["width"], stats["height"] = W0, H0
    return finish(svg)
