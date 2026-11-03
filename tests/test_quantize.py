import numpy as np
from PIL import Image, ImageDraw

from vectorizer.pipeline.quantize import quantize


def _aa_image():
    big = Image.new("RGB", (400, 400), (250, 250, 245))
    d = ImageDraw.Draw(big)
    d.ellipse((60, 60, 260, 260), fill=(200, 30, 40))
    d.rectangle((200, 180, 360, 340), fill=(20, 60, 200))
    return np.asarray(big.resize((100, 100), Image.LANCZOS))


def test_palette_has_exactly_the_three_colours():
    rgb = _aa_image()
    lbl, pal, _, info, _ = quantize(rgb, np.full(rgb.shape[:2], 255, np.uint8))
    assert info["n_colors"] == 3
    target = np.array([[250, 250, 245], [200, 30, 40], [20, 60, 200]], float)
    for t in target:
        assert np.abs(pal - t).sum(1).min() < 12


def test_no_inbetween_colour_on_red_blue_border():
    rgb = _aa_image()
    lbl, pal, _, _, _ = quantize(rgb, np.full(rgb.shape[:2], 255, np.uint8))
    # no purple palette entry created by anti-aliasing between red and blue
    purple = (pal[:, 0] > 80) & (pal[:, 2] > 80) & (pal[:, 1] < 120)
    assert not purple.any()


def test_thin_dark_line_survives():
    big = Image.new("RGB", (800, 800), (255, 255, 255))
    ImageDraw.Draw(big).line((40, 100, 760, 700), fill=(0, 0, 0), width=6)
    rgb = np.asarray(big.resize((200, 200), Image.LANCZOS))   # ~1.5 px wide AA line
    lbl, pal, _, _, _ = quantize(rgb, np.full(rgb.shape[:2], 255, np.uint8))
    dark = int(np.argmin(pal.sum(1)))
    assert pal[dark].sum() < 200
    from scipy import ndimage as ndi
    n = ndi.label(lbl == dark, structure=np.ones((3, 3)))[1]
    assert n <= 2                     # continuous (not dashed)
    assert (lbl == dark).sum() > 180  # roughly length 225 * width ~1.5


def test_transparent_pixels_get_minus_one():
    rgb = np.zeros((20, 20, 3), np.uint8) + 100
    a = np.full((20, 20), 255, np.uint8)
    a[:, :10] = 0
    lbl, *_ = quantize(rgb, a)
    assert (lbl[:, :10] == -1).all() and (lbl[:, 10:] >= 0).all()
