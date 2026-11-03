# RAPOR — vector-press (raster → SVG)

Tüm sayılar **ayrılmış test kümesinden** (130 görsel). Ölçüm donanımı: Intel Xeon @ 2.10 GHz, 4 vCPU, GPU yok.
Yeniden üretmek için: `python -m data.build && make eval-all` → `eval/reports/report_tables.md`,
kaynağa göre kırılım `eval/reports/by_source_test.md`, kontak sayfaları `eval/reports/final/sheet_<kategori>.png`.

Karşılaştırılanlar:
- **VTracer varsayılan**: `vtracer` 0.6.15, varsayılan parametreler (exp_000).
- **VTracer ayarlı**: kategori başına dev kümesinde ızgara aramasıyla ayarlanmış VTracer. Doğru kategori ona *önceden
  verilir* (oracle), yani baseline lehine olan en güçlü karşılaştırma budur (exp_001).
- **final**: bu proje, varsayılan `mode="fast"`, `preset="auto"` (kategoriyi sınıflandırıcıyla kendisi bulur).
- **final max**: `mode="max"` (düz grafikler 2× çözünürlükte işlenir).

## 1. Özet (önce / sonra, test)

| kategori | bileşik: VTracer vars. → ayarlı → **final** | SSIM ayarlı → **final** | ΔE2000 ayarlı → **final** | kenar-F ayarlı → **final** | gzip bayt ayarlı → **final** |
|---|---|---|---|---|---|
| **TÜMÜ** | 0.798 → 0.817 → **0.901** | 0.944 → **0.967** | 2.24 → **1.29** | 0.936 → **0.957** | 51 404 → **33 945** |
| icon | 0.819 → 0.845 → **0.937** | 0.963 → **0.982** | 1.98 → **1.23** | 0.943 → **0.999** | 5 599 → **1 492** |
| logo | 0.842 → 0.841 → **0.928** | 0.948 → **0.982** | 2.11 → **1.09** | 0.965 → **0.978** | 9 891 → **2 321** |
| flat_illustration | 0.846 → 0.845 → **0.929** | 0.960 → **0.981** | 1.27 → **0.72** | 0.962 → **0.983** | 24 962 → **15 280** |
| line_art | 0.801 → 0.805 → **0.908** | 0.947 → **0.979** | 2.04 → **0.96** | 0.977 → **0.991** | 33 804 → **5 664** |
| diagram | 0.817 → 0.821 → **0.904** | 0.965 → **0.986** | 2.24 → **1.62** | 0.965 → **0.986** | 14 241 → **2 471** |
| gradient | 0.715 → 0.777 → **0.878** | 0.938 → **0.962** | 3.53 → **1.38** | 0.849 → **0.866** | 54 325 → **15 856** |
| photo | 0.691 → 0.751 → 0.746 | 0.829 → 0.824 | 2.73 → 2.76 | 0.847 → 0.835 | 382 609 → 355 122 |

- **Doğruluk**: fotoğraf dışındaki her kategoride final, SSIM, PSNR, GMSD (LPIPS ölçülemediği için yerine kullanıldı),
  ΔE (ortalama ve p95) ve kenar-F'de ayarlı VTracer'ı geçiyor. PSNR 27.3 → **32.4 dB** (max modda 34.1 dB).
- **Kompaktlık**: düz grafiklerde dosyalar ayarlı VTracer'a göre %39–%85, varsayılan VTracer'a göre %35–%90 daha küçük.
  Yol sayısı ayarlıya göre %32–%81 daha az; varsayılana göre de az, yalnız flat_illustration'da yaklaşık eşit (107 → 106).
- **Gerçek veri / sentetik veri**: kazanç yalnız kendi ürettiğimiz prosedürel sahnelerden gelmiyor. 72 gerçek
  ikon/logo/emoji görselinde bileşik 0.833 → **0.919** (SSIM 0.954 → 0.977, PSNR 27.5 → 33.5 dB, dosya −%52). Yalnız 2/72
  görsel ayarlı VTracer'dan kötü (test_0013, test_0048). Prosedürel sahnelerde 0.806 → 0.907.
- **Fotoğraf** (hedef dışı bırakılabilen kategori): ayarlı VTracer ile aynı düzeyde (0.746 vs 0.751). Fotoğraf olarak
  algılanan ya da bölge sayısı patlayan görseller ayarlı VTracer yoluna gider.
- **`mode="max"`**: bileşik 0.905, PSNR 34.1 dB (line_art 0.924, icon 0.945). Karşılığında köşe yakalama ve primitif
  oranı düşüyor (aşağıda).

## 2. Geometri (gerçek SVG'si bilinen sentetik görseller)

| metrik | VTracer varsayılan | VTracer cutout | VTracer ayarlı | **final** | final max |
|---|---|---|---|---|---|
| köşe yakalama oranı | 0.483 | 0.605 | 0.492 | **0.773** | 0.708 |
| köşe konum hatası (px) | 1.11 | 1.08 | 1.13 | **1.04** | 1.08 |
| ortalama sınır sapması (px, 4× render) | 0.713 | 0.679 | 0.617 | **0.264** | 0.240 |
| boşluk pikseli (4×, görsel başına) | 0 (stacked) | **6 669** | 0 | **0** | **0** |
| yerel primitif çıktı oranı* | 0.000 | 0.000 | 0.000 | **0.417** | 0.268 |

\* Bağımsız incelemenin haklı uyarısıyla: bu metrik eşleşen bir `<circle>/<ellipse>/<rect>` ya da yalnız doğru
parçalarından oluşan çokgen yolu sayar. VTracer düz kenarları da kübik eğri olarak yazdığı için yapısı gereği 0 alır.
Dolayısıyla bu bir **biçim/düzenlenebilirlik** istatistiğidir, tek başına geometrik doğruluk kanıtı değildir.
Biçimden bağımsız geometri ölçüleri **sınır sapması** (0.617 → 0.264 px) ve **köşe yakalama** (0.49 → 0.77) satırlarıdır.
Final türlere göre: dikdörtgen 31/61, yuvarlak dikdörtgen 12/28, daire 1/2, elips 1/3, yıldız 1/4, üçgen 1/1.

Boşluk: VTracer "stacked" modu katmanları üst üste koyarak boşluğu gizler, "cutout" modunda kılcal boşluklar oluşur.
Final çıktı her ortak sınırı tek bir eğriden üretir ve bitişik bölgelerin altına ince "dikiş" çizgisi koyar; ölçülen boşluk 0.

## 3. Hız (varsayılan mod, tek süreç, 1024 px, test kümesi SVG'lerinden; n = 30)
**medyan 2.10 s, p95 2.90 s, en fazla 3.00 s** (Xeon @ 2.10 GHz). Aşama medyanları: sınıflandırma 0.02 s,
niceleme 1.18 s, gradyan 0.07 s, grafik 0.08 s, uydurma 0.60 s, çıktı 0.04 s.
- ≤ 5 s hedefi karşılandı; 2 s esnek hedef sınırda (dev kümesinde medyan 1.99 s, test kümesinde 2.10 s).
- `mode="max"`: 1024 px'te ~10 s, 1500 px'te ~24 s. İşleme en fazla 3072 px'e kadar ölçeklenir; ≤ 30 s sınırı 1500 px'e
  kadar tutuyor.
- Fotoğraflar: 1024 px'e küçültülüp VTracer ile işlenir (3000×3000 fotoğraf 7 s).
- Patolojik saf gürültü (1024² rastgele piksel): ~14 s, çok büyük SVG.

Apple Silicon'da çekirdek başına performans genelde daha yüksek, bu nedenle süreler eşit ya da daha kısa beklenir.

## 4. Geçerlilik ve dayanıklılık
- Geçerli SVG oranı: dev ve test kümelerinde %100 (her çıktı XML olarak ayrıştırılıp resvg ile render edildi).
- 47 test (`tests/`): birim testleri (daire uydurma < 0.5 px, kesin dikdörtgen, köşe algılama, Bézier hata sınırı,
  sınır grafiği alan korunumu, palet, ince çizgi sürekliliği), entegrasyon testleri ve uç durumlar:
  - boyut: 1×1, 2×3, 3×300, 16 px, 4000×3000;
  - renk/biçim: gri, LA, paletli, CMYK JPEG, 16-bit, uint16/float dizi, WebP, tek renk;
  - saydamlık: saydam PNG, tamamen saydam, yarı saydam alanlar;
  - yoğun gürültü.
- Taze klon testi: boş dizine klon → yeni venv → yalnız `requirements.txt` → tüm testler geçti, CLI çalıştı.

## 5. Sınıflandırıcı (W7)
Önayar ailesi doğruluğu (düz / çizgi / gradyan / fotoğraf) testte **114/130 = %88**. Dev kümesinde "oracle" ön ayar ile
otomatik arasındaki fark 0.001 bileşik puandı. Diyagramlar `line_art`, düz illüstrasyonlar `logo/icon` olarak raporlanır;
aynı ön ayarları paylaştıkları için bu zararsız. Ek güvenlik: bölge yoğunluğu 1000 pikselde 8'i aşarsa (dev: düz grafikler
≤ 5.7, fotoğraflar 18–26) fotoğraf motoruna geçilir.

## 6. Ne işe yaradı (dev kümesi ablasyonları, ayrıntı EXPERIMENTS.md)
| aşama | bileşik katkı | not |
|---|---|---|
| OKLab palet + AA'ya duyarlı atama + paylaşımlı sınır grafiği + eğri/primitif uydurma (exp_002) | +0.078 | ana sıçrama |
| katman/renk birleştirme, yuvarlak dikiş, TLS doğru testi (exp_004) | ≈0 | yol −%93, boşluk → 0 |
| ince çizgi kurtarma, karışım rengi bastırma (exp_005) | +0.003 (line_art/diagram) | köşegen köprüleme reddedildi (+%33 bayt) |
| sağlam primitif kabulü + şerit (sliver) temizleme (exp_007) | +0.005 | |
| gradyan uydurma (exp_008, exp_015) | gradyan kategorisinde +0.019 | |
| sınıflandırıcı + ön ayarlar (exp_009) | +0.004 | |
| sigma filtresiyle gürültü giderme (exp_010) | +0.006 | |
| AA değerlerinden alt-piksel kenar konumu (exp_011) | +0.006 | |
| hızlandırmalar (exp_013) | +0.002 | süre −%7, fotoğrafta −%38 |

Denenip **reddedilenler**: köşegen köprüleme; top-hat sırt dedektörü; merkez çizgisi varsayılan olarak (−0.014/−0.025;
seçenek olarak duruyor); kavşaklarda alt-piksel enterpolasyonu; tüm toleransları ölçekleyen 2× işleme; varsayılan detay
0.7. Son üç ciddi denemenin her biri < %0.5 kazanç verdi, yani azalan getiri noktasına gelindi.

## 7. Görsel gözlemler (kontak sayfaları: en kötü 5 görsel / kategori; seçme yapılmadı)
- **Logolar/ikonlar**: kenarlar pürüzsüz, köşeler keskin, AA halesi yok; basit şekiller `<circle>/<rect>` olarak çıkıyor.
  Kusurlar: test_0013'te dalgalı eğik çizgi ve açık renkli saçak (ayarlı VTracer'dan kötü olan tek ikon);
  test_0007'de camgöbeği hale; test_0030'da yuvarlak kare arka plan kayboluyor.
- **Karmaşık emojiler + yeniden ölçekleme/JPEG**: gölgeli alanlarda lekeli renk geçişleri (test_0046, test_0048).
- **İnce çizgili çizimler**: çizgiler çoğunlukla sürekli. Renk kaymalı/JPEG girdilerde çok ince çizgiler kesik kesik
  olabiliyor (test_0089, test_0091); kesişimlerde perdeli lekeler ve gri tonlar oluşuyor (test_0097, test_0099).
- **Diyagramlar**: kutu içindeki tire satırları zaman zaman birleşiyor (test_0102); kavşaklarda ok uçları perdeleniyor
  (test_0100, test_0116).
- **Gradyanlar**: doğrusal ve eliptik dolgular bantlaşmayı büyük ölçüde kaldırıyor; uydurulamayan bölgelerde
  posterizasyon kalıyor (test_0063).

## 8. Bağımsız inceleme (§3) ve yapılanlar
Geliştirme gerekçelerini görmemiş bağımsız bir inceleyici kodu, test metriklerini, kontak sayfalarını ve lisansları
inceledi. Bulgular ve yapılanlar:

| bulgu (önem) | yapılan |
|---|---|
| Gürültü/doku/yıldız alanı "logo" sanılınca çalışma süresi ve dosya boyutu patlıyor (1024² gürültü 93 s, 15 MB; Hubble fotoğrafları yanlış motorda) **(ciddi)** | Bölge yoğunluğu sigortası + erken çıkış: gürültü 93 s → 14 s; Hubble fotoğrafları artık fotoğraf motorunda. Fotoğraf ön ayarı ≤ 1024 px'te işler (3000² fotoğraf 55 s → 7 s). |
| Yarı saydamlık atılıyor (alfa 128 kare opak çıkıyordu) **(ciddi)** | Düz yarı saydam alanlar `fill-opacity` ile korunuyor (alfa 128 → 128). Yumuşak alfa *rampaları* hâlâ tek değere iniyor (sınırlama). |
| Primitif metriği biçime göre baseline aleyhine **(orta)** | Raporda "yerel primitif çıktı oranı" olarak yeniden adlandırıldı; biçimden bağımsız ölçüler ayrıca verildi (§2). |
| Test kümesinden koda geri bildirim **(orta)** | Açıkça kabul ediliyor, aşağıdaki "Açıklama"ya bakın. Kaynağa göre kırılım eklendi: gerçek görsellerde de kazanç büyük. |
| `mode="max"` 1024 px üstünde sessizce çalışmıyordu **(orta)** | Artık 3072 px'e kadar ölçekleniyor (1500 px'te 2×). |
| Fotoğraf yolunun SVG'si farklı biçimde (viewBox yok, XML başlığı, sürüm yorumu) **(orta)** | VTracer çıktısı normalize ediliyor: viewBox, başlık ve yorum yok. |
| LICENSES.md hataları (libimagequant, torch, Unicode-3.0, LLVM-exception, kontak sayfalarındaki üçüncü taraf görseller) **(orta)** | Düzeltildi: Pillow tekerleğinde libimagequant **yok** (features.check=False). torch/NVIDIA notu ve atıf bildirimleri eklendi. |
| uint16 dizi kırpılıyor, NaN, 1×1 sıfır alanlı yol, 2×800 taşma, boş girdide eksik `stats`, `detail="0.5"` hatası **(küçük)** | Hepsi düzeltildi; küçük/ince görseller piksel koşusu dikdörtgenleriyle birebir çıkıyor; testler eklendi. |
| Bileşik skor, girdiyi `<image>` olarak gömen sahte bir çıktıyla oyunlanabilir (0.877) **(küçük)** | Gömülü raster içeren çıktı artık 0 puan alıyor (`is_vector`). viewBox kaydırması da dikkate alınıyor. |
| Hız iddiası sınırda, ölçüm yalnız fast modda yapılmış **(küçük)** | Raporda medyan 2.10 / p95 2.90 s olarak dürüstçe verildi; max mod ve fotoğraf süreleri ayrıca yazıldı. |
| `gap_px` tüm stacked yöntemlerde 0, köşe metriği yalnız yakalama (recall) ölçüyor **(küçük)** | Cutout karşılaştırması eklendi; köşe metriğinin yalnız recall olduğu not edildi. |

İncelemeden sonra çözülmemiş ciddi sorun yok. Kalan görsel kusurlar §7 ve §9'da listelendi.

**Açıklama (dürüstlük notu).** Test kümesi hiçbir parametre ayarında kullanılmadı. Ancak test çıktılarına bakarken üç
**hata** bulunup düzeltildi, sonra test yeniden çalıştırıldı:
1. max modda dikiş genişliğinin ölçeklenmemesi (test_0020);
2. metrikte birleşik yollardaki çokgenlerin ve neredeyse dairesel elipslerin sayılmaması;
3. inceleme düzeltmesinden sonra AA alfa bantlarının yanlışlıkla yarı saydam çizilmesi (test_0066'da 257 px boşluk).

Bunlar genel hata düzeltmeleridir, test görsellerine özgü ayar değildir. Bölge yoğunluğu eşiği yalnız dev kümesinden
seçildi. Ayrıca prosedürel üreteç motorla birlikte yazıldı; bu yüzden geometri metriklerinde kısmen "kendini doğrulayan"
bir taraf var. Bunu dengelemek için gerçek veri kırılımı (§1) verildi. Test kümesinde yalnız 4 farklı fotoğraf var.

## 9. Kalan en büyük 3 sınırlama
1. **Çok bozuk girdilerde ince ayrıntı**: JPEG/renk kaymalı girdilerde ≤ 1 px çizgiler kesikli olabiliyor; çizgi
   kesişimlerinde sıkışma ve perdeleme; karmaşık gölgeli emojilerde lekelenme. Renk kayması (white balance) geri alınamaz.
2. **Fotoğraflar ve yumuşak alfa**: fotoğraflar ancak ayarlı VTracer düzeyinde ve çok büyük dosyalı. Alfa gradyanları
   (yumuşak gölge rampaları) tek opaklığa iniyor. Saf gürültü gibi patolojik girdiler büyük SVG üretiyor.
3. **Primitif kapsamı**: kapalı ve kesişmeyen sınırlar için daire/elips/dikdörtgen bulunuyor. Kısmen örtülen daireler
   yay (arc) değil Bézier olarak çıkıyor; bozulmuş girdilerde yıldız ve elips kurtarma düşük. Max modda köşe yakalama
   0.77 → 0.71'e iniyor.

Ek: LPIPS ölçülemedi (download.pytorch.org ve huggingface.co bu ortamda engelli); yerine GMSD ve MS-SSIM kullanıldı.
Mac'te torch ve ağırlıklar varsa `lpips: true` ile hesaplanabilir.

## 10. Tamamlanma kriterleri (§5)
| kriter | durum |
|---|---|
| 1. Fotoğraf dışı her kategoride doğrulukta ayarlı VTracer'ı geçmek; düz kategorilerde daha az yol / küçük dosya | ✅ SSIM, PSNR, GMSD, ΔE, kenar-F (LPIPS → GMSD) |
| 2. Primitif, köşe ve boşluk ölçümlerinde açık iyileşme, boşluk ≈ 0 | ✅ köşe 0.49 → 0.77, sınır sapması 0.62 → 0.26 px, primitif oranı 0 → 0.42, boşluk 0 (cutout: 6 669) |
| 3. %100 geçerli SVG, uç durumlarda çökme yok | ✅ |
| 4. Hız bütçesi (medyan/p95 + CPU) | ✅ 2.10 / 2.90 s (≤ 5 s) |
| 5. Bağımsız inceleme, çözülmemiş ciddi sorun yok | ✅ §8 |
| 6. Lisanslar doğrulandı | ✅ LICENSES.md |
| 7. Taze klon testi | ✅ |
