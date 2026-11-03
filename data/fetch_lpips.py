"""Fetch the torchvision AlexNet ImageNet weights (BSD-3-Clause, torchvision) used by LPIPS (evaluation only).

download.pytorch.org is blocked in the development container; a HuggingFace mirror is used and the file is accepted
only if its SHA-256 equals the official one (the hash prefix is part of torchvision's file name).
  python -m data.fetch_lpips
"""
import hashlib
import os
import urllib.request

SHA = "7be5be791159472b1fbf3c69796f7cb30dca7ad8466c2df70058c37116cdee02"
URLS = ["https://download.pytorch.org/models/alexnet-owt-7be5be79.pth",
        "https://huggingface.co/blanchon/image-gs-models-utils/resolve/main/torch/checkpoints/alexnet-owt-7be5be79.pth"]


def main():
    d = os.path.join(os.path.expanduser("~"), ".cache", "torch", "hub", "checkpoints")
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "alexnet-owt-7be5be79.pth")
    if os.path.exists(dst) and hashlib.sha256(open(dst, "rb").read()).hexdigest() == SHA:
        print("ok", dst)
        return
    for u in URLS:
        try:
            urllib.request.urlretrieve(u, dst + ".part")
        except Exception as e:
            print("failed", u, e)
            continue
        if hashlib.sha256(open(dst + ".part", "rb").read()).hexdigest() == SHA:
            os.replace(dst + ".part", dst)
            print("ok", dst, "from", u)
            return
        print("hash mismatch", u)
    raise SystemExit("could not obtain verified AlexNet weights")


if __name__ == "__main__":
    main()
