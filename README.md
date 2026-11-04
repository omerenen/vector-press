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
# 3b) (önerilir) geometri eki: kesim/baskı için kendini kesen yol onarımı + baskı/kesim metrikleri
pip install -r requirements-geometry.txt
```
Kurulum notu: `shapely` (BSD-3) tekerlekleri GEOS kütüphanesini (LGPL-2.1, dinamik bağlı) içerir. Proje kuralı "yalnız
izin verici lisanslar" olduğu için çekirdek kurulumda değildir; kurulmazsa vektörleştirici yine çalışır, yalnız geometri
onarımı atlanır (`stats["geom_repair"]`). Ayrıntı: [LICENSES.md](LICENSES.md).

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

### Baskı ve kesim (print / cut)

```bash
vectorize tasarim.png -o kesim.svg --preset cut          # vinil / Cricut / lazer: kesim dosyası
```

```bash
vectorize poster.png -o baski.svg --preset print         # baskı: temiz katmanlı vektör (her zaman kendi motoru)
```

- `cut`: her bölge gerçek delikleriyle (cutout, üst üste binme yok, dikiş çizgisi yok), en fazla 8 düz renk (birbirine
  çok yakın renkler — CIE76 ΔE < 6 — tek katmanda birleşir), gradyan ve yarı saydamlık yok, arka plan rengi atılır.
  `cut_width_mm` (varsayılan 100 mm) çıktı genişliğinde `min_feature_mm` (0.5 mm) altındaki ince parçalar ve adacıklar
  **azaltılır** (piksel düzeyinde morfolojik açma; eğri uydurmadan sonra birkaç ince uç kalabilir — ttest'te görsel başına
  medyan ~26). Bir renk birden çok öğeden oluşabilir (yol + daire/dikdörtgen primitifleri); kesim yazılımları katmanları
  renge göre gruplar. `silhouette=True` ile tek renk siluet.
- `print`: üst üste (stacked), gradyanlı, VTracer'a hiç düşmeyen bölge motoru: az renk, neredeyse hiç kendini kesen yol
  yok, çok az örtüşme. **Doğruluğu `auto`dan düşüktür** (dokulu yapay zekâ görsellerinde ince tarama/doku sadeleşir;
  ttest bileşik 0.625 vs `auto` 0.705) ve dokulu 1024 px görsellerde yavaştır (10–40 s). Fotoğraf benzeri en yüksek
  doğruluk için `auto` kullanın.
- Kendini kesen yolların onarımı (`geom_repair`) isteğe bağlı `shapely` paketini ister (aşağıda "Kurulum notu").
- Hazırlık metrikleri (kapalı yollar, kendini kesen yollar, örtüşme oranı, küçük adacık, ince detay, renk ve düğüm sayısı):
  `eval/printcut.py`.

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
| `mode` | `fast` (varsayılan) / `max` | `fast` artık sıkı eğri toleransıyla çalışır (eski max kazancının çoğu); `max`: yalnız çizim/diyagram 2× çözünürlükte işlenir (1 px çizgiler için, ~3-4× süre, daha büyük dosya) |
| `colors` | `"auto"` veya tamsayı | en fazla düz dolgu rengi (kesin üst sınır; gradyan durakları ve VTracer yedek yolu hariç) |
| `detail` | 0 (kaba) … 1 (ince), varsayılan 0.5 | eğri toleransı, renk birleştirme yarıçapı, benek boyutu |
| `corner_sharpness` | 0 (yuvarlak) … 1 (keskin), varsayılan 0.5 | köşe algılama eşiği |
| `primitives` | bool | daire/elips/dikdörtgen/yuvarlak dikdörtgen öğeleri |
| `gradients` | bool | doğrusal / dairesel / eliptik gradyan dolguları |
| `centerline` | bool (varsayılan kapalı) | ince çizgileri `stroke` yolları olarak izle (düzenlenebilirlik; doğruluğu biraz düşürür) |

`stats` alanları: `image_type` (icon / logo / line_art / gradient / photo), `preset`, `width`, `height`, `timings`
(aşama başına saniye: classify, quantize, gradients, graph, fit, assemble, total), `n_colors`, `n_regions`, `n_chains`,
`n_primitives`, `n_gradients`, `bytes`. Gelişmiş/iç parametreler: `vectorizer/api.py` içindeki `DEFAULTS`.

## Nasıl çalışır (kısaca)

Faz 2 yenilikleri: Mumford–Shah bölge birleştirme (dokulu yapay zekâ çizimlerinde temiz bölgeler), bölge düzeyinde
primitif uydurma (daire/elips/dikdörtgen/yuvarlak dikdörtgen/çokgen/yıldız), geometri onarımı (kendini kesen yol yok),
JPEG kenar saçağı temizliği, motor seçimi (bölge motoru ↔ VTracer) düzeltmeleri, `cut`/`print` ön ayarları.

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
