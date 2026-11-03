import io
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from PIL import Image, ImageDraw

from vectorizer import vectorize
from vectorizer.imageio import composite_over
from vectorizer.render import render_svg


def _logo(size=200):
    im = Image.new("RGB", (size * 4, size * 4), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.ellipse((size * 0.5, size * 0.5, size * 2.5, size * 2.5), fill=(230, 80, 20))
    d.rectangle((size * 2.7, size * 2.6, size * 3.7, size * 3.4), fill=(30, 40, 120))
    return im.resize((size, size), Image.LANCZOS)


def _check(svg, w, h):
    ET.fromstring(svg)
    out = render_svg(svg, w, h)
    assert out.shape == (h, w, 4)
    return out


def test_logo_high_fidelity_and_no_gaps():
    im = _logo()
    r = vectorize(im)
    out = _check(r.svg, 200, 200)
    ref = np.asarray(im).astype(float)
    err = np.abs(composite_over(out).astype(float) - ref).mean()
    assert err < 3.0
    hi = render_svg(r.svg, 800, 800)
    assert (hi[8:-8, 8:-8, 3] < 250).sum() == 0          # no hairline gaps at 4x
    assert r.stats["image_type"] in ("icon", "logo")
    assert "<circle" in r.svg or "<ellipse" in r.svg       # primitive recovered


@pytest.mark.parametrize("case", ["1x1", "2x3", "16", "gray", "la", "palette", "rgba_transparent", "all_transparent",
                                  "one_color", "cmyk_jpeg", "16bit", "noisy", "webp", "tall_thin", "float_array"])
def test_edge_cases_do_not_crash(case):
    rng = np.random.default_rng(0)
    if case == "1x1":
        img = Image.new("RGB", (1, 1), (10, 20, 30))
    elif case == "2x3":
        img = Image.fromarray(rng.integers(0, 255, (3, 2, 3), dtype=np.uint8))
    elif case == "16":
        img = _logo(16)
    elif case == "gray":
        img = _logo(64).convert("L")
    elif case == "la":
        img = _logo(64).convert("LA")
    elif case == "palette":
        img = _logo(64).convert("P", palette=Image.ADAPTIVE, colors=8)
    elif case == "rgba_transparent":
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse((10, 10, 50, 50), fill=(255, 0, 0, 255))
    elif case == "all_transparent":
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    elif case == "one_color":
        img = Image.new("RGB", (50, 40), (12, 200, 99))
    elif case == "cmyk_jpeg":
        buf = io.BytesIO()
        _logo(64).convert("CMYK").save(buf, "JPEG")
        img = buf.getvalue()
    elif case == "16bit":
        arr = (np.linspace(0, 65535, 64 * 64).reshape(64, 64)).astype(np.uint16)
        img = Image.fromarray(arr)
    elif case == "noisy":
        img = Image.fromarray(rng.integers(0, 255, (80, 80, 3), dtype=np.uint8))
    elif case == "webp":
        buf = io.BytesIO()
        _logo(64).save(buf, "WEBP")
        img = buf.getvalue()
    elif case == "tall_thin":
        img = Image.new("RGB", (3, 300), (0, 0, 0))
    elif case == "float_array":
        img = np.asarray(_logo(32)).astype(np.float32) / 255.0
    r = vectorize(img)
    W = r.stats["width"]
    H = r.stats["height"]
    _check(r.svg, max(W, 1), max(H, 1))


def test_one_color_image_is_single_rect():
    r = vectorize(Image.new("RGB", (50, 40), (12, 200, 99)))
    out = composite_over(render_svg(r.svg, 50, 40))
    assert np.abs(out.astype(int) - [12, 200, 99]).max() <= 2


def test_transparent_background_stays_transparent():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((10, 10, 50, 50), fill=(255, 0, 0, 255))
    r = vectorize(img)
    out = render_svg(r.svg, 64, 64)
    assert out[2, 2, 3] == 0 and out[30, 30, 3] == 255


def test_presets_and_user_options():
    im = _logo(96)
    for p in ["logo", "icon", "illustration", "line_art", "diagram", "gradient", "photo", "photo_posterize"]:
        _check(vectorize(im, preset=p).svg, 96, 96)
    r = vectorize(im, colors=2, detail=0.2, corner_sharpness=0.9, primitives=False, gradients=False, mode="max")
    _check(r.svg, 96, 96)
    assert "<circle" not in r.svg and "<ellipse" not in r.svg
    with pytest.raises(TypeError):
        vectorize(im, not_an_option=1)
    with pytest.raises(ValueError):
        vectorize(im, preset="nope")


def test_vtracer_engines():
    im = _logo(64)
    for e in ["vtracer", "vtracer_raw"]:
        _check(vectorize(im, engine=e).svg, 64, 64)


def test_centerline_option_produces_strokes():
    im = Image.new("RGB", (400, 400), "white")
    ImageDraw.Draw(im).line((40, 40, 360, 300), fill="black", width=12)
    r = vectorize(im.resize((200, 200), Image.LANCZOS), centerline=True)
    assert "stroke-linecap" in r.svg and r.stats["n_strokes"] >= 1
