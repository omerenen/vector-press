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
