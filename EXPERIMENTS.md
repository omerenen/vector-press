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

## Final-stage experiments (dev)
- `abl_015_up2` (process at 2×, tolerances unscaled): composite +0.003, PSNR +2.0 dB, line_art +0.019, diagram +0.011, but corner
  recall −0.155, bytes +25 %, time ×2.8. `abl_015_up2s` (all px tolerances scaled ×2): composite −0.003 → the gain comes from
  effectively tighter fitting, not from resolution. `abl_015_up2c` (only corner arm scaled): +0.002, line_art +0.019,
  diagram +0.011, icon +0.008, gradient −0.014 → **mode="max" = 2× processing for icon/logo/line_art/diagram presets only**
  (fast mode unchanged). `abl_015_detail07` (finer default detail): mixed (logo +0.005, diagram −0.007) → default kept.
- Seam width must scale with the processing factor (max mode showed a 2-px 3 % leak on test_0020 with a 0.5 px effective
  seam) → fixed, gap 0.
- `abl_016_taper` (fade the sub-pixel shift in over 3 samples at junctions): neutral, corner recall +0.006 → kept.
  `abl_016_interp` (interpolate unknown shifts across junction profiles): slightly worse (prim −0.026) → reverted.
  Visible residual defect: thin strokes look slightly pinched where they cross other strokes (see sheet_line_art).

## Independent review (M6) and fixes
An independent reviewer (fresh context: code, test metrics, contact sheets, licenses only) reported; full list and actions
in REPORT.md §8. Fixed: region-explosion fallback to the photo engine with early bail-out (1024² noise 93 s → 14 s; Hubble
star fields no longer routed to the region engine), photo preset processes ≤1024 px (3000² photo 55 s → 7 s), genuinely
translucent regions keep `fill-opacity` (alpha-128 square was rendered opaque), max mode now upsamples above 1024 px
(cap 3072 px), VTracer output normalised (viewBox, no prolog), uint16/NaN input, tiny/thin images emitted as exact pixel
runs, full `stats` on empty input, string options, metric: embedded raster scores 0, viewBox offset; LICENSES.md corrected
(libimagequant is NOT in the Pillow wheel; torch/NVIDIA note; Unicode-3.0 / LLVM-exception; third-party imagery notice).
A first version of the opacity fix treated anti-aliased alpha bands as translucent and produced gaps on test_0066
(257 px) — caught by the test-split gap metric, fixed (only regions whose pixels mostly have *flat* partial alpha).
Disclosure: three generic bugs were found while inspecting test outputs (seam width in max mode on test_0020, the
primitive-metric subpath/near-circle handling, the opacity regression above); no parameter was tuned on test.
Final test: fast 0.901 (gap 0), max 0.905 (gap 0); dev: fast 0.904. Real-world subset (72 icons/logos/emoji):
tuned VTracer 0.833 → final 0.919.

## Best versions (git tags cannot be pushed from this environment: HTTP 403 on refs/tags; recorded here instead)
| tag | commit | dev composite | note |
|---|---|---|---|
| best-v1 | e07f24d | 0.895 | graph engine + presets + gradients + denoise (exp_010) |
| best-v2 | 48e89b6 | 0.901 | + sub-pixel boundaries (exp_011) |
| best-v3 | e0fe785 | 0.904 | + speedups, photo preset, gradient robustness (exp_015) |

## Fresh-clone test (2026-11-03)
`git clone --branch claude/laughing-rubin-n46tic https://github.com/omerenen/vector-press.git` into an empty directory →
`python3.12 -m venv .venv` → `pip install -r requirements.txt` → `python -m pytest -q`: **42 passed** →
`python -m vectorizer demo.png -o demo.svg` OK → `pip install -e .` → `vectorize demo.png -o demo2.svg --preset logo --mode max` OK
(output: exact `<rect>` + `<circle>`). Nothing depends on files outside the repository (datasets are rebuilt by `python -m data.build`).

Fresh-clone test re-run on the final commit 6f3dd9e: 47 passed; `python -m vectorizer` and batch `vectorize in -o out --stats` OK.
| best-v4 | 9c82f5b | dev 0.904 / test 0.901 | final: review fixes (fallback, alpha, max mode, licences) |


# PHASE 2 — target benchmark, print/cut readiness, rethink bottlenecks (2026-11-03)

## P2-1 Target benchmark (AI-generated art)
`data/target/` does not exist in the repository (only branch `claude/laughing-rubin-n46tic`), so no vectorizer.ai outputs
are available. HuggingFace became reachable in this phase, so instead of a synthetic stand-in the target set is built from
**real AI-generated images with a verified permissive license**:
- first attempt: DiffusionDB (`poloclub/diffusiondb`, CC0-1.0, Stable Diffusion 1.x). Rejected after looking at the
  montage: SD 1.x mostly ignored the style keywords (sticker / vector / logo prompts produced photoreal portraits, several of
  real public figures) → poor proxy for the use case and unsuitable for committed contact sheets. Script kept
  (`data/target_fetch.py`, with an HTTP-range zip reader).
- adopted: **`OpenDatasets/dalle-3-dataset` (CC0-1.0, DALL-E 3 images with their prompts)**, `data/target_dalle3.py`:
  captions of all 67 shards scanned (1 423 use-case matches: cutfile/line-art/icon 405, logo 331, poster 290,
  vector/flat 198, t-shirt 186, sticker 13), one image per distinct prompt, greedy quota-balanced selection of parquet row
  groups (≤3 images of a category per row group, because one user's prompt series clusters in a row group), no manual
  picking. A first, unbalanced selection (rank row groups by match count) gave 55 posters / 48 logos / 2 cut-files / 0
  stickers → replaced. Split by hash into `tdev` (tuning) and `ttest` (held-out, never tuned on). Native DALL-E 3 sizes
  (1024², 1792×1024, 1024×1792). No ground truth → fidelity is measured against the input image.
- `data/target_local.py` + `eval/configs/vectorizer_ai.yaml` (method `external`) are ready for a real `data/target/`
  folder with `data/target/vectorizer_ai/<stem>.svg`.
- LPIPS is now computed (AlexNet weights fetched from a HuggingFace mirror, accepted only with the official SHA-256,
  `data/fetch_lpips.py`; download.pytorch.org is still blocked).

## P2-1b Overfitting check — procedural scenes with a new seed and different ranges (`python -m data.build --proc2`)
Split `proc2`: 60 scenes, seed 777, canvases 640–1024 px (phase 1: 256–512), 8–18 shapes (4–12), 5–9 diagram boxes
(3–7) with thinner strokes 0.9–2.5 px (1.5–3.5), 4–9 gradient shapes (2–6), 6–12 strokes 0.8–3.0 px (4–9, 1.2–4.5).
| method | composite | SSIM | edge_dev | corner recall | prim | gz |
|---|---|---|---|---|---|---|
| VTracer default | 0.769 | 0.956 | 0.920 | 0.354 | 0 | 105 116 |
| VTracer tuned | 0.796 | 0.961 | 0.840 | 0.330 | 0 | 120 171 |
| current final (best-v4) | **0.885** | **0.981** | **0.329** | **0.527** | 0.306 | **11 626** |
Gain over tuned VTracer +0.089 (phase-1 test procedural items: +0.101) → no strong overfitting to the phase-1 generator
ranges; corner recall and primitive recovery are lower on these busier scenes (work items 3/4).

## P2-2 Print / cut-readiness metrics (`eval/printcut.py`, enabled with `printcut: true`)
At a physical output width of 100 mm: open subpaths, self-intersecting subpaths (flattened outlines, shapely),
overlap ratio (Σ shape areas / union − 1; 0 = pure cutout), distinct paints, per cut layer (fill paint) tiny islands
(equivalent diameter < 0.5 mm) and thin features (parts thinner than 0.5 mm: opening with a 0.5 mm disk; component counted if
2·max distance < 0.5 mm or >20 % of its area is thin), thin area in mm², node count. Format-agnostic (works on VTracer output).
First observations (phase-1 test SVGs): our stacked output has overlap 0.2–1.1 (filled holes) but VTracer's is higher
(0.4–1.1); we have a few *real* self-intersections (e.g. test_0049: 5 crossings from curve fitting at junctions) where
VTracer has none → assigned to work item A (fit.py).
New presets (`vectorizer/presets.py`, applied on top of the classifier's content preset):
- `cut`: cutout geometry (every region with its real holes, no stacking, no seams, one path per colour), ≤8 flat colours,
  no gradients, background colour dropped, minimum feature 0.5 mm at `cut_width_mm` (100 mm) enforced on the label map
  (per-colour opening + island merge, `vectorizer/pipeline/cut.py`), optional `silhouette=True` (single colour).
- `print`: stacked, full fidelity (= content preset; gradients on).

## P2-3 Target baseline on `tdev` (phase2-base; full run, 53 images, metrics vs the input image)
| method | composite | SSIM | PSNR | LPIPS | ΔE | edgeF | paths | gz KB | overlap | self-x | tiny islands | colours | t_med s* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VTracer default | 0.680 | 0.783 | 22.9 | 0.184 | 4.15 | 0.883 | 10044 | 2306 | 2.62 | 92.8 | 10979 | 8276 | 4.3 |
| VTracer tuned (oracle cat.) | 0.680 | 0.783 | 23.4 | 0.184 | 3.92 | 0.868 | 10838 | 2104 | 2.75 | 74.6 | 12287 | 9010 | 4.9 |
| final (best-v4, auto) | 0.702 | 0.796 | 24.9 | 0.185 | 3.35 | 0.865 | 11903 | 1777 | 3.11 | 121.3 | 13225 | 9676 | 6.7 |
| print preset | 0.688 | 0.780 | 24.4 | 0.203 | 3.50 | 0.843 | 9300 | 1390 | 3.03 | 104.8 | 10078 | 7432 | 5.8 |
| cut preset | 0.391 | 0.496 | 12.7 | 0.495 | 22.52 | 0.544 | 1819 | 297 | 0.77 | 40.0 | 1462 | 1710 | 6.1 |
\* eval timings with 4 workers (contended), not the speed benchmark.
Diagnosis (root cause, before any change): **37/53 target images end up as photo-like VTracer output** (region-density
fallback, median 7 000–16 000 paths, 1.2–2.4 MB gzipped); even logos have a median of 1 600 paths. The region engine
explodes on DALL-E textures (painterly shading, generator noise, fine fake detail), so the safeguard routes to VTracer.
Our lead over VTracer on the target set is therefore small (0.702 vs 0.680) — the key target problem is a segmentation /
palette stage that turns textured AI art into clean, compact, print/cut-ready regions (→ stream B). Cut preset: overlap
≈ 0 by construction, but still ~1 800 paths and ~300 KB for a cut file (same root cause).

## Phase 2 — stream B

### B-0 Diagnosis (before code changes): why the region engine explodes on tdev
Measured stage by stage on the worst tdev images (`quantize` internals, label maps and renders viewed side by side with
the input and VTracer):
1. **Early bail-out counts fragments, not regions.** `quantize(bail_density=4×0.008)` counts 4-connected components of
   the *raw* nearest-palette assignment, before any clean-up. DALL-E output carries generator noise / paper grain /
   halftone dots, so this raw map is salt-and-pepper: tdev_0051 (clean cartoon sticker) has 39 119 raw components but only
   815 regions after the phase-1 clean-up → it is routed to VTracer anyway (11 184 paths, 1.06 MB, visibly worse).
   tdev_0000 (stencil with halftones) has 303 k raw components (> 0.1·HW) → VTracer with the "pure noise" parameters
   (1 256 blobby paths, composite 0.481 vs VTracer default 0.607).
2. **The fixed-area speckle merge cannot converge in texture.** `merge_small_regions` moves each component smaller than
   `min_area` into the most similar neighbouring *label*; inside texture all neighbours are fragments too, so fragments
   merge into fragments and stay small. tdev_0003: 71 903 components → 38 431 / 27 132 / 22 802 after passes 1/2/3,
   19 109 after 7 passes; median region area stays 2–3 px (min_area 42). Sliver removal then halves it (10 112) but the
   result is still far above the fallback threshold (11 521 regions, 4.5 MB through VTracer).
3. **Palette quantisation with a fixed OKLab radius (0.045, ≤64 colours) is the wrong primitive for shaded art.** Region
   colours are palette colours, so soft shading needs either many palette colours (→ more fragments) or posterises.
4. **Thin bright features are lost** where the region engine does run (tdev_0039 hair strands, tdev_0000 bow string):
   speckle merge / sliver removal treat 1–3 px strands as noise (edge-F 0.699 vs VTracer 0.929).
Consequence: 37/53 images go to VTracer (photo parameters, ≤1024 px) and ~8 images that stay in the region engine are
worse than VTracer default (0000, 0017, 0020, 0024, 0039, 0045, 0048, 0049).
Root cause in one sentence: the clean-up stage decides by *area* only (fixed speckle size), so it has no notion of how
much a merge costs in colour error versus how much boundary (= SVG bytes) it saves.

### B-1 Alternatives for the segmentation stage (raster-level screening, then full pipeline)
Screening metric (cheap, same for every segmenter): render every region with its mean colour, compute the composite's
fidelity part (SSIM/PSNR/ΔE/edge-F/GMSD vs the input) and the total boundary length (crack edges = the SVG's cost driver).
tdev_0051 / 0003 / 0040 / 0039 / 0012 / 0024, at several detail levels each (`/tmp` script, numbers in RESEARCH.md):
- current palette + fixed-area merge: 0040 135 k boundary px → fid 0.811; 0051 66.6 k → 0.873.
- **Mumford–Shah region merging (RAG, colour + boundary length) on the palette over-segmentation**: 0040 141 k → 0.839,
  0051 64.5 k → 0.876 (better at equal or lower boundary length on every image; scale-aware).
- Felzenszwalb (graph-based) alone: far worse at equal boundary length (0051: 152 k → 0.819; leaks + fragments).
- Felzenszwalb fine over-segmentation + MS merging: same curve as MS, slightly better at high detail on 3/6 images
  (0040 131 k → 0.857), worse on 0024 → kept as option `seg_init="fz"` for the pipeline test.
- SLIC + mean colours: much worse (0051 6 800 regions → 0.751). L0 gradient smoothing (Xu et al. 2011) + palette:
  no better than MS and 25 s per image → rejected.
MS merge cost on 1 MP: 0.3–1 s (vectorised rounds, 10–16 rounds).

### B-2 `segment="ms"` in the pipeline (tdev_small, t_final settings, 18 images)
| run | composite | SSIM | PSNR | ΔE | edge-F | GMSD | LPIPS | paths (med) | gz (med) |
|---|---|---|---|---|---|---|---|---|---|
| phase2-base (t_final) | 0.689 | 0.788 | 24.2 | 3.60 | 0.864 | 0.125 | 0.182 | 7 735 | 1 559 KB |
| VTracer default | 0.678 | 0.779 | 22.4 | 4.15 | 0.893 | 0.121 | 0.184 | 10 641 | 2 361 KB |
| ms λ=0.01 | **0.723** | **0.821** | **25.1** | **3.18** | **0.896** | **0.105** | **0.162** | 12 636 | 1 645 KB |
| ms λ=0.03 | 0.705 | 0.808 | 25.1 | 3.31 | 0.856 | 0.127 | 0.168 | 6 458 | 570 KB |
The early bail-out now uses a pure-noise test (>0.25 raw components per px); the density fallback in api.py is unchanged
but sees the MS region count. Per image: clean cartoon / logo art wins big (0051 0.734→0.824 at 62 KB instead of
1 064 KB, 0012 0.575→0.716, 0042 0.863→0.886); heavy-texture images (0003 fur, 0045/0048 painterly) are better on the
composite with the VTracer fallback (0003: MS 0.589 / 615 KB vs VTracer 0.720 / 4.5 MB) - the metric rewards
reproducing texture; λ=0.01 routes more of them to the fallback than λ=0.03, hence its higher score.
Dev (phase-1, 44 images): ms λ=0.01 regresses line_art (−0.016: thin AA lines took their diluted region mean colour,
6→74 paths because every region had its own paint) and photo (dev_0123 no longer falls back) → fix B-3.

### B-3 Making `ms` safe on phase-1 art (dev_small, 44 images) + routing
- `ms` alone keeps high-contrast AA/JPEG fragments along strokes as regions (they are "real" for a piecewise-constant
  energy): dev_0081 (simple line drawing) 207 regions instead of 5, ragged edges, line_art −0.016.
- Fixes: (1) `seg_premerge`: run the phase-1 speckle merge + sliver removal on the palette over-segmentation first, MS
  then merges what the area rule cannot (texture fragments surrounded by fragments); (2) region colours: regions within
  0.02 OKLab of their majority palette colour share that palette label (one paint, one path per colour as before);
  thin regions without flat pixels take the pure palette colour; final colours = per-label median of flat pixels
  (phase-1 rule).
| dev_small | composite | diagram | flat | gradient | icon | line_art | logo | photo |
|---|---|---|---|---|---|---|---|---|
| base (speed-refactored, identical to phase2-base 0.9061) | 0.9061 | 0.8876 | 0.9617 | 0.8724 | 0.9553 | 0.9126 | 0.9351 | 0.7609 |
| ms λ0.01 | 0.9006 | 0.8834 | 0.9621 | 0.8733 | 0.9550 | 0.8968 | 0.9344 | 0.7337 |
| ms + premerge + snap + medians | 0.9036 | 0.8883 | 0.9619 | 0.8742 | 0.9553 | 0.9135 | 0.9359 | 0.7261 |
All non-photo categories within tolerance (gradient edge-F −0.004, ΔE ±0.01); photo −0.035 = one image (dev_0123)
no longer routed to the photo engine because MS produces far fewer regions than the palette stage.
- tdev_small with premerge: 0.7179 (paths median 8 518, 1.16 MB) vs 0.7229 without; region densities after MS drop
  (0039 14→6.7, 0003 5.2→3.5 per 1000 px) so the unchanged density threshold (8/1000) sends 0039/0048 to the region engine.
  Per image, region output beats the VTracer photo engine up to 2.5 regions/1000 px (0012) and loses from 3.5 (0003 fur:
  0.566 vs 0.720; 0048: 0.598 vs 0.673) → `seg_max_density` (density threshold used when segment="ms"), simulated 0.003:
  0.7293 on tdev_small.

### B-4 Routing with the ms engine (preset auto)
Region density after MS is a poor texture detector (MS merges smooth photos into few regions: dev_0123 photo 403 regions
→ region output 0.656 vs VTracer 0.765; tdev_0003 fur 3.5/1000 px). Measured per image on tdev_small + dev_small:
the phase-1 post-clean-up count (`merge_small_regions`+slivers, computed anyway by `seg_premerge`) and the raw palette
fragment count separate the cases: region output wins for 0051 (raw 48 / p1 0.9 per 1000 px), 0012 (51 / 6.7), 0021,
0033, 0042, 0006; the photo engine wins for 0003 (69 / 11.3), 0048 (107 / 15.6), dev_0123 (69 / 4.4), 0039/0045/0024/0000
(>130 / >26). Rule (auto only): photo engine if p1 > `max_region_density` (0.008, unchanged) or raw > `seg_raw_bail`
(0.06; phase 1 bailed at 0.032 raw, which sent 0051/0012 to VTracer). Thresholds rest on few images → lead/stream C
should re-check them on the full set (HANDOFF).
| run (tdev_small) | composite | SSIM | ΔE | edge-F | LPIPS |
|---|---|---|---|---|---|
| phase2-base | 0.689 | 0.788 | 3.60 | 0.864 | 0.182 |
| ms + premerge, density 0.008 | 0.718 | 0.819 | 3.23 | 0.884 | 0.163 |
| **ms + premerge + routing (default now)** | **0.729** | **0.829** | **3.13** | **0.904** | **0.157** |
dev_small with the defaults: 0.9067 vs 0.9061; every category ≥ base (photo identical, gradient edge-F −0.004, ΔE ±0.01).

### B-5 Gradients (work item 6): piecewise-affine MS + per-region linear gradients (`seg_model="affine"`)
Root cause on the dev gradient category (dev_0068 edge-F 0.41, dev_0061, dev_0066, Fluent-emoji style art): soft
shading and *blurred* features are cut into flat bands; every band border is a hard edge that the input does not have
(Canny precision drops), and smooth ramps inside one object are not linear/radial over the whole soft group, so the
soft-group fitter (phase 1) rejects them. Approach: MS with an affine colour model per region (ridge-regularised
slopes, batched 3×3 solves), then every region whose affine fit removes more squared error than the price of ~60 px of
boundary gets a `linearGradient` along its dominant colour-change direction (2–3 stops, sRGB interpolation corrected
by a mid stop when needed); the phase-1 soft-group gradients still run first.
- Raster screening tdev_0030 (poster with bokeh): fid 0.739 → 0.760 at −18 % boundary; pipeline: −22 % bytes, GMSD
  0.112 → 0.094, contour banding gone (visual).
- dev_small: gradient edge-F 0.8638 → **0.8754** (+0.012), but PSNR −0.9 dB / ΔE +0.07 on gradient and ΔE +0.07 on
  logo (AA rings give flat regions a small slope), composite gradient 0.8734 vs 0.8742 (const) → mixed.
- tdev_small (region-engine images only): +0.002..+0.004 on 0012/0033/0042, −0.005 on 0003; affine also changes region
  counts (routing) and costs ~0.3 s/MP (moment accumulation) → **kept as an option, default "const"**.
Soft (blurred) boundaries themselves would need blur filters or mesh gradients (resvg: no mesh) – open problem.

### B-6 Speed of quantize (work item 7), cProfile ratios on the same machine/run (12 dev items rendered at 1024 px)
Changes with identical output (verified: label maps equal on 30 dev runs except float-rounding flips in ≤0.1 % px of
2 images; dev_small composite 0.9061 = phase2-base): symmetric sigma filter (4 instead of 8 neighbour distances, channel
planes – 3× faster), `_dir_stats` from one neighbour-distance plane per direction (2.4×), dense-histogram palette binning
instead of `np.unique` sort, one-sort per-label medians instead of K full-image masks, uint8 OKLab LUT, low-alpha pass
skipped on opaque input, MS region stats on channel planes. Same 8 images, same process: quantize 12.5 s → 6.5 s
(−48 %); share of quantize in the whole pipeline 0.511 → 0.385 (palette engine). The default ms engine (premerge + MS)
costs +12 % over that on flat art (quantize/fit ratio 0.80 → 0.98, base 1.36): estimated median ≈ 1.6–1.7 s at 1024 px
from the phase-1 stage medians (quantize 1.18→~0.85 s, fit unchanged 0.6 s) → the ≤1.2 s target needs fit-stage work
(stream A) too; real timing by the lead.

### B-7 Full runs (defaults: segment="ms", seg_premerge, routing B-4; code snapshot = commit 9ea9d0b-equivalent tree of
`vectorizer/` at the time of the run, recorded in HANDOFF_B.md) vs phase2-base re-run (`B_base_*`)
- tdev t_final (53): composite **0.702 → 0.724** (VTracer default 0.680), SSIM 0.796 → 0.818, ΔE 3.35 → 3.07,
  edge-F 0.865 → 0.882, LPIPS 0.185 → 0.169; every category ≥ base (cutfile +0.028, logo +0.021, poster +0.020,
  sticker +0.032, tshirt =, vector_flat +0.019 with median paths 11 222 → 3 334 and 1.32 MB → 393 KB); 22 images
  better, 3 worse (0040 −0.034, 0013 −0.008, 0007 −0.006).
- dev (130): **0.9044 → 0.9050**, all categories within tolerance, valid 100 %, gap 0 (per-category table in HANDOFF_B.md).
- tdev t_cut: see HANDOFF_B.md.
Honest limitation: 35/53 tdev outputs are still VTracer-like (photo engine) because on heavy texture the composite
prefers the 30 k-path stack; the clean region output for those images exists (print/cut intents, `seg_budget`) but
scores lower (tdev_small print: 0.654 vs 0.671 for the old run with fallbacks; 368 KB vs 1.2 MB, 1 176 vs 7 485 paints,
3 272 vs 8 262 tiny islands, overlap 0.10 vs 3.05).
