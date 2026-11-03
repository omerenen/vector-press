# HANDOFF — stream B (segmentation of textured AI art, gradients, quantize speed)

Branch `phase2/B` (from `phase2-base`). Details and every experiment: EXPERIMENTS.md `## Phase 2 — stream B` (B-0 … B-7),
alternatives and decisions: RESEARCH.md `## Phase 2 — stream B`.

## What changed (flags / defaults, all in `vectorizer/api.py` DEFAULTS)
| key | default | meaning |
|---|---|---|
| `segment` | **`"ms"`** (was the only path: `"palette"`) | Mumford–Shah region merging (colour SSE vs λ·boundary length) on the palette over-segmentation; `"palette"` = phase-1 stage, unchanged |
| `seg_lambda` | 0.01 | boundary price (OKLab² per px of boundary, at 1024 px; scaled by √(HW)/1024) |
| `seg_premerge` | **True** | phase-1 speckle merge + sliver removal before MS (keeps phase-1 behaviour on clean flat art; needed for AA strokes) |
| `seg_pal_snap` | 0.02 | regions within this OKLab distance of their majority palette colour share that palette label (one paint) |
| `seg_raw_bail` | 0.06 | preset auto: > 0.06 raw palette fragments per px → photo engine (phase 1 bailed at 0.032, which sent clean cartoons to VTracer) |
| `seg_budget` | 0.004 | no-fallback runs (print/cut/explicit preset): λ doubles until ≤ 0.004 regions/px (bounds time/size on heavy texture) |
| `seg_model` | "const" | `"affine"` = piecewise-affine MS + per-region `linearGradient` fills (opt-in, see B-5) |
| `seg_grad_cost` | 60 | affine: gradient fill if it removes > 60·λ squared error |
| `seg_init` | "palette" | `"fz"` = Felzenszwalb over-segmentation instead of palette components (opt-in, not better on average) |
| `seg_snap` | 0.0 | optional extra colour snapping of region colours (fewer paints) |
Cut files (`cutout=True`): region colours are reduced to `max_colors` paints by area-weighted k-means after MS
(`segment.reduce_paints`), then `cut.enforce_min_feature` as before.
Routing (preset auto) with `segment="ms"`: photo engine if the phase-1 post-clean-up region count > `max_region_density`
(0.008, unchanged semantics) or raw fragments > `seg_raw_bail`; a new `pure_noise` flag in the quantize info decides the
"pure noise" VTracer parameters (the raw-count bail-out used to select them for halftone art, tdev_0000).

Speed refactors with identical output (palette engine): symmetric sigma filter, 2-plane direction stats, dense
histogram, one-sort label medians, uint8 OKLab LUT, low-alpha pass skipped on opaque input.

## Numbers vs phase2-base (full runs; see tables below — filled from `eval/runs/B_final_*` vs `B_base_*`)
FULL_RESULTS_PLACEHOLDER

## Files touched
- Own scope: `vectorizer/pipeline/quantize.py`, `vectorizer/pipeline/preprocess.py`, `vectorizer/pipeline/gradients.py`
  (`affine_fills`, `apply_gradients_ms`), new `vectorizer/pipeline/segment.py`, new `tests/test_segment.py`.
- Outside scope: `vectorizer/api.py` (DEFAULTS keys above, quantize call arguments, `apply_gradients_ms` for
  segment="ms", `pure_noise` flag in the fallback branch), `vectorizer/pipeline/color.py` (uint8 LUT in
  `rgb8_to_oklab`, identical values), EXPERIMENTS.md / RESEARCH.md (own sections), this file.
- No new dependencies (numpy / scipy / scikit-image only; Felzenszwalb from scikit-image, BSD-3).

## Interactions
- Stream A (fit.py / boundary.py): label maps are now MS regions. On flat art they equal the phase-1 maps except where
  MS merges further; on textured art there are far fewer, larger regions with smoother borders. With `seg_pal_snap`
  most regions share palette labels; unsnapped regions get their own label (palette can have hundreds/thousands of
  entries → fit/assemble must not assume ≤64 labels; `n_paths` grows with distinct paints). Gradient regions from
  `affine_fills` are in `label_fill` and skipped by the sub-pixel step like phase-1 gradients.
- Stream C (classifier / presets / fallback): the auto fallback now sees (a) phase-1 post-clean-up count, (b) raw
  fragment count (`seg_raw_bail`), both computed inside `quantize` (`segment="ms"`); `max_region_density` keeps its
  meaning. The thresholds were chosen on tdev_small + dev_small only (few decisive images: 0003, 0012, 0048, 0051,
  dev_0123) → please re-check on the full set together with your classifier/fallback changes. Print/cut intents never
  fall back and are now bounded by `seg_budget`. Photos classified as photo still go straight to VTracer (unchanged).

## Open problems
- Heavy texture (fur, painterly brushwork, halftones, charcoal hair): the composite still prefers the VTracer stack
  (e.g. tdev_0003: MS region output 0.566 at 536 KB vs VTracer 0.720 at 4.5 MB). Clean region output exists (print/cut
  intents) but loses on fidelity metrics; a texture layer (detail strokes / halftone patterns) would be needed.
- Soft (blurred) boundaries in gradient art (dev_0068 class) are still drawn hard → edge-F; would need blur filters or
  mesh gradients (not supported by resvg).
- `seg_model="affine"` helps gradient edge-F (+0.012 on dev gradient) but costs ΔE on logos and ~0.3 s/MP → opt-in.
- Speed: quantize −48 % on the palette path; the ms default adds ~12 % on flat art; ≤ 1.2 s per 1024 px also needs
  fit-stage time (stream A) — real timing at integration.
