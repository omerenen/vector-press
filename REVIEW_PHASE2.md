# Independent review — phase 2 (`phase2-base..phase2/integration`, HEAD ac0ced9)

Scope: code diff `phase2-base..HEAD -- vectorizer eval data tests`, held-out reports and per-item rows, contact sheets,
`print`/`cut` outputs on tdev, docs. Nothing was re-run on held-out splits. Single images only.
`python -m pytest -q`: **81 passed** (8 s).

Reproduction helpers used below live in the reviewer scratchpad; every command is short enough to be repeated inline.

---

## BLOCKER

### B1. The user option `colors=N` / `--colors N` is silently ignored by every graph preset except `cut` (regression)
`segment="ms"` became the default (api.py:91). `_quantize_ms` gives every merged region its own mean colour and appends it
to the palette (`newpal = concatenate([pal, newpal[~snap]])`, quantize.py, `_quantize_ms`). `max_colors` only bounds
the initial palette. Only `cut` caps paints (`seg_paints=max_colors if cutout`, api.py:246).
```
python -c "import re,sys; sys.path.insert(0,'/home/user/vp-I'); from vectorizer import vectorize
for c in (2,4,6):
  r=vectorize('data/sets/tdev/tdev_0044/input.png', preset='logo', colors=c); print(c, len(set(re.findall(r'fill=\"(#\w+)\"', r.svg))))"
```
HEAD: colors=2/4/6 → **32/43/47** distinct fills (auto, print, logo all the same). `phase2-base`: exactly 2/4/6.
README documents `--colors 6` as the first CLI example. Screen print needs a fixed colour count, so this is a product
regression. No test covers it.

### B2. `shapely` is now a hard runtime dependency, but it is not declared and it is documented as eval-only. Its wheel bundles LGPL GEOS
- `geom_repair=True` and `region_prims=True` are defaults. `validity._ring_ok` (validity.py:48) imports shapely outside its
  `try`, so `vectorize()` raises `ModuleNotFoundError` on any graph-engine image when shapely is missing (reproduced with
  `sys.modules["shapely"]=None`). The error is raised from validity.py:48.
- `pyproject.toml` `dependencies` has no shapely, so `pip install vector-press` gives a package that crashes.
  `requirements.txt` puts it under "evaluation / tests", and LICENSES.md:36 says "print/cut metrics (eval only)".
- The shapely 2.2.0 wheel ships `shapely.libs/libgeos*.so` with `LICENSE_GEOS` (GEOS = **LGPL-2.1**). The project
  rule (PHASE2_BRIEF rule 5) allows only MIT/Apache/BSD/ISC/CC0/OFL/CC-BY. LICENSES.md went into the same depth for
  Pillow's FriBiDi (LGPL) but does not mention GEOS. LICENSES.md was not changed in phase 2 at all.

## MAJOR

### M1. The ttest headline gain (+0.012 vs phase2-base) comes from a VTracer parameter switch, not from the phase-2 vectorizer work
Per-item decomposition (F_t_final vs P2BASE_t_final). The engine was inferred from the SVGs: VTracer output carries
`transform="translate`.

| engine base → final | n | mean Δcomposite |
|---|---|---|
| VTracer → VTracer | 53 | +0.0174 (**all of it from 10 items**, sum +0.924) |
| graph → graph | 9 | +0.0106 |
| VTracer → graph (newly routed to the region engine) | 5 | **−0.046** (0020 −0.068, 0029 −0.048, 0030 −0.065, 0055 −0.095; 0044 +0.047) |

- In the 10 items (ttest_0008/0009/0025/0031/0035/0040/0047/0048/0049/0050), the fallback switched from the coarse
  "pure-noise" VTracer parameters to the fine photo parameters (`noise_density` 0.1→0.35). Paths went ×7 and gz went
  1.70 → 3.48 MB per image.
- **Without those 10 items, final = 0.7131 vs phase2-base 0.7155 (−0.0024) on the other 57.** The region-engine changes
  from streams A, B and C give no net gain on the target set. All 4 large regressions come from the new routing into the
  region engine.
- EXPERIMENTS.md:815 says "auto = 34/67 VTracer fallback". In fact **53/67** final outputs are VTracer: 34 from the
  fallback plus 19 where the classifier picked the photo preset (`st_engine`/`st_preset` in metrics.jsonl). Only 14/67
  target images use the project's own engine.

The metric is blind to file size, so the gain is bought with bytes (paths 13.6k → 16.7k mean, gz +8 %).

### M2. The comparison against VTracer flatters the pipeline
- `t_vtracer_tuned` uses phase-1 parameters tuned on the *procedural* dev split (logo → filter_speckle 8, cutfile →
  layer_difference 32). The pipeline's own routing and noise thresholds were tuned on `tdev`, which comes from the same
  distribution as ttest.
- 32 of the 44 "wins vs tuned VTracer" are VTracer against VTracer with different parameters (53 VTracer items: F 0.6862
  vs VTt 0.6610). The fair baseline is VTracer run with the pipeline's own photo parameters on every image. On 53/67
  items it equals F by construction.
- Conversely, the pipeline's VTracer path downsamples to `max_side=1024` (presets.py PHOTO). The baselines run at full
  resolution, and 16/67 ttest images are 1792 px. On poster items the parameters are identical, so F − VTt is exactly 0
  except ttest_0002 (−0.098) and ttest_0009 (−0.099), both 1792 px. The 4 worst items vs VTt (0009, 0002, 0016, 0008)
  are all 1792 px. This is an easy, untested fix, and it changes the picture for posters.

### M3. Photo regression on `test` and visible damage, missing from the final summary
F_final vs P2BASE_final on `test`: photo −0.019 (test_0126 −0.083, 0122 −0.067, 0125 −0.039). These are
`photo_route="try"` photos sent to the region engine. `eval/reports/F_final/sheet_photo.png` shows:
- Hubble fields lose most faint stars (285 vs 2 334 paths).
- Retina images become flat posterised plates with the vessels gone and the fovea turned into a hard blob (38 paths).

On ttest, ttest_0030 (P2BASE VTracer 0.721 → graph 0.656) shows contour banding on the wall gradient
(`F_t_final/sheet_cutfile.png`). EXPERIMENTS "Final held-out evaluation" reports only the overall test mean. Corner
recall also dropped (0.773 → 0.745, reported).

### M4. The `cut` preset is not reliably cut-ready
Run on tdev_0042, 0044 and 0021 plus synthetic images. Good: all subpaths closed, no self-intersections, pairwise
overlap between colours below 200 px² (subpixel), background dropped on 2 of 3.
- **Background kept when it covers ≥ 95 % of the canvas** (api.py:283 `(lbl == bgl).mean() < 0.95`). A small design on a
  large canvas (very common for sticker/Cricut art) gets a full-canvas frame with a hole as a cut path. Repro: 512² white
  canvas with a 45 px-radius black disc and `preset="cut"` gives `<path fill="#fff" d="M0 0h512v512h-512z...">` plus the disc.
- **Near-identical paints become separate layers.** tdev_0021 (B/W line art) produces `#000`, `#000101`, `#030404` and
  `#1c1c..` as 4 separate black layers, plus 2 near-whites. OKLab distance near black is inflated by the cube root, and
  `reduce_paints` only runs when K > 8. On ttest, 63/67 cut outputs use exactly 7 colours (8 minus the background), so
  the paint budget is always filled whatever the image.
- **Vignette backgrounds are only partly dropped.** On tdev_0042 a large dark wedge in the top-right stays as a cut shape.
- **Thin features remain.** F_t_cut has a median of about 26 thin features per image (max 161) at the same 0.5 mm /
  100 mm threshold that `enforce_min_feature` uses. README:72 says such parts "are removed".
- README:71 says "one path per colour". Primitives are emitted as separate `<rect>`/`<ellipse>` elements: tdev_0044 has
  6 paints in 31 elements.
- Detailed line art turns into blobs at the 100 mm default: tdev_0021 wolf fur, render in the scratchpad `cut_sheet.png`.
  This is by design given the 5 px minimum feature at 1024 px. It still needs a sentence in the docs.

### M5. The `print` preset is below VTracer-default fidelity, yet the README claims "tam doğruluk" (full fidelity)
- ttest composite: **0.625**. Auto is 0.705 and VTracer default is 0.654. edge_f 0.70, LPIPS 0.251 (worst of all
  non-cut methods).
- Median 37 s, max 76 s per image (F_t_print rows).
- Median 1 428 paints per image, which is unusable for screen print, and B1 removes the way to cap it.
- The region budget (`seg_budget` 0.004/px) wipes out hatching in line art: tdev_0021 wolf face, scratchpad
  `print_sheet.png`.
- 6 ttest items still have self-intersections (0009, 0011, 0014, 0021, 0032, 0035), although `geom_repair` is meant to
  guarantee simple rings.

What works: outputs are stacked, every shared border has seam strokes, there are no open fill subpaths, and flat logos
(tdev_0044) look clean.

### M6. `proc2` was used during development
PHASE2_BRIEF says to treat proc2 as held-out.
- Stream A classified primitive failures on proc2 before and while changing code (EXPERIMENTS.md:305, 364).
- After seeing proc2_0012, stream A committed a code change motivated by that item: DP thinning of `make_valid` parts,
  commit 0b2bf17, validity.py:284-287.

The numeric impact is probably small. Still, the "overfitting check passed" claim for stream A's primitive work is not
clean.

## MINOR
- **validity.py:159.** A loop is dropped when `abs(signed area) < 0.5` on the first pass. A large self-crossing
  figure-8 has near-zero *signed* area and would be dropped (not drawn). Use the unsigned area of `valid_parts`, or
  `Polygon(P).buffer(0).area`.
- **quantize.py `_quantize_ms`.** When `K*Kp > 5e7` the majority colour falls back to `pal[0]`, so thin regions get a
  wrong colour. `reduce_paints` can pick the same centroid twice (`argmax` of all-zero distances), which leaves unused
  paints.
- **api.py:149 tiny-image path.** In `cut` it emits one rect per pixel run including the background, with no
  `drop_background`, no merging, and possibly `fill-opacity`. `cut` also keeps `fill-opacity` for semi-transparent
  regions (64² alpha-60 input → `fill-opacity="0.235"`). `cut` with `colors=1` gives a full-canvas rectangle.
- **test_0020 (JPEG logo).** Straight diagonal edges come out wobbly with dark-red fringe slivers. edge_f 0.98 → 0.81,
  composite −0.065.
- **Report hygiene.**
  - P2BASE_* rows are re-scored outputs, so their `time_median` (0.004 s) is scoring time and should be blanked.
  - Contact sheets use `t_vtracer_tuned` as "base", which hides the regressions vs phase2-base (ttest_0030 looks like
    +0.056 in the sheet but is −0.065 vs base).
  - F_t_print has sheets for 3 of 5 categories and F_t_cut has none. Rendering was possibly still running.
- **ttest categories.** The labels come from prompts. Most "logo"/"cutfile" items are painterly or photographic scenes
  (motorbike rider, cave painting, food truck), so per-category numbers say little about real logos or cut files.
- **Docs.**
  - README:57 preset list omits `cut`/`print` (the CLI accepts them).
  - PLAN.md still describes phase 1 ("All milestones done", architecture without the MS merge, region primitives,
    validity repair or fringe).
  - REPORT.md and LICENSES.md were not updated in phase 2.

## NOTE — uncommitted change appeared during this review (not made by the reviewer)
While this review ran, `vectorizer/api.py` and `eval/run.py` were modified in the working tree by another process.
The change adds `photo_try_max_err` (default `None` = off) and a `q_err` stat: if a "tried" photo's label map has a
large mean OKLab error, it is sent to the VTracer engine. This targets exactly the posterised-photo failure that is
visible only on the **held-out** `test` sheet (M3: retina, star field). It is behaviour-neutral at its default, and all
reviewer runs are unaffected. But if its threshold is chosen or validated by looking at `test` photos, that is tuning
on held-out data. It must be set on dev/tdev only, and `test` must then be reported as no longer clean for the photo
category.

## NOTE (checked, no problem found)
- **Edge cases.** All produced well-formed SVGs (xml.etree) in auto/print/cut: 1×1, 3×3, 5×5, fully transparent, single
  colour, 8×2000, 3000×6, 16-bit gray PNG, 16-bit RGB array, palette PNG with tRNS, LA, all-semi-transparent, float
  input, noise, JPEG, CMYK JPEG, `mode="max"`, `silhouette`, `seg_model="affine"`, `seg_init="fz"`,
  `segment="palette"`. Every `cut` fill subpath was closed.
- **No held-out ids anywhere.** No test/ttest/proc2 id or split name appears in vectorizer/, eval/*.py, data/*.py or
  tests/. Thresholds that look data-derived (`route_max_c90=100`, `noise_density=0.35`, `seg_raw_bail=0.06`) are
  documented as coming from tdev/dev. The commits after the held-out runs are byte-identical: cd34538 checked on
  tdev_0042/0044 × print/cut against 7e06f5d.
- **Metric changes apply to all methods.** The `corner_metrics` change (error vs the GT Harris peak) and the printcut
  rule (drop a duplicate closing point) live in the shared scorer. `corner_err_nominal` is present in all four `test`
  runs, and baselines exp_000/exp_001 were re-scored. The new rule also helps VTracer, whose closed paths repeat the
  start point.
- **EXPERIMENTS numbers check out.** The "Final held-out evaluation" figures match the raw rows: composite, SSIM, PSNR,
  LPIPS, ΔE, edge-F, paths, gz, the print/cut table, 16 better / 4 worse, 44/67, poster-only category loss, test 0.9143
  vs 0.9012, prim 0.775, corner 0.745/0.363, proc2 0.8897 vs 0.7957. The only exception is the "34/67" wording (M1).
- **The test/proc2 gains on procedural data are real and broad.** Graph → graph on test: +0.0131 over 117 items,
  every non-photo category positive. proc2: +0.094 vs tuned VTracer, and +0.004 vs the stream-A base A_base.

## Verdict
The engineering is solid: tests pass, no crash found on edge inputs, cut geometry is closed and non-overlapping, and
the procedural held-out gains (test +0.013, prim recovery 0.42 → 0.77) are real.

The target-domain claim does not hold as stated. On the DALL-E 3 held-out set the phase-2 vectorizer work is neutral
to slightly negative (−0.002 without the 10 items whose VTracer fallback parameters changed). 79 % of auto outputs
are VTracer. The VTracer baseline is weaker than the pipeline's own VTracer path and runs at a different resolution.

Before release, fix B1 (`colors` ignored) and B2 (undeclared shapely runtime dependency and the GEOS LGPL policy
question). Rewrite the final EXPERIMENTS summary to attribute the gain correctly and to report the photo regressions.
Then address the cut background, duplicate-paint and thin-feature issues and the print fidelity/size gap before
calling the presets print-ready or cut-ready.
