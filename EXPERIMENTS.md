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
