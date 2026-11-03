import numpy as np
from PIL import Image, ImageDraw

from eval.printcut import printcut_metrics
from vectorizer import vectorize


def _design(size=400):
    im = Image.new("RGB", (size, size), (250, 250, 250))
    d = ImageDraw.Draw(im)
    d.ellipse((40, 40, 360, 360), fill=(200, 30, 40))
    d.ellipse((120, 120, 280, 280), fill=(250, 250, 250))       # ring: a real hole
    d.rectangle((180, 20, 220, 380), fill=(20, 40, 160))          # crosses the ring
    d.line((10, 390, 390, 392), fill=(20, 40, 160), width=1)      # hairline (< 0.5 mm at 100 mm width)
    d.ellipse((30, 300, 32, 302), fill=(200, 30, 40))             # speck
    return im


def test_cut_preset_is_cut_ready():
    r = vectorize(_design(), preset="cut")
    m = printcut_metrics(r.svg, 400, 400)
    assert m["open_subpaths"] == 0
    assert abs(m["overlap_ratio"]) < 0.01           # cutout geometry, no layering (raster union: +-0.5 %)
    assert m["tiny_islands"] == 0
    assert m["n_colors"] <= 2                        # background dropped
    assert r.stats["preset"].startswith("cut:")


def test_print_preset_is_stacked_and_faithful():
    r = vectorize(_design(), preset="print")
    m = printcut_metrics(r.svg, 400, 400)
    assert m["open_subpaths"] == 0 and m["n_colors"] == 3


def test_silhouette_single_colour():
    r = vectorize(_design(), preset="cut", silhouette=True)
    assert printcut_metrics(r.svg, 400, 400)["n_colors"] == 1


def test_printcut_detects_overlap_and_tiny_islands():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">'
           '<rect x="0" y="0" width="100" height="100" fill="#fff"/><rect x="10" y="10" width="50" height="50" fill="#f00"/>'
           '<rect x="80" y="80" width="0.3" height="0.3" fill="#00f"/></svg>')
    m = printcut_metrics(svg, 100, 100)
    assert m["overlap_ratio"] > 0.2 and m["tiny_islands"] >= 1 and m["n_colors"] == 3
