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

### A-9 Repair refinement after the target check
tdev_0021 classification (base output): 317 of 379 non-simple subpaths are **zero-area collapsed tiny regions** (1–3 px
regions between two junctions whose chains are fitted as the same line), 40 float-closing artefacts, 15 pinches, 7 real
crossings. Re-emitting the collapsed regions as polylines gave them their real sub-pixel area → +23 % tiny islands and
+15 % nodes. Now loops whose *fitted* outline has |area| < 0.5 px² are simply not emitted (they were invisible before as
well; the shared chains are left untouched). Tried before that: a tighter Bézier refit level (fit_tol/2, no smoothing)
before the polyline levels — nodes −2 % only on tdev_0021, kept as the first repair level (`repair_refit`).
tdev_0021: self-intersections 391 → 0, tiny islands 656 → 659, nodes 20 035 → 18 737 (vs. no repair).

### A-10 Full runs: `A_final` vs `A_base` (= phase2-base, run from a clean `git archive phase2-base`), `printcut: true`
**dev (130 images, workers 2)**
| cat | composite | SSIM | PSNR | ΔE | edge_f | edge_dev | gap | corner rec | corner err | prim | nodes | gz | self-x |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 0.907 (+0.002) | 0.970 (+0.001) | 32.6 (+0.38) | 1.166 (−0.016) | 0.957 (+0.001) | 0.213 (−0.007) | 0 | 0.856 (+0.034) | 0.948 (−0.039) | **0.844 (+0.378)** | −0 % | −0 % | **0.53 (−2.47)** |
| icon | 0.951 (+0.001) | +0.000 | +0.29 | −0.005 | +0.000 | −0.001 | 0 | | | | −3 % | −0 % | 0 (−0.85) |
| logo | 0.924 (+0.001) | +0.001 | +0.47 | −0.014 | −0.000 | −0.006 | 0 | | | | −2 % | −0 % | 0.05 (−1.70) |
| flat_illustration | 0.958 (+0.005) | +0.001 | +1.09 | −0.024 | +0.001 | −0.015 | 0 | 0.958 (+0.184) | 0.530 (−0.171) | 0.917 (+0.500) | −3 % | −1 % | 0 (−1.00) |
| line_art | 0.901 (+0.002) | +0.001 | +0.30 | −0.019 | +0.000 | −0.004 | 0 | | | | −2 % | +2 % | 0 (−6.75) |
| diagram | 0.898 (+0.004) | +0.002 | +0.32 | −0.044 | +0.002 | −0.015 | 0 | 0.868 (−0.004) | 1.116 (0) | 0.822 (+0.341) | −5 % | −5 % | 0 (−1.90) |
| gradient | 0.882 (+0.001) | +0.000 | +0.00 | −0.001 | +0.004 | −0.000 | 0 | 0.642 (0) | 0.731 (−0.035) | | −3 % | +0 % | 0.20 (−3.85) |
| photo | 0.758 (0) | 0 | 0 | 0 | 0 | | | | | | 0 | 0 | 6.4 (0) |
Pooled dev primitives: 58/122 → **103/122** (rect 36→58/73, roundrect 18→38/42, triangle 2→3/3, polygon 1→2/2, star 0→1/1,
ellipse 1/1). The only remaining self-intersections on dev are in two images classified as photo (VTracer engine:
dev_0029, dev_0069) and the photos. All categories within the no-regression tolerances.

**tdev (53 DALL-E images, primary target score)**: composite 0.702 (+0.000), SSIM +0.000, PSNR +0.015 dB, ΔE −0.001,
edge_f ±0, nodes −0 %, gz +0 %, overlap ratio +0.01, tiny islands −2.4 / image, thin features ±0, **self-intersections
121 → 56 per image**. 39 of 53 outputs are byte-identical (VTracer fallback, untouched by stream A); on the 14 graph-engine
outputs self-intersections go **3460 → 0**. (The target score is dominated by the segmentation / fallback problem → stream B.)

**proc2 (60 scenes, new generator seed/ranges, treated as held-out, run once)**: composite 0.887 (+0.002), SSIM +0.000,
PSNR +0.18, ΔE −0.010, edge_f −0.000, edge_dev −0.009, gap 0, corner recall 0.606 (+0.079), corner_err 0.848 (−0.097),
prim recovery per-image 0.585 (+0.280), **pooled 46/157 → 101/157 (0.293 → 0.643)** (rect 25→57/71, roundrect 15→32/54,
polygon 0→3/10, star 0→1/5, triangle 3→4/8, circle 2→3/5, ellipse 1/4), self-intersections 18.7 → **0**, nodes −1 %,
gz −1 %; per category flat_illustration +0.002, line_art +0.002, diagram +0.004, gradient +0.000 (PSNR −0.02, ΔE +0.005,
within tolerance). Overfitting check passed: the gain is as large as on dev. Flat_illustration nodes +33 % come from a
single image (proc2_0012: one 8 000-px background loop whose ordinary chain still crossed an exact primitive edge after
the polyline repair → emitted as `make_valid` parts with flattened curves, 1 126 → 5 304 nodes). After the run the valid
parts are thinned (DP 0.15 px, re-validated on the output grid): 5 304 → 3 675 nodes on that image (not re-run on all of proc2).
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

### B-7 Full runs (defaults: segment="ms", seg_premerge, routing B-4; code = commit d7f1949, `vectorizer/` unchanged
since) vs phase2-base re-run (`B_base_*`)
- tdev t_final (53): composite **0.702 → 0.724** (VTracer default 0.680), SSIM 0.796 → 0.818, ΔE 3.35 → 3.07,
  edge-F 0.865 → 0.882, LPIPS 0.185 → 0.169; every category ≥ base (cutfile +0.028, logo +0.021, poster +0.020,
  sticker +0.032, tshirt =, vector_flat +0.019 with median paths 11 222 → 3 334 and 1.32 MB → 393 KB); 22 images
  better, 3 worse (0040 −0.034, 0013 −0.008, 0007 −0.006).
- dev (130): **0.9044 → 0.9050**, all categories within tolerance, valid 100 %, gap 0 (per-category table in HANDOFF_B.md).
- tdev t_cut (53): composite 0.326 → 0.331; tiny islands 2.25 → 1.42, thin features 48.2 → 40.2, thin area
  81.7 → 69.1 mm², self-intersections 42.3 → 37.3, gz 81.7 → 68.1 KB (median), nodes 8 223 → 6 962; ΔE +0.5.
Honest limitation: 35/53 tdev outputs are still VTracer-like (photo engine) because on heavy texture the composite
prefers the 30 k-path stack; the clean region output for those images exists (print/cut intents, `seg_budget`) but
scores lower (tdev_small print: 0.654 vs 0.671 for the old run with fallbacks; 368 KB vs 1.2 MB, 1 176 vs 7 485 paints,
3 272 vs 8 262 tiny islands, overlap 0.10 vs 3.05).
## Phase 2 — stream C (classifier / presets / fallback / regressions / fast-vs-max)

### C-0 Setup
`eval/run.py` now also stores `st_preset`, `st_fallback`, `st_engine`, `st_n_regions`, `st_upscale` per item (needed for the
fallback / classifier analysis; no metric changed). New option `photo_fallback` (None = old behaviour: region-explosion
fallback only with preset "auto"; True/False force it) so that explicit presets can be evaluated with and without the
VTracer fallback.

### C-8 Diagnosis of the two phase-1 held-out regressions (disclosure: the diagnosis STARTED from test items
test_0013 and test_0048 — allowed only for diagnosis; the failure classes were then searched on dev, fixes validated on dev)
- **test_0013** (icon, colour-shift + JPEG q86; ours 0.851 vs tuned VTracer 0.882, 16 paths but 1 560 nodes, ragged
  outlines). Root cause, measured on the label map: the palette has 4 colours for a 2-colour icon — a pink *halo* band
  (L .957) on the light side and a darker *rim* band (L .52) on the dark side of every edge (JPEG ringing / chroma
  subsampling overshoot). They are 1-px bands fragmented into 154 small components. The AA sliver removal does not
  remove them because (a) they are not mixtures of the two sides (they overshoot: rim is 0.06 OKLab off the
  purple–cream segment, > radius 0.045) and (b) halo and rim are adjacent, so each band's main neighbour is the other
  band. Every shape then gets a jagged boundary through dozens of fragments.
  Same class on dev (thin components whose colour is < 0.09 OKLab from an adjacent label, counted after quantisation):
  dev_0028 (logo, jpeg; 90 such components, 4 colours for a 2-colour logo, 107 regions), dev_0005 (icon, noise; 52),
  dev_0029 (logo, noise; 192), plus JPEG line art / diagrams (dev_0092, 0097, 0118, 0089, 0108 ...).
- **test_0048** (flat_illustration emoji, JPEG q74; ours 0.805 = VTracer photo preset vs tuned VTracer 0.806). Root
  cause: classifier → "photo" (c90 = 24 colours > 13.5 because of JPEG noise, flat share 0.51 < 0.53) → the image never
  reaches the region engine. With preset logo/gradient the region engine scores 0.895 / 0.905 (9 KB instead of 134 KB).
  Failure class: compressed/noisy flat art classified as photo from colour-count features. On dev: dev logo→photo (1),
  gradient→photo (1). Fix belongs to the classifier work (C-5).

### C-8b Fringe clean-up (new module `vectorizer/pipeline/fringe.py`, option `fringe`)
Three approaches considered (RESEARCH.md stream C): (1) component-level *halo* model, (2) palette-level *edge-only
colour* model, (3) pre-quantisation edge restoration (shock filter) — rejected without prototype because it destroys
the AA coverage the sub-pixel boundary placement (exp_011) relies on; widening the sliver mixture test (quantize.py,
stream B) cannot catch the double fringe (each band's main neighbour is the other band, measured above).
First halo version marked both members of a pair of near-coloured thin components → erased thin dark connector
lines in diagrams (dev_0114 −0.054). Fixed by requiring the near partner to be a non-thin component.
Targeted dev items (14 items with the most near-colour thin components), composite base → halo / colour:
| item | cat (deg) | preset | base | halo | colour |
|---|---|---|---|---|---|
| dev_0028 | logo (jpeg) | icon | 0.900 | **0.961** | 0.963 |
| dev_0005 | icon (noise) | icon | 0.935 | **0.974** | 0.974 |
| dev_0075 | gradient (colorshift) | icon | 0.835 | **0.853** | 0.853 |
| dev_0023 | logo (rescale) | logo | 0.779 | **0.787** | 0.779 |
| dev_0097 | line_art (jpeg) | line_art | 0.761 | 0.722 | 0.598 |
| dev_0092 | line_art (jpeg) | line_art | 0.876 | 0.845 | 0.788 |
| dev_0089 | line_art (colorshift) | line_art | 0.778 | 0.766 | 0.540 |
| dev_0118 | diagram (jpeg) | line_art | 0.859 | 0.832 | 0.783 |
| dev_0065 | gradient (jpeg) | gradient | 0.856 | 0.848 | — |
On line art the thin bands ARE the content (JPEG splits a stroke into a dark core and a lighter edge colour), so the
clean-up is only applied to the flat presets: `fringe="auto"` = halo for icon/logo/flat_illustration, off for line_art /
diagram / gradient / photo. Halo is kept over colour (equal on flat items, more local, much less destructive when misapplied).
(test_0013 diagnosis item: 156 → 7 regions, 18.3 KB → 1.7 KB SVG.)

### C-9 Fast vs max (dev_small, categories with max mode; composite Δ vs fast base, gz bytes Δ)
| variant | icon | logo | flat_ill | line_art | diagram | bytes | prim_recovery |
|---|---|---|---|---|---|---|---|
| max (2× bicubic, corner arm ×2) | +0.006 | +0.003 | +0.001 | +0.007 | **+0.023** | +93…+193 % | −0.21…−0.25 |
| tight fit at 1× (fit_tol 0.3, line_tol 0.33) | +0.006 | **+0.004** | +0.000 | **+0.010** | +0.008 | +24…+63 % | ±0 |
| tight + smooth_sigma 0.5 | +0.003 | +0.002 | −0.003 | +0.008 | +0.007 | +39…+95 % | ±0 |
| fit_tol 0.45, line_tol 0.5 | +0.003 | +0.002 | +0.000 | +0.005 | +0.005 | +9…+28 % | ±0 |
Root cause of the max-mode gain (confirms phase 1 abl_015_up2s): for icon/logo/line_art it is the effectively halved
fit tolerance, which 1× tight fitting reproduces without 4× pixels, without the primitive loss and with ~⅓ of the
byte increase. Only diagrams gain from resolution itself (max − tight = +0.015): 1-px box outlines between a fill and the
background are lost at 1× and kept at 2× (dev_0117 +0.054, look: sheet). Max mode also has large losses on
colour-shifted / JPEG line art (dev_0084 −0.066, 10× bytes: staircased diagonals at 2×).

### C-5a Region-density fallback on tdev — the "pure noise" branch is the main loss (tdev_small, 18 items)
Diagnosis: the fallback has two outputs — VTracer with the tuned photo parameters, or, when `n_regions > 0.1·H·W`,
coarse "pure noise" parameters (filter_speckle 8, colour precision 6, layer difference 24) to bound the file size. With
the early bail-out the region count is taken *before* speckle merging, so halftone / screen-print / stencil AI art
(16–29 % of pixels start a new region) is treated as random noise: 6 of 18 tdev_small items, blotchy posterised
output (look: tdev_0024 sheet). Measured on dev / synthetic: real uniform noise has 0.62–0.65 regions/px
(256² and 1024²), dev photos ≤ 0.12, tdev art ≤ 0.22.
Per item (base = noise branch → tuned photo params): tdev_0000 0.481→0.559, tdev_0024 0.517→0.618, tdev_0039
0.543→0.639, tdev_0045 0.567→0.660, tdev_0048 0.590→0.673 (LPIPS 0.52→0.50, 0.49→0.39, 0.21→0.17, 0.33→0.28,
0.20→0.13; SSIM +0.06…+0.16; edgeF +0.07…+0.16); cost: 2–2.5× bytes (already in the zero-compactness range >1 MB)
and 2–3× nodes. Fix: new key `noise_density` (old 0.1) → 0.35 (between art ≤0.22 and noise ≥0.6).
Same bug on dev only through the classifier change below (dev_0120 photo, 0.117 regions/px when routed through the
region engine).

### C-5b Classifier "photo" → region engine first (`photo_route="try"`)
test_0048-class (JPEG'd flat art → photo). Instead of trusting colour-count features, a "photo" verdict goes to the
gradient preset and reaches VTracer only through the measured region explosion (cost = quantisation until the bail-out).
Dev items classified photo (12): dev_0029 (logo, noise) 0.758→**0.861** (143→16 KB), dev_0069 (gradient)
0.765→**0.866** (97→14 KB); all 10 real photos still end in the photo engine (2 729–18 124 regions) with identical
output once `noise_density` is fixed (dev_0120 −0.136 with the old 0.1 noise branch).

### C-9b Candidate fast/max split (dev_small; cand0 = fringe auto + photo_route try + noise_density 0.35)
cand1 = cand0 + `fit_profile="tight"` (fit_tol 0.3 / line_tol 0.33 at 1× for all graph content presets, not for cut):
ALL +0.005 vs cand0 (icon +0.006, logo +0.004, flat ±0, line_art +0.010, diagram +0.008, gradient +0.003; PSNR +1.3 dB,
ΔE −0.05, edge_dev −0.020, corner recall +0.006, primitives ±0; bytes +3 % overall, +24…+63 % on flat art).
cand2 = cand1 + mode="max" with 2× only for line_art/diagram (`max_presets`): vs cand1 line_art −0.003, diagram
**+0.015** (thin box outlines), bytes +61…+118 %, primitive recovery −0.21 (rects no longer detected at 2×).
Old max mode vs old fast (C_s_max): icon +0.006 / logo +0.003 / flat +0.001 / line_art +0.007 / diagram +0.023 at
+93…+193 % bytes → for icon/logo/flat the tight 1× profile gives the same or more for ~⅓ of the bytes and no
primitive loss.

### C-5c Cost of the classifier (dev_small, 44 items; all variants with fringe auto + noise_density 0.35 + fallback on)
Per-image oracle over the four preset families (FLAT = icon/logo/flat_illustration, LINES = line_art/diagram, GRADIENT,
PHOTO) vs auto (cand0):
| cat | auto | FLAT | LINES | GRADIENT | PHOTO | per-image oracle |
|---|---|---|---|---|---|---|
| icon | 0.9553 | 0.9553 | 0.9553 | 0.9341 | 0.8204 | 0.9553 |
| logo | 0.9351 | 0.9351 | 0.9304 | 0.9351 | 0.8393 | 0.9362 |
| flat_illustration | 0.9618 | 0.9618 | 0.9551 | 0.9618 | 0.8561 | 0.9619 |
| gradient | 0.8895 | 0.8833 | 0.8626 | 0.8869 | 0.8037 | 0.8920 |
| line_art | 0.9126 | 0.9134 | 0.9126 | 0.8947 | 0.8193 | 0.9152 |
| diagram | 0.8875 | 0.8786 | 0.8875 | 0.8783 | 0.7881 | 0.8890 |
| photo | 0.7609 | (all four fall back) | | | | 0.7609 |
| ALL | **0.9088** | 0.9067 | 0.9029 | 0.9009 | 0.8156 | 0.9100 |
True-category oracle (icon/logo/flat→FLAT, line_art/diagram→LINES, gradient→GRADIENT) = the FLAT/LINES/GRADIENT
columns of the matching rows: equal to auto within ±0.003 (auto is better on gradient). The remaining classifier
cost on dev is **0.0012** composite (per-image oracle), so "flat_illustration never detected" and "diagram → line_art"
cost nothing — they share presets. Decision: no learned family classifier (nothing to gain); keep the family
presets, the type labels are cosmetic. The cross-family error that does matter is "photo" on compressed flat art
(C-5b) — fixed by routing, not by a better classifier.

### C-5d Engine choice on tdev (region engine vs VTracer) — the real classification problem on the target set
tdev_small, region engine forced (FLAT preset, no fallback) vs VTracer photo preset, Δcomposite (region − VTracer):
region wins on strong-edge graphic art: tdev_0012 +0.130, tdev_0051 +0.082, tdev_0039 +0.060, tdev_0000 +0.046,
tdev_0021 +0.025, tdev_0006/0033/0042 (already region); VTracer wins on painterly / smooth-shaded images: tdev_0003
−0.125, 0036 −0.122, 0009 −0.125, 0018 −0.129, 0030 −0.083, 0015 −0.080, 0048 −0.068, 0045 −0.044, 0024 −0.038,
0027 −0.026. Post-clean region density does not separate them (tdev_0030: 2 718 regions, VTracer much better;
tdev_0039: 48 802 regions, region better); the early bail-out on the *pre*-clean count also sends items with only
928 (tdev_0051) / 12 345 (tdev_0012, density 0.0067 < 0.008) final regions to VTracer.
The classifier features separate them: VTracer-better items all have flat < 0.2 (c90 ≥ 67); region-better items have
flat ≥ 0.2 and ink_edge ≥ 0.4 (exception: tdev_0000, flat 0.187). Dev: all flat art has flat ≥ 0.27 except dev_0102
(diagram, noise, flat 0.127) — region better there, but it never explodes; dev photos have ink_edge ≤ 0.23.
New flag `graphic_override` (fitted on tdev_small + dev_small, 2 rounded thresholds; disclosed): when flat ≥ 0.2 and
ink_edge ≥ 0.4 the density fallback is disabled and only pure noise (`noise_density`) bails.

### C-10 Combined candidate on tdev_small (18 items, LPIPS + print/cut)
cand3 = fringe auto + photo_route try + noise_density 0.35 + graphic_override; vs phase2-base (C_ts_base):
composite 0.689 → **0.725 (+0.035)**, SSIM +0.042, PSNR +0.8 dB, LPIPS 0.182 → **0.157**, ΔE −0.41, edgeF +0.036; every
category improves (logo +0.050, sticker +0.040, vector_flat +0.032, poster +0.028, cutfile +0.019). Per item: noise
branch removed on tdev_0000/0024/0045/0048 (+0.077…+0.101), region engine kept on tdev_0012 (+0.101, 1.3 MB → 0.5 MB),
0039 (+0.107), 0051 (+0.080, 1.06 MB → 46 KB); only loss tdev_0033 −0.004 (fringe). Cost: paths +24 %, gz +14 %,
nodes / tiny islands up on the items that leave the coarse noise branch (they had been blotchy posterisations).
cand4 = cand3 + `fit_profile="tight"`: +0.001 more (region-engine items +0.003…+0.006), gz +2 %.
Per-image oracle over {base, VTracer photo params, region FLAT, region GRADIENT} on tdev_small = 0.735 → cand4 (0.726)
recovers 80 % of the oracle gap.

### C-9c Old max mode on tdev_small (phase2-base settings + mode=max): +0.032 — but not from resolution
Per item the gain sits exactly on the items the routing fixes address: the region counts are taken in *processed*
pixels, so at 2× the density falls below the thresholds — tdev_0000/0024/0039/0045 leave the coarse noise branch
(+0.07…+0.10, same as `noise_density`), tdev_0012/0051/0048 stay in the region engine (+0.14/+0.11/+0.05, same as
`graphic_override`), and tdev_0003 is wrongly kept in the region engine (−0.101). Region-engine items proper:
tdev_0021 +0.026, tdev_0033 −0.002. With the routing fixed (cand3/cand4 +0.035/+0.036 in fast mode) there is no
tdev argument for 2× on flat presets; decision unchanged (2× only for line_art/diagram).

### C-11 Full tdev with cand4 defaults (C_tfinal): +0.012 only (tdev_small: +0.036) → losses on unseen items, diagnosed
C_tbase 0.7023 → C_tfinal 0.7140 (SSIM +0.015, LPIPS −0.006, ΔE −0.14, edgeF +0.008; logo +0.020, cutfile +0.027,
poster +0.011, sticker +0.004, vector_flat **−0.009**). Gains as on tdev_small (tdev_0049 +0.118, 0039 +0.113, 0012
+0.105, 0024 +0.101, 0020 +0.093, 0045 +0.093, 0051 +0.086, 0048 +0.083, 0017 +0.081, 0000 +0.077). Losses, by cause:
- `photo_route="try"` on many-colour painterly images whose region count stays low (no fallback): tdev_0005 −0.077
  (c90 272, LPIPS 0.10→0.20), tdev_0050 −0.073 (c90 189).
- `graphic_override` on many-colour items: tdev_0040 −0.098 (c90 146, LPIPS 0.05→0.17), tdev_0028 −0.067 (c90 672);
  small: tdev_0013 −0.012 (c90 10).
- `fringe` on textured art: tdev_0010 −0.041 (47 colours, 56 608 px re-assigned).
All winners of the routing rules have c90 ≤ 74 (and the dev / test_0048-class items c90 ≤ 61); all losers c90 ≥ 146;
fringe's targets have ≤ 6 colours. Fix (thresholds now chosen on full tdev + dev — disclosed; ttest is the check):
`route_max_c90=100` gates photo_route "try" and graphic_override, `fringe_max_colors=16` gates the fringe clean-up.
Expected by construction: the 4 routing losers return to their phase2-base output (same engine and parameters).
Result (C_tfinal2 = new defaults, full tdev): composite 0.7023 → **0.7220 (+0.020)**, SSIM +0.024, PSNR +0.72 dB,
LPIPS 0.185 → **0.170**, ΔE −0.26, edgeF +0.018, GMSD −0.013; every category ≥ 0 (logo +0.020, sticker +0.029,
cutfile +0.031, vector_flat +0.012, poster +0.018, tshirt ±0); **no item loses more than 0.005**; 13 items gain
+0.012…+0.136. Cost: paths +18 %, gz +12 %, print/cut nodes +23 %, tiny islands +22 % (items leaving the coarse
noise branch / the bail-out now carry their real detail); self-intersections +26 per image (VTracer output).

## Phase 2 — integration (lead, branch `phase2/integration`)
Merge A → B → C onto phase2-base (EXPERIMENTS/RESEARCH/PLAN merged with git's union driver; one real code conflict in
`api.py`). Routing unified: B's MS path bails out on raw fragments (`seg_raw_bail` 0.06/px) and C's `graphic_override`
keeps strong-edge graphics in the region engine — merged so that graphic art uses C's `noise_density` (0.35) for B's raw
check as well, and a single "pure noise" density (`noise_density`, 0.35; C measured noise ≈ 0.6, AI art ≤ 0.22; B had 0.25)
serves both engines. B's region budget applies whenever the fallback is off. 81 tests pass.

### Ablation (each stream switched off on top of the others; full tdev 53 + full dev 130, 4 workers, machine otherwise idle)
| variant | tdev composite | dev composite | dev prim | dev corner rec | tdev gz KB |
|---|---|---|---|---|---|
| phase2-base | 0.702 | 0.904 | 0.466 | 0.822 | 1 778 |
| full A+B+C | 0.7239 | **0.9150** | **0.863** | 0.833 | 1 856 |
| − A (region_prims, rect_refine, blur_sharp, geom_repair off) | 0.7238 | 0.9129 | 0.475 | 0.802 | 1 857 |
| − B (segment=palette) | 0.7220 | 0.9145 | 0.852 | 0.843 | 1 995 |
| − C (fringe off, photo_route features, graphic_override off, fit default; noise_density 0.25 = B's value) | 0.7241 | 0.9076* | 0.834 | 0.838 | 1 868 |
\* dev −C was run with noise_density 0.1 (C's old value); on tdev that setting wrongly triggered B's coarse-noise branch
(0.6996), the corrected tdev −C row uses 0.25. dev is insensitive to it (no dev image reaches the noise branch).
Reading: on the target set B and C fix the same root cause (engine routing) — together they are not additive (each alone
+0.020/+0.022). C is what gives dev +0.007 (fringe clean-up, tight fitting, JPEG flat art), A is what gives the geometry
(primitives 0.48 → 0.86, self-intersections → 0) and +0.002 dev. **All three kept.**

### Integration fix: photo verdicts tried in the region engine
Per-category check vs phase2-base found one tdev regression: the only t-shirt item (tdev_0052, a photo of a person wearing
a printed shirt) −0.094. Interaction B×C: C's `photo_route="try"` sends a classifier "photo" to the region engine first;
B relaxed the raw-fragment bail-out from 0.032 to 0.06/px (for grainy cartoons), this photo's raw count lies between the
two and B's MS merge then keeps it compact → stays in the region engine. Fix (general): when the region engine is only
*tried* for a photo verdict, the raw bail-out keeps the phase-1 value `min(seg_raw_bail, 4·max_region_density)`.
Result: tdev 0.7239 → **0.7257** (t-shirt back to 0.760), **no dev image changed**.

### Speed (quiet machine, `python -m eval.bench --split test --n 30`, 1024 px, Xeon @ 2.10 GHz)
| version | median | p95 | max | quantize | fit |
|---|---|---|---|---|---|
| phase2-base | 2.10 s | 2.90 s | 3.00 s | 1.18 s | 0.60 s |
| integration | 1.48 s | 2.51 s | 3.48 s | 0.75 s | 0.44 s |
| + Schneider reparameterisation 3 iterations with stall test (fit −25 % on dev_small, SSIM +0.0001, nodes +0.5 %) | **1.45 s** | **2.30 s** | 2.69 s | 0.78 s | 0.45 s |
Target ≤ 1.2 s median **not reached**: B cut the quantize core by ~48 %, but the new quality stages (MS merge ~12 %,
fringe, region primitives ~1.4× fit work on line art/diagrams, tight fitting more splits) spend part of it again; the
rest of the time is spread over ~10 steps of 0.05–0.15 s with no single hotspot. Next steps would be a compiled
(numba/Rust) crack-graph + fitter or a fully vectorised multi-segment Bézier fit.

### Metric changes (stream A's proposals, applied identically to all methods)
- `corner_err` = distance from the output's Harris peak to the GT render's own Harris peak in the same disc (the nominal
  vertex is not where any detector peaks; GT vs itself gave 0.44–1.15 px). The old value is kept as `corner_err_nominal`.
- print/cut `self_intersections`: a closed subpath whose last point repeats the first within 1e-6 is not counted (relative /
  arc commands end ~1e-13 px from the start → false GEOS hits).
All held-out numbers below are computed with these definitions; phase2-base outputs are re-scored from their saved SVGs.

### Print preset cost (tdev only; ttest timings were under 4-worker contention)
Profile (tdev_0003 / 0040 / 0022, 1 thread): 41 / 27 / 7.6 s; the print preset forces the region engine with the MS
region budget (`seg_budget` 0.004/px ≈ 4 200 regions at 1024²) on textured AI art → 2–4 k regions, 5–10 k chains:
fit 8–16 s, region primitives 2–12 s (polygon greedy search + rounded-rect fits), quantize 2–6 s.
- Exact speed-up (commit cd34538): memoised per-run line fits / run directions in `fit_polygon` (the greedy vertex removal
  re-fitted the same runs O(corners²) times). SVG output byte-identical on all three images; region_prims −15…−30 %.
- Region budget alternative (tdev_small, 18 items, 3 workers): 0.004 → composite 0.6548, median 38.1 s; 0.002 → 0.6286
  (−0.026), median 28.2 s (−26 %). **Rejected**: the fidelity loss is larger than the time gain is worth for an offline
  print export. Print stays slow on heavily textured art (documented limitation); it is fast on flat art (tdev_0022 7 s).

### Final held-out evaluation (all methods scored with the same code; per-item rows in eval/runs/<exp>/<split>/)
Target set **ttest** (67 CC0 DALL-E 3 images, never used for tuning):
| method | composite | SSIM | PSNR | LPIPS ↓ | ΔE mean | edge-F | paths | gz KB |
|---|---|---|---|---|---|---|---|---|
| VTracer default | 0.6541 | 0.762 | 22.0 | 0.207 | 5.09 | 0.854 | 10 839 | 2 549 |
| VTracer tuned (oracle category) | 0.6731 | 0.781 | 23.5 | 0.193 | 4.27 | 0.848 | 13 462 | 2 434 |
| phase2-base | 0.6936 | 0.793 | 25.0 | 0.192 | 3.42 | 0.846 | 13 607 | 2 098 |
| **final (auto)** | **0.7054** | **0.807** | **25.5** | **0.187** | **3.22** | 0.850 | 16 709 | 2 271 |
| final `print` | 0.6251 | 0.745 | 24.8 | 0.251 | 4.06 | 0.700 | 2 538 | 587 |
| final `cut` (≤ 8 colours, background dropped — fidelity not the goal) | 0.3280 | 0.471 | 11.1 | 0.552 | 20.8 | 0.425 | 36 | 81 |
final vs phase2-base per item: 16 better (> +0.01), 4 worse (< −0.01: ttest_0055 −0.095, 0020 −0.068, 0030 −0.065,
0029 −0.048; not investigated/tuned — held out), final beats tuned VTracer on 44/67 items; per category it loses only on
poster (0.7035 vs 0.7184) where VTracer's tuned gradient parameters stay better.
Print/cut readiness (ttest means; auto = 34/67 VTracer fallback):
| metric | VTracer tuned | final auto | final print | final cut |
|---|---|---|---|---|
| open subpaths | 0 | 0 | 0 | 0 |
| self-intersections / image | 71.8 | 55.7 | 0.19 | **0** |
| overlap ratio (stacked area / canvas) | 3.15 | 3.66 | 0.10 | **0.00** |
| distinct colours | 12 442 | 14 502 | 1 419 | **6.8** |
| tiny islands (< 0.5 mm at 100 mm width) | 15 595 | 18 433 | 5 646 | **2.7** |
| thin features (< 0.5 mm, opening test) | 6 270 | 8 437 | 773 | **37** |
Dev **test** (130, phase-1 held-out): final 0.9143 vs phase2-base 0.9012, tuned VTracer 0.8170, default 0.7979;
primitive recovery 0.775 (base 0.417), corner recall 0.745 (base 0.773), corner err 0.363 px (base 0.408).
Overfitting check **proc2** (60 procedural scenes, new seed 777 and parameter ranges): final 0.8897 vs tuned VTracer 0.7957
(+0.094; the phase-1 gap on the old procedural scenes was +0.10) → the gain transfers to unseen generator settings.

### Independent review (REVIEW_PHASE2.md, fresh subagent) and what was done
| finding | action |
|---|---|
| B1 `colors=N` ignored (MS engine appends region mean colours; tdev_0044 colors=2/4/6 → 32/43/47 fills) | fixed: an explicit colour count is passed to the MS paint cap (`reduce_paints`), as for cut; test `test_explicit_colors_is_a_cap` |
| B2 shapely imported at run time by `geom_repair` (default on) but declared "eval only"; its wheel bundles GEOS (LGPL-2.1, checked in `LICENSE_GEOS`) | shapely moved to an optional `geometry` extra (`requirements-geometry.txt`); without it `vectorize()` runs, skips the repair and reports `stats["geom_repair"]`; test with shapely import blocked. All numbers were measured *with* the extra |
| M1 ttest gain is from VTracer parameters, not the region engine | confirmed and reported as such: all of +0.012 vs phase2-base comes from items whose fallback left the coarse "pure noise" VTracer parameters (C-5a); the region-engine items newly kept by the routing average −0.046 (the 4 large ttest regressions). 53/67 ttest outputs are VTracer (34 through the region-explosion fallback, 19 classified photo); "34/67" above counted only the former |
| M2 VTracer baseline tuned on dev (not on the target), pipeline downsizes to 1024 px in the VTracer path | baseline kept as is (stated); the 1024 px cap was tested on tdev (below) |
| M3 photo regression on test (test_0126 −0.083, test_0122 −0.067: `photo_route="try"` keeps them in the region engine with 28/120 regions) | **not fixed** (held-out). A label-map reconstruction-error gate was tried on tuning data only: winners (dev_0029/0069, q_err 1.6/1.9) and losers (tdev_0005/0050 with the c90 gate lifted, 2.3/2.5) — 4 points, and good region-engine tdev art has q_err up to 4.5 → no separable threshold on tuning data; code removed. Reported as a limitation |
| M4 cut: background kept when ≥ 95 % of the canvas; near-identical blacks as separate layers; fill-opacity; "thin features removed" | fixed: background dropped whenever anything else remains; paints closer than CIE76 ΔE 6 merged (OKLab exaggerated near-black differences: L 0.009 vs 0.06); `opaque` for cut; README now says thin features are *reduced* and a colour may be several elements |
| M5 `print` below VTracer fidelity, slow, "full fidelity" claim | README corrected (clean layered output, lower fidelity than auto, 10–40 s on textured 1024 px); budget alternative measured above (rejected) |
| M6 proc2 used during development by stream A (fix motivated by proc2_0012, commit 0b2bf17) | disclosed: proc2 is not a pristine held-out set; the overfitting check rests mainly on the generator-level shift (new seed + ranges) and on test |
| minor: figure-8 loops, tiny images in cut, timing columns of re-scored phase2-base, sheets vs tuned VTracer | documented; tiny-image cut background fixed by the background rule |

### VTracer-path working size (review M2; tuning data only)
The photo engine (classifier "photo" and the region-explosion fallback) worked at ≤ 1024 px (phase-1 speed choice for
3000² photos). DALL-E art is 1024² or 1792×1024, i.e. the 1792 px items were traced at 57 % resolution.
tdev (53, 4 workers), `max_side`/`photo_max_side` 2048 vs 1024: composite 0.7257 → **0.7415 (+0.016)**, LPIPS 0.167 → 0.147,
SSIM 0.821 → 0.841; 9 of the 18 large items change, each +0.080…+0.115, no item loses; gz bytes +39 %, time +12 %.
dev: identical (no dev image > 1024 px). Cost on a pathological 3000² texture (tdev_0008 upscaled, 430 k regions):
1024 → 38 s / 13 MB, 2048 → 163 s / 56 MB, **1792 → 121 s / 43 MB**. Adopted: photo preset `max_side=1792` (= DALL-E's
native long side; larger inputs are still capped).

### Held-out re-run after the review fixes (second and last ttest pass; test / proc2 unaffected: no image > 1024 px, auto path unchanged)
ttest final (auto): **0.7273** (SSIM 0.834, PSNR 26.1, LPIPS 0.161, ΔE 2.99, edge-F 0.877, gz 3.25 MB, median 20 s under 4 workers);
vs tuned VTracer 0.6731 → wins 50/67 items (before: 44); vs phase2-base: 31 better, the same 4 worse (region-engine items).
ttest cut: 0.3245 (fidelity not the goal); self-intersections 0, overlap 0.00, colours 6.6, tiny islands 2.6, thin features
36 (median 25), no fill-opacity. Core install without shapely (geometry repair off), dev: 0.9153 vs 0.9151, prim 0.860 vs 0.863.
Fresh clone: core requirements → 69 passed, 2 skipped (shapely tests); + geometry extra → 85 passed; CLI ok.
