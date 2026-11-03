"""Colour space helpers: sRGB <-> linear <-> OKLab (Ottosson 2020, public domain formulas)."""
from __future__ import annotations

import numpy as np


def srgb_to_linear(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, np.float32), 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055).astype(np.float32)


_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]], np.float32)
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]], np.float32)
_M1i = np.linalg.inv(_M1.astype(np.float64)).astype(np.float32)
_M2i = np.linalg.inv(_M2.astype(np.float64)).astype(np.float32)


def rgb8_to_oklab(rgb):
    """uint8/float(0..255) RGB (...,3) -> OKLab float32 (...,3)."""
    lin = srgb_to_linear(np.asarray(rgb, np.float32) / 255.0)
    lms = lin @ _M1.T
    lms = np.cbrt(np.maximum(lms, 0))
    return (lms @ _M2.T).astype(np.float32)


def oklab_to_rgb8(lab):
    lab = np.asarray(lab, np.float32)
    lms = lab @ _M2i.T
    lms = lms ** 3
    lin = lms @ _M1i.T
    return np.clip(linear_to_srgb(lin) * 255.0, 0, 255).astype(np.float32)


def hex_color(rgb):
    r, g, b = (int(np.clip(round(float(v)), 0, 255)) for v in rgb[:3])
    s = f"#{r:02x}{g:02x}{b:02x}"
    if s[1] == s[2] and s[3] == s[4] and s[5] == s[6]:
        return "#" + s[1] + s[3] + s[5]
    return s
