import numpy as np
import pytest

from vectorizer.pipeline.color import rgb8_to_oklab
from vectorizer.pipeline.fringe import clean_fringe


def _haloed_disk(n=96):
    """Purple disk on cream with a fragmented pink halo outside and a darker rim inside (JPEG/sharpening fringe)."""
    yy, xx = np.mgrid[:n, :n]
    r = np.hypot(yy - n / 2, xx - n / 2)
    cols = np.array([[255, 243, 221], [137, 57, 230], [255, 232, 255], [129, 68, 192]], np.uint8)
    lbl = np.where(r < 30, 1, 0).astype(np.int32)
    ang = np.arctan2(yy - n / 2, xx - n / 2)
    frag = np.sin(ang * 9) > -0.3                      # fragmented bands
    lbl[(r >= 30) & (r < 31.2) & frag] = 2          # light halo outside
    lbl[(r >= 28.8) & (r < 30) & frag] = 3          # dark rim inside
    pal = rgb8_to_oklab(cols.reshape(1, -1, 3)).reshape(-1, 3).astype(np.float32)
    lab = pal[lbl]
    return lbl, lab, pal, r


@pytest.mark.parametrize("method", ["halo", "colour", "both"])
def test_fringe_bands_are_absorbed(method):
    lbl, lab, pal, r = _haloed_disk()
    out, n = clean_fringe(lbl, lab, pal, method=method)
    assert n > 0
    assert set(np.unique(out).tolist()) == {0, 1}
    # halo pixels go to the background, rim pixels to the disk
    assert (out[(lbl == 2)] == 0).all()
    assert (out[(lbl == 3)] == 1).all()


def test_distinct_thin_line_is_kept():
    n = 80
    lbl = np.zeros((n, n), np.int32)
    lbl[40, 5:75] = 1                               # 1-px black line on white: far colour, not a fringe
    pal = rgb8_to_oklab(np.array([[[255, 255, 255], [0, 0, 0]]], np.uint8)).reshape(-1, 3).astype(np.float32)
    out, changed = clean_fringe(lbl, pal[lbl], pal, method="both")
    assert changed == 0 and (out == lbl).all()


def test_transparent_neighbours_only_are_kept():
    lbl = np.full((20, 20), -1, np.int32)
    lbl[5:15, 10] = 0
    pal = np.array([[0.5, 0.0, 0.0]], np.float32)
    out, _ = clean_fringe(lbl, pal[np.maximum(lbl, 0)], pal, method="halo")
    assert (out == lbl).all()
