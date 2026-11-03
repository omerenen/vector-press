import os

from PIL import Image, ImageDraw

from vectorizer.cli import main


def test_cli_single_and_batch(tmp_path):
    d = tmp_path / "in"
    d.mkdir()
    for i in range(2):
        im = Image.new("RGB", (60, 60), "white")
        ImageDraw.Draw(im).rectangle((10, 10, 40 + i * 5, 40), fill=(200, 0, 0))
        im.save(d / f"img{i}.png")
    out = tmp_path / "one.svg"
    assert main([str(d / "img0.png"), "-o", str(out), "--preset", "logo"]) == 0
    assert out.read_text().startswith("<svg")
    od = tmp_path / "out"
    assert main([str(d), "-o", str(od), "--stats", "--detail", "0.7"]) == 0
    assert sorted(os.listdir(od)) == ["img0.svg", "img1.svg"]
