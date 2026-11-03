"""Build the AI-generated *target* benchmark from DiffusionDB (CC0-1.0, poloclub/diffusiondb on HuggingFace).

Real Stable Diffusion outputs whose prompts match the use case (stickers, t-shirt / screen-print designs, logos /
emblems, flat vector illustrations, graphic posters, silhouettes / cut-files / line art). Selection is deterministic
(fixed seed, NSFW-filtered by the dataset's own scores, no manual picking). Images are split by a hash of the image
name into `tdev` (tuning) and `ttest` (held-out, never tuned on).

Only the needed files are read out of the remote part-*.zip archives with HTTP range requests.

  python -m data.target_fetch [--per-cat 20]
Output: data/sets/{tdev,ttest}/<id>/{input.png, gt.png, meta.json} + manifest.json   (gt = input: no ground truth)
A user-provided folder data/target/ (+ data/target/vectorizer_ai/) is handled by data/target_local.py.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import urllib.request
import zipfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cache", "diffusiondb")
SETS = os.path.join(ROOT, "data", "sets")
BASE = "https://huggingface.co/datasets/poloclub/diffusiondb/resolve/main"
META_URL = BASE + "/metadata.parquet"

CATS = {
    "sticker": r"\bsticker|die[- ]?cut",
    "tshirt": r"t-?shirt|tee design|screen ?print",
    "logo": r"\blogo\b|emblem|\bbadge\b|mascot",
    "vector_flat": r"vector art|vector illustration|flat design|flat illustration|flat colou?rs?|\bsvg\b|clip ?art",
    "poster": r"\bposter\b.*(flat|vector|minimal|graphic|illustration|retro|vintage|art deco|screen ?print)|"
              r"(flat|vector|minimal|graphic|retro|vintage|art deco).*\bposter\b",
    "cutfile": r"silhouette|stencil|papercut|paper cut|laser cut|cricut|line art|lineart",
}


class HTTPRangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP range requests (64 KiB blocks, small cache)."""

    def __init__(self, url, block=1 << 16):
        self.url, self.block, self.pos, self.cache = url, block, 0, {}
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as r:
            self.size = int(r.headers["Content-Length"])
            self.url = r.geturl()

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def _get(self, a, b):
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={a}-{b - 1}"})
        for _ in range(4):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return r.read()
            except Exception:  # transient network error -> retry
                continue
        raise IOError(f"range request failed {a}-{b}")

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        if n == 0:
            return b""
        if n > 4 * self.block:                         # large read: fetch directly
            data = self._get(self.pos, self.pos + n)
        else:
            out = bytearray()
            p, end = self.pos, self.pos + n
            while p < end:
                bi = p // self.block
                if bi not in self.cache:
                    if len(self.cache) > 64:
                        self.cache.clear()
                    a = bi * self.block
                    self.cache[bi] = self._get(a, min(self.size, a + self.block))
                blk = self.cache[bi]
                o = p - bi * self.block
                take = min(end - p, len(blk) - o)
                out += blk[o:o + take]
                p += take
            data = bytes(out)
        self.pos += len(data)
        return data

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)


def split_of(name):
    return "ttest" if int(hashlib.sha1(name.encode()).hexdigest(), 16) % 2 else "tdev"


def select(per_cat, seed=2024):
    import pandas as pd
    os.makedirs(CACHE, exist_ok=True)
    mp = os.path.join(CACHE, "metadata.parquet")
    if not os.path.exists(mp):
        urllib.request.urlretrieve(META_URL, mp)
    df = pd.read_parquet(mp)
    df = df[(df.image_nsfw < 0.15) & (df.prompt_nsfw < 0.05) & (df.width >= 512) & (df.height >= 512)]
    df = df.drop_duplicates("prompt")                  # many users re-run the same prompt
    rng = np.random.default_rng(seed)
    chosen, used = [], set()
    for cat, pat in CATS.items():
        m = df[df.prompt.str.contains(pat, case=False, regex=True) & ~df.image_name.isin(used)]
        idx = rng.permutation(len(m))
        picked = {"tdev": 0, "ttest": 0}
        for i in idx:
            row = m.iloc[i]
            sp = split_of(row.image_name)
            if picked[sp] >= per_cat // 2:
                continue
            picked[sp] += 1
            used.add(row.image_name)
            chosen.append((cat, sp, row))
            if all(v >= per_cat // 2 for v in picked.values()):
                break
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cat", type=int, default=20)
    a = ap.parse_args()
    chosen = select(a.per_cat)
    by_part = {}
    for c in chosen:
        by_part.setdefault(int(c[2].part_id), []).append(c)
    for sp in ("tdev", "ttest"):
        shutil.rmtree(os.path.join(SETS, sp), ignore_errors=True)
    manifests = {"tdev": [], "ttest": []}
    counters = {"tdev": 0, "ttest": 0}
    for part, items in sorted(by_part.items()):
        url = f"{BASE}/images/part-{part:06d}.zip"
        zf = zipfile.ZipFile(HTTPRangeFile(url))
        for cat, sp, row in items:
            raw = zf.read(row.image_name)
            im = Image.open(io.BytesIO(raw)).convert("RGBA")
            iid = f"{sp}_{counters[sp]:04d}"
            counters[sp] += 1
            d = os.path.join(SETS, sp, iid)
            os.makedirs(d, exist_ok=True)
            im.save(os.path.join(d, "input.png"))
            im.save(os.path.join(d, "gt.png"))
            meta = {"id": iid, "split": sp, "category": cat, "source": f"diffusiondb:{row.image_name}",
                    "license": "CC0-1.0 (DiffusionDB)", "prompt": row.prompt, "width": im.width, "height": im.height,
                    "has_gt": False, "transparent": False, "degradation": {"name": "ai_generated"}}
            with open(os.path.join(d, "meta.json"), "w") as f:
                json.dump(meta, f, indent=1)
            manifests[sp].append(meta)
            print(sp, iid, cat, row.image_name, row.prompt[:70].replace("\n", " "), flush=True)
    for sp in manifests:
        with open(os.path.join(SETS, sp, "manifest.json"), "w") as f:
            json.dump(manifests[sp], f, indent=1)


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    main()
