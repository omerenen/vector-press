"""Compare experiment summaries: python -m eval.compare EXP_A EXP_B [--split dev] [--keys ...]

Prints per-category value of B and delta vs A for the main metrics.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from eval.run import REPORTS  # noqa: E402

DEFAULT = ["composite", "ssim", "psnr", "gmsd", "de_mean", "edge_f", "edge_dev", "corner_recall", "prim_recovery",
           "gap_px", "n_paths", "gz_bytes", "time_median"]
LOWER_BETTER = {"gmsd", "de_mean", "de_p95", "edge_dev", "corner_err", "gap_px", "n_paths", "n_nodes", "gz_bytes",
                "bytes", "time_median", "time_p95", "time", "lpips", "mismatch4x"}


def load(exp, split):
    with open(os.path.join(REPORTS, exp, f"summary_{split}.json")) as f:
        return json.load(f)["summary"]


def compare(a, b, split="dev", keys=None):
    keys = keys or DEFAULT
    A, B = load(a, split), load(b, split)
    lines = [f"### {b} vs {a} ({split})\n", "| cat | " + " | ".join(keys) + " |", "|" + "---|" * (len(keys) + 1)]
    for cat in B:
        cells = []
        for k in keys:
            vb, va = B[cat].get(k), A.get(cat, {}).get(k)
            if vb is None:
                cells.append("")
                continue
            s = f"{vb:.0f}" if abs(vb) >= 1000 else (f"{vb:.3f}" if abs(vb) < 10 else f"{vb:.1f}")
            if va is not None and va != 0 and k in ("n_paths", "gz_bytes", "time_median", "n_nodes"):
                s += f" ({(vb / va - 1) * 100:+.0f}%)"
            elif va is not None:
                d = vb - va
                good = (d < 0) if k in LOWER_BETTER else (d > 0)
                s += f" ({d:+.3f}{'✓' if good and abs(d) > 1e-9 else ''})"
            cells.append(s)
        lines.append(f"| {cat} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--keys", nargs="*")
    x = ap.parse_args()
    print(compare(x.a, x.b, x.split, x.keys))
