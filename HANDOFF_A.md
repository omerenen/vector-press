# HANDOFF — stream A (primitive fitting, corners, geometry validity)

Branch `phase2/A` (from `phase2-base`). Every experiment, the failure tables and the alternatives: EXPERIMENTS.md and
RESEARCH.md, sections "Phase 2 — stream A".

## What changed
New behaviour is ON by default; every part has a flag in `vectorizer/api.py` DEFAULTS (new keys):

| key | default | old behaviour | what it does |
|---|---|---|---|
| `region_prims` | True | False | primitives (circle/ellipse/rect/rounded rect/**polygon**) fitted to a region's whole outer loop even when junctions split it into several chains; the loop's chains are replaced by the exact pieces of the primitive outline, junctions projected onto it and moved for all incident chains (shared borders stay watertight); region emitted as `<rect>/<circle>/<ellipse>` or as a polygon subpath without collinear junction vertices. Rejected if it would make a neighbour outline self-cross in a way the repair cannot fix |
| `prim_polygons` | True | – | straight-edged polygon/star model (corner detection at 25°, collinear merge, greedy vertex removal = MDL-like model order) |
| `poly_corner_angle` | 25.0 | – | permissive corner angle for the polygon model |
| `region_prim_min_len` | 24 | – | minimum loop length (samples) |
| `region_prim_max_shift` | 1.5 | – | max junction displacement onto a primitive (px) |
| `rect_refine` | True | False | robust soft-L1 IRLS Gauss–Newton refinement of rect / rounded-rect fits (chain- and region-level) |
| `blur_sharp_ratio` | 3.8 | 0 (off) | sharp vs rounded corners under blur: fitted radius < 3.8 × measured edge spread σ of the same rect → sharp model |
| `geom_repair` | True | False | every emitted ring simple: pinch loops split, collapsed zero-area tiny loops not emitted, self-crossing loops re-fitted (crossing chains only: tighter Bézier, then polylines), leftovers as `make_valid` parts on the 0.01 grid; closing segment written in absolute coordinates, loops never end with an arc; primitives are not snapped if that would create an unrepairable crossing |
| `repair_refit` | True | – | first repair level: tighter Bézier refit (fit_tol/2, no smoothing) before polylines |
| `corner_lines` | False | – | line-pair (blur-robust) corner detector — measured, **rejected** (corner recall −0.10) |
| `corner_blur_zone` | 2.0 | – | parameter of `corner_lines` |

Other behaviour changes (not flagged, numerically equivalent or strictly better): `ellipse_dist` is now the exact
point–ellipse distance (vectorised Newton; was 720-point sampling), `robust_err` is partition-based (same value as
`np.percentile`), the rounded-rect radius grid is vectorised (same values), `choose_closed_primitive()` is the refactored
chain-level model selection (same decisions with `rect_refine=False`, `blur_sharp_ratio=0`).

## Numbers vs phase2-base (full runs, `printcut: true`; `A_base` = clean `git archive phase2-base`, `A_final` = this branch)
Reports: `eval/reports/A_base`, `eval/reports/A_final` (`python -m eval.compare A_base A_final --split dev|tdev|proc2`).

**dev (130)** — every category within the no-regression tolerances:
| cat | composite | SSIM | PSNR | ΔE | edge_f | edge_dev | gap | corner rec | prim | nodes | self-x |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 0.907 (+0.002) | 0.970 (+0.001) | +0.38 dB | −0.016 | +0.001 | −0.007 | 0 | 0.856 (+0.034) | **0.844 (+0.378)** | −0 % | **0.53 (−2.47)** |
| icon | +0.001 | +0.000 | +0.29 | −0.005 | +0.000 | −0.001 | 0 | | | −3 % | 0 (−0.85) |
| logo | +0.001 | +0.001 | +0.47 | −0.014 | −0.000 | −0.006 | 0 | | | −2 % | 0.05 (−1.70)¹ |
| flat_illustration | +0.005 | +0.001 | +1.09 | −0.024 | +0.001 | −0.015 | 0 | 0.958 (+0.184) | 0.917 (+0.500) | −3 % | 0 (−1.00) |
| line_art | +0.002 | +0.001 | +0.30 | −0.019 | +0.000 | −0.004 | 0 | | | −2 % | 0 (−6.75) |
| diagram | +0.004 | +0.002 | +0.32 | −0.044 | +0.002 | −0.015 | 0 | 0.868 (−0.004) | 0.822 (+0.341) | −5 % | 0 (−1.90) |
| gradient | +0.001 | +0.000 | +0.00 | −0.001 | +0.004 | −0.000 | 0 | 0.642 (0) | | −3 % | 0.20 (−3.85)¹ |
| photo | 0 | 0 | 0 | 0 | 0 | | | | | 0 | 6.4 (0)¹ |
¹ only in images that go to the VTracer engine (photo class / fallback). Pooled dev primitives 58/122 → 103/122 (rect
36→58/73, roundrect 18→38/42, triangle 2→3, polygon 1→2, star 0→1, ellipse 1/1). Official corner_err 0.987 → 0.948
(flat 0.70 → 0.53); see the metric note below.

**tdev (53, primary score)**: composite 0.702 (+0.000), SSIM +0.000, PSNR +0.015, ΔE −0.001, edge_f ±0, nodes −0 %,
gz +0 %, tiny islands −2.4/image, self-intersections 121 → 56/image. 39/53 outputs are byte-identical (VTracer fallback);
on the 14 graph-engine outputs self-intersections **3460 → 0**.

**proc2 (60, held-out generator, run once)**: composite 0.887 (+0.002), PSNR +0.18, ΔE −0.010, edge_dev −0.009, gap 0,
corner recall +0.079, prim recovery pooled **0.293 → 0.643** (per-image mean 0.305 → 0.585), self-intersections 18.7 → 0,
nodes −1 %, gz −1 %; every category within tolerance. One image (proc2_0012) gets +4 000 nodes from an unrepairable crossing
emitted as flattened valid parts (thinned afterwards: 5 304 → 3 675; see open problems).

**Primitive target**: dev recovery 0.844 pooled (target ≥ 0.75 ✓), confirmed on proc2 (0.29 → 0.64; proc2 scenes are
busier: remaining failures there are mostly segmentation / occlusion by thin strokes).
**Corner target**: not reachable as defined (metric floor 0.44–1.15 px, see below); recall +0.034 dev / +0.079 proc2,
official corner_err −0.04 / −0.10, peak-relative error 0.26 px on dev_small.

## Files touched
In scope: `vectorizer/pipeline/fit.py`, `vectorizer/pipeline/boundary.py` (Chain gets `samples`, `snapped`),
`vectorizer/pipeline/assemble.py` (region primitives, validity pass, polygon/ring emission), new
`vectorizer/pipeline/primfit.py`, new `vectorizer/pipeline/validity.py`, new `vectorizer/pipeline/svgarc.py`,
new `tests/test_primfit.py`.
Outside scope (small): `vectorizer/api.py` (new DEFAULTS keys only), `vectorizer/pipeline/svgout.py`
(`loop_d(..., exact_close)` / `geom_to_tokens(..., close)`: optional exact closing, default unchanged),
`eval/configs/A_base.yaml`, `eval/configs/A_final.yaml`, `eval/reports/A_*` (run summaries), EXPERIMENTS.md /
RESEARCH.md (own sections). No metric code changed.

## Metric issues found (proposals, not applied)
1. **corner_err measures the distance to the nominal vertex, not to the GT's own Harris peak.** The GT render evaluated
   against itself gives corner_err 0.59 px (flat_illustration), 0.44 (gradient), **1.15 (diagram**: nominal vertex = stroke
   centre line, visible corners are sw/2·√2 away). The ≤ 0.5 px target is below the metric's floor. Proposal (same for all
   methods): in `corner_metrics`, `err = |argmax(out window) − argmax(GT window)|` (both within the same disc). On
   dev_small the base output then has 0.27 px instead of 0.83 (`/tmp/claude-0/A/corner_eval.py` implements both).
2. **printcut `self_intersections` counts float noise at the closing point**: relative path data (and arcs, whose end point
   the flattener recomputes from the centre parameterisation) end 1e-13 px from the start, GEOS reports a self-intersection
   at the start vertex. 50 of 68 "self-intersections" of the base graph output on dev_small were this. Proposal: in
   `_flatten_subpaths` drop the last point of a `Z`-closed subpath when it is within 1e-6 of the first (all methods).
   Our output no longer triggers it (absolute closing command), so the comparison with VTracer is not affected by it any more.

## Interactions with the other streams
- **B (quantize.py / gradients.py)**: region primitives run on whatever region loops segmentation produces. Fragmented
  thin strokes (JPEG) and shapes on top of other shapes are exactly what `region_prims` now absorbs, so a cleaner
  segmentation will not conflict, it only reduces the work. The remaining dev primitive failures (~10 of 122) are
  segmentation failures (stroke merged into the fill / background, region boundary > 1 px from every GT edge) → B.
  Cost of `region_prims` grows with the number of multi-chain loops (1.4× pipeline CPU on dev images; texture-heavy
  target images with thousands of regions could cost more: loops with hull solidity < 0.9 skip rect/ellipse, but the
  polygon model still runs for loops with ≤ 8 corners or a valid first polygon). If B's segmentation produces many
  regions, consider `region_prims=False` for the photo_posterize preset (stream C).
- **C (classify / presets / api)**: only new DEFAULTS keys in `api.py`; presets can override them. Cut preset
  (`cutout=True`) benefits most from `geom_repair` (self-intersections 0 on the checked dev images, nodes −8 %).
  `geom_repair` must stay on for cut/print intents.

## Open problems
- ~10 % of dev primitives are lost to segmentation (B) and ~1 small true radius (2.5 px) is now emitted sharp.
- Corner recall on diagrams is limited by obtuse corners where a stroke meets a connector of the same colour (curve
  instead of corner); the line-pair detector found them but also produced false corners (rejected). A curvature-scale
  check of the arms or a learned corner classifier would be the next step.
- Lattice pinch points are split into two rings that touch at one point (valid rings, still a single touching point).
- Repaired loops use polylines (sub-pixel samples, DP 0.25 px): a few more nodes locally. A loop whose ordinary chain still
  crosses an exact primitive edge after the raw-polyline level is emitted as its `make_valid` parts with flattened curves
  (rare: 1 loop in proc2_0012, +2 500 nodes even after DP thinning). Better: un-snap that primitive (needs stored
  pre-snap geometry incl. moved junctions) or a local-window repair.
- Cost: all new options ≈1.4× pipeline CPU on dev images (diagrams/line art up to 2×); timing not measured (shared CPU).
