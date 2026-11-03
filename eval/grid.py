"""Per-category grid search of plain VTracer parameters on the dev split.

  python -m eval.grid  -> writes eval/configs/exp_001_baseline_tuned.yaml and eval/reports/grid/grid.json
Resumable: finished configs are cached in eval/reports/grid/grid.json.
"""
from __future__ import annotations

import itertools
import json
import os
import shutil
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from eval.run import CATEGORIES, REPORTS, RUNS, run  # noqa: E402

OUT = os.path.join(REPORTS, "grid")


def key(p):
    return ",".join(f"{k}={p[k]}" for k in sorted(p))


def main():
    os.makedirs(OUT, exist_ok=True)
    gpath = os.path.join(OUT, "grid.json")
    done = json.load(open(gpath)) if os.path.exists(gpath) else {}

    def evaluate(p):
        k = key(p)
        if k in done:
            return done[k]
        name = "grid_tmp"
        _, summ = run({"name": name, "method": "vtracer", "params": p}, "dev", workers=4)
        done[k] = {"params": p, "summary": {c: {m: s.get(m) for m in ("composite", "ssim", "de_mean", "edge_f", "n_paths", "gz_bytes")}
                                            for c, s in summ.items()}}
        json.dump(done, open(gpath, "w"), indent=1)
        shutil.rmtree(os.path.join(RUNS, name), ignore_errors=True)
        print(k, {c: round(s["composite"], 4) for c, s in done[k]["summary"].items()}, flush=True)
        return done[k]

    stage1 = [dict(filter_speckle=f, color_precision=c, layer_difference=l)
              for f, c, l in itertools.product([2, 4, 8, 16], [6, 7, 8], [8, 16, 32])]
    for p in stage1:
        evaluate(p)
    best = {}
    for cat in CATEGORIES + ["ALL"]:
        cands = [v for v in done.values() if set(v["params"]) == {"filter_speckle", "color_precision", "layer_difference"}]
        best[cat] = max(cands, key=lambda v: v["summary"].get(cat, {}).get("composite", -1))["params"]
    # stage 2: curve params on top of each category's stage-1 best
    for cat in CATEGORIES:
        for ct, lt in itertools.product([30, 60, 90, 135], [4.0]):
            p = dict(best[cat], corner_threshold=ct, length_threshold=lt)
            evaluate(p)
        cands = [v for v in done.values() if all(v["params"].get(k) == best[cat][k] for k in ("filter_speckle", "color_precision", "layer_difference"))]
        best[cat] = max(cands, key=lambda v: v["summary"].get(cat, {}).get("composite", -1))["params"]
    cfg = {"name": "exp_001_baseline_tuned", "method": "vtracer",
           "description": "Plain VTracer with per-category parameters tuned by grid search on dev (oracle category).",
           "params": {}, "per_category": best}
    best.pop("ALL", None)
    with open(os.path.join(ROOT, "eval", "configs", "exp_001_baseline_tuned.yaml"), "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    print(yaml.safe_dump(best))


if __name__ == "__main__":
    main()
