import numpy as np

from eval import metrics as M


def test_identical_images_perfect():
    a = (np.random.default_rng(0).random((40, 40, 3)) * 255).astype(np.uint8)
    assert M.ssim(a, a) > 0.999 and M.psnr(a, a) == 60.0 and M.gmsd(a, a) < 1e-9
    assert M.delta_e(a, a)[0] < 1e-6 and M.edge_f(a, a) == 1.0


def test_parse_path_relative_and_shorthand():
    segs = M.parse_path("M10 10h5v5l-5 0z")
    pts = [s[1][0] for s in segs]
    assert pts[:4] == [(10, 10), (15, 10), (15, 15), (10, 15)]


def test_primitive_recovery_matches_circle_and_poly():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50.2" cy="50" r="20.5"/>'
           '<path d="M10 10L30 10L20 30Z"/></svg>')
    prims = [{"type": "circle", "cx": 50, "cy": 50, "rx": 20, "ry": 20},
             {"type": "triangle", "points": [(10, 10), (30, 10), (20, 30)]}]
    rec, per = M.primitive_recovery(svg, prims)
    assert rec == 1.0


def test_primitive_recovery_multi_subpath_and_round_ellipse():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
           '<path d="M0 0h5v5h-5zM10 10L30 10L20 30Z"/>'
           '<ellipse cx="60" cy="60" rx="20.4" ry="20" transform="rotate(37 60 60)"/></svg>')
    prims = [{"type": "triangle", "points": [(10, 10), (30, 10), (20, 30)]},
             {"type": "ellipse", "cx": 60, "cy": 60, "rx": 20.2, "ry": 20.0, "angle": 120.0}]
    rec, per = M.primitive_recovery(svg, prims)
    assert rec == 1.0


def test_embedded_raster_scores_zero():
    m = {"is_vector": M.is_vector('<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,AA"/></svg>'),
         "ssim": 1, "psnr": 60, "de_mean": 0, "edge_f": 1, "gmsd": 0, "gz_bytes": 100}
    assert m["is_vector"] is False and M.composite(m) == 0.0


def test_primitive_recovery_viewbox_offset():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 10 50 50"><circle cx="35" cy="35" r="10"/></svg>'
    # 100 px render of a 50-unit viewBox starting at 10: centre (35,35) -> (50,50), r 10 -> 20
    rec, _ = M.primitive_recovery(svg, [{"type": "circle", "cx": 50, "cy": 50, "rx": 20, "ry": 20}], 2.0, 2.0, -20.0, -20.0)
    assert rec == 1.0
