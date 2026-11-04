# LICENSES

Project code: MIT (see `LICENSE`). No GPL/AGPL code is used or linked by the project itself; no Potrace/AutoTrace.
No model weights are shipped or downloaded by the vectoriser. Licenses below were checked from the primary source named
in the "checked" column (package metadata / LICENSE file / SBOM inside the installed wheel / dataset `info.json`).

## Runtime dependencies (requirements.txt)
| package | version | license | checked |
|---|---|---|---|
| numpy | 2.5.4 | BSD-3-Clause (+0BSD, MIT, Zlib, CC0 parts) | wheel metadata `License-Expression` |
| scipy | 1.18.1 | BSD-3-Clause; wheel bundles libgfortran/libquadmath (GPL-3 **with GCC Runtime Library Exception** → no copyleft effect) and OpenBLAS (BSD-3) | wheel metadata, `scipy.libs/` |
| scikit-image | 0.26.0 | BSD-3-Clause | wheel metadata; https://github.com/scikit-image/scikit-image/blob/main/LICENSE.txt |
| imageio, networkx, lazy-loader, tifffile, packaging (skimage deps) | pinned by pip | BSD-2/BSD-3/Apache-2.0 | wheel metadata |
| pillow | 13.0.0 | MIT-CMU — **see flag below** | wheel metadata + `sboms/` |
| vtracer | 0.6.15 | MIT (Rust deps: MIT/Apache-2.0/Zlib/BSD-2/Unlicense, see SBOM) | wheel metadata, `vtracer-0.6.15.dist-info/sboms/vtracer.cyclonedx.json`; https://github.com/visioncortex/vtracer/blob/master/LICENSE |
| resvg_py | 0.5.0 | MIT (bundles resvg/usvg/tiny-skia: Apache-2.0 OR MIT / BSD-3-Clause, see SBOM) | `resvg_py-0.5.0.dist-info/licenses/LICENSE`, `sboms/resvg_py.cyclonedx.json` |

### Pillow binary wheels (checked, corrected after the independent review)
The Pillow SBOM lists optional components. In the installed wheel `features.check("libimagequant")` is **False** and
`PIL/_imaging*.so` exports no `liq_` symbols → libimagequant (GPL-3) is **not** included. FriBiDi (LGPL-2.1) is not
bundled either; Pillow loads a system copy at run time if present (dynamic, optional; used only for complex text layout,
which vector-press never calls). Bundled libraries are permissive (libjpeg-turbo IJG/BSD, libpng, zlib, libtiff, libwebp
BSD-3, FreeType FTL, HarfBuzz MIT, lcms2 MIT, OpenJPEG BSD-2, libavif BSD-2). Re-check on the target Mac with
`python -c "from PIL import features; print(features.check('libimagequant'))"` (expected `False` for PyPI wheels).

### Rust crates inside the vtracer / resvg_py wheels
From the wheels' CycloneDX SBOMs: MIT, Apache-2.0, MIT OR Apache-2.0, BSD-2-Clause, BSD-3-Clause (tiny-skia), Zlib,
Unlicense OR MIT, 0BSD, **Unicode-3.0** (unicode-ident data) and **Apache-2.0 WITH LLVM-exception** (target-lexicon,
build-time). All permissive; no copyleft.

## Optional "geometry" extra (requirements-geometry.txt / `pip install "vector-press[geometry]"`)
| package | license | checked | used for |
|---|---|---|---|
| shapely 2.2.0 | BSD-3-Clause; **the binary wheel bundles GEOS 3.14.1 (`shapely.libs/libgeos*.so`), LGPL-2.1** | wheel metadata `License-Expression: BSD-3-Clause`, `shapely-2.2.0.dist-info/licenses/LICENSE_GEOS` ("License: LGPLv2.1") | geometry repair (no self-intersecting rings: `geom_repair`, region-primitive validation) and the print/cut readiness metrics (`eval/printcut.py`) |

GEOS is weak copyleft (LGPL-2.1), used unmodified as a dynamically loaded shared library. Because the project's rule is
"permissive licenses only", shapely is **not** in the core install: `requirements.txt` is permissive-only and
`vectorize()` runs without shapely (geometry repair is then skipped and `stats["geom_repair"]` says so; outputs stay valid
SVG but rare self-intersecting rings are not repaired). Install the extra (`make setup` does) to get the measured phase-2
behaviour — all phase-2 numbers in REPORT.md / EXPERIMENTS.md were measured with it. Found by the independent review
(REVIEW_PHASE2.md, B2); before, shapely was listed as "eval only" although `geom_repair` (default on) imported it.

## Evaluation / development only (not needed at runtime)
| package | license | note |
|---|---|---|
| PyYAML 6.0.3 | MIT | eval configs |
| pytest 9.2.0 | MIT | tests |
| pyarrow | Apache-2.0 | reads the DALL-E 3 parquet shards (dataset builder only) |
| pandas | BSD-3-Clause | DiffusionDB metadata (abandoned builder only) |
| AlexNet ImageNet weights (torchvision) | BSD-3-Clause | LPIPS backbone, eval only; fetched from a HuggingFace mirror and accepted only with the official SHA-256 7be5be79…cdee02 (`data/fetch_lpips.py`) |
| scikit-learn 1.9.1 | BSD-3-Clause | used once offline to fit the classifier decision tree (rules are hard-coded; not a dependency) |
| torch (optional) | Apache-2.0 AND BSD-2/BSD-3/MIT/ISC/Zlib/BSL-1.0 (wheel metadata); the Linux PyPI wheel pulls **NVIDIA CUDA runtime wheels under the proprietary NVIDIA EULA** — only installed for the optional LPIPS metric, never needed by the vectoriser | LPIPS only |
| lpips 0.1.4 (optional) | BSD-2-Clause | AlexNet weights could not be downloaded here (download.pytorch.org blocked) |
| npm (Iconify JSON packages download) | — | tooling only |

## Datasets (test data only; the datasets are not committed and are regenerated by `python -m data.build`)
**Note:** the committed contact sheets (`eval/reports/*/sheet_*.png`) contain downscaled renders of the third-party icons,
emoji and logos below. Attribution: Twemoji graphics © Twitter, Inc. and other contributors, CC-BY 4.0; Noto Emoji ©
Google, Apache-2.0; Fluent Emoji © Microsoft, MIT; Lucide (ISC), Tabler/Bootstrap/skill-icons/vscode-icons/flat-color-icons
(MIT), Material Symbols © Google (Apache-2.0); logos from gilbarbara/logos (CC0 files; the marks themselves are trademarks of
their owners and are shown only as test inputs). Delete `eval/reports/` before redistributing the repository if you do not want
to carry these notices.
| source | version | license | checked |
|---|---|---|---|
| @iconify-json/lucide (Lucide) | 1.2.150 | ISC | package `info.json` → https://github.com/lucide-icons/lucide/blob/main/LICENSE |
| @iconify-json/tabler (Tabler Icons) | 1.2.43 | MIT | `info.json` → https://github.com/tabler/tabler-icons/blob/master/LICENSE |
| @iconify-json/bi (Bootstrap Icons) | 1.2.7 | MIT | `info.json` → https://github.com/twbs/icons/blob/main/LICENSE.md |
| @iconify-json/material-symbols | 1.2.97 | Apache-2.0 | `info.json` → https://github.com/google/material-design-icons/blob/master/LICENSE |
| @iconify-json/logos (gilbarbara/logos) | 1.2.18 | CC0-1.0 (SVG files; the depicted logos are trademarks of their owners — used only as test images) | `info.json` → https://raw.githubusercontent.com/gilbarbara/logos/master/LICENSE.txt |
| @iconify-json/skill-icons | 1.2.4 | MIT | `info.json` → https://github.com/tandpfun/skill-icons/blob/main/LICENSE |
| @iconify-json/vscode-icons | 1.2.95 | MIT | `info.json` → https://github.com/vscode-icons/vscode-icons/blob/master/LICENSE |
| @iconify-json/flat-color-icons | 1.2.3 | MIT | `info.json` |
| @iconify-json/fluent-emoji-flat, fluent-emoji (Microsoft Fluent Emoji) | 1.2.6 / 1.2.7 | MIT | `info.json` → https://github.com/microsoft/fluentui-emoji/blob/main/LICENSE |
| @iconify-json/noto (Noto Emoji) | 1.2.10 | Apache-2.0 | `info.json` → https://github.com/googlefonts/noto-emoji/blob/main/svg/LICENSE |
| @iconify-json/twemoji (Twemoji graphics) | 1.2.5 | **CC-BY-4.0** — attribution: "Twemoji graphics © Twitter, Inc. and other contributors, CC-BY 4.0" | `info.json` → https://creativecommons.org/licenses/by/4.0/ |
| scikit-image sample photos: coffee, chelsea, camera, retina | — | CC0-1.0 | docstrings in `skimage/data/__init__.py` |
| scikit-image sample photos: rocket (SpaceX), astronaut, hubble_deep_field (NASA) | — | public domain | docstrings in `skimage/data/__init__.py` |
| scikit-image immunohistochemistry | — | "no known copyright restrictions" | docstring |
| procedural scenes (`data/procedural.py`, incl. `proc2`) | — | generated by this project (CC0) | — |
| **Target benchmark** `tdev`/`ttest`: OpenDatasets/dalle-3-dataset (DALL-E 3 images + prompts) | HF snapshot 2026-11 | **CC0-1.0** | dataset card `license: cc0-1.0` (https://huggingface.co/datasets/OpenDatasets/dalle-3-dataset); images are AI-generated; prompts may name brands/characters — used only as test inputs |
| DiffusionDB (poloclub/diffusiondb) — evaluated, not used | — | CC0-1.0 (images), MIT (code) | dataset card / README |

Rejected because of their license: OpenMoji (CC-BY-SA-4.0), MMSVG-2M (non-commercial), Potrace (GPL-2.0).

## Algorithms / ideas (no code copied)
Schneider 1990 curve fitting; Fitzgibbon et al. 1999 ellipse fit; Lee 1983 sigma filter; OKLab (Ottosson 2020, public
domain); Immerkær 1996 noise estimate; Xue et al. 2014 GMSD; Wang et al. SSIM/MS-SSIM; CIEDE2000 via scikit-image.
