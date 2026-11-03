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

## Phase 2 — stream C
### Edge fringes on degraded flat art (work item 8)
- **Component halo model** (own): thin component (2·area/perimeter < 1.6 px, < 1 % of the image) whose colour is within
  0.09 OKLab of an adjacent *non-thin* component is an overshoot band of that surface; its pixels are re-assigned per
  pixel to the most similar label within 3 px, then specks are merged. Decision: **kept** for the flat presets
  (`fringe="auto"`), see EXPERIMENTS C-8b.
- **Palette edge-only colour model** (own): drop a palette colour whose pixels never survive a 3×3 erosion and that is
  within 0.09 of an adjacent colour. Same gain on flat art, but on line art it deletes whole stroke colours (dev_0089
  −0.24, dev_0097 −0.16) → rejected (kept as `fringe="colour"` for experiments).
- **Pre-quantisation edge restoration** (shock filter, Osher & Rudin 1990; Kuwahara/mode filters): would remove the
  fringe colours before palette extraction, but also removes the anti-aliasing coverage that the sub-pixel boundary
  placement (exp_011) reads → not prototyped.
- **Wider sliver mixture test** (quantize.py): cannot see double fringes (each band's main neighbour is the other band) →
  rejected on the diagnosis data.
