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
| `geom_repair` | True | False | every emitted ring simple: pinch loops split, self-crossing / zero-area loops re-emitted as polylines (crossing chains only), leftovers as `make_valid` parts on the 0.01 grid; closing segment written in absolute coordinates, loops never end with an arc |
| `corner_lines` | False | – | line-pair (blur-robust) corner detector — measured, **rejected** (corner recall −0.10) |
| `corner_blur_zone` | 2.0 | – | parameter of `corner_lines` |

Other behaviour changes (not flagged, numerically equivalent or strictly better): `ellipse_dist` is now the exact
point–ellipse distance (vectorised Newton; was 720-point sampling), `robust_err` is partition-based (same value as
`np.percentile`), the rounded-rect radius grid is vectorised (same values), `choose_closed_primitive()` is the refactored
chain-level model selection (same decisions with `rect_refine=False`, `blur_sharp_ratio=0`).

## Numbers vs phase2-base (full runs, `printcut: true`)
_(see section below, filled from eval/reports/A_final vs A_base)_

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
- Repaired loops use polylines (sub-pixel samples, DP 0.25 px): a few more nodes locally.
