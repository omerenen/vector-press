import numpy as np

from vectorizer.pipeline.boundary import assemble_regions, build_graph, label_regions


def _check_areas(lbl):
    R, rl = label_regions(lbl.astype(np.int32))
    ch = build_graph(R)
    regs = assemble_regions(ch, rl, R)
    for r in regs:
        assert abs(sum(r.loop_area) - r.area) < 1e-9, (r.rid, r.loop_area, r.area)
        assert r.loop_area[r.outer] > 0
    return R, ch, regs


def test_nested_and_touching_regions_area_exact():
    lbl = np.zeros((10, 10), int)
    lbl[2:7, 2:7] = 1
    lbl[3:6, 3:6] = 2
    lbl[0, 0] = 1
    lbl[7, 7] = 1        # touches the ring diagonally (saddle)
    lbl[9, 9] = -1
    _check_areas(lbl)


def test_checkerboard_saddles():
    lbl = (np.indices((8, 8)).sum(0) % 2)
    R, ch, regs = _check_areas(lbl)
    assert len(regs) == 64      # 4-connectivity: every pixel is its own region


def test_random_labels_area_exact():
    rng = np.random.default_rng(1)
    for _ in range(5):
        lbl = rng.integers(-1, 4, (16, 12))
        _check_areas(lbl)


def test_every_chain_shared_by_exactly_two_sides():
    rng = np.random.default_rng(2)
    lbl = rng.integers(0, 3, (12, 12))
    R, ch, regs = _check_areas(lbl)
    use = {}
    for r in regs:
        for loop in r.loops:
            for cid, rev in loop:
                use.setdefault(cid, []).append(rev)
    for cid, c in enumerate(ch):
        sides = [s for s in (c.left, c.right) if s >= 0]
        assert len(use.get(cid, [])) == len(sides)
