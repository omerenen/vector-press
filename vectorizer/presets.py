"""Named presets and the mapping from detected image type to preset.

Preset values were chosen from dev-split ablations (EXPERIMENTS.md exp_005, exp_007, exp_009).
User options always override preset values.
"""
from __future__ import annotations

FLAT = dict(merge_frac=1.0, mix_suppress=False, gradients=True)
LINES = dict(merge_frac=1.0, mix_suppress=True, gradients=False)
GRADIENT = dict(merge_frac=0.6, mix_suppress=False, gradients=True)
PHOTO = dict(merge_frac=0.6, mix_suppress=False, gradients=True)

PRESETS = {
    "logo": FLAT,
    "icon": FLAT,
    "illustration": GRADIENT,
    "flat_illustration": FLAT,
    "line_art": LINES,
    "diagram": LINES,
    "gradient": GRADIENT,
    "photo_posterize": PHOTO,
    "photo": PHOTO,
}

TYPE_TO_PRESET = {"icon": "icon", "logo": "logo", "flat_illustration": "logo", "line_art": "line_art",
                  "diagram": "diagram", "gradient": "gradient", "photo": "photo_posterize"}


def preset_options(name: str) -> dict:
    if name not in PRESETS:
        raise ValueError(f"unknown preset {name!r}; choose from auto, {', '.join(sorted(PRESETS))}")
    return dict(PRESETS[name])
