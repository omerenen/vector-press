"""AI-generated target benchmark from OpenDatasets/dalle-3-dataset (CC0-1.0, HuggingFace; DALL-E 3 images with prompts).

Use-case prompts (stickers, t-shirt / screen-print designs, logos / emblems / mascots, flat vector illustrations,
posters, silhouettes / cut-files / line art / icons). Deterministic: captions of all shards are scanned, row groups are
ranked by number of matches, whole row groups are downloaded until enough images are collected (no manual picking),
one image per distinct prompt, split by hash of the image hash into tdev (tuning) / ttest (held-out).

  python -m data.target_dalle3 [--n 120]
Output: data/sets/{tdev,ttest}/<id>/{input.png, gt.png (= input), meta.json} + manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402

from data.target_fetch import HTTPRangeFile  # noqa: E402

REVISION = "96822d5c0b1338ec4bfd04b0d5909fa070e301b6"  # pinned dataset snapshot (reproducible selection)
REPO = f"https://huggingface.co/datasets/OpenDatasets/dalle-3-dataset/resolve/{REVISION}/"
SETS = os.path.join(ROOT, "data", "sets")
CACHE = os.path.join(ROOT, "data", "cache", "dalle3")

CATS = [  # first match wins; prompts must express *design intent*, photographic prompts are excluded
    ("sticker", r"\bstickers?\b|die[- ]?cut"),
    ("tshirt", r"t-?shirt (design|print|graphic|art)|design (for|on) a t-?shirt|tee design|screen ?print"),
    ("logo", r"logo design|\blogo (for|of)\b|\bemblem\b|mascot|badge design|brand mark"),
    ("cutfile", r"silhouette|stencil|papercut|paper[- ]cut|laser[- ]cut|line art|lineart|\bsvg\b|\bicons?\b|"
                r"coloring (book|page)|black and white (illustration|drawing)"),
    ("vector_flat", r"vector|flat (design|illustration|colou?rs?|style)|clip ?art|cel[- ]shaded|minimalist illustration|"
                    r"cartoon(ish)? illustration|graphic design"),
    ("poster", r"\bposter\b"),
]
EXCLUDE = r"\bphoto|photograph|photo-?realistic|\brealistic|hyper-?realistic|cinematic|\b8k\b|\bdslr\b|bokeh|portrait of"


def category(caption):
    if re.search(EXCLUDE, caption or "", re.I):
        return None
    for c, p in CATS:
        if re.search(p, caption or "", re.I):
            return c
    return None


def shard_list():
    import json as _j
    import urllib.request
    with urllib.request.urlopen(f"https://huggingface.co/api/datasets/OpenDatasets/dalle-3-dataset/revision/{REVISION}", timeout=60) as r:
        d = _j.load(r)
    return sorted(s["rfilename"] for s in d["siblings"] if s["rfilename"].endswith(".parquet"))


def scan():
    import pyarrow.parquet as pq
    os.makedirs(CACHE, exist_ok=True)
    idx_path = os.path.join(CACHE, "captions_all.json")
    if os.path.exists(idx_path):
        allrows = json.load(open(idx_path))
        out = []
        for r in allrows:
            c = category(r["caption"])
            if c:
                out.append(dict(r, cat=c))
        return out
    rows = []
    for sh in shard_list():
        pf = pq.ParquetFile(HTTPRangeFile(REPO + sh, block=1 << 20))
        off = 0
        for rg in range(pf.metadata.num_row_groups):
            t = pf.read_row_group(rg, columns=["caption", "image_hash"])
            for i, (c, h) in enumerate(zip(t.column("caption").to_pylist(), t.column("image_hash").to_pylist())):
                rows.append({"shard": sh, "rg": rg, "i": i, "caption": c, "hash": h})
            off += t.num_rows
        print("scanned", sh, len(rows), flush=True)
    json.dump(rows, open(idx_path, "w"))
    return scan()


def split_of(h):
    return "ttest" if int(hashlib.sha1(str(h).encode()).hexdigest(), 16) % 2 else "tdev"


def main():
    import pyarrow.parquet as pq
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    a = ap.parse_args()
    rows = scan()
    # one image per distinct prompt
    seen, uniq = set(), []
    for r in rows:
        k = (r["caption"] or "").strip().lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    groups = {}
    for r in uniq:
        groups.setdefault((r["shard"], r["rg"]), []).append(r)
    # greedy, quota-balanced choice of row groups: each category gets up to `quota` images, at most `per_rg`
    # images of a category per row group (prompt series of one user cluster in a row group)
    avail = {c: sum(1 for r in uniq if r["cat"] == c) for c, _ in CATS}
    quota = {c: 0 for c, _ in CATS}
    left = a.n
    while left > 0 and any(quota[c] < avail[c] for c in quota):     # water-filling: equal shares, capped by availability
        for c in quota:
            if left > 0 and quota[c] < avail[c]:
                quota[c] += 1
                left -= 1
    print("quota", quota, flush=True)
    per_rg = 3
    order, take = [], {}
    remaining = dict(groups)
    while any(v > 0 for v in quota.values()) and remaining:
        def gain(g):
            cnt = {}
            for r in remaining[g]:
                cnt[r["cat"]] = cnt.get(r["cat"], 0) + 1
            return sum(min(quota[c], per_rg, n) for c, n in cnt.items())
        best = max(sorted(remaining), key=gain)
        if gain(best) == 0:
            break
        sel, used = [], {}
        for r in remaining[best]:
            c = r["cat"]
            if quota[c] > 0 and used.get(c, 0) < per_rg:
                sel.append(r)
                used[c] = used.get(c, 0) + 1
                quota[c] -= 1
        order.append(best)
        take[best] = sel
        del remaining[best]
    groups = take
    print("row groups to download:", len(order), "quota left:", quota, flush=True)
    for sp in ("tdev", "ttest"):
        shutil.rmtree(os.path.join(SETS, sp), ignore_errors=True)
    man = {"tdev": [], "ttest": []}
    cnt = {"tdev": 0, "ttest": 0}
    total = 0
    for g in order:
        sh, rg = g
        pf = pq.ParquetFile(HTTPRangeFile(REPO + sh, block=1 << 22))
        t = pf.read_row_group(rg, columns=["image", "image_hash"])
        imgs = t.column("image").to_pylist()
        for r in groups[g]:
            rec = imgs[r["i"]]
            raw = rec["bytes"] if isinstance(rec, dict) else rec
            try:
                im = Image.open(io.BytesIO(raw)).convert("RGBA")
            except Exception:
                continue
            sp = split_of(r["hash"])
            iid = f"{sp}_{cnt[sp]:04d}"
            cnt[sp] += 1
            total += 1
            d = os.path.join(SETS, sp, iid)
            os.makedirs(d, exist_ok=True)
            im.save(os.path.join(d, "input.png"))
            im.save(os.path.join(d, "gt.png"))
            meta = {"id": iid, "split": sp, "category": r["cat"], "source": f"dalle3:{sh}:{rg}:{r['i']}",
                    "license": "CC0-1.0 (OpenDatasets/dalle-3-dataset)", "prompt": r["caption"],
                    "width": im.width, "height": im.height, "has_gt": False, "transparent": False,
                    "degradation": {"name": "ai_generated"}}
            json.dump(meta, open(os.path.join(d, "meta.json"), "w"), indent=1)
            man[sp].append(meta)
            print(sp, iid, r["cat"], im.size, (r["caption"] or "")[:70].replace("\n", " "), flush=True)
    for sp in man:
        os.makedirs(os.path.join(SETS, sp), exist_ok=True)
        json.dump(man[sp], open(os.path.join(SETS, sp, "manifest.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
