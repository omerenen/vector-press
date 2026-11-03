"""Named presets and the mapping from detected image type to preset.

Preset values were chosen from dev-split ablations (EXPERIMENTS.md exp_005, exp_007, exp_009).
User options always override preset values.
"""
from __future__ import annotations

FLAT = dict(merge_frac=1.0, mix_suppress=False, gradients=True)
LINES = dict(merge_frac=1.0, mix_suppress=True, gradients=False)
GRADIENT = dict(merge_frac=0.6, mix_suppress=False, gradients=True)
# photos: plain VTracer with the dev-grid-tuned photo parameters beats our region engine on fidelity
# (exp_014: composite 0.758 vs 0.722) and is ~15x faster; the graph engine stays available as
# "photo_posterize" (3x smaller files, flatter look).
PHOTO = dict(engine="vtracer_raw", max_side=1024,
             vtracer_params=dict(filter_speckle=2, color_precision=8, layer_difference=8, corner_threshold=30,
                                 length_threshold=4.0))
PHOTO_POSTERIZE = dict(merge_frac=0.6, mix_suppress=False, gradients=True, max_side=640)

PRESETS = {
    "logo": FLAT,
    "icon": FLAT,
    "illustration": GRADIENT,
    "flat_illustration": FLAT,
    "line_art": LINES,
    "diagram": LINES,
    "gradient": GRADIENT,
    "photo_posterize": PHOTO_POSTERIZE,
    "photo": PHOTO,
}

TYPE_TO_PRESET = {"icon": "icon", "logo": "logo", "flat_illustration": "logo", "line_art": "line_art",
                  "diagram": "diagram", "gradient": "gradient", "photo": "photo"}


def preset_options(name: str) -> dict:
    if name not in PRESETS:
        raise ValueError(f"unknown preset {name!r}; choose from auto, {', '.join(sorted(PRESETS))}")
    return dict(PRESETS[name])
