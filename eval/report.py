"""Build the result tables used in REPORT.md from the test-split summaries.

  python -m eval.report > eval/reports/report_tables.md
"""
from __future__ import annotations

import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from eval.run import CATEGORIES, REPORTS, RUNS  # noqa: E402


def S(exp, split="test"):
    with open(os.path.join(REPORTS, exp, f"summary_{split}.json")) as f:
        return json.load(f)["summary"]


def f(v, k):
    if v is None:
        return "–"
    if k in ("gz_bytes", "n_paths", "n_nodes"):
        return f"{v:.0f}"
    if k in ("psnr",):
        return f"{v:.1f}"
    return f"{v:.3f}"


def main():
    base0, base1, fin, mx = S("exp_000_baseline"), S("exp_001_baseline_tuned"), S("final"), S("final_max")
    out = ["# Result tables (held-out test split, 130 images)\n"]
    keys = ["composite", "ssim", "psnr", "gmsd", "de_mean", "edge_f", "edge_dev", "n_paths", "gz_bytes"]
    out.append("## Per category: VTracer default → VTracer tuned → **final (fast)** → final (max)\n")
    for k in keys:
        out.append(f"\n### {k}\n\n| category | VTracer default | VTracer tuned | final | final max |\n|---|---|---|---|---|")
        for c in ["ALL"] + CATEGORIES:
            out.append(f"| {c} | {f(base0[c].get(k), k)} | {f(base1[c].get(k), k)} | **{f(fin[c].get(k), k)}** | {f(mx[c].get(k), k)} |")
    out.append("\n## Geometry (synthetic items with ground-truth SVG)\n")
    out.append("| metric | VTracer default | VTracer cutout | VTracer tuned | final | final max |\n|---|---|---|---|---|---|")
    try:
        cut = S("exp_000b_cutout")
    except FileNotFoundError:
        cut = {"ALL": {}}
    for k in ["corner_recall", "corner_err", "prim_recovery", "gap_px", "edge_dev"]:
        out.append(f"| {k} | {f(base0['ALL'].get(k), k)} | {f(cut['ALL'].get(k), k)} | {f(base1['ALL'].get(k), k)} | "
                   f"{f(fin['ALL'].get(k), k)} | {f(mx['ALL'].get(k), k)} |")
    out.append(f"\nPrimitive recovery pooled by type (final): {fin['ALL'].get('prim_pooled')}\n")
    out.append(f"Valid SVG rate: final {fin['ALL']['valid_rate']:.3f}, final max {mx['ALL']['valid_rate']:.3f}\n")
    # classifier confusion
    recs = [json.loads(l) for l in open(os.path.join(RUNS, "final", "test", "metrics.jsonl"))]
    conf = collections.Counter((r["category"], r.get("detected_type")) for r in recs)
    fam = {"icon": "flat", "logo": "flat", "flat_illustration": "flat", "line_art": "lines", "diagram": "lines",
           "gradient": "gradient", "photo": "photo"}
    famd = {"icon": "flat", "logo": "flat", "line_art": "lines", "gradient": "gradient", "photo": "photo"}
    ok = sum(n for (c, d), n in conf.items() if fam[c] == famd.get(d))
    out.append(f"\n## Classifier (test): preset-family accuracy {ok}/{len(recs)} = {ok / len(recs):.2f}\n")
    out.append("| true category | detected → count |\n|---|---|")
    for c in CATEGORIES:
        out.append(f"| {c} | " + ", ".join(f"{d}: {n}" for (cc, d), n in sorted(conf.items()) if cc == c) + " |")
    bp = os.path.join(REPORTS, "bench_test.json")
    if os.path.exists(bp):
        b = json.load(open(bp))
        out.append(f"\n## Speed (1024 px, single process, {b['cpu']})\nmedian {b['median_s']:.2f} s, p95 {b['p95_s']:.2f} s, "
                   f"max {b['max_s']:.2f} s (n={b['n']}); stage medians: "
                   + ", ".join(f"{k} {v:.2f}s" for k, v in b["stages_median"].items()))
    print("\n".join(out))


if __name__ == "__main__":
    main()
