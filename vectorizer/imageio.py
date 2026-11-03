"""Robust image loading: bytes / path / PIL / ndarray -> RGBA uint8 ndarray.

Handles palette, grayscale (+alpha), 16-bit, CMYK JPEG, EXIF orientation,
animated images (first frame) and premultiplied edge cases.
"""
from __future__ import annotations

import io
import os
from typing import Union

import numpy as np
from PIL import Image, ImageOps

ImageLike = Union[bytes, bytearray, str, os.PathLike, Image.Image, np.ndarray]


def _pil_to_rgba(im: Image.Image) -> np.ndarray:
    try:
        im.seek(0)
    except Exception:
        pass
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    mode = im.mode
    if mode in ("I;16", "I;16B", "I;16L", "I"):
        arr = np.asarray(im).astype(np.float64)
        mx = arr.max() if arr.size else 1
        scale = 65535.0 if mx > 255 else 255.0
        g = np.clip(arr / scale * 255.0 + 0.5, 0, 255).astype(np.uint8)
        im = Image.fromarray(g, "L")
    elif mode == "F":
        arr = np.asarray(im).astype(np.float64)
        lo, hi = float(np.nanmin(arr)), float(np.nanmax(arr))
        g = np.zeros(arr.shape, np.uint8) if hi <= lo else ((arr - lo) / (hi - lo) * 255).astype(np.uint8)
        im = Image.fromarray(g, "L")
    if im.mode == "CMYK":
        # PIL inverts Adobe CMYK JPEGs on load; convert via RGB.
        im = im.convert("RGB")
    if im.mode == "P" and "transparency" in im.info:
        im = im.convert("RGBA")
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    return np.ascontiguousarray(np.asarray(im, dtype=np.uint8))


def load_rgba(image: ImageLike) -> np.ndarray:
    """Return an (H, W, 4) uint8 RGBA array."""
    if isinstance(image, np.ndarray):
        a = image
        if a.dtype != np.uint8:
            a = a.astype(np.float64)
            if a.max() <= 1.0 + 1e-6:
                a = a * 255.0
            a = np.clip(a + 0.5, 0, 255).astype(np.uint8)
        if a.ndim == 2:
            a = np.stack([a, a, a, np.full_like(a, 255)], -1)
        elif a.ndim == 3 and a.shape[2] == 1:
            a = np.concatenate([a, a, a, np.full_like(a, 255)], -1)
        elif a.ndim == 3 and a.shape[2] == 2:
            a = np.stack([a[..., 0]] * 3 + [a[..., 1]], -1)
        elif a.ndim == 3 and a.shape[2] == 3:
            a = np.concatenate([a, np.full(a.shape[:2] + (1,), 255, np.uint8)], -1)
        elif not (a.ndim == 3 and a.shape[2] == 4):
            raise ValueError(f"unsupported array shape {a.shape}")
        return np.ascontiguousarray(a)
    if isinstance(image, Image.Image):
        return _pil_to_rgba(image)
    if isinstance(image, (bytes, bytearray)):
        with Image.open(io.BytesIO(bytes(image))) as im:
            im.load()
            return _pil_to_rgba(im)
    if isinstance(image, (str, os.PathLike)):
        with Image.open(os.fspath(image)) as im:
            im.load()
            return _pil_to_rgba(im)
    raise TypeError(f"unsupported image type: {type(image)!r}")


def composite_over(rgba: np.ndarray, bg=(255, 255, 255)) -> np.ndarray:
    """Alpha-composite RGBA uint8 over a solid background -> RGB uint8."""
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    rgb = rgba[..., :3].astype(np.float32)
    out = rgb * a + np.asarray(bg, np.float32)[None, None, :] * (1 - a)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)
