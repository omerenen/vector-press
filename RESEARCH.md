# RESEARCH — candidate methods and decisions

Format: what · source · license · expected benefit · CPU feasibility · decision (tried → see EXPERIMENTS.md).

## Tracing backbone & topology
- **VTracer** (visioncortex) — hierarchical colour clustering + path walking + spline fitting. github.com/visioncortex/vtracer,
  MIT. Fast (Rust). Weaknesses measured in exp_000 (AA halos, staircase on alpha, colour drift, wobbly curves).
  Decision: baseline; kept as `engine="vtracer"`/`"vtracer_raw"` and as the speed fallback. exp_003 showed that feeding it a
  clean palette helps (+0.033) but our own boundary graph is much better (+0.078).
- **Shared boundary graph / planar map vectorisation** (classic: crack-edge lattice, junction-split chains; used by
  Potrace-style tracers and "Vector Magic"-type tools; cf. Selinger 2003 for polygon optimisation). License: own
  implementation from first principles (no GPL code consulted/copied). Benefit: each border fitted once → zero gaps (W5).
  Decision: **implemented** (`pipeline/boundary.py`), core of the engine (exp_002+).
- **Potrace** — GPL-2.0 → not used, not linked (license rule).

## Curve fitting / corners
- **Schneider, "An Algorithm for Automatically Fitting Digitized Curves" (Graphics Gems, 1990)** — least-squares cubic
  with Newton reparameterisation and recursive splitting. Public algorithm. Decision: **implemented** (`fit.py`).
- **Raph Levien — near-optimal cubic fitting by matching signed area & moments; Euler-spiral intermediate**
  (raphlinus.github.io "Fitting cubic Bézier curves", kurbo `fit.rs`, Apache-2.0/MIT; arXiv 2405.00127 "GPU-friendly
  Stroke Expansion"). Benefit: fewer segments at equal error. Cost: quartic solves per segment in Python.
  Decision: **deferred** — our size is already 3× smaller than VTracer; the measured bottleneck is fidelity of boundary
  *placement* (fixed by sub-pixel refinement), not segment count.
- **Scale-consistent corner detection** (turning angle at arm length k vs 2k) — own; standard idea from curvature
  scale-space (Mokhtarian & Mackworth). Decision: **implemented**, plus TLS line snapping and line–line corner refinement.
- **Primitive fitting**: Fitzgibbon et al. 1999 direct least-squares ellipse fit (public algorithm); rounded rectangle by
  min-area rectangle + signed-distance radius search (own). Decision: **implemented** with robust acceptance (exp_006/007).
- **Arc splines / circular-arc fitting of open chains** — would raise primitive recovery for partially occluded circles.
  Decision: **not done** (time); listed as limitation.

## Sub-pixel / anti-aliasing
- **vectorizer.ai public description**: "deep learning networks + classical algorithms", "places boundaries according to
  the anti-aliasing pixel values", "teases out features less than a pixel wide" (vectorizer.ai home page; marketing text
  only, no code). Benefit: sub-pixel edge accuracy. Decision: **implemented our own coverage-unmixing edge placement**
  (exp_011, +0.006 composite, primitive recovery +0.095) and **thin-line ridge rescue** (exp_005).

## Colour quantisation
- **OKLab** (Björn Ottosson 2020, public-domain formulas) — perceptual distance. Decision: **used**.
- **Median-cut / k-means / Wu quantiser** — generic; they place colours *between* clusters for AA pixels. Decision: replaced
  by histogram mode-seeking on non-mixed pixels + weighted k-means refinement + AA-aware assignment (exp_002) +
  mixture suppression (preset-dependent, exp_005) + sliver removal (exp_007).
- **Edge-preserving smoothing**: bilateral (Tomasi & Manduchi 1998), guided filter (He et al. 2010), non-local means,
  Lee's sigma filter (1983). Decision: **sigma filter implemented** (exp_010: +0.006, every category improves); bilateral/NLM
  skipped (slower, the sigma filter already gives the gain at ~0.1 s / MP).

## Gradients
- **Segmentation-guided Layer-wise Image Vectorization with Gradient Fills** (Zhou et al., ECCV 2024, arXiv 2408.15741) —
  LIVE-style differentiable optimisation with radial gradients. GPU minutes per image → not feasible in the 5 s budget.
  Idea reused: gradient-aware segmentation. Decision: **own CPU method** — soft-boundary band grouping + linear/radial
  multi-stop fit with acceptance test (exp_008, gradient category +0.012).

## Differentiable rendering refinement
- **DiffVG** (Li et al. 2020, Apache-2.0), **LIVE** (CVPR 2022, Apache-2.0), **Optimize & Reduce** (2023),
  **SAMVG** (2023), **Bézier Splatting** (Liu et al., NeurIPS 2025, arXiv 2503.16424: 30×/150× faster forward/backward
  than DiffVG, still reported on an RTX 4090, ~3 min per image). CPU feasibility: no (minutes per image even with
  splatting); pydiffvg also needs a native build. Decision: **skipped**; a short CPU refinement of colours only would
  bring little because palette colours are already medians of pure pixels (ΔE ≈ 0.3 on clean flat art).
- **Layered Image Vectorization via Semantic Simplification** (arXiv 2406.05404, 2024) — diffusion-based; GPU, model
  weights; not feasible. Skipped.

## Learned components
- **Real-ESRGAN / ESRGAN** (BSD-3 code; weights BSD-3 from GitHub releases) for W1 clean-up/upscaling: ~seconds per MP
  on CPU for the full model; HuggingFace/PyTorch hubs are blocked here, GitHub releases are reachable. Decision: **not
  pursued** — the heuristic chain (sigma filter + mixed-pixel-aware palette + ridge rescue + sliver removal + sub-pixel
  placement) already reaches SSIM ≈ 0.98 on degraded flat art; the remaining error is dominated by colour-shift
  degradations (cannot be undone without a reference) and photos. No data-driven reason to train a model yet (§4 rule).
- **LPIPS** (BSD-2) for evaluation: the AlexNet backbone weights are only on download.pytorch.org / HuggingFace, both
  blocked (HTTP 403) in this container → LPIPS is optional (`lpips: true` in a config) and GMSD + MS-SSIM are used as
  weight-free perceptual metrics.

## Commercial tools (ideas only)
- **Vector Magic / vectorizer.ai** (same authors): segmentation → shared boundaries → curve fitting with corner
  detection; "stacked" vs "cutouts" output, gap filler strokes. Our seam strokes and stacked-with-filled-holes model
  are the same family of ideas, implemented from scratch.
- **Adobe Image Trace / Inkscape Trace Bitmap** (Inkscape uses Potrace, GPL) — presets per content type (logo, sketch,
  photo) → mirrored by our classifier + presets.

## Phase 2 — stream B

Problem: textured AI art (DALL-E 3: generator noise, paper grain, halftones, painterly shading) makes the palette +
fixed-area speckle-merge stage explode (diagnosis in EXPERIMENTS.md B-0). Alternatives considered for the segmentation
stage (screened on the raster level = mean-colour render vs input at equal boundary length, then full pipeline):
- **Piecewise-constant Mumford–Shah / Potts region merging on the region-adjacency graph** (Koepfler, Lopez & Morel,
  "A multiscale algorithm for image segmentation by variational method", SIAM J. Numer. Anal. 1994; Mumford & Shah 1989).
  Own vectorised implementation (numpy, parallel "nearest-neighbour stars" per round instead of a priority queue).
  Merge cost = colour SSE increase vs λ·shared boundary → scale aware, boundary length is also the SVG cost driver.
  Decision: **implemented** (`pipeline/segment.py`, `segment="ms"`); best rate–distortion on the screening set.
- **Piecewise-affine Mumford–Shah** (same energy with an affine colour model per region, ridge-regularised slopes): smooth
  shading is no longer cut into contour bands; each region with a significant slope becomes a `linearGradient` if the
  SSE reduction pays for ~60 px of boundary. Raster screening tdev_0030: fid 0.739→0.760 at −18 % boundary length.
  Decision: **implemented** (`seg_model="affine"`, `gradients.affine_fills`).
- **Felzenszwalb–Huttenlocher graph segmentation** (IJCV 2004, scikit-image BSD-3): alone it leaks/fragments (worse
  rate–distortion than the current stage); as a fine over-segmentation before MS merging it is on par with the palette
  over-segmentation (better at high detail on 3/6 screening images). Kept as option `seg_init="fz"`.
- **SLIC superpixels** (Achanta et al. 2012, scikit-image): compact-shape prior fights thin structures; clearly worse.
  Rejected.
- **L0 gradient minimisation** (Xu, Lu, Xu & Jia, SIGGRAPH Asia 2011) as edge-preserving pre-smoothing for the palette
  stage: no better than MS and ~25 s/MP with FFT solves. Rejected.
- **Learned edge detectors (TEED / DexiNed class, MIT licensed)** to modulate the boundary price: the MS energy already
  separates real edges from texture on the screening set; a learned edge map would need ~1 s/MP extra on CPU and the
  remaining loss on heavy texture comes from the metric rewarding texture reproduction (VTracer stacks 30 k paths), not
  from misplaced boundaries. Not pursued (no data-driven reason); `ms_merge(edge_weight=...)` is the hook for it.
- **Routing between region engine and photo engine**: region density after MS (rejected: MS merges smooth photos into
  few regions), residual texture energy / boundary length (rejected: no separation on tdev_small), phase-1 post-clean-up
  count + raw fragment count (kept, B-4). A per-image rate–distortion estimate of both engines would be principled but
  needs a VTracer run + render per image (2–4 s) → not done.
- Winner: MS (const) + phase-1 pre-clean-up + palette snapping as the default segmentation (tdev 0.702 → 0.724, dev
  0.9044 → 0.9050, full runs); piecewise-affine and Felzenszwalb initialisation stay options (mixed results, B-5).
