"""SVG rasterisation via resvg (resvg-py, pip-only, MIT/Apache)."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
import resvg_py


def render_svg(svg: str, width: int, height: int) -> np.ndarray:
    """Render SVG to (height, width, 4) RGBA uint8 (straight alpha)."""
    png = resvg_py.svg_to_bytes(svg_string=svg, width=int(width), height=int(height),
                                skip_system_fonts=True)
    with Image.open(io.BytesIO(bytes(png))) as im:
        im = im.convert("RGBA")
        if im.size != (width, height):
            im = im.resize((width, height), Image.BILINEAR)
        return np.asarray(im, dtype=np.uint8).copy()
