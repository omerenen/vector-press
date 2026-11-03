"""Command line interface.

  vectorize input.png -o output.svg [--preset auto] [--mode fast]
  vectorize ./in_dir -o ./out_dir          (batch: png/jpg/jpeg/webp/bmp/gif/tif)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .api import vectorize
from .presets import INTENTS, PRESETS

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def _bool(v):
    return v.lower() in ("1", "true", "yes", "on")


def build_parser():
    ap = argparse.ArgumentParser(prog="vectorize", description="Raster (PNG/JPG/WebP) to SVG vectoriser.")
    ap.add_argument("input", help="input image file or directory")
    ap.add_argument("-o", "--output", help="output .svg file or directory (default: next to input)")
    ap.add_argument("--preset", default="auto", choices=["auto"] + sorted(INTENTS) + sorted(PRESETS))
    ap.add_argument("--mode", default="fast", choices=["fast", "max"])
    ap.add_argument("--colors", default=None, help="max number of colours or 'auto'")
    ap.add_argument("--detail", type=float, default=None, help="0 (coarse) .. 1 (fine), default 0.5")
    ap.add_argument("--corner-sharpness", type=float, default=None, help="0 (round) .. 1 (sharp), default 0.5")
    ap.add_argument("--primitives", type=_bool, default=None, help="emit circle/ellipse/rect elements (default on)")
    ap.add_argument("--gradients", type=_bool, default=None, help="fit gradients (default: per preset)")
    ap.add_argument("--centerline", type=_bool, default=None, help="trace thin strokes as centre lines (default off)")
    ap.add_argument("--silhouette", type=_bool, default=None, help="cut preset: single-colour silhouette")
    ap.add_argument("--width-mm", type=float, default=None, help="cut preset: physical output width (mm) for size limits")
    ap.add_argument("--min-feature-mm", type=float, default=None, help="cut preset: smallest feature kept (mm)")
    ap.add_argument("--stats", action="store_true", help="print per-image stats as JSON lines")
    return ap


def _opts(a):
    o = {}
    if a.colors is not None:
        o["colors"] = a.colors if a.colors == "auto" else int(a.colors)
    if a.width_mm is not None:
        o["cut_width_mm"] = a.width_mm
    for k in ("detail", "corner_sharpness", "primitives", "gradients", "centerline", "silhouette", "min_feature_mm"):
        v = getattr(a, k)
        if v is not None:
            o[k] = v
    return o


def _one(src, dst, a, opts):
    t = time.perf_counter()
    res = vectorize(src, preset=a.preset, mode=a.mode, **opts)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    res.save(dst)
    if a.stats:
        s = {k: v for k, v in res.stats.items()}
        s.update(input=src, output=dst, seconds=round(time.perf_counter() - t, 3))
        print(json.dumps(s, default=str))
    else:
        print(f"{src} -> {dst} ({res.stats.get('image_type') or res.stats.get('preset')}, "
              f"{res.stats['bytes']} bytes, {time.perf_counter() - t:.2f}s)")


def main(argv=None):
    a = build_parser().parse_args(argv)
    opts = _opts(a)
    if os.path.isdir(a.input):
        out_dir = a.output or a.input
        files = sorted(f for f in os.listdir(a.input) if os.path.splitext(f)[1].lower() in EXTS)
        if not files:
            print("no images found", file=sys.stderr)
            return 1
        fails = 0
        for f in files:
            src = os.path.join(a.input, f)
            dst = os.path.join(out_dir, os.path.splitext(f)[0] + ".svg")
            try:
                _one(src, dst, a, opts)
            except Exception as e:  # keep going in batch mode
                fails += 1
                print(f"FAILED {src}: {e}", file=sys.stderr)
        return 1 if fails else 0
    dst = a.output or os.path.splitext(a.input)[0] + ".svg"
    if os.path.isdir(dst):
        dst = os.path.join(dst, os.path.splitext(os.path.basename(a.input))[0] + ".svg")
    _one(a.input, dst, a, opts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
