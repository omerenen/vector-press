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

## Phase 2 plan (2026-11-03)
Step 1 (lead, sequential, done → tag `phase2-base` = 3117d48, also pushed as `main`): target benchmark from CC0 DALL-E 3
images (`tdev` tuning / `ttest` held-out), `proc2` overfitting set, LPIPS, print/cut metrics, `cut` / `print` presets.
Step 2 (parallel, 3 subagents in git worktrees from phase2-base, rules in PHASE2_BRIEF.md, 1 thread each, full evaluations
serialised with `flock /tmp/claude-0/fulleval.lock`, timings invalid during this step):
- A `phase2/A` (/home/user/vp-A): primitives (item 3), corner accuracy (item 4), geometry validity (self-intersections).
- B `phase2/B` (/home/user/vp-B): segmentation of textured AI art (region explosion → photo fallback on 37/53 tdev
  images), gradients (item 6), quantize speed (item 7).
- C `phase2/C` (/home/user/vp-C): classifier + fallback (item 5), regressions test_0013/test_0048 (item 8), fast vs max (item 9).
Fallback rule: if 3 parallel streams prove too slow/unstable, drop to 2 parallel or sequential and note it here.
Step 3 (lead, sequential): merge A/B/C into `phase2/integration`, full evaluation (target first), ablation of each stream on top
of the others, keep only winning combinations, speed measured once alone, independent review, merge to main, best-vN.
Status (phase 2, done): integration merged to main as best-v5. Results and limitations: REPORT.md (Turkish), review:
REVIEW_PHASE2.md. Parallel plan executed as written (3 streams, no fallback to 2/sequential needed). Open items for a next
phase: per-image engine choice (render both / learned quality predictor), compiled boundary graph + fitter for the 1.2 s
target, faster print preset on textured art, real user target set + vectorizer.ai comparison (data/target).
