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
Base = `phase2-base` code (`B_base_*`), final = branch defaults at commit d7f1949 (`B_final_*`; `vectorizer/` unchanged
since), full splits, `--workers 2` under the shared lock (timings not valid).

### tdev, t_final settings (preset auto, LPIPS + print/cut metrics), 53 images
| cat (n) | composite base → final | SSIM | ΔE | edge-F | LPIPS | paths (med) | gz KB (med) |
|---|---|---|---|---|---|---|---|
| **ALL (53)** | 0.702 → **0.724** | 0.796 → 0.818 | 3.35 → 3.07 | 0.865 → 0.882 | 0.185 → 0.169 | 11 184 → 13 900 | 1 757 → 2 157 |
| cutfile (9) | 0.630 → 0.658 | 0.707 → 0.746 | 4.10 → 3.73 | 0.826 → 0.849 | 0.290 → 0.271 | 7 665 → 22 483 | 2 191 → 3 204 |
| logo (17) | 0.734 → 0.755 | 0.795 → 0.817 | 3.02 → 2.85 | 0.882 → 0.906 | 0.177 → 0.165 | 1 618 → 10 024 | 663 → 1 147 |
| poster (11) | 0.670 → 0.690 | 0.761 → 0.777 | 3.72 → 3.42 | 0.834 → 0.853 | 0.224 → 0.207 | 13 900 → 15 571 | 1 990 → 2 649 |
| sticker (3) | 0.763 → 0.794 | 0.907 → 0.919 | 1.87 → 1.70 | 0.880 → 0.887 | 0.105 → 0.090 | 13 766 → 13 766 | 2 157 → 2 157 |
| tshirt (1) | 0.760 → 0.760 | = | = | = | = | = | = |
| vector_flat (12) | 0.721 → 0.740 | 0.860 → 0.880 | 3.43 → 3.06 | 0.901 → 0.905 | 0.104 → 0.087 | 11 222 → **3 334** | 1 324 → **393** |
VTracer default on the same set: 0.680 (final is +0.044). Per image: 22 better, 3 worse (> 0.002): 0007 −0.006,
0013 −0.008, 0040 −0.034 (art-deco skyline: region output 225 KB vs VTracer 1.7 MB). Two mechanisms: (a) clean,
compact region output instead of the VTracer fallback (0051 0.734→0.829 at 40 KB instead of 1 064 KB; 0012
0.575→0.712 at 426 KB instead of 1.3 MB; 0001 0.612→0.706; 0037 0.701→0.722 at 168 KB instead of 2 MB); (b) images on
which the phase-1 region engine produced bad output (thin features lost, 0000/0017/0020/0024/0039/0045/0048/0049,
+0.08…+0.12 each) now go to the photo engine with the normal (not "pure noise") parameters → this raises the median
path count / bytes. VTracer-like outputs (> 3 000 paths): 37 → 35 of 53.
Print/cut metrics (t_final, medians): distinct paints 9 676 → 10 879, tiny islands 13 225 → 15 303, thin features
6 184 → 6 989 (more fallbacks), self-intersections 121 → 110, overlap 3.10 → 2.96; vector_flat: paints 10 022 → 8 195,
tiny islands 14 750 → 11 941, overlap 2.57 → 1.67, nodes 105 k → 49 k.

### dev (phase 1), final settings, 130 images
| cat | composite base → final | SSIM | PSNR | ΔE | edge-F | gz B (med) |
|---|---|---|---|---|---|---|
| **ALL** | 0.9044 → **0.9050** | 0.9689 → 0.9691 | 32.21 → 32.28 | 1.183 → 1.180 | 0.9557 → 0.9544 | 2 254 → 2 220 |
| diagram | 0.8942 → 0.8941 | 0.9784 → 0.9782 | 29.12 → 29.25 | 1.139 → 1.142 | 0.9788 → 0.9789 | 2 905 → 2 817 |
| flat_illustration | 0.9526 → 0.9530 | 0.9891 → 0.9895 | 36.37 → 36.42 | 0.302 → 0.281 | 0.9850 → 0.9847 | 1 876 → 1 884 |
| gradient | 0.8813 → 0.8833 | 0.9685 → 0.9692 | 33.44 → 33.59 | 1.584 → 1.573 | 0.8419 → 0.8386 | 3 775 → 3 458 |
| icon | 0.9495 → 0.9508 | 0.9912 → 0.9914 | 34.84 → 34.93 | 0.836 → 0.833 | 0.9980 → 0.9977 | 626 → 626 |
| line_art | 0.8991 → 0.9001 | 0.9781 → 0.9783 | 28.88 → 28.89 | 1.579 → 1.579 | 0.9790 → 0.9789 | 2 148 → 2 068 |
| logo | 0.9231 → 0.9226 | 0.9787 → 0.9787 | 32.93 → 32.92 | 0.840 → 0.854 | 0.9863 → 0.9820 | 1 196 → 1 196 |
| photo | 0.7575 → 0.7575 | identical | | | | |
All within the phase-2 tolerances (worst: logo composite −0.0005, edge-F −0.0043, ΔE +0.015; gradient edge-F −0.0033).
Valid SVG 130/130, gap_px 0 on all items, edge deviation 0.2203 → 0.2191 px; corner recall 0.822 → 0.804 (not in the
tolerance list; MS merges a few small corner regions – stream A may want to look).

### tdev, t_cut settings (cut preset)
Cut preset (never falls back; background dropped, ≤ 8 paints, 0.5 mm minimum feature at 100 mm width). Fidelity
numbers are low for both because the dropped background is compared with the input. Means except paths/gz/nodes (median).
| cat | composite | ΔE | edge-F | LPIPS | gz KB | tiny islands | thin features | thin area mm² | self-x | nodes |
|---|---|---|---|---|---|---|---|---|---|---|
| **ALL (53)** | 0.326 → **0.331** | 25.4 → 25.9 | 0.473 → 0.473 | 0.558 → 0.546 | 81.7 → **68.1** | 2.25 → **1.42** | 48.2 → **40.2** | 81.7 → **69.1** | 42.3 → **37.3** | 8 223 → **6 962** |
| cutfile | 0.233 → 0.245 | 26.3 → 26.7 | 0.338 → 0.339 | 0.696 → 0.679 | 100 → 85 | 1.67 → 0.78 | 43.1 → 30.7 | 84.0 → 67.9 | 46.9 → 37.2 | 10 319 → 8 166 |
| logo | 0.368 → 0.369 | 30.1 → 31.1 | 0.568 → 0.566 | 0.539 → 0.533 | 58 → 60 | 2.18 → 1.41 | 70.8 → 59.8 | 85.8 → 70.9 | 38.9 → 34.2 | 5 844 → 6 008 |
| poster | 0.284 → 0.282 | 21.2 → 22.5 | 0.391 → 0.383 | 0.617 → 0.605 | 88 → 80 | 2.27 → 2.00 | 22.0 → 21.8 | 73.0 → 63.5 | 40.9 → 37.7 | 9 059 → 8 247 |
| sticker | 0.475 → 0.489 | 11.9 → 11.3 | 0.590 → 0.590 | 0.382 → 0.375 | 55 → 44 | 2.00 → 1.33 | 31.7 → 25.3 | 51.0 → 44.3 | 28.7 → 28.7 | 5 416 → 4 235 |
| tshirt | 0.530 → 0.533 | 6.6 → 7.2 | 0.468 → 0.451 | 0.440 → 0.423 | 82 → 68 | 1 → 2 | 28 → 20 | 78.1 → 55.2 | 34 → 37 | 8 756 → 6 949 |
| vector_flat | 0.319 → 0.328 | 26.8 → 26.0 | 0.485 → 0.498 | 0.482 → 0.466 | 91 → 91 | 2.92 → 1.33 | 49.7 → 41.8 | 89.9 → 79.8 | 49.3 → 43.3 | 9 220 → 8 937 |
Every cut-readiness metric improves (fewer tiny islands / thin features / self-intersections, −17 % bytes, −15 %
nodes); ΔE +0.5 (paints chosen by area-weighted k-means over MS region colours instead of the palette's top colours).
Print preset (tdev_small, 18, no fallback): 368 KB vs 1.25 MB, 1 176 vs 7 485 paints, 3 272 vs 8 262 tiny islands,
overlap 0.10 vs 3.05 compared with the lead's t_print run; composite 0.654 vs 0.671 (that run still contained
VTracer outputs); self-intersections 258 vs 78 (fit stage on long complex borders, stream A).


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
