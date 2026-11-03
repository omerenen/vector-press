# Phase 2 — brief for the parallel work streams (A, B, C)

Base: tag/branch `phase2-base` (see EXPERIMENTS.md "PHASE 2"). Each stream works in its own git worktree and branch,
commits often and pushes its branch (`git push -u origin <branch>`). Integration is done afterwards by the lead.

## Use case and primary score
AI-generated posters, illustrations, sticker / t-shirt designs and cut-file artwork → print-ready and cut-ready vectors.
**Primary score: target benchmark** = DALL-E 3 images (CC0), splits `tdev` (tuning, 53 images) and `ttest` (held-out,
67 images, **never tune on it, never look at per-image ttest results while developing**). Secondary: phase-1 `dev`
(tuning) / `test` (held-out), and `proc2` (procedural overfitting check, treat as held-out).
Composite score definition is fixed (eval/metrics.py `composite`); report individual metrics too, plus LPIPS and the
print/cut metrics (`printcut: true` in a config) where relevant.

## Rules (same as phase 1, plus "rethink, don't just tune")
1. Root cause first, with data (profiling, failure analysis on worst cases, contact sheets you actually look at). Write the
   diagnosis in your EXPERIMENTS section **before** changing code.
2. For every problem list at least 2–3 genuinely different algorithmic approaches (classical, optimisation-based, learned,
   hybrid — e.g. RANSAC / robust fitting, global model selection, sub-pixel edge models, graph/superpixel segmentation,
   region-adjacency-graph merging, multi-resolution, a tiny learned model). Prototype the most promising ones, compare
   head-to-head with the current stage on the relevant metrics AND quality-relevant counts, keep the winner even if it
   replaces a whole stage. Record alternatives + numbers + why the winner won in your RESEARCH section.
3. Keep the old path behind a flag until the new one wins. Never break the regression tests (`python -m pytest -q`).
   Add unit tests for new core logic.
4. Tolerances for "no regression": composite −0.002, SSIM −0.002, ΔE +0.05, edge_f −0.005, gap_px must stay 0, valid SVG
   rate 100 %, on every phase-1 category of `dev` and on `tdev`.
5. Licenses: only MIT / Apache-2.0 / BSD / ISC / CC0 / OFL / CC-BY code, weights and data, verified from the primary
   source; record in your HANDOFF (lead updates LICENSES.md). No GPL/AGPL, no non-commercial data or weights.
   Learned components allowed (CPU, small, shippable, ≤ ~1 h training on CPU, resumable); keep only if it beats the best
   heuristic in the full-pipeline evaluation. HuggingFace and GitHub are reachable; download.pytorch.org is not — never try
   to bypass a blocked host.
6. CPU only. Portable (macOS + Linux). Never claim an improvement without numbers; log failures and revert them.

## Resource rules (shared 4-core machine)
- Before any command: `source /home/user/vector-press/.venv/bin/activate; export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
  OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1`.
- Development evaluations: **`--workers 1`** on the fixed subsets `--split dev --ids-file eval/subsets/dev_small.txt` and
  `--split tdev --ids-file eval/subsets/tdev_small.txt` (and `--categories ...` if useful).
- Full evaluations (all of dev / tdev): one at a time across all streams — wrap them in
  `flock /tmp/claude-0/fulleval.lock python -m eval.run ... --workers 2`.
- **Timing numbers measured now are NOT valid** (other streams are running). Report work/complexity proxies (e.g. per-stage
  time ratios on the same run, operation counts) if needed; real speed is measured by the lead in the integration step.
- Data are shared read-only via symlinks (`data/sets`, `data/cache`); do not rebuild datasets. Put scratch files in
  `/tmp/claude-0/<stream>/`. Use distinct experiment names prefixed with your stream letter (`A_...`, `B_...`, `C_...`)
  so `eval/runs/` and `eval/reports/` never collide.

## Deliverables per stream
- Commits on your branch (pushed), each experiment logged in **your own section** of EXPERIMENTS.md
  (`## Phase 2 — stream X`) and RESEARCH.md (`## Phase 2 — stream X`); do not edit other sections.
- Stay inside your scope; list every file you touched outside it in HANDOFF.md.
- `HANDOFF_<X>.md` at the repo root: what changed (with flags/defaults), numbers vs `phase2-base` on tdev (+ dev,
  per category; full runs), files touched, expected interactions with the other streams, open problems.
