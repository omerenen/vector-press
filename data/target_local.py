"""Turn a user folder data/target/ (AI-generated images; optional data/target/vectorizer_ai/<same stem>.svg) into the
evaluation split `target` (no ground truth: metrics are computed against the input image).

  python -m data.target_local
Then:  python -m eval.run --config eval/configs/final.yaml --split target
       python -m eval.run --config eval/configs/vectorizer_ai.yaml --split target     (reads the vectorizer.ai SVGs)
"""
import json
import os
import shutil

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "target")
DST = os.path.join(ROOT, "data", "sets", "target")
EXTS = (".png", ".jpg", ".jpeg", ".webp")


def main():
    if not os.path.isdir(SRC):
        raise SystemExit(f"{SRC} not found")
    shutil.rmtree(DST, ignore_errors=True)
    man = []
    for i, f in enumerate(sorted(x for x in os.listdir(SRC) if x.lower().endswith(EXTS))):
        stem = os.path.splitext(f)[0]
        im = Image.open(os.path.join(SRC, f)).convert("RGBA")
        iid = f"target_{i:04d}"
        d = os.path.join(DST, iid)
        os.makedirs(d)
        im.save(os.path.join(d, "input.png"))
        im.save(os.path.join(d, "gt.png"))
        meta = {"id": iid, "split": "target", "category": "target", "source": f"user:{f}", "stem": stem,
                "license": "user-provided", "width": im.width, "height": im.height, "has_gt": False,
                "transparent": bool((__import__("numpy").asarray(im)[..., 3] < 255).any()),
                "vectorizer_ai": os.path.exists(os.path.join(SRC, "vectorizer_ai", stem + ".svg")),
                "degradation": {"name": "user"}}
        json.dump(meta, open(os.path.join(d, "meta.json"), "w"), indent=1)
        man.append(meta)
    json.dump(man, open(os.path.join(DST, "manifest.json"), "w"), indent=1)
    print(len(man), "images;", sum(m["vectorizer_ai"] for m in man), "with vectorizer.ai SVG")


if __name__ == "__main__":
    main()
