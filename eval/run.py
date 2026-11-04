"""Evaluation runner.

  python -m eval.run --config eval/configs/exp_000_baseline.yaml --split dev [--workers 4]

Writes eval/runs/<exp>/<split>/{svgs/*.svg, metrics.jsonl} and
eval/reports/<exp>/summary_<split>.{json,md}.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
from multiprocessing import Pool

import numpy as np
import yaml
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from eval import metrics as M  # noqa: E402
from vectorizer.imageio import composite_over, load_rgba  # noqa: E402
from vectorizer.render import render_svg  # noqa: E402

SETS = os.path.join(ROOT, "data", "sets")
RUNS = os.path.join(ROOT, "eval", "runs")
REPORTS = os.path.join(ROOT, "eval", "reports")
CATEGORIES = ["icon", "logo", "flat_illustration", "line_art", "diagram", "gradient", "photo",
              # target benchmark (AI-generated, DALL-E 3)
              "sticker", "tshirt", "cutfile", "vector_flat", "poster"]


def make_method(cfg):
    method = cfg.get("method", "pipeline")
    params = cfg.get("params", {}) or {}
    per_cat = cfg.get("per_category", {}) or {}
    if method == "vtracer":
        from vectorizer.pipeline.trace import vtracer_trace

        def run(rgba, category):
            p = dict(params)
            p.update(per_cat.get(category, {}))
            t = time.perf_counter()
            svg = vtracer_trace(rgba, **p)
            return svg, {"timings": {"vtracer": time.perf_counter() - t}}
        return run
    if method == "pipeline":
        from vectorizer.api import vectorize

        def run(rgba, category):
            p = dict(params)
            p.update(per_cat.get(category, {}))
            if cfg.get("oracle_preset"):
                p.setdefault("preset", cfg["oracle_preset"].get(category, "auto"))
            res = vectorize(rgba, **p)
            return res.svg, res.stats
        return run
    if method == "external":
        d = os.path.join(ROOT, params["dir"])

        def run(rgba, category, item=None):
            stem = (item or {}).get("stem") or (item or {}).get("id")
            path = os.path.join(d, f"{stem}.svg")
            if not os.path.exists(path):
                raise FileNotFoundError(path)
            return open(path, encoding="utf-8").read(), {"timings": {}}
        run.external = True
        return run
    raise ValueError(method)


def svg_scale(svg, W, H):
    """Scale from output user units to input pixels (handles viewBox)."""
    import re
    import xml.etree.ElementTree as ET
    root = ET.fromstring(svg)
    vb = root.attrib.get("viewBox")
    if vb:
        v = [float(x) for x in re.split(r"[ ,]+", vb.strip())]
        return W / v[2], H / v[3], -v[0] * W / v[2], -v[1] * H / v[3]
    return 1.0, 1.0, 0.0, 0.0


def evaluate_one(args):
    cfg, split, item = args
    iid = item["id"]
    d = os.path.join(SETS, split, iid)
    out_dir = os.path.join(RUNS, cfg["name"], split, "svgs")
    rec = {"id": iid, "category": item["category"], "degradation": item.get("degradation", {}).get("name")}
    try:
        rgba = load_rgba(os.path.join(d, "input.png"))
        gt = load_rgba(os.path.join(d, "gt.png"))
        H, W = gt.shape[:2]
        method = make_method(cfg)
        t0 = time.perf_counter()
        if getattr(method, "external", False):
            svg, stats = method(rgba, item["category"], item)
        else:
            svg, stats = method(rgba, item["category"])
        rec["time"] = time.perf_counter() - t0
        rec["timings"] = stats.get("timings", {})
        rec["detected_type"] = stats.get("image_type")
        for k in ("preset", "fallback", "engine", "n_regions", "upscale"):
            if stats.get(k) is not None:
                rec["st_" + k] = stats[k]
        with open(os.path.join(out_dir, iid + ".svg"), "w") as f:
            f.write(svg)
        rec["valid"] = M.svg_valid(svg)
        rec["is_vector"] = M.is_vector(svg)
        try:
            out = render_svg(svg, W, H)
        except Exception as e:  # render failure = invalid
            rec["valid"] = False
            rec["error"] = f"render: {e}"
            return rec
        a = composite_over(gt)
        b = composite_over(out)
        inp = composite_over(rgba)
        rec["ssim"] = M.ssim(a, b)
        rec["ssim_in"] = M.ssim(inp, b)
        rec["psnr"] = M.psnr(a, b)
        rec["msssim"] = M.msssim(a, b)
        rec["gmsd"] = M.gmsd(a, b)
        rec["de_mean"], rec["de_p95"] = M.delta_e(a, b)
        rec["edge_f"] = M.edge_f(a, b)
        if cfg.get("lpips"):
            rec["lpips"] = M.lpips_dist(a, b)
        if item.get("transparent"):
            ga, oa = gt[..., 3] > 127, out[..., 3] > 127
            u = (ga | oa).sum()
            rec["alpha_iou"] = float((ga & oa).sum() / u) if u else 1.0
        rec.update(M.structure_stats(svg))
        gt_svg_path = os.path.join(d, "gt.svg")
        if os.path.exists(gt_svg_path):
            gsvg = open(gt_svg_path).read()
            scale = max(1.0, min(4.0, 2048.0 / max(W, H)))
            W4, H4 = int(round(W * scale)), int(round(H * scale))
            gt4 = render_svg(gsvg, W4, H4)
            out4 = render_svg(svg, W4, H4)
            rec["edge_dev"], rec["mismatch4x"] = M.edge_deviation(composite_over(gt4), composite_over(out4), scale)
            rec["gap_px"] = M.gap_pixels(out4, gt4[..., 3] > 250)
            rec["gap_ppm"] = rec["gap_px"] / (W4 * H4) * 1e6
            cr, ce, cn = M.corner_metrics(composite_over(gt4), composite_over(out4), item.get("corners", []), scale)
            rec["corner_recall"], rec["corner_err"], rec["corner_err_nominal"] = cr, ce, cn
            sx, sy, ox, oy = svg_scale(svg, W, H)
            pr, per = M.primitive_recovery(svg, item.get("primitives", []), sx, sy, ox, oy)
            rec["prim_recovery"] = pr
            rec["prim_per_type"] = per
        if cfg.get("printcut"):
            from eval.printcut import printcut_metrics
            try:
                for k, v in printcut_metrics(svg, W, H).items():
                    rec["pc_" + k] = v
            except Exception as e:      # a metric failure must not mark the SVG invalid
                rec["pc_error"] = f"{type(e).__name__}: {e}"
        rec["composite"] = M.composite(rec)
    except Exception as e:
        rec["valid"] = False
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()
    return rec


KEYS = ["composite", "ssim", "ssim_in", "psnr", "msssim", "gmsd", "de_mean", "de_p95", "edge_f", "lpips", "alpha_iou",
        "edge_dev", "mismatch4x", "gap_px", "corner_recall", "corner_err", "corner_err_nominal", "prim_recovery",
        "n_paths", "n_nodes", "n_primitives", "bytes", "gz_bytes", "time",
        "pc_open_subpaths", "pc_self_intersections", "pc_overlap_ratio", "pc_n_colors", "pc_tiny_islands",
        "pc_thin_features", "pc_thin_area_mm2", "pc_n_nodes"]


def summarize(recs):
    out = {}
    groups = {"ALL": recs}
    for c in CATEGORIES:
        g = [r for r in recs if r["category"] == c]
        if g:
            groups[c] = g
    for name, g in groups.items():
        s = {"n": len(g), "valid_rate": float(np.mean([bool(r.get("valid")) for r in g]))}
        for k in KEYS:
            v = [r[k] for r in g if r.get(k) is not None and not (isinstance(r.get(k), float) and math.isnan(r[k]))]
            if v:
                s[k] = float(np.mean(v))
        tv = [r["time"] for r in g if r.get("time") is not None]
        if tv:
            s["time_median"] = float(np.median(tv))
            s["time_p95"] = float(np.percentile(tv, 95))
        # primitive recovery pooled over shapes
        tot = {}
        for r in g:
            for t, (a, b) in (r.get("prim_per_type") or {}).items():
                x = tot.setdefault(t, [0, 0])
                x[0] += a
                x[1] += b
        if tot:
            s["prim_pooled"] = {t: f"{a}/{b}" for t, (a, b) in sorted(tot.items())}
        out[name] = s
    return out


def fmt_table(summary, keys=None):
    keys = keys or ["n", "valid_rate", "composite", "ssim", "psnr", "gmsd", "de_mean", "de_p95", "edge_f", "edge_dev",
                    "gap_px", "corner_recall", "corner_err", "prim_recovery", "n_paths", "n_nodes", "gz_bytes",
                    "time_median", "time_p95"]
    hdr = "| cat | " + " | ".join(keys) + " |\n|" + "---|" * (len(keys) + 1) + "\n"
    rows = ""
    for cat, s in summary.items():
        cells = []
        for k in keys:
            v = s.get(k)
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.0f}" if abs(v) >= 1000 else (f"{v:.4f}" if abs(v) < 10 else f"{v:.1f}"))
            else:
                cells.append(str(v))
        rows += f"| {cat} | " + " | ".join(cells) + " |\n"
    return hdr + rows


def run(cfg, split, workers=4, limit=None, ids=None, categories=None):
    with open(os.path.join(SETS, split, "manifest.json")) as f:
        items = json.load(f)
    if ids:
        items = [it for it in items if it["id"] in ids]
    if categories:
        items = [it for it in items if it["category"] in categories]
    if cfg.get("method") == "external":
        items = [it for it in items if it.get("vectorizer_ai", True)]
    if limit:
        items = items[:limit]
    os.makedirs(os.path.join(RUNS, cfg["name"], split, "svgs"), exist_ok=True)
    t0 = time.time()
    if workers > 1:
        with Pool(workers, maxtasksperchild=20) as pool:
            recs = pool.map(evaluate_one, [(cfg, split, it) for it in items], chunksize=1)
    else:
        recs = [evaluate_one((cfg, split, it)) for it in items]
    wall = time.time() - t0
    with open(os.path.join(RUNS, cfg["name"], split, "metrics.jsonl"), "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    summ = summarize(recs)
    rep = os.path.join(REPORTS, cfg["name"])
    os.makedirs(rep, exist_ok=True)
    tag = split if not (limit or ids or categories) else split + "_partial"
    with open(os.path.join(rep, f"summary_{tag}.json"), "w") as f:
        json.dump({"config": cfg, "split": split, "wall_s": wall, "summary": summ}, f, indent=1)
    with open(os.path.join(rep, f"summary_{tag}.md"), "w") as f:
        f.write(f"# {cfg['name']} — {split}\n\n{cfg.get('description', '')}\n\n" + fmt_table(summ))
    errs = [r for r in recs if r.get("error")]
    for r in errs[:5]:
        print("ERROR", r["id"], r["error"], r.get("traceback", "")[-800:])
    return recs, summ


def load_cfg(path):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("name", os.path.splitext(os.path.basename(path))[0])
    return cfg


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--ids-file", help="file with one item id per line (fixed development subsets: eval/subsets/*.txt)")
    ap.add_argument("--categories", nargs="*")
    ap.add_argument("--name")
    ap.add_argument("--set", nargs="*", default=[], help="override params: key=value (YAML value)")
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    if a.name:
        cfg["name"] = a.name
    for kv in a.set:
        k, v = kv.split("=", 1)
        cfg.setdefault("params", {})[k] = yaml.safe_load(v)
    ids = a.ids
    if a.ids_file:
        ids = [l.strip() for l in open(a.ids_file) if l.strip() and not l.startswith("#")]
    recs, summ = run(cfg, a.split, a.workers, a.limit, ids, a.categories)
    print(fmt_table(summ))
