"""Speed benchmark: single process, typical 1024x1024 logos/illustrations.

  python -m eval.bench [--split dev] [--n 30] [--size 1024] [--set key=value ...]

Inputs: ground-truth SVGs of non-photo items rendered at --size (longest side) on their
own background (clean anti-aliasing) + a JPEG q=85 variant. Reports median / p95 per stage.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import platform
import sys
import time

import numpy as np
import yaml
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from vectorizer.api import vectorize  # noqa: E402
from vectorizer.render import render_svg  # noqa: E402


def cpu_name():
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--set", nargs="*", default=[])
    ap.add_argument("--out")
    a = ap.parse_args()
    opts = {}
    for kv in a.set:
        k, v = kv.split("=", 1)
        opts[k] = yaml.safe_load(v)
    man = json.load(open(os.path.join(ROOT, "data", "sets", a.split, "manifest.json")))
    items = [m for m in man if m["has_gt"]]
    step = max(1, len(items) // a.n)
    items = items[::step][: a.n]
    times, stages = [], {}
    for k, m in enumerate(items):
        svg = open(os.path.join(ROOT, "data", "sets", a.split, m["id"], "gt.svg")).read()
        s = a.size / max(m["width"], m["height"])
        W, H = int(round(m["width"] * s)), int(round(m["height"] * s))
        rgba = render_svg(svg, W, H)
        if k % 2 == 1 and (rgba[..., 3] == 255).all():
            buf = io.BytesIO()
            Image.fromarray(rgba[..., :3]).save(buf, "JPEG", quality=85)
            rgba = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGBA"))
        t = time.perf_counter()
        r = vectorize(rgba, **opts)
        dt = time.perf_counter() - t
        times.append(dt)
        for st, v in r.stats["timings"].items():
            stages.setdefault(st, []).append(v)
        print(f"{m['id']} {m['category']:18s} {W}x{H} {dt:.2f}s", flush=True)
    res = {"cpu": cpu_name(), "n": len(times), "size": a.size, "median_s": float(np.median(times)),
           "p95_s": float(np.percentile(times, 95)), "max_s": float(np.max(times)),
           "stages_median": {k: float(np.median(v)) for k, v in stages.items()}, "opts": opts}
    print(json.dumps(res, indent=1))
    if a.out:
        with open(a.out, "w") as f:
            json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
