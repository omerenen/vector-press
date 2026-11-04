# PLAN — vector-press (raster → SVG engine on top of VTracer)

Resume protocol: `git pull`, read this file and `EXPERIMENTS.md`, rebuild data with
`python -m data.build` (deterministic), then continue with the first unchecked item.

Environment measured: Intel Xeon @ 2.10 GHz, 4 vCPU, 15 GB RAM, no GPU, Python 3.12 venv.
Blocked hosts (logged): download.pytorch.org, huggingface.co → LPIPS backbone weights unavailable;
LPIPS is computed only when the weights are already in the torch cache (`eval: lpips: true`).

## Milestones
- [x] M1  env, dataset builder (dev/test, 130 images each, 7 categories), metrics, runner, contact sheets, baseline exp_000
- [x] M1b per-category VTracer grid search (exp_001_baseline_tuned)
- [x] M2  preprocessing & quantization (W1, W2): OKLab palette, AA-aware assignment, speckle merge
- [x] M3  geometry (W3–W5): shared boundary graph (done v0), corners, curves, primitives, gaps
- [x] M4  gradients (W6), centerline (W8), classifier + presets (W7)
- [x] M5  research extras (subpixel refinement, arc fitting, optional learned parts)
- [x] M6  final held-out test evaluation, independent review, fresh-clone test
- [x] M7  API/CLI polish, README (TR), REPORT (TR), LICENSES

## Architecture (current)
load → quantize (OKLab palette, mixed-pixel aware) → region labels → crack-lattice boundary graph
→ per-chain fit (corners, lines, Schneider Béziers, ellipse/rect/rounded-rect primitives)
→ stacked drawing with filled holes + seam strokes → compact SVG.
VTracer is used for photo/posterize mode and as a fallback engine (`engine="vtracer"`).

## Status (final)
All milestones done; final numbers in REPORT.md (held-out test: composite 0.901 vs 0.817 tuned VTracer).
Remaining ideas if work resumes: arc fitting for partially occluded circles, alpha-gradient fills, JPEG thin-line
continuity (crossings), faster quantisation for the 2 s stretch goal, photo mode beyond VTracer.

Status (phase 2, done): integration merged to main as best-v5. Results and limitations: REPORT.md (Turkish), review:
REVIEW_PHASE2.md. Parallel plan executed as written (3 streams, no fallback to 2/sequential needed). Open items for a next
phase: per-image engine choice (render both / learned quality predictor), compiled boundary graph + fitter for the 1.2 s
target, faster print preset on textured art, real user target set + vectorizer.ai comparison (data/target).
