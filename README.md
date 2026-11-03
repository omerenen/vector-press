# vector-press

Raster görselleri (PNG / JPG / WebP …) yüksek doğruluklu, temiz ve kompakt SVG'ye dönüştüren vektörleştirme motoru.
VTracer'ın zayıf noktalarını kapatmak için kendi **paylaşımlı sınır grafiği (shared boundary graph)** motorunu,
renk niceleme, köşe/eğri/primitif uydurma, alt-piksel kenar yerleştirme ve gradyan uydurma aşamalarını içerir;
fotoğraflar için ayarlanmış VTracer arka ucunu kullanır. Yalnızca CPU, saf Python + pip tekerlekleri (macOS ve Linux).

Sonuçlar ve ölçümler: **[REPORT.md](REPORT.md)** · deney günlüğü: [EXPERIMENTS.md](EXPERIMENTS.md) ·
araştırma notları: [RESEARCH.md](RESEARCH.md) · lisanslar: [LICENSES.md](LICENSES.md)

## macOS kurulumu (Apple Silicon, adım adım)

```bash
# 1) Homebrew (yoksa): https://brew.sh
brew install python@3.12 git
```

```bash
# 2) Depoyu klonla
git clone https://github.com/omerenen/vector-press.git
cd vector-press
git checkout claude/laughing-rubin-n46tic
```

```bash
# 3) Proje içi sanal ortam
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .          # `vectorize` komutunu kurar
```

```bash
# 4) Kontrol
python -m pytest -q
vectorize --help
```

Lisanslar: tüm çalışma zamanı bağımlılıkları izin verici (MIT/BSD/Apache/Zlib…); ayrıntılar ve kontrol komutları
[LICENSES.md](LICENSES.md) içinde.

## Komut satırı (CLI)

```bash
vectorize logo.png -o logo.svg
```

```bash
vectorize logo.png -o logo.svg --preset logo --mode max --colors 6 --detail 0.7 --corner-sharpness 0.8
```

```bash
vectorize ./girdiler -o ./ciktilar --stats      # toplu (batch) mod, her görsel için JSON istatistik
```

Seçenekler: `--preset {auto, logo, icon, illustration, flat_illustration, line_art, diagram, gradient, photo, photo_posterize}`,
`--mode {fast, max}`, `--colors N|auto`, `--detail 0..1`, `--corner-sharpness 0..1`, `--primitives true|false`,
`--gradients true|false`, `--centerline true|false`. (`python -m vectorizer ...` de çalışır.)

## Python API

```python
from vectorizer import vectorize

res = vectorize("logo.png")                  # yol, bytes, PIL.Image veya numpy dizisi
res.save("logo.svg")
print(res.stats["image_type"], res.stats["preset"], res.stats["timings"], res.stats["bytes"])

res = vectorize(open("cizim.jpg", "rb").read(), preset="line_art", mode="max", detail=0.6, centerline=False)
svg_text = res.svg
```

`vectorize(image, preset="auto", mode="fast", **options) -> Result(svg: str, stats: dict)`

| seçenek (UI için) | değer | etkisi |
|---|---|---|
| `preset` | `auto` (sınıflandırıcı) veya hazır ayar adı | içerik türüne göre ayarlar |
| `mode` | `fast` (varsayılan) / `max` | `max`: düz grafikler 2× çözünürlükte işlenir (daha yüksek doğruluk, ~3-5× süre, ~%20-100 daha büyük dosya) |
| `colors` | `"auto"` veya tamsayı | en fazla renk sayısı |
| `detail` | 0 (kaba) … 1 (ince), varsayılan 0.5 | eğri toleransı, renk birleştirme yarıçapı, benek boyutu |
| `corner_sharpness` | 0 (yuvarlak) … 1 (keskin), varsayılan 0.5 | köşe algılama eşiği |
| `primitives` | bool | daire/elips/dikdörtgen/yuvarlak dikdörtgen öğeleri |
| `gradients` | bool | doğrusal / dairesel / eliptik gradyan dolguları |
| `centerline` | bool (varsayılan kapalı) | ince çizgileri `stroke` yolları olarak izle (düzenlenebilirlik; doğruluğu biraz düşürür) |

`stats` alanları: `image_type` (icon / logo / line_art / gradient / photo), `preset`, `width`, `height`, `timings`
(aşama başına saniye: classify, quantize, gradients, graph, fit, assemble, total), `n_colors`, `n_regions`, `n_chains`,
`n_primitives`, `n_gradients`, `bytes`. Gelişmiş/iç parametreler: `vectorizer/api.py` içindeki `DEFAULTS`.

## Nasıl çalışır (kısaca)

1. **Yükleme**: her tür PNG/JPEG/WebP/CMYK/16-bit/paletli/alfa → RGBA.
2. **Sınıflandırma** (W7): 256 px küçük resim özelliklerinden karar kuralları → hazır ayar.
3. **Ön işleme** (W1): OKLab'da kenar koruyan sigma filtresi.
4. **Niceleme** (W2): "karışık" (anti-alias) pikselleri hariç tutan OKLab histogram mod arama + k-means; AA pikselleri
   yalnızca komşu saf renklere atanır; ince çizgi kurtarma; benek birleştirme; karışım renkli şerit (sliver) temizleme.
5. **Gradyanlar** (W6): yumuşak şerit sınırlarının tespiti, doğrusal/dairesel/eliptik çok duraklı gradyan uydurma.
6. **Sınır grafiği** (W5): piksel çatlak kafesinde her komşu bölge çifti arasındaki sınır bir kez izlenir; iki bölge de
   aynı eğriyi kullanır → boşluk/kılcal çatlak oluşamaz.
7. **Uydurma** (W3, W4): alt-piksel kenar konumu (AA değerlerinden), çok ölçekli köşe algılama, doğru parçası yakalama,
   Schneider Bézier uydurma, kapalı sınırlar için daire/elips/dikdörtgen/yuvarlak dikdörtgen primitifleri.
8. **Çıktı** (W10): iç içe derinlik düzeyleri, renk başına birleştirilmiş yollar, bitişik sınırlar için ince "dikiş"
   alt-çizgileri, göreli komutlar, 2 ondalık hassasiyet.

## Değerlendirme

```bash
python -m data.build                 # dev + ayrılmış test kümeleri (npm gerekir; deterministik)
make test
make eval EXP=final SPLIT=test       # tek deney
make eval-all                        # REPORT.md'deki tüm sayılar (test kümesi) + kontak sayfaları + hız ölçümü
python -m eval.compare exp_001_baseline_tuned final --split test
```

Raporlar `eval/reports/<deney>/` altında (`summary_test.md`, `sheet_<kategori>.png`). Metrikler ve bileşik skor:
EXPERIMENTS.md → "E-metrics".

## Depo yapısı

```
vectorizer/          paket: api.py, cli.py, presets.py, imageio.py, render.py
  pipeline/          classify, preprocess, quantize, gradients, boundary, fit, assemble, centerline, svgout, trace (VTracer)
data/                veri kümesi oluşturucu + prosedürel sahne üreteci (büyük dosyalar repoda değil)
eval/                metrikler, çalıştırıcı, karşılaştırma, kontak sayfaları, hız ölçümü, configs/, reports/
tests/               pytest birim + entegrasyon + uç durum testleri
models/              (öğrenilmiş model kullanılmadı — gerekçe RESEARCH.md'de)
```
