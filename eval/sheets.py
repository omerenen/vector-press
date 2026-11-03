"""Contact sheets: input | baseline | experiment | diff heatmap | 4x zoom (GT vs exp) on worst region.

  python -m eval.sheets --exp exp_010 --base exp_000_baseline --split dev [--n 6]
Writes eval/reports/<exp>/sheet_<category>.png (rows = worst-N images by composite of exp).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import color as skcolor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from eval.run import CATEGORIES, REPORTS, RUNS, SETS  # noqa: E402
from vectorizer.imageio import composite_over, load_rgba  # noqa: E402
from vectorizer.render import render_svg  # noqa: E402

T = 200  # tile size


def _tile(rgb, label):
    im = Image.fromarray(rgb)
    im.thumbnail((T, T), Image.LANCZOS)
    canvas = Image.new("RGB", (T, T + 14), (90, 90, 90))
    canvas.paste(im, ((T - im.width) // 2, (T - im.height) // 2))
    ImageDraw.Draw(canvas).text((3, T + 1), label[:34], fill=(255, 255, 255))
    return canvas


def heat(de, vmax=20.0):
    x = np.clip(de / vmax, 0, 1)
    r = np.clip(3 * x, 0, 1)
    g = np.clip(3 * x - 1, 0, 1)
    b = np.clip(3 * x - 2, 0, 1)
    return (np.dstack([r, g, b]) * 255).astype(np.uint8)


def load_metrics(exp, split):
    p = os.path.join(RUNS, exp, split, "metrics.jsonl")
    return {r["id"]: r for r in map(json.loads, open(p))}


def make_sheets(exp, base, split, n=6, ids_per_cat=None):
    me = load_metrics(exp, split)
    mb = load_metrics(base, split) if base else {}
    man = {it["id"]: it for it in json.load(open(os.path.join(SETS, split, "manifest.json")))}
    out_dir = os.path.join(REPORTS, exp)
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for cat in CATEGORIES:
        recs = [r for r in me.values() if r["category"] == cat and r.get("composite") is not None]
        if not recs:
            continue
        recs.sort(key=lambda r: r["composite"])
        chosen = recs[:n] if not ids_per_cat else [me[i] for i in ids_per_cat.get(cat, []) if i in me]
        rows = []
        for r in chosen:
            iid = r["id"]
            d = os.path.join(SETS, split, iid)
            gt = load_rgba(os.path.join(d, "gt.png"))
            H, W = gt.shape[:2]
            inp = composite_over(load_rgba(os.path.join(d, "input.png")))
            svg_e = open(os.path.join(RUNS, exp, split, "svgs", iid + ".svg")).read()
            oe = composite_over(render_svg(svg_e, W, H))
            tiles = [_tile(inp, f"{iid} input ({man[iid].get('degradation', {}).get('name', '')})")]
            if base and os.path.exists(os.path.join(RUNS, base, split, "svgs", iid + ".svg")):
                svg_b = open(os.path.join(RUNS, base, split, "svgs", iid + ".svg")).read()
                ob = composite_over(render_svg(svg_b, W, H))
                tiles.append(_tile(ob, f"base c={mb.get(iid, {}).get('composite', 0):.3f} p={mb.get(iid, {}).get('n_paths', 0)}"))
            tiles.append(_tile(oe, f"exp c={r['composite']:.3f} p={r.get('n_paths', 0)}"))
            g = composite_over(gt)
            de = skcolor.deltaE_ciede2000(skcolor.rgb2lab(g), skcolor.rgb2lab(oe))
            tiles.append(_tile(heat(de), f"dE mean={de.mean():.2f}"))
            # worst region: window of ~1/4 size with max blurred error
            win = max(16, min(H, W) // 4)
            sm = ndi.uniform_filter(de, win)
            cy, cx = np.unravel_index(np.argmax(sm), sm.shape)
            y0 = int(np.clip(cy - win // 2, 0, max(0, H - win)))
            x0 = int(np.clip(cx - win // 2, 0, max(0, W - win)))
            z = 4
            gsvg_p = os.path.join(d, "gt.svg")
            if os.path.exists(gsvg_p):
                g4 = composite_over(render_svg(open(gsvg_p).read(), W * z, H * z))
            else:
                g4 = np.asarray(Image.fromarray(g).resize((W * z, H * z), Image.NEAREST))
            e4 = composite_over(render_svg(svg_e, W * z, H * z))
            cg = g4[y0 * z:(y0 + win) * z, x0 * z:(x0 + win) * z]
            ce = e4[y0 * z:(y0 + win) * z, x0 * z:(x0 + win) * z]
            tiles.append(_tile(cg, "4x GT crop"))
            tiles.append(_tile(ce, "4x exp crop"))
            row = Image.new("RGB", (T * len(tiles), T + 14))
            for i, t in enumerate(tiles):
                row.paste(t, (i * T, 0))
            rows.append(row)
        if not rows:
            continue
        sheet = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows)), (0, 0, 0))
        y = 0
        for r in rows:
            sheet.paste(r, (0, y))
            y += r.height
        p = os.path.join(out_dir, f"sheet_{cat}.png")
        sheet.save(p, optimize=True)
        paths.append(p)
    return paths


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True)
    ap.add_argument("--base")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--n", type=int, default=6)
    a = ap.parse_args()
    for p in make_sheets(a.exp, a.base, a.split, a.n):
        print(p)
