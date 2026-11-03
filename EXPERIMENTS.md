# EXPERIMENTS

All numbers: `dev` split (130 images: 20 per category, 10 photos) unless stated. Reproduce any row with
`python -m eval.run --config eval/configs/<exp>.yaml --split dev`. CPU: Intel Xeon @ 2.10 GHz (4 vCPU),
eval uses 4 worker processes (timings per image measured inside a worker, so they include contention).

## E-metrics: metric definitions & composite (decided before any tuning)
Reference = clean ground-truth render (`gt.png`) for synthetic items (the vectoriser should *undo*
degradations), the clean photo for photos. All raster metrics on RGB composited over white.
- `ssim` (7×7, RGB), `psnr`, `msssim` (4 scales, luma), `gmsd` (gradient magnitude similarity
  deviation, lower=better; weight-free perceptual substitute for LPIPS, whose backbone weights are not downloadable here),
  `de_mean`/`de_p95` (CIEDE2000), `edge_f` (Canny F1 with 1.5 px tolerance).
- `edge_dev` (px): renders GT SVG and output at 4× (≤2048 px); mismatching pixels (Lab Δ>15) within 3 px of a GT
  boundary divided by GT boundary length → mean boundary displacement. Measures wobble / rounded corners / shifts.
- `gap_px`: pixels at 4× inside the opaque GT area (eroded 6 px) that the output leaves not fully covered (α<250).
- `corner_recall` / `corner_err`: for each true sharp vertex (procedural scenes, unoccluded shapes) is there a colour-Harris
  corner in the output within 1.5 px with ≥50 % of the GT response; mean position error of found corners.
- `prim_recovery`: share of unoccluded GT primitives (circle/ellipse/rect/roundrect/polygon/star/triangle) represented by a
  matching native element or an exact straight-edge polygon (centre/vertex error ≤1.5 px, radius error ≤max(1.5 px, 3 %)).
- compactness: `n_paths` (drawable elements), `n_nodes` (segments), `bytes`, `gz_bytes`; `time` per image.
- **composite** = 0.75·fid + 0.15·geo + 0.10·compact (items without GT SVG: 0.9·fid + 0.1·compact) with
  fid = 0.25·SSIM + 0.15·min(PSNR,40)/40 + 0.20·(1−min(ΔE,20)/20) + 0.20·edgeF + 0.20·(1−min(GMSD,0.35)/0.35),
  geo = 1−min(edge_dev,3)/3, compact = 1−clip(log10(gz_bytes/1000)/3). Fidelity dominates; zoom-level geometric
  accuracy is what distinguishes a good vector from a good raster; size matters but is secondary. Never optimised alone.

## exp_000_baseline — plain VTracer defaults (2026-11-03)
Hypothesis: reference point. Config: `eval/configs/exp_000_baseline.yaml`.

| cat | composite | ssim | psnr | gmsd | ΔE | edgeF | edge_dev | corner_rec | prim | paths | gz | t_med |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 0.8007 | 0.932 | 26.1 | 0.100 | 2.52 | 0.925 | 0.637 | 0.528 | 0.00 | 152 | 33241 | 0.04 |
| icon | 0.8238 | 0.955 | 27.5 | 0.101 | 1.65 | 0.931 | 0.646 | | | 86 | 17798 | |
| logo | 0.8241 | 0.944 | 26.8 | 0.109 | 1.81 | 0.954 | 0.530 | | | 56 | 15740 | |
| flat_illustration | 0.8584 | 0.959 | 29.1 | 0.080 | 0.86 | 0.966 | 0.463 | 0.546 | 0.00 | 36 | 14914 | |
| line_art | 0.8079 | 0.950 | 23.8 | 0.108 | 2.51 | 0.973 | 0.449 | | | 145 | 29798 | |
| diagram | 0.8019 | 0.950 | 25.3 | 0.106 | 1.89 | 0.959 | 0.628 | 0.522 | 0.00 | 145 | 35585 | |
| gradient | 0.7484 | 0.928 | 25.3 | 0.087 | 5.43 | 0.826 | 1.106 | 0.529 | | 79 | 18395 | |
| photo | 0.6802 | 0.749 | 24.5 | 0.124 | 4.47 | 0.814 | | | | 878 | 167667 | 0.15 |

Visual (sheet_*.png): staircase edges on transparent inputs (alpha keying), AA halos traced as separate rings on
blurred inputs (concentric light rings on the "target" icon), colour drift from `color_precision=6`, wobbly curves.
Gap check is 0 because stacked mode overlaps layers (cutout mode would show seams).

## exp_002_graph_v0 — palette quantization + shared boundary graph (2026-11-03)
Hypothesis: W1/W2 (AA-aware OKLab palette, speckle merge) + W4/W5 (one fit per shared border, corners, line snapping,
Schneider curves) + W3 (closed-chain ellipse/rect primitives) beat VTracer on fidelity and size. Cost: Python time.

| cat | composite | ssim | psnr | gmsd | ΔE | edgeF | edge_dev | gap_px | corner_rec | prim | paths | gz | t_med |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | **0.8785** | 0.958 | 30.9 | 0.062 | 1.37 | 0.930 | 0.261 | 0.12 | 0.675 | 0.042 | 399 | 17076 | 0.81 |
| icon | 0.9294 | 0.987 | 33.4 | 0.049 | 0.89 | 0.993 | 0.173 | 0.05 | | | 51 | 3701 | 0.54 |
| logo | 0.9030 | 0.974 | 31.5 | 0.061 | 0.89 | 0.958 | 0.209 | 0.35 | | | 198 | 11933 | 0.55 |
| flat_illustration | 0.9383 | 0.986 | 35.7 | 0.032 | 0.35 | 0.984 | 0.195 | 0 | 0.528 | 0.083 | 146 | 6229 | 0.48 |
| line_art | 0.8761 | 0.976 | 27.1 | 0.074 | 1.63 | 0.972 | 0.220 | 0 | | | 246 | 8428 | 1.14 |
| diagram | 0.8518 | 0.965 | 27.1 | 0.089 | 1.46 | 0.967 | 0.415 | 0.15 | 0.753 | 0.030 | 401 | 13741 | 1.12 |
| gradient | 0.8488 | 0.951 | 32.6 | 0.051 | 1.94 | 0.760 | 0.355 | 0.15 | 0.508 | | 121 | 9988 | 1.12 |
| photo | 0.7251 | 0.774 | 26.1 | 0.091 | 3.47 | 0.826 | | | | | 2864 | 113947 | 5.33 |

Decision: **keep** as the main engine (+0.078 composite; every category better on SSIM/ΔE/GMSD, edge_dev ÷2.4,
gz size ÷2). Open problems: path count ↑ (seam strokes + more regions), photo time 5.3 s at ≤512 px, small
gap counts, corner recall on procedural shapes not better than baseline, primitive recovery only 4 %.

## exp_003_quant_vtracer — palette quantization feeding VTracer
Hypothesis: maybe the cleaned palette alone fixes most of VTracer's problems (cheap). Result: composite 0.8337
(baseline 0.8007, graph 0.8785); SSIM 0.944, ΔE 1.66, edge_dev 0.364, corner recall 0.75 (best so far).
Decision: keep as `engine="vtracer"` option (fast, 0.41 s median); not default.

## exp_004_graph_v1 — layered emission, round seams, TLS line test (2026-11-03)
Hypothesis: (a) per-depth-level drawing (one fill path per colour per nesting level, seams underneath) cuts element
count without fidelity loss; (b) round seam caps remove the residual 1-px junction leaks; (c) a total-least-squares
straight-line test (corner samples sit off the true vertex, so the chord test rejected straight edges) improves corners.
Result vs exp_002: paths −93 % (399→26), gz −19 %, gap_px 0.12→**0.000**, corner recall 0.675→0.747, prim 0.04→0.14,
but PSNR −0.67 dB. Ablation `abl_004_no_tls` showed the loss came only from the TLS test with tol 0.65 (it straightens
gentle curves); `line_tls=0.45` keeps −10 % bytes and the corner gain for −0.001 composite → **keep with 0.45**.

## exp_005_thin_mix — thin-line rescue, saddle bridging, palette mixture suppression
Hypothesis (from contact sheets): thin AA lines break into dashes (diagonal pixels only touch at corners → 4-connected
specks → merged away); blurred line art produces grey plateaus at stroke crossings that become palette colours.
Ablations (vs exp_005 = all three on):
- `mix_suppress=false`: gradient +0.013, photo +0.018, logo +0.004 but line_art −0.004, diagram −0.004 → **preset option** (line_art/diagram only).
- ridge rescue only (`thin_lines=ridge`): composite +0.002 and **−25 % bytes** vs all-on.
- saddle bridging only: same as all-on → bridging is what inflates bytes (+33 %) without fidelity gain → **off by default**.
- A morphological top-hat ridge detector was also tried: worse on JPEG (ringing rescued as grey specks, dev_0090 PSNR 19.8→18.6) → reverted.
Visual: clean thin-line art (dev_0096) is now continuous (SSIM 0.962→0.982); JPEG thin lines (dev_0097) are still dashed.

## exp_006_prims — primitive model selection + adaptive corner scale
Ellipse vs sharp rect vs rounded rect chosen by error with a small axis-aligned sharp-rect prior; rect fits on raw crack
midpoints (smoothing rounded the corners and produced r≈1.5 on sharp rects); explicit axis-aligned candidate (min-area
rect gave 1.7° spurious rotation on tiny bars); corner arm length ≤ perimeter/16. Composite ±0, corner recall +0.02
(flat_illustration +0.13). Primitive recovery fell to 0.08: diagnosis showed **all degraded images recover 0 %**
(clean ones 83–86 %) because max-error acceptance is vetoed by one noisy pixel and because JPEG creates sliver regions
that split boxes into 10–27 chains → exp_007.

## exp_007_slivers — robust primitive acceptance + sliver removal
(a) primitive error = max(p90, max/2) (a few noisy samples no longer veto a fit; real notches >1.5 px still do);
(b) thin regions (mean thickness < 1.6 px) whose colour lies between their two main neighbours are dissolved
pixel-wise into the nearer neighbour.
Result vs exp_006: composite **0.883 (+0.005)**, SSIM +0.002, ΔE −0.034, edge_dev −0.014, corner recall +0.033,
prim recovery 0.08→0.19, gz −24 %, paths −12 %, every non-photo category improved on every fidelity metric;
photo −0.010 (handled by its own preset later). **Keep.**
Ablation `abl_007_merge1` (palette merge radius 0.6→1.0×): icon +0.004, diagram +0.007, prim 0.19→0.26, gz −20 %,
but gradient −0.005, photo −0.012 → **preset-dependent** → motivates the classifier/presets (W7).

### State of the system (Evaluator note after 7 experiments)
- Biggest remaining weaknesses by data: gradient (0.853, ΔE 1.9, edge_f 0.76 — banding), photo (0.71, 7 s on ≤512 px),
  diagram (0.863, edge_dev 0.38 — thin connectors/text bars), JPEG thin line art (dashes).
- Three parameters (mix_suppress, merge_frac, slivers on photos) split flat vs continuous-tone content the same way →
  next: heuristic classifier + presets, then gradient fitting (W6) and a photo/posterize path.
- Not in a local optimum yet: every recent structural change gave measurable gains; parameter tweaks were small.

## exp_008_gradients — W6 gradient detection & fitting
Soft boundaries between quantisation bands are detected by comparing the input change over a 5-px span across the
boundary with the palette step (a first version comparing only the two adjacent pixels mistook anti-aliased/blurred
real edges for soft ones and chained unrelated shapes into one group; its fits were worse than the bands).
Regions joined by soft boundaries get one linear or radial gradient (principal direction / quadratic-luminance centre,
multi-stop profile simplified by Douglas–Peucker), accepted only if OKLab RMS ≤ 0.03 and < 0.85× the banded error.
Result: gradient category 0.853→**0.864** (SSIM +0.008, PSNR +0.85, ΔE −0.23, edgeF +0.024); all flat categories
unchanged (no false gradients). e.g. dev_0071 SSIM 0.950→0.985. **Keep.**

## exp_009_auto — heuristic classifier + presets (W7)
Features on a ≤256 px median-filtered thumbnail (colour-histogram coverage c90/c99, top-bin share, flat / smooth / edge
pixel fractions, chroma, "ink" share and ink-edge share). A depth-3 decision tree (5-fold CV acc. 0.82 on 4 preset
families) was fitted on dev and hard-coded as rules (no runtime sklearn). Presets: flat → merge_frac 1.0;
lines (line_art/diagram) → merge 1.0 + mixture suppression, no gradients; gradient/photo → merge 0.6.
Result: composite 0.885→**0.889**; oracle presets (true category) give 0.890 → classifier errors cost 0.001.
Dev confusion: diagrams → line_art (same preset family behaviour), some gradients → logo.

## exp_010 (abl_009_denoise1) — W1 edge-preserving sigma filter
Lee sigma filter in OKLab (3×3, threshold max(0.03, 4σ_noise)) before palette extraction / assignment.
1 iteration: composite **0.895 (+0.006)**, PSNR +0.54, ΔE −0.044, edgeF +0.007, edge_dev −0.019, gz −13 %;
every category improves (gradient +0.015, logo +0.007). 2 iterations: same overall, diagram slightly worse, slower.
**Keep, denoise=1 default.**

## exp_011_subpixel — sub-pixel boundary placement from anti-aliasing (research-driven)
Idea (vectorizer.ai publicly states it "places boundaries according to the anti-aliasing pixel values"): for every
crack between regions A|B take the 4-px profile across it, unmix each pixel into coverage α of B's palette colour,
and move the crack midpoint to e = Σ(1−α) − 2 px (clamped ±0.7) along the normal; profiles touching a third region,
low-contrast pairs (<0.05 OKLab) and gradient regions are skipped.
Result vs exp_010: composite **0.901 (+0.006)**, PSNR +0.43, edge_dev −0.013, corner recall +0.020, corner err −0.022 px,
primitive recovery 0.287→**0.382**, diagram +0.014 (PSNR +1.14 dB), icon +0.007; gradient/photo neutral. **Keep → best-v2.**

## abl_011_centerline — W8 centre-line strokes (optional)
Thin regions (max half-width ≤ 5 px) → skeleton (scikit-image) → polylines (spurs < width pruned) → line/Bézier fit →
`stroke` paths with width = area / skeleton length; each region verified by rendering (IoU ≥ 0.75) else kept as fill.
Result (line_art + diagram, dev): line_art composite 0.896→0.883, diagram 0.892→0.868, PSNR −1.5/−2.3 dB, bytes ≈ equal.
Failure modes seen: variable-width strokes (procedural sketches) get one width; skeleton junctions leave small defects.
Decision: **optional flag `centerline=True` (off by default)** — useful when the user wants editable strokes, not for fidelity.

## exp_001_baseline_tuned — per-category VTracer grid search (dev, oracle category)
Stage 1: filter_speckle {2,4,8,16} × color_precision {6,7,8} × layer_difference {8,16,32}; stage 2: corner_threshold
{30,60,90,135} on each category's best (length_threshold sweep dropped for time, 3.5/4/6 made <0.002 difference where tried).
Best per category in `eval/configs/exp_001_baseline_tuned.yaml`. Dev composite **0.8218** (defaults 0.8007);
photo 0.7575 with color_precision 8 / layer_difference 8 (better than our region engine on photos at that time: 0.722).
All later comparisons use this as "best baseline".

## exp_012_fitfix — bugs found by the new unit tests
`turning()` for closed chains ran off the end of the extended arclength array → every closed loop had a spurious corner at
its last sample; parabola-sagitta straight-line test (staircase residual up to 0.45–0.5 px on true straight edges);
fully rounded squares are emitted as circles; empty-palette guards. Composite 0.901→0.900 (sagitta test: −0.06 dB PSNR,
+0.007 corner recall, −2 % bytes; `abl_012_nosag` = 0.901). Kept for cleaner geometry (within tolerance).

## exp_013_speed — vectorised speckle merge, one-pass component labelling, fast tiny chains, global sub-pixel field
Composite **0.902 (+0.002)**, photo +0.008, median time −7 % (photo −38 %): processing all small components at once
(instead of smallest-first) turned out slightly better as well.

## exp_014_photo — photo preset = VTracer with tuned params; `max_side`
Photos detected by the classifier go to plain VTracer (fs 2, cp 8, ld 8, ct 30) — faster (0.3 s) and higher fidelity than
the region engine; the region engine remains as `photo_posterize` (≤640 px, 3× smaller files). Inputs larger than
`max_side` (2048) are processed downscaled, output keeps the original size via viewBox. Dev composite 0.902,
photo 0.747 (tuned baseline 0.758: two photos are classified as logo → region engine).

## exp_015_grad2 — gradient robustness
Iterative removal of member regions the model explains badly (a similar-coloured shape chained to a background ramp
made the whole group fail → background stayed banded, dev_0079 edgeF 0.58), elliptical radial gradients via
`gradientTransform` (bounding-box radial fills on non-square shapes), acceptance rms ≤ 1.1× banded rms (equal-error
gradients look much better than contour bands). Gradient category 0.875→**0.881**, edgeF 0.819→0.842 (now above the
tuned baseline 0.838), ΔE −0.11. Overall **0.904** → best-v3.

## Best versions (git tags cannot be pushed from this environment: HTTP 403 on refs/tags; recorded here instead)
| tag | commit | dev composite | note |
|---|---|---|---|
| best-v1 | e07f24d | 0.895 | graph engine + presets + gradients + denoise (exp_010) |
| best-v2 | 48e89b6 | 0.901 | + sub-pixel boundaries (exp_011) |
| best-v3 | e0fe785 | 0.904 | + speedups, photo preset, gradient robustness (exp_015) |
