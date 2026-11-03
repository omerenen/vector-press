"""Build the evaluation datasets (dev + held-out test) deterministically.

Sources (all permissive, see LICENSES.md):
  - Iconify JSON packages from npm (downloaded with `npm pack` into data/cache/npm)
  - procedural scenes (data/procedural.py)
  - CC0 / public-domain photos shipped inside scikit-image

Output: data/sets/<split>/<id>/{input.png, gt.png, gt.svg?, meta.json} and
        data/sets/<split>/manifest.json

Usage: python -m data.build [--per-cat 20] [--seed 1234]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
import tarfile

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from data.procedural import GENERATORS  # noqa: E402
from vectorizer.render import render_svg  # noqa: E402

CACHE = os.path.join(ROOT, "data", "cache", "npm")
SETS = os.path.join(ROOT, "data", "sets")

# Pinned iconify packages: name -> version
PACKAGES = {
    "lucide": "1.2.150", "tabler": "1.2.43", "bi": "1.2.7", "material-symbols": "1.2.97",
    "logos": "1.2.18", "skill-icons": "1.2.4", "vscode-icons": "1.2.95", "flat-color-icons": "1.2.3",
    "fluent-emoji-flat": "1.2.6", "fluent-emoji": "1.2.7", "noto": "1.2.10", "twemoji": "1.2.5",
}


def fetch_packages():
    os.makedirs(CACHE, exist_ok=True)
    for name, ver in PACKAGES.items():
        tgz = os.path.join(CACHE, f"iconify-json-{name}-{ver}.tgz")
        if not os.path.exists(tgz):
            subprocess.run(["npm", "pack", "-q", f"@iconify-json/{name}@{ver}"], cwd=CACHE, check=True)


_icon_cache = {}


def load_iconset(name):
    if name in _icon_cache:
        return _icon_cache[name]
    tgz = os.path.join(CACHE, f"iconify-json-{name}-{PACKAGES[name]}.tgz")
    with tarfile.open(tgz) as tf:
        j = json.load(tf.extractfile("package/icons.json"))
    _icon_cache[name] = j
    return j


def icon_svg(setname, iname, size, color=None, stroke_width=None):
    j = load_iconset(setname)
    ic = j["icons"][iname]
    w = ic.get("width", j.get("width", 16))
    h = ic.get("height", j.get("height", 16))
    body = ic["body"]
    if color:
        body = body.replace("currentColor", color)
    if stroke_width is not None:
        body = re.sub(r'stroke-width="[0-9.]+"', f'stroke-width="{stroke_width}"', body)
    W = size
    H = max(1, int(round(size * h / w)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{W}" height="{H}" viewBox="0 0 {w} {h}">{body}</svg>'), W, H


def usable_icon_names(setname):
    j = load_iconset(setname)
    names = []
    for n, ic in j["icons"].items():
        b = ic["body"]
        if "<image" in b or "<text" in b or "<foreignObject" in b or len(b) > 60000:
            continue
        if setname in ("fluent-emoji", "fluent-emoji-flat", "noto", "twemoji") and ("flag" in n or "keycap" in n):
            continue
        names.append(n)
    return sorted(names)


def split_of(key):
    h = int(hashlib.sha1(key.encode()).hexdigest(), 16)
    return "test" if h % 2 else "dev"


# ---------------------------------------------------------------- degradations
DEGRADATIONS = [("clean", 0.2), ("jpeg", 0.25), ("blur_jpeg", 0.15), ("noise", 0.1),
                ("rescale", 0.15), ("colorshift", 0.1), ("screenshot", 0.05)]


def pick_degradation(rng):
    r = rng.random()
    acc = 0
    for name, p in DEGRADATIONS:
        acc += p
        if r < acc:
            return name
    return "clean"


def _jpeg(rgb, q):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=int(q))
    return np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))


def degrade(rgba, name, rng):
    """Apply degradation; returns (rgba, params). Transparent images skip JPEG."""
    rgb = rgba[..., :3].copy()
    a = rgba[..., 3].copy()
    has_alpha = bool((a < 255).any())
    H, W = a.shape
    params = {"name": name}
    if name == "clean":
        pass
    elif name in ("jpeg", "colorshift", "blur_jpeg", "noise", "rescale"):
        if name == "blur_jpeg":
            s = rng.uniform(0.5, 1.2)
            params["sigma"] = s
            rgb = np.asarray(Image.fromarray(rgb).filter(ImageFilter.GaussianBlur(s)))
        if name == "noise":
            s = rng.uniform(3, 10)
            params["sigma"] = s
            nrng = np.random.default_rng(rng.randrange(1 << 30))
            rgb = np.clip(rgb.astype(np.float32) + nrng.normal(0, s, rgb.shape), 0, 255).astype(np.uint8)
        if name == "rescale":
            f = rng.uniform(0.4, 0.7)
            params["factor"] = f
            sw, sh = max(1, int(W * f)), max(1, int(H * f))
            im = Image.fromarray(rgba).resize((sw, sh), Image.BILINEAR).resize((W, H), Image.BICUBIC)
            arr = np.asarray(im)
            rgb, a = arr[..., :3].copy(), arr[..., 3].copy()
        if name == "colorshift":
            gain = np.array([rng.uniform(0.94, 1.06) for _ in range(3)], np.float32)
            off = np.array([rng.uniform(-8, 8) for _ in range(3)], np.float32)
            params["gain"], params["offset"] = gain.tolist(), off.tolist()
            rgb = np.clip(rgb.astype(np.float32) * gain + off, 0, 255).astype(np.uint8)
        q = None
        if name in ("jpeg",):
            q = rng.randint(40, 90)
        elif name in ("blur_jpeg", "colorshift"):
            q = rng.randint(60, 90)
        elif name in ("noise", "rescale") and rng.random() < 0.5:
            q = rng.randint(70, 92)
        if q and not has_alpha:
            params["quality"] = q
            rgb = _jpeg(rgb, q)
    elif name == "screenshot":
        f = rng.choice([1.25, 1.5, 0.8])
        params["factor"] = f
        sw, sh = max(1, int(W * f)), max(1, int(H * f))
        im = Image.fromarray(rgba).resize((sw, sh), Image.NEAREST).resize((W, H), Image.BILINEAR)
        arr = np.asarray(im)
        rgb, a = arr[..., :3].copy(), arr[..., 3].copy()
    return np.dstack([rgb, a]).astype(np.uint8), params


# ---------------------------------------------------------------- item writers
def write_item(split, iid, category, source, license_, gt_rgba, rgba_in, meta_extra, svg=None, rng=None):
    d = os.path.join(SETS, split, iid)
    os.makedirs(d, exist_ok=True)
    Image.fromarray(rgba_in).save(os.path.join(d, "input.png"))
    Image.fromarray(gt_rgba).save(os.path.join(d, "gt.png"))
    if svg:
        with open(os.path.join(d, "gt.svg"), "w") as f:
            f.write(svg)
    meta = {"id": iid, "split": split, "category": category, "source": source, "license": license_,
            "width": int(gt_rgba.shape[1]), "height": int(gt_rgba.shape[0]),
            "has_gt": svg is not None, "transparent": bool((rgba_in[..., 3] < 255).any())}
    meta.update(meta_extra)
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta


def add_bg(svg, W, H, bg):
    if not bg:
        return svg
    i = svg.find(">") + 1
    # background rect in user units of viewBox: use huge rect to cover
    return svg[:i] + f'<rect x="-10000" y="-10000" width="20000" height="20000" fill="{bg}"/>' + svg[i:]


ICON_COLORS = ["#111111", "#1e66f5", "#d20f39", "#40a02b", "#8839ef", "#fe640b", "#04a5e5", "#2b2b2b"]
BGS = ["#ffffff", "#ffffff", "#f6f6f6", "#fff7e6", "#eaf2ff", "#1b1b1f", "#ffe0e0"]

LIC = {"lucide": "ISC", "tabler": "MIT", "bi": "MIT", "material-symbols": "Apache-2.0", "logos": "CC0-1.0",
       "skill-icons": "MIT", "vscode-icons": "MIT", "flat-color-icons": "MIT", "fluent-emoji-flat": "MIT",
       "fluent-emoji": "MIT", "noto": "Apache-2.0", "twemoji": "CC-BY-4.0"}


def build(per_cat=20, seed=1234):
    fetch_packages()
    manifests = {"dev": [], "test": []}
    # pools of icon names by split
    pools = {}
    for s in PACKAGES:
        names = usable_icon_names(s)
        pools[s] = {"dev": [n for n in names if split_of(s + ":" + n) == "dev"],
                    "test": [n for n in names if split_of(s + ":" + n) == "test"]}

    def iconset_items(split, rng, category, mix, mode):
        out = []
        for setname, k in mix:
            names = rng.sample(pools[setname][split], k)
            for n in names:
                size = rng.choice([192, 256, 320, 384, 448, 512])
                sw = None
                color = None
                bg = None
                if mode == "mono":
                    color = rng.choice(ICON_COLORS)
                    bg = rng.choice(BGS + [None])
                    if bg == "#1b1b1f":
                        color = "#f0f0f0"
                elif mode == "line":
                    color = rng.choice(["#111111", "#202733"])
                    bg = rng.choice(["#ffffff", "#fbf8f1"])
                    size = rng.choice([448, 512, 640])
                    sw = rng.choice([0.3, 0.4, 0.5])
                else:
                    bg = rng.choice(["#ffffff", "#ffffff", "#f6f6f6", None, "#eaf2ff"])
                svg, W, H = icon_svg(setname, n, size, color=color, stroke_width=sw)
                svg = add_bg(svg, W, H, bg)
                out.append((f"{setname}:{n}", setname, svg, W, H))
        return out

    for split in ("dev", "test"):
        rng = random.Random(f"{seed}-{split}")
        idx = 0
        spec = {
            "icon": ("icons", [("lucide", 5), ("tabler", 5), ("bi", 5), ("material-symbols", 5)], "mono"),
            "logo": ("icons", [("logos", 8), ("skill-icons", 4), ("vscode-icons", 4), ("flat-color-icons", 4)], "color"),
            "flat_illustration": ("icons", [("fluent-emoji-flat", 6), ("noto", 4), ("twemoji", 4)], "color"),
            "gradient": ("icons", [("fluent-emoji", 10)], "color"),
            "line_art": ("icons", [("tabler", 4), ("lucide", 4)], "line"),
        }
        proc = {"flat_illustration": ("shapes", 6), "gradient": ("gradient", 10), "line_art": ("line_art", 12),
                "diagram": ("diagram", 20)}
        scale = per_cat / 20.0
        for cat in ["icon", "logo", "flat_illustration", "gradient", "line_art", "diagram"]:
            items = []
            if cat in spec:
                _, mix, mode = spec[cat]
                mix = [(s, max(1, int(round(k * scale)))) for s, k in mix]
                for key, setname, svg, W, H in iconset_items(split, rng, cat, mix, mode):
                    items.append((key, LIC[setname], svg, W, H, {}))
            if cat in proc:
                kind, k = proc[cat]
                for j in range(max(1, int(round(k * scale)))):
                    S = rng.choice([256, 320, 384, 448, 512])
                    ar = rng.uniform(0.75, 1.33)
                    W, H = (S, int(S / ar)) if ar > 1 else (int(S * ar), S)
                    sc = GENERATORS[kind](random.Random(f"{seed}-{split}-{cat}-{j}"), W, H)
                    items.append((f"procedural:{kind}:{j}", "CC0-1.0 (generated)", sc.svg, W, H,
                                  {"primitives": sc.primitives, "corners": sc.corners}))
            for key, lic, svg, W, H, extra in items:
                gt = render_svg(svg, W, H)
                dname = pick_degradation(rng)
                inp, params = degrade(gt, dname, rng)
                iid = f"{split}_{idx:04d}"
                idx += 1
                extra = dict(extra)
                extra["degradation"] = params
                m = write_item(split, iid, cat, key, lic, gt, inp, extra, svg=svg)
                manifests[split].append(m)
                print(split, iid, cat, key, dname, flush=True)
        # photos (no ground truth SVG: evaluate vs. the clean photo)
        from skimage import data as skd
        photos = {"dev": ["coffee", "chelsea", "rocket", "camera"],
                  "test": ["astronaut", "hubble_deep_field", "retina", "immunohistochemistry"]}
        plic = {"coffee": "CC0-1.0", "chelsea": "CC0-1.0", "rocket": "Public domain (SpaceX)",
                "camera": "CC0-1.0", "astronaut": "Public domain (NASA)", "hubble_deep_field": "Public domain (NASA)",
                "retina": "CC0-1.0", "immunohistochemistry": "No known copyright restrictions"}
        nph = max(2, int(round(10 * scale)))
        k = 0
        while k < nph:
            p = photos[split][k % len(photos[split])]
            arr = getattr(skd, p)()
            if arr.ndim == 2:
                arr = np.stack([arr] * 3, -1)
            arr = arr[..., :3]
            H0, W0 = arr.shape[:2]
            if k >= len(photos[split]):  # random crop variant
                cs = rng.uniform(0.45, 0.7)
                ch, cw = int(H0 * cs), int(W0 * cs)
                y0, x0 = rng.randrange(0, H0 - ch + 1), rng.randrange(0, W0 - cw + 1)
                arr = arr[y0:y0 + ch, x0:x0 + cw]
            im = Image.fromarray(arr)
            mx = max(im.size)
            tgt = rng.choice([320, 384, 448, 512])
            if mx > tgt:
                im = im.resize((max(1, int(im.width * tgt / mx)), max(1, int(im.height * tgt / mx))), Image.LANCZOS)
            gt = np.dstack([np.asarray(im), np.full((im.height, im.width), 255, np.uint8)])
            dname = rng.choice(["clean", "jpeg"])
            inp, params = degrade(gt, dname, rng)
            iid = f"{split}_{idx:04d}"
            idx += 1
            m = write_item(split, iid, "photo", f"skimage:{p}", plic[p], gt, inp, {"degradation": params}, svg=None)
            manifests[split].append(m)
            print(split, iid, "photo", p, dname, flush=True)
            k += 1
        with open(os.path.join(SETS, split, "manifest.json"), "w") as f:
            json.dump(manifests[split], f, indent=1)
    return manifests


def build_proc2(seed=777, per_kind=15):
    """Procedural-only set with a NEW seed and DIFFERENT ranges (bigger canvases, more shapes, other stroke widths)."""
    from data import procedural as P
    P.P.update(shapes_n=(8, 18), diagram_n=(5, 9), diagram_sw=(0.9, 2.5), grad_n=(4, 9), line_n=(6, 12),
               line_sw=(0.8, 3.0))
    rng = random.Random(f"proc2-{seed}")
    cat_of = {"shapes": "flat_illustration", "diagram": "diagram", "gradient": "gradient", "line_art": "line_art"}
    man, idx = [], 0
    for kind in ("shapes", "diagram", "gradient", "line_art"):
        for j in range(per_kind):
            S = rng.choice([640, 768, 896, 1024])
            ar = rng.uniform(0.6, 1.6)
            W, H = (S, int(S / ar)) if ar > 1 else (int(S * ar), S)
            sc = GENERATORS[kind](random.Random(f"proc2-{seed}-{kind}-{j}"), W, H)
            gt = render_svg(sc.svg, W, H)
            dname = pick_degradation(rng)
            inp, params = degrade(gt, dname, rng)
            iid = f"proc2_{idx:04d}"
            idx += 1
            m = write_item("proc2", iid, cat_of[kind], f"procedural2:{kind}:{j}", "CC0-1.0 (generated)", gt, inp,
                           {"primitives": sc.primitives, "corners": sc.corners, "degradation": params}, svg=sc.svg)
            man.append(m)
            print("proc2", iid, kind, dname, flush=True)
    with open(os.path.join(SETS, "proc2", "manifest.json"), "w") as f:
        json.dump(man, f, indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cat", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--proc2", action="store_true",
                    help="overfitting check: procedural scenes only, new seed + different parameter ranges -> split proc2")
    a = ap.parse_args()
    import shutil
    if a.proc2:
        shutil.rmtree(os.path.join(SETS, "proc2"), ignore_errors=True)
        build_proc2(seed=a.seed if a.seed != 1234 else 777)
    else:
        for sp in ("dev", "test"):
            shutil.rmtree(os.path.join(SETS, sp), ignore_errors=True)
        build(a.per_cat, a.seed)
