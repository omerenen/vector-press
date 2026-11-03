import numpy as np
from PIL import Image, ImageDraw

from vectorizer.api import vectorize


def _noise(n=128, seed=0):
    return np.random.default_rng(seed).integers(0, 256, (n, n, 3), dtype=np.uint8)


def test_photo_fallback_flag():
    img = _noise()
    r = vectorize(img, preset="logo", photo_fallback=False)
    assert r.stats["engine"] == "graph" and "fallback" not in r.stats
    r = vectorize(img, preset="logo", photo_fallback=True)
    assert r.stats["engine"] == "vtracer_raw" and "fallback" in r.stats


def test_photo_route_try_reaches_photo_engine_through_fallback():
    img = _noise()
    r = vectorize(img, photo_route="try")
    assert r.stats["engine"] == "vtracer_raw"
    if r.stats["image_type"] == "photo":
        assert "fallback" in r.stats


def _fringed_logo():
    big = Image.new("RGB", (384, 384), (255, 243, 221))
    ImageDraw.Draw(big).ellipse((60, 60, 320, 320), fill=(137, 57, 230))
    small = big.resize((96, 96), Image.LANCZOS)
    import io
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=60, subsampling=2)    # chroma subsampling + ringing = edge fringes
    return np.asarray(Image.open(buf).convert("RGB"))


def test_fringe_auto_reduces_regions_on_flat_preset_only():
    img = _fringed_logo()
    base = vectorize(img, preset="icon")
    fr = vectorize(img, preset="icon", fringe="auto")
    assert fr.stats["n_regions"] <= base.stats["n_regions"]
    lines = vectorize(img, preset="line_art", fringe="auto")
    assert "fringe_px" not in lines.stats
