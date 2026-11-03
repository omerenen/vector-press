"""Thin wrapper around VTracer (visioncortex, MIT)."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
import vtracer

VTRACER_DEFAULTS = dict(colormode="color", hierarchical="stacked", mode="spline", filter_speckle=4,
                        color_precision=6, layer_difference=16, corner_threshold=60, length_threshold=4.0,
                        max_iterations=10, splice_threshold=45, path_precision=8)


def vtracer_trace(rgba: np.ndarray, **params) -> str:
    """Run VTracer on an RGBA uint8 array and return the SVG string."""
    p = dict(VTRACER_DEFAULTS)
    p.update({k: v for k, v in params.items() if v is not None})
    p["length_threshold"] = float(p["length_threshold"])
    for k in ("filter_speckle", "color_precision", "layer_difference", "corner_threshold",
              "max_iterations", "splice_threshold", "path_precision"):
        p[k] = int(p[k])
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(rgba), "RGBA").save(buf, "PNG", compress_level=0)
    return vtracer.convert_raw_image_to_svg(buf.getvalue(), img_format="png", **p)
