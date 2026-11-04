"""Stream B: fast quantisation helpers are equivalent to the reference versions; Mumford-Shah region merging."""
import numpy as np

from vectorizer.pipeline import quantize as Q
from vectorizer.pipeline.preprocess import sigma_filter, sigma_filter_ref
from vectorizer.pipeline.segment import ms_merge, region_edges, snap_colors
from vectorizer.pipeline.boundary import label_regions


def _lab(seed=0, H=37, W=53):
    rng = np.random.default_rng(seed)
    lab = np.zeros((H, W, 3), np.float32)
    lab[..., 0] = 0.3
    lab[:, W // 2:, 0] = 0.8
    lab[H // 3:, :, 1] = 0.1
    return lab + rng.normal(0, 0.01, lab.shape).astype(np.float32)


def test_sigma_filter_matches_reference():
    lab = _lab()
    np.testing.assert_allclose(sigma_filter(lab, 0.03, 1), sigma_filter_ref(lab, 0.03, 1), atol=1e-5)


def test_dir_stats_matches_reference():
    lab = _lab(1)
    for x, y in zip(Q._dir_stats(lab), Q._dir_stats_ref(lab)):
        for u, v in zip(x, y):
            np.testing.assert_allclose(u, v, atol=1e-6)


def test_label_medians_matches_loop():
    rng = np.random.default_rng(2)
    lab = rng.random((20, 30, 3)).astype(np.float32)
    lbl = rng.integers(-1, 5, (20, 30)).astype(np.int32)
    flat = rng.random((20, 30)) > 0.7
    fb = rng.random((6, 3)).astype(np.float32)
    got = Q.label_medians(lbl, lab, flat, fb)
    for k in range(6):
        mk = (lbl >= 0) & flat & (lbl == k)
        if mk.sum() < 3:
            mk = lbl == k
        exp = np.median(lab[mk], axis=0) if mk.any() else fb[k]
        np.testing.assert_allclose(got[k], exp, atol=1e-6)


def test_ms_merge_texture_collapses_but_line_survives():
    rng = np.random.default_rng(3)
    H, W = 60, 60
    lab = np.zeros((H, W, 3), np.float32)
    lab[..., 0] = 0.5 + rng.normal(0, 0.03, (H, W))        # textured grey field
    lab[:, 30:, 0] += 0.3                                    # a real edge
    lab[10:50, 15, 0] = 0.0                                  # 1-px black line (high contrast)
    R0 = np.arange(H * W, dtype=np.int32).reshape(H, W)      # every pixel its own region
    Rn, info = ms_merge(R0, lab, lam=0.02)
    assert info["n1"] <= 6, info
    # the line is its own region, separate from both halves
    assert Rn[20, 15] != Rn[20, 5] and Rn[20, 15] != Rn[20, 40] and Rn[20, 5] != Rn[20, 40]
    assert len(np.unique(Rn[10:50, 15])) == 1


def test_region_edges_lengths():
    R = np.array([[0, 0, 1], [0, 2, 1]], np.int32)
    a, b, L = region_edges(R)
    got = {(int(x), int(y)): int(l) for x, y, l in zip(a, b, L)}
    assert got == {(0, 1): 1, (0, 2): 2, (1, 2): 1}


def test_snap_colors_merges_close_paints():
    lbl = np.array([[0, 1, 2]], np.int32)
    pal = np.array([[0.5, 0, 0], [0.505, 0, 0], [0.9, 0, 0]], np.float32)
    out, _ = snap_colors(lbl, pal, 0.02)
    assert out[0, 0] == out[0, 1] and out[0, 2] != out[0, 0]


def test_quantize_ms_engine_runs():
    rgb = np.zeros((64, 64, 3), np.uint8) + 200
    rgb[16:48, 16:48] = (30, 60, 200)
    rgb = np.clip(rgb + np.random.default_rng(4).normal(0, 4, rgb.shape), 0, 255).astype(np.uint8)
    lbl, pr, pl, info, _ = Q.quantize(rgb, np.full((64, 64), 255, np.uint8), segment="ms", seg_lambda=0.01)
    R, rl = label_regions(lbl)
    assert len(rl) == 2, info


def test_ms_engine_textured_flat_art_stays_vector():
    """Grainy flat art (generator noise) must not be routed to the photo engine and must stay compact."""
    from vectorizer.api import vectorize
    rng = np.random.default_rng(5)
    img = np.zeros((256, 256, 3), np.float64) + (235, 225, 200)
    yy, xx = np.mgrid[0:256, 0:256]
    img[(xx - 128) ** 2 + (yy - 128) ** 2 < 70 ** 2] = (200, 60, 40)
    img[100:160, 30:90] = (30, 30, 30)
    img = np.clip(img + rng.normal(0, 7, img.shape), 0, 255).astype(np.uint8)
    res = vectorize(img, segment="ms", seg_premerge=True)
    assert res.stats["engine"] == "graph" and "fallback" not in res.stats
    assert res.stats["n_regions"] <= 10, res.stats["n_regions"]


def test_reduce_paints_caps_colours():
    from vectorizer.pipeline.segment import reduce_paints
    rng = np.random.default_rng(6)
    pal = rng.random((50, 3)).astype(np.float32)
    lbl = rng.integers(0, 50, (30, 30)).astype(np.int32)
    out, P = reduce_paints(lbl, pal, 8)
    assert len(P) == 8 and out.max() < 8 and out.min() >= 0
