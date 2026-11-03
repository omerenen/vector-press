# HANDOFF — stream C (classifier / presets / fallback / regressions / fast vs max)

Branch `phase2/C` (from `phase2-base`). Details and every experiment: EXPERIMENTS.md "Phase 2 — stream C",
alternatives: RESEARCH.md "Phase 2 — stream C".

## What changed (all behind option keys; DEFAULTS still reproduce phase2-base unless noted)
| key (vectorizer/api.py DEFAULTS) | old behaviour | recommended | what it does |
|---|---|---|---|
| `fringe` | None | `"auto"` | edge-fringe clean-up after quantisation (new `vectorizer/pipeline/fringe.py`, halo model); "auto" = only icon/logo/flat_illustration presets (it erases strokes in line art) |
| `fringe_near` | 0.09 | 0.09 | OKLab distance for "overshoot band of its neighbour" |
| `photo_route` | "features" | `"try"` | classifier "photo" → gradient preset; VTracer is reached only through the measured region explosion |
| `noise_density` | 0.1 | `0.35` | fallback "pure noise" branch (coarse VTracer) threshold, regions/px counted before clean-up |
| `graphic_override` | False | `True` | strong-edge graphic art (classifier flat ≥ 0.2, ink_edge ≥ 0.4) keeps the region engine; only noise bails |
| `fit_profile` | "default" | `"tight"` | fit_tol 0.3 / line_tol 0.33 at 1× for graph-engine content presets (not cut, not 2× max) |
| `max_presets` | None (= icon, logo, flat_illustration, line_art, diagram) | `["line_art","diagram"]` with tight | presets that mode="max" processes at 2× |
| `photo_fallback` | (implicit: auto only) | None | force the region-explosion fallback on/off for explicit presets (evaluation tool) |
Config with the recommended values: `eval/configs/C_final.yaml` (dev) / `C_tfinal.yaml` (tdev, LPIPS + print/cut).
`eval/run.py`: per-item `st_preset`, `st_fallback`, `st_engine`, `st_n_regions`, `st_upscale` are now stored.

## Numbers
(see bottom section "Full runs" — filled in from the full runs)

## Decisions
- **Classifier (item 5)**: measured cost of the classifier on dev = 0.0012 composite vs the per-image oracle over the four
  preset families; true-category presets = auto ±0.003. "flat_illustration never detected" / "diagram → line_art" cost
  nothing (shared presets) → no new classifier, no learned model. The real target-set problem is the *engine* choice
  (region engine vs VTracer): the density fallback is a cost proxy, not a quality predictor, and its noise branch
  destroyed halftone / stencil AI art → `noise_density`, `graphic_override`, `photo_route="try"`.
- **Regressions (item 8)**: test_0013 = JPEG/colour-shift edge fringes (two overshoot bands per edge, 156 regions for
  a 2-colour icon) → `fringe="auto"`; test_0048 = JPEG flat art classified photo → `photo_route="try"`. Both failure
  classes found and validated on dev (dev_0028 +0.061, dev_0005 +0.039, dev_0075 +0.017, dev_0023 +0.009;
  dev_0029 +0.103, dev_0069 +0.102). Disclosure: diagnosis started from the two test items.
- **Fast vs max (item 9)**: the max-mode gain on icon/logo/line art is the halved fit tolerance; 1× tight fitting
  reproduces it (dev_small: icon +0.006, logo +0.004, line_art +0.010, diagram +0.008, gradient +0.003) for ~⅓ of the
  byte increase and without the primitive loss (max: −0.21). Move it into fast mode (`fit_profile="tight"`).
  2× upscaling stays max-only and only for line_art/diagram (diagram +0.015 over tight: 1-px box outlines); dropped
  for icon/logo/flat_illustration (no gain over tight, +93…+193 % bytes).

## Files touched
Own scope: `vectorizer/api.py`, new `vectorizer/pipeline/fringe.py`, new `tests/test_fringe.py`,
`tests/test_stream_c.py`. Outside scope: `eval/run.py` (stats fields only), `eval/configs/C_*.yaml` (new),
EXPERIMENTS.md / RESEARCH.md (own sections). `vectorizer/presets.py` and `classify.py` unchanged (nothing to gain).
No new dependencies, no new licences.

## Interactions
- Stream B (quantize / segmentation): `fringe` runs after `quantize()` and imports `merge_small_regions` from
  quantize.py (read-only). If B reduces the region explosion on textured art, `graphic_override` / the fallback
  thresholds should be re-measured: B's segmentation may make the region engine win on the painterly items too
  (then `max_region_density` can rise). The pre-clean bail-out count is what `noise_density` compares to — if B
  changes what `qinfo["n_regions"]` means at bail time, re-check the 0.35 threshold (noise 0.6, art ≤ 0.22).
- Stream A (fit.py / boundary.py): `fit_profile="tight"` only sets `fit_tol` / `line_tol`; if A changes the meaning of
  these tolerances, re-tune TIGHT_FIT. More nodes with tight fitting (+25…+100 % on flat art) — A's node reduction work
  offsets this.

## Open problems
- Engine choice is still the biggest tdev lever: per-image oracle region-vs-VTracer on tdev_small is +0.046 over base;
  the two-threshold rule recovers most of it but misses tdev_0000 (flat 0.187). A learned selector needs full-tdev
  region-engine runs (expensive: print/cut metrics on 1–5 MB SVGs take > 30 min per item).
- Selective 2× (thin structures only) / per-chain adaptive tolerance: not prototyped (needs fit.py / quantize hooks).
- Fringe clean-up on line art (JPEG strokes split into core + edge colour) needs a stroke-aware variant.
