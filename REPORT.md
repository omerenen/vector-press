# RAPOR — vector-press (raster → SVG)

Tüm sayılar **ayrılmış test kümesinden** (130 görsel; bu küme üzerinde hiçbir ayar yapılmadı). Ölçüm donanımı:
Intel Xeon @ 2.10 GHz, 4 vCPU, GPU yok. Yeniden üretmek için: `python -m data.build && make eval-all`
(tablolar: `eval/reports/report_tables.md`; kontak sayfaları: `eval/reports/final/sheet_<kategori>.png`).

Karşılaştırılanlar:
- **VTracer varsayılan** — `vtracer` 0.6.15 varsayılan parametreler (exp_000).
- **VTracer ayarlı** — kategori başına dev kümesinde ızgara aramasıyla ayarlanmış VTracer; doğru kategori ona
  *önceden verilir* (oracle) → en güçlü ve baseline lehine olan karşılaştırma (exp_001).
- **final** — bu proje, varsayılan `mode="fast"`, `preset="auto"` (kategori sınıflandırıcıyla kendisi bulur).
- **final max** — `mode="max"` (düz grafikler 2× çözünürlükte işlenir).

## 1. Özet (önce / sonra)

| kategori | bileşik skor: VTracer varsayılan → ayarlı → **final** | SSIM ayarlı → **final** | ΔE2000 ort. ayarlı → **final** | kenar-F ayarlı → **final** | gzip bayt ayarlı → **final** |
|---|---|---|---|---|---|
| **TÜMÜ** | 0.798 → 0.817 → **0.901** | 0.944 → **0.966** | 2.24 → **1.28** | 0.936 → **0.954** | 51 404 → **27 804** |
| icon | 0.819 → 0.845 → **0.937** | 0.963 → **0.982** | 1.98 → **1.23** | 0.943 → **0.999** | 5 599 → **1 492** |
| logo | 0.842 → 0.841 → **0.928** | 0.948 → **0.982** | 2.11 → **1.09** | 0.965 → **0.978** | 9 891 → **2 321** |
| flat_illustration | 0.846 → 0.845 → **0.929** | 0.960 → **0.981** | 1.27 → **0.72** | 0.962 → **0.983** | 24 962 → **15 292** |
| line_art | 0.801 → 0.805 → **0.912** | 0.947 → **0.981** | 2.04 → **0.91** | 0.977 → **0.992** | 33 804 → **3 436** |
| diagram | 0.817 → 0.821 → **0.904** | 0.965 → **0.986** | 2.24 → **1.62** | 0.965 → **0.986** | 14 241 → **2 471** |
| gradient | 0.715 → 0.777 → **0.878** | 0.938 → **0.962** | 3.53 → **1.38** | 0.849 → **0.866** | 54 325 → **15 872** |
| photo | 0.691 → 0.751 → 0.733 | 0.829 → 0.816 | 2.73 → 2.80 | 0.847 → 0.802 | 382 609 → 279 679 |

- Fotoğraf dışındaki **her kategoride** final; SSIM, PSNR, GMSD (LPIPS yerine), ΔE (ortalama ve p95) ve kenar-F'de
  ayarlı VTracer'ı geçiyor (tam tablolar: `eval/reports/report_tables.md`). PSNR: 27.3 → **32.4 dB** (max: 34.2).
- Düz grafik kategorilerinde dosyalar ayarlı VTracer'a göre **%39–%90 daha küçük**, yol sayısı %32–%96 daha az
  (line_art: 178 → 7 yol). Varsayılan VTracer'a göre de tüm düz kategorilerde daha küçük; yol sayısı yalnız
  flat_illustration'da eşit (107 → 106).
- Fotoğraf: hedef dışı bırakılabilen kategori. Fotoğraf olarak algılanan görseller ayarlı VTracer ile işleniyor; fark,
  sınıflandırıcının 3 fotoğrafı düz grafik sanmasından geliyor (0.733 vs 0.751).
- `mode="max"`: bileşik 0.906, PSNR 34.2 dB (line_art 0.924, diagram 0.916, icon 0.950); yaklaşık 2.5× süre.

## 2. Geometri (gerçek SVG'si bilinen sentetik görseller)

| metrik | VTracer varsayılan | VTracer cutout | VTracer ayarlı | **final** | final max |
|---|---|---|---|---|---|
| köşe yakalama oranı | 0.483 | 0.605 | 0.492 | **0.773** | 0.716 |
| köşe konum hatası (px) | 1.11 | 1.08 | 1.13 | **1.04** | 1.05 |
| primitif kurtarma (daire/elips/dikdörtgen/çokgen) | 0.000 | 0.000 | 0.000 | **0.417** | 0.317 |
| boşluk pikseli (4× render, ortalama) | 0 (stacked) | **6 669** | 0 | **0** | **0** |
| ortalama sınır sapması (px, 4×) | 0.713 | 0.679 | 0.617 | **0.263** | 0.227 |

Boşluk: VTracer'ın "stacked" modu katmanları üst üste koyarak boşluğu gizler; "cutout" modunda kılcal boşluklar
oluşur (görsel başına ~6 700 piksel). Final çıktı, her ortak sınırı tek bir eğriden ürettiği ve bitişik bölgelerin altına
ince "dikiş" çizgisi koyduğu için yapısal olarak boşluksuz (ölçülen: 0). Primitif dağılımı (final): dikdörtgen 31/61,
yuvarlak dikdörtgen 12/28, daire 1/2; bozulmuş (JPEG/bulanık) yıldız ve elipslerde hâlâ zayıf.

## 3. Hız (varsayılan mod, tek süreç, 1024 px logo/illüstrasyon, test kümesi SVG'lerinden)

**medyan 1.92 s, p95 2.89 s, en fazla 3.22 s** (n = 30; Xeon @ 2.10 GHz). Aşama medyanları: sınıflandırma 0.02 s,
niceleme 1.12 s, gradyan 0.07 s, grafik 0.08 s, uydurma 0.62 s, çıktı 0.03 s. Hedef (≤ 5 s) karşılandı, 2 s esnek
hedefi medyan olarak karşılandı. `mode="max"` aynı boyutta ~10 s (≤ 30 s sınırı içinde). Test kümesindeki fotoğraflar (≤512 px): medyan 0.65 s,
p95 3.1 s (yanlış sınıflanıp bölge motoruna giden fotoğraflar daha yavaş). Apple Silicon'da çekirdek başına performans genelde daha yüksek olduğundan süreler eşit ya da daha kısa beklenir.

## 4. Geçerlilik ve dayanıklılık
- Geçerli SVG oranı: dev ve test kümelerinde %100 (her çıktı XML olarak ayrıştırılıp resvg ile render edildi).
- Uç durum testleri (`tests/test_api.py`): 1×1, 2×3, 3×300, 16 px, gri, LA, paletli, şeffaf PNG, tamamen şeffaf,
  tek renk, CMYK JPEG, 16-bit, yoğun gürültü, WebP, float dizi; 4000×3000 görüntü (`max_side=2048` ile işlenir,
  çıktı orijinal boyutta). Hepsi geçti; 43 test.
- Taze klon testi: boş dizine klon → yeni venv → yalnız `requirements.txt` → 43/43 test, CLI çalıştı.

## 5. Sınıflandırıcı (W7)
Önayar ailesi doğruluğu (düz / çizgi / gradyan / fotoğraf) testte **114/130 = %88**. Dev kümesinde "oracle" ön ayar ile
otomatik arasındaki fark yalnız 0.001 bileşik puandı; hatalar çoğunlukla benzer davranan ön ayarlar arasında.

## 6. Ne işe yaradı (dev kümesi ablasyonları, EXPERIMENTS.md)
| aşama | bileşik katkı | not |
|---|---|---|
| OKLab palet + AA'ya duyarlı atama + paylaşımlı sınır grafiği + eğri/primitif uydurma (exp_002) | +0.078 | ana sıçrama |
| katman/renk birleştirme, yuvarlak dikiş, TLS doğru testi (exp_004) | ≈0, yol −%93, boşluk → 0 | |
| ince çizgi kurtarma, karışım rengi bastırma (exp_005) | +0.003 (line_art/diagram) | köprüleme reddedildi (+%33 bayt) |
| sağlam primitif kabulü + şerit (sliver) temizleme (exp_007) | +0.005 | primitif 0.08 → 0.19 |
| gradyan uydurma (exp_008, 015) | gradyan +0.019 | |
| sınıflandırıcı + ön ayarlar (exp_009) | +0.004 | |
| sigma filtresi ile gürültü giderme (exp_010) | +0.006 | |
| AA değerlerinden alt-piksel kenar konumu (exp_011) | +0.006 | primitif +0.095 |
| hızlandırmalar (exp_013) | +0.002, süre −%7 / fotoğraf −%38 | |
Denenip **reddedilenler**: köşegen köprüleme, top-hat sırt dedektörü, merkez çizgisi varsayılan olarak (−0.014/−0.025,
seçenek olarak duruyor), kavşaklarda alt-piksel enterpolasyonu, tüm toleransları ölçekleyen 2× işleme, varsayılan
detay 0.7. Son üç ciddi denemenin her biri < %0.5 kazanç verdi → azalan getiri noktası.

## 7. Görsel gözlemler (kontak sayfaları)
- Logolar/ikonlar: kenarlar pürüzsüz, köşeler keskin, AA haleleri yok; basit şekiller `<circle>/<rect>` olarak çıkıyor.
- Karmaşık emojiler + yeniden ölçekleme/JPEG: gölgeli alanlarda lekeli renk geçişleri (test_0046 gözlük, test_0048 sepet).
- İnce çizgili çizimler: çizgiler sürekli; çizgilerin kesiştiği yerlerde hafif "sıkışma"/çentikler, renk kaymalı
  girdilerde çok ince çizgiler incelebiliyor (test_0089).
- Gradyanlar: doğrusal ve eliptik dolgular bantlaşmayı büyük ölçüde kaldırıyor; uydurulamayan bölgelerde ince bantlar kalıyor.

## 8. Bağımsız inceleme (§3)
Bağımsız bir inceleyici (geliştirme gerekçelerini görmeden) kodu, test metriklerini, kontak sayfalarını ve lisansları
inceledi. Bulgular ve yapılan düzeltmeler aşağıda.

REVIEW_PLACEHOLDER

## 9. Kalan en büyük 3 sınırlama
1. **Fotoğraflar**: ayarlı VTracer seviyesinde (biraz altında), "posterize" görünümlü; gerçek fotoğraf kalitesi bu
   yaklaşımın hedefi değil. Sınıflandırıcı bazı fotoğrafları düz grafik sanabiliyor (`preset="photo"` ile zorlanabilir).
2. **Çok bozuk girdilerde ince ayrıntı**: JPEG/bulanık girdilerde çok ince (≤1 px) çizgiler kesik kesik olabiliyor;
   çizgi kesişimlerinde hafif sıkışma; karmaşık gölgeli emojilerde lekelenme. Renk kayması (white balance) geri alınamaz.
3. **Primitif kapsamı**: kapalı ve kesişmeyen sınırlar için daire/elips/dikdörtgen bulunuyor; başka şekillerle kesişen
   (kısmen örtülen) daireler yay (arc) olarak değil Bézier olarak çıkıyor; bozulmuş girdilerde yıldız/elips kurtarma düşük.

Ek not (lisans): resmi Pillow tekerleği GPL-3 libimagequant içeriyor; ticari dağıtımda Pillow kaynaktan derlenmeli
(LICENSES.md). LPIPS ölçülemedi (ağırlık sunucuları bu ortamda engelli); yerine GMSD ve MS-SSIM kullanıldı.

## 10. Tamamlanma kriterleri (§5)
| kriter | durum |
|---|---|
| 1. Fotoğraf dışı her kategoride doğrulukta ayarlı VTracer'ı geçmek; düz kategorilerde daha az yol/küçük dosya | ✅ (SSIM/GMSD/ΔE/kenar-F hepsi; LPIPS ölçülemedi → GMSD) |
| 2. Primitif, köşe ve boşluk ölçümlerinde açık iyileşme, boşluk ≈ 0 | ✅ (0 → 0.417, 0.49 → 0.77, 0 boşluk) |
| 3. %100 geçerli SVG, uç durumlarda çökme yok | ✅ |
| 4. Hız bütçesi (medyan/p95 + CPU) | ✅ 1.92 / 2.89 s |
| 5. Bağımsız inceleme, çözülmemiş ciddi sorun yok | bkz. §8 |
| 6. Lisanslar doğrulandı | ✅ LICENSES.md (Pillow uyarısıyla) |
| 7. Taze klon testi | ✅ |
