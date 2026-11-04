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

## Phase 2 — stream A (primitive fitting, corners, geometry validity)

### Primitive recovery: why shapes were lost, and the alternatives considered
Diagnosis (EXPERIMENTS A-1): 54 of 64 dev failures were *detection* failures — the shape's outline is a single loop of
one region but split into several chains by junctions (fragmented thin strokes, shapes lying on other shapes,
connectors). Fitting is per chain, so the shape identity is lost before any primitive test runs.
- **(a) Region-loop model fitting + chain snapping (chosen).** Concatenate the samples of all chains of a region's outer
  loop, run model selection on the whole outline, then replace each chain by the exact sub-path of the primitive between
  its junctions and move the junctions onto the outline for every incident chain. Keeps the shared-boundary (watertight,
  cut-consistent) property, works for every primitive type, cost ∝ number of multi-chain loops. Classical "fit to the
  region, not to the edge fragment" idea (cf. region-based shape fitting in graphics recognition; own implementation).
- **(b) Merge fragments in the label map** (absorb thin/small regions along strokes before graph construction): fixes only
  the diagram case, changes segmentation (stream B's area) and cannot help shapes overlapping other shapes. Not pursued.
- **(c) Arc/line fitting of open chains + chain merging by G1 continuity at junctions**: recovers partially occluded
  circles too, but the junction vertices stay (polygon vertex count wrong), and arcs of the same circle fitted per chain
  disagree slightly → no single primitive. Not pursued (occluded shapes are also not GT primitives).
- **Robust model refinement**: bbox / convex-hull initialisation of rects is pulled by single outlying samples (junction
  bumps, JPEG specks). Alternatives: RANSAC on the four sides (needs side assignment, unstable for rounded corners),
  trimmed least squares, **soft-L1 IRLS Gauss–Newton on the signed distance (chosen; 2–3 ms per fit)**. scipy
  `least_squares` gave the same results but was 4× slower (finite-difference overhead).
- **Polygon / star model**: corners at a permissive angle (25°, regular octagons turn 45°), collinear-run merging
  (staircase noise), then greedy vertex removal while the robust error stays ≤ prim_tol and grows ≤ 0.1 px
  (an MDL-style model-order selection), vertices = TLS line intersections. A Douglas–Peucker-first variant needs a
  tolerance that is wrong either for blurred star tips or for noisy edges.
- **Sharp vs rounded corners under blur**: the iso-contour of a blurred sharp corner is rounded (apparent r ≈ 1.9σ), so the
  fitted radius alone is biased. Tried (1) **mass-preserving radius from anti-aliased coverage** (blur-invariant in theory:
  r² = (corner deficit − 2Lk + k²)/(1 − π/4)): too noisy on real inputs (±2 px at r = 0 even on clean images, 3rd colours in
  the window) → rejected; (2) radius correction r² − (cσ)²: hurts true small radii; (3) **scale-aware model selection
  (chosen)**: measure the edge spread σ of the same rectangle (erf fit to the unmixed coverage profile across its sides) and
  prefer the sharp model when r_fit < 3.8σ and the sharp model is acceptable (3.8 ≈ 2 × 1.9σ; dev: separates 5/5 blurred
  sharp boxes from all but one real r = 2.5 px corner).

### Corners
The official corner error is measured from the nominal GT vertex; the Harris peak of a perfect corner is 0.4–1.15 px away
from it (GT-vs-GT floor), so the metric cannot reach 0.5 px. Alternatives for real corner accuracy: sub-pixel corner
localisation from intensities (Förstner), line–line intersection (already used: TLS lines + intersection), primitive
snapping (exact corners for rect/polygon outlines, chosen as a by-product of A-3). Proposed metric fix in HANDOFF_A.md.
Prototyped a **line-pair corner detector** (straight TLS arms on both sides of a sample outside a 2-px blur zone, corner
= their intersection; vectorised with cumulative moments) to recover blurred obtuse corners: diagram PSNR +0.6 dB but
overall corner recall −0.10 (false corners on gentle curves / stroke ends) → rejected, kept as `corner_lines=False`.

### Geometry validity
Self-intersections in our output have four causes (EXPERIMENTS A-4): float noise of relative path coordinates at the closing
point (metric false positives, ~45 %), zero-area loops of tiny regions, lattice pinch vertices, and genuine curve
crossings near junctions. Alternatives: constrained Bézier fitting (control points inside the chain's lattice corridor:
needs a QP per segment), crossing detection + local refit (chosen: polylines through the sub-pixel samples, then raw
crack midpoints, whose ring is simple by construction), clipping the output with a polygon boolean library (shapely
`make_valid`/buffer(0): changes topology and breaks shared borders). Pinch vertices are split into separate rings.
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
### Classifier / engine choice (work item 5)
- **Better hand features / learned family classifier** (depth-limited tree or logistic regression on dev features):
  not pursued — the per-image oracle over the four preset families is only +0.0012 above auto on dev_small, and the
  type labels that are "wrong" (flat_illustration, diagram) share presets. Nothing to learn.
- **Measured routing instead of predicted routing** (`photo_route="try"`): a classifier "photo" goes to the region
  engine and reaches VTracer only through the measured region explosion — uses the actual cost signal; kept.
- **Region-density fallback** (existing): density is a cost proxy, not a quality predictor — on tdev the region engine
  wins at 48 802 regions and loses at 2 718. The pre-clean early bail-out further mislabels halftone/stencil art as
  noise. Replaced by: noise-only bail for strong-edge graphics (`graphic_override`, features flat ≥ 0.2 and
  ink_edge ≥ 0.4) + a noise threshold (`noise_density` 0.35) that separates real noise (0.6 regions/px) from art (≤ 0.22).
- **Tiny learned engine selector** (logistic regression on the 10 classifier features, LOO-CV on tdev_small + dev_small):
  considered; with 18 target items two rounded thresholds are as expressive as the data supports — revisit when
  the full tdev region-engine runs exist (open problem in HANDOFF_C).
### Fast vs max (work item 9)
- **Plain 2× bicubic processing** (old max): gains = halved effective fit tolerance (+ diagrams' 1-px outlines), at
  +93…+193 % bytes and −0.21 primitive recovery.
- **Tight 1× fitting** (`fit_profile="tight"`, fit_tol 0.3 / line_tol 0.33): same gain on icon/logo/line art without
  4× pixels; cost proxy: only the fit stage does more work (+25…+100 % nodes), quantisation / graph unchanged.
- **Selective 2× for line art / diagrams only** (`max_presets`): keeps the diagram gain (+0.015 over tight).
- **Region-selective upscaling of thin structures / adaptive tolerance by local feature size**: would need per-chain
  tolerances inside fit.py (stream A) or a thin-structure mask in quantize (stream B); not prototyped — listed as
  open problem (target: the dev_0117-type 1-px box outlines lost at 1×).
