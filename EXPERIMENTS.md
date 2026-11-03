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

## Phase 2 — stream A (primitives, corners, geometry validity)

Scope: `vectorizer/pipeline/fit.py`, `boundary.py`, emission parts of `assemble.py`, new `vectorizer/pipeline/primfit.py`.
Baseline = unchanged `phase2-base` code (`A_base`, `A_base_small`). Analysis scripts (not committed, /tmp/claude-0/A):
per-primitive failure classifier (`analyze_prims.py`: finds the region loop that best matches each GT primitive outline,
incl. the ±sw/2 stroke edges, and classifies why the metric did not match), self-intersection classifier
(`svg_selfx.py`, `selfx.py`), corner metric decomposition (`corner_eval.py`, `corner_floor.py`).

### A-1 Diagnosis: primitive recovery (before any code change)
dev: 122 GT primitives (111 of them are stroked diagram boxes: 73 rect / 42 roundrect overall, plus 3 triangles,
2 polygons, 1 star, 1 ellipse), base recovery 58/122 = **0.475**. Every one of the 64 failures classified:

| failure class (dev, base) | n | what happens |
|---|---|---|
| split by junctions | **54** | the shape's outline is one loop of the region but consists of 2–20 chains. Diagram boxes: the thin box stroke is fragmented by JPEG/noise/AA into several colour regions (and connectors merge with the stroke), so the *fill* region's outline (= inner stroke edge, an exact GT target) gets junctions; flat shapes lying on top of other shapes get junctions where underlying edges touch. Chains are fitted one by one → no primitive, and straight edges carry extra junction vertices (polygon metric needs the exact vertex count) |
| fit selected wrong radius ("prim on hole") | 4 | chain-level rect accepted but a sharp corner was fitted as r≈2.1–2.6 px (blur / JPEG chroma subsampling rounds the iso-contour of convex corners; apparent radius of a blurred sharp corner ≈1.9σ) or a roundrect radius +1.7 px too large |
| fit rejected (single closed chain) | 6 | rect error just above `prim_tol` (bbox/hull initialisation pulled by 1–2 outlier samples), star with one undetected tip |
| threshold too strict / metric matching / occlusion | 0 | — (the metric's ±sw/2 stroke offsets work; occluded shapes are not GT primitives) |

proc2 (count only, no tuning; 157 primitives, base 0.293): split by junctions 81, no matching loop at all (segmentation
merged/destroyed the shape) 17, fit rejected 9, prim-on-hole 4.

### A-2 Diagnosis: corner error is mostly the metric's reference point
`corner_err` = distance of the output's Harris maximum from the *nominal* GT vertex. The Harris response of a perfect
corner peaks *inside* the corner (σ = 0.6 px window), and for diagram boxes the nominal vertex is the stroke centre line
while the visible corners are the outer/inner stroke corners (sw/2·√2 away). Evaluating the GT render against itself
(`corner_floor.py`): dev corner_err floor = **0.59 px** (flat_illustration), 0.44 (gradient), **1.15** (diagram), recall
0.95–1.0. On dev_small the base output has official err 0.830 while the GT's own peak offset is 0.903; measured against
the GT Harris peak instead (`err_peak`, proposed fix) the base error is **0.268 px** (diagram 0.350, flat 0.126).
→ the target "corner_err ≤ 0.5 px" is below the metric's own floor; the localisation error of our corners is already
≈0.27 px. Proposed metric fix (not applied, needs the lead): measure the error to the GT Harris peak in the same
window (identical for all methods). What *is* improvable is recall (rounded/missing corners) — handled by A-3.

### A-3 Region-level primitives (`region_prims`) + robust rect refinement (`rect_refine`)
Approach (chosen among: (a) fit primitives to whole region loops and snap the shared chains, (b) clean the label map
so strokes are not fragmented (stream B territory, and only helps diagrams), (c) fit primitives to open chains/arcs and
merge — loses exactness at junctions): for every drawn region whose outer loop is made of ≥2 chains, concatenate the
chains' fitting samples (sub-pixel shifted) and run the model selection on the whole loop (ellipse/circle, sharp rect,
rounded rect, new straight-edged polygon model with greedy vertex removal = MDL-like selection, per-vertex penalty).
Accepted → every chain of the loop is replaced by the exact piece of the primitive outline between its junctions, the
junctions are projected onto the outline and moved for **all** incident chains (neighbours stay watertight, cut-consistent),
conflicts (a chain/junction already snapped by another primitive) must agree within 0.35 px or the second one is
rejected. Regions are emitted as `<rect>/<circle>/<ellipse>`, polygons as a subpath with only their vertices.
Loops clipped by the canvas are skipped. `rect_refine`: soft-L1 IRLS Gauss–Newton refinement of the rect/rounded-rect
fit (bbox/hull initialisation is pulled by junction bumps and JPEG specks).

### A-4 Diagnosis: self-intersections (before the fix)
`pc_self_intersections` counts filled subpaths whose flattened outline is not simple (shapely). Classified on dev_small
(base, graph-engine outputs only; the photo items and one photo fallback are VTracer output, 42 subpaths there):
| class | n | root cause |
|---|---|---|
| float closing artefact | **50** | our loops are written with relative coordinates; the parser's accumulated float sum ends 1e-13 px away from the start point, GEOS sees two non-adjacent segments touching at the start → "Self-intersection". Same for loops ending with an elliptical arc (consumers recompute the arc end point from the centre parameterisation). Not a real defect, but a cutter's importer can see the same duplicate point |
| zero-area loop | 13 | tiny regions (3×3 px dots, 1-px slivers between two junctions) whose chains are all fitted as the same straight line(s) |
| lattice pinch | 3 | a 4-connected region touching itself at one lattice vertex (diagonal pixels): ring touches itself |
| real crossing | 2 | curve of one chain crossing a neighbouring chain of the same loop near a junction (small angle between chains), e.g. phase-1 test_0049 |
New with region primitives: an exact snapped primitive edge can deviate ≤1.5 px from the pixel lattice, so a neighbouring
chain (thin sliver regions along the shape) can cross it.

### A-5 Geometry repair (`geom_repair`)
(1) the last segment of every closed loop is written in absolute coordinates (a closing line is left to `z`); loops are
rotated so they do not end with an arc; (2) loops are split at repeated lattice vertices (pinch → two simple rings);
(3) every emitted ring is tested (shapely `LinearRing.is_simple` + area > 0); chains of invalid loops are re-emitted as
polylines through their sub-pixel samples, then through the raw crack midpoints (simple by construction); changed chains
re-trigger the check of the other loops using them (each chain escalates ≤ 2×, so this terminates); (4) loops still
invalid (polylines crossing an exact primitive edge) are emitted as their `make_valid` parts snapped to the output grid
(`set_precision(0.01)`, so rounding to 2 decimals cannot re-create a crossing); zero-area leftovers are dropped.
Alternatives considered: constrained Bézier fitting (control points kept inside the lattice corridor; a QP per segment, does
not handle zero-area and pinch cases), boolean clean-up of every path (`buffer(0)` on all regions: changes shared borders
→ gaps between neighbours), relaxing the metric (not ours to change).

### A-6 Results on dev_small (44 items, `--workers 1`), phase2-base = `A_base_small`
Primitive analysis on all dev primitives (`analyze_prims.py`, 122 GT primitives; recovery as in the metric):
| variant | dev prim recovery | remaining failures |
|---|---|---|
| base | 0.475 | split by junctions 54, wrong radius 4, fit rejected 6 |
| + region_prims | 0.754 | radius (blur-rounded sharp boxes) 13, 5-gon instead of rect 5, split 11 (segmentation broken), rejected 5 |
| + rect_refine (soft-L1 IRLS) | 0.828 | sharp boxes with r≈2–3.7 px 5, polygons on damaged boxes 5, segmentation failures ~11 |
| + blur_sharp_ratio 3.8 | **0.861** | 1 real r=2.5 px corner now sharp (−1), 5 fixed (+5); the rest are segmentation failures (stroke fragmented into fill, score > 1 px from every GT edge) |
proc2 (count only, no tuning; 157 primitives): base 0.293 → **0.65** with the same settings.

Full metric runs on dev_small (A_all2_small = region_prims + rect_refine + blur_sharp 3.8 + geom_repair, before the
snap-time validity check / culprit-only repair / solidity gate; the final code is measured on the full splits below):
| cat | composite | SSIM | PSNR | ΔE | edge_f | edge_dev | corner rec | prim | gz | self-x |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 0.909 (+0.003) | 0.971 (+0.001) | 32.7 (+0.35) | 1.139 (−0.025) | 0.959 (+0.003) | 0.199 (−0.008) | 0.911 (+0.075) | 0.943 (+0.405) | +0 % | 0.96 (−1.48) |
| icon | +0.004 | +0.001 | +0.75 | −0.014 | 0 | −0.007 | | | −9 % | 0 |
| logo | +0.002 | +0.001 | +0.31 | −0.023 | 0 | −0.004 | | | +1 % | 0 |
| flat_illustration | +0.002 | +0.001 | +0.80 | −0.014 | +0.003 | −0.016 | +0.364 | +0.500 | +2 % | 0 |
| line_art | +0.002 | +0.002 | +0.02 | −0.057 | +0.002 | +0.003 | | | +6 % | 0 |
| diagram | +0.005 | +0.002 | +0.41 | −0.056 | +0.003 | −0.025 | −0.008 | +0.373 | −5 % | 0 |
| gradient | +0.002 | 0 | +0.06 | −0.004 | +0.011 | −0.001 | 0 | | 0 % | 0.57 |
No category regresses beyond the tolerances. Polyline fallback at that stage repaired *every* chain of an invalid loop
(n_nodes +80 %); fixed afterwards (only crossing chains, light simplification, snap-time check) — dev_0090/0105/0063
then have fewer nodes than base.

**corner_lines (line-pair corner detector, blur zone 2 px; `A_all2cl_small` vs `A_all2_small`) — rejected:** diagram
composite +0.006 / PSNR +0.64, but corner recall −0.10 overall (diagram −0.153), flat_illustration −0.006, line_art −0.004
(false corners on gentle curves and on stroke ends). Kept behind `corner_lines=False`.

**Cost** (process time, 6 dev images, same machine state): all new options together 1.37× the base pipeline (line-art
and diagrams up to 2×: model selection on every multi-chain loop). Gates: loops clipped by the canvas skipped, rect/ellipse
only for loops with hull solidity ≥ 0.9, IRLS refinement only when the grid fit is within 2× tolerance, partition-based
robust error, exact vectorised ellipse distance (replaces 720-point sampling).

### A-7 Snap-time validity (final code) — dev_small `A_final_small`
A snapped primitive edge may deviate ≤1.5 px from the lattice, so it can cross a neighbouring chain. First version of the
check (reject the primitive whenever a neighbour outline turns non-simple) removed the crossings but cost primitive
recovery (dev_small diagram 0.925 → 0.849: thin JPEG slivers along the box edge). Final rule: a primitive is rejected only
if the neighbour outline cannot be repaired by turning its ordinary crossing chains into raw polylines *and* the
neighbour is not a sliver (area ≤ 30 px or mean thickness < 2 px; slivers are emitted as their valid parts).
dev_small, final code vs phase2-base: composite +0.003, SSIM +0.001, PSNR +0.36 dB, ΔE −0.018, edge_f +0.003,
edge_dev −0.009, corner recall +0.081, prim recovery +0.35, gz −0 %, self-intersections on graph-engine output **0**
(remaining 0.95/image are the VTracer photo fallbacks), every category within tolerance (no regression).
Checked items after the sliver rule: dev_0105 prim 0.71 / dev_0108 1.0 (as before the check), self-x 0.

### A-8 Target subset (tdev_small, 19 DALL-E images, `--workers 1`), final vs phase2-base
14 of the 19 images go to the VTracer fallback (unchanged). Overall: composite ±0.000 (cutfile +0.001), SSIM ±0, PSNR
+0.01 dB, edge_f +0.001, self-intersections 103 → 63 per image (all remaining ones are in VTracer-fallback outputs; the
graph-engine images go 379→0, 196→0, 140→0, 1→0), tiny islands +0.1 % overall but +23 % on tdev_0021 (line-art cut file:
526 self-crossing thin-stroke loops repaired with polylines; the thin strokes whose Bézier sides crossed now have their
real, very small width and fall apart into sub-0.5 mm islands in the raster check; nodes +15 % on that image). Region
primitives found 40 primitives on tdev_0021 (6 before).
