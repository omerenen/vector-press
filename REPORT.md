# RAPOR — vector-press, Faz 2 (yapay zekâ görsellerinden baskıya / kesime hazır vektör)

Ölçüm donanımı: Intel Xeon @ 2.10 GHz, 4 vCPU, GPU yok. Tüm "ayrılmış" (held-out) sayılar hiçbir ayarda kullanılmayan
kümelerden. Ayrıntılı günlük: [EXPERIMENTS.md](EXPERIMENTS.md) · araştırma notları: [RESEARCH.md](RESEARCH.md) ·
bağımsız inceleme: [REVIEW_PHASE2.md](REVIEW_PHASE2.md) · Faz 1 raporu: bu dosyanın sonunda (Ek).

Kümeler:
- **ttest** (hedef küme, 67 görsel): CC0 lisanslı DALL-E 3 görsellerinden ([OpenDatasets/dalle-3-dataset](https://huggingface.co/datasets/OpenDatasets/dalle-3-dataset),
  sabit revizyon) istem metnine göre seçilmiş logo / sticker / kesim dosyası / düz vektör / poster görselleri; 1024² ve
  1792×1024. Ayar için ayrı **tdev** (53 görsel). Gerçek SVG yok → yalnız görüntü metrikleri + LPIPS.
- **test** (130, Faz 1'in ayrılmış kümesi: ikon/logo/emoji/çizim/diyagram/gradyan/fotoğraf; gerçek SVG'li geometri).
- **proc2** (60, aşırı uyum kontrolü): yeni tohum (777) ve yeni parametre aralıklarıyla üretilmiş prosedürel sahneler.
- vectorizer.ai karşılaştırması: `data/target/` klasörü (kullanıcının kendi görselleri + vectorizer.ai çıktıları) bu
  ortamda yok; karşılaştırma altyapısı hazır (`data/target_local.py`, `eval/configs/vectorizer_ai.yaml`), ölçülemedi.

## 1. Hedef küme sonuçları (ttest, ayrılmış)

| yöntem | bileşik | SSIM | PSNR | LPIPS ↓ | ΔE ort. | kenar-F | gzip KB |
|---|---|---|---|---|---|---|---|
| VTracer varsayılan | 0.6541 | 0.762 | 22.0 | 0.207 | 5.09 | 0.854 | 2 549 |
| VTracer ayarlı (Faz 1 dev ayarı, kategori oracle) | 0.6731 | 0.781 | 23.5 | 0.193 | 4.27 | 0.848 | 2 434 |
| phase2-base (Faz 2 başlangıcı) | 0.6936 | 0.793 | 25.0 | 0.192 | 3.42 | 0.846 | 2 098 |
| **final (`auto`)** | **0.7273** | **0.834** | **26.1** | **0.161** | **2.99** | **0.877** | 3 247 |
| final `print` | 0.6251 | 0.745 | 24.8 | 0.251 | 4.06 | 0.700 | 587 |
| final `cut` (≤ 8 düz renk, arka plan atılır — doğruluk amacı değil) | 0.3245 | 0.455 | 10.8 | 0.559 | 23.2 | 0.425 | 79 |

Kategoriye göre bileşik (VTracer ayarlı → phase2-base → **final**): logo 0.680 → 0.741 → **0.789**, sticker 0.672 →
0.735 → **0.755**, kesim dosyası 0.613 → 0.664 → **0.702**, düz vektör 0.692 → 0.678 → **0.722**, poster **0.718** →
0.701 → 0.715 (posterde ayarlı VTracer hâlâ biraz önde).
- final, ayarlı VTracer'ı 67 görselin **50**'sinde, varsayılan VTracer'ı **66**'sında geçiyor.
- phase2-base'e göre: 31 görsel daha iyi (> +0.01), **4 görsel daha kötü** (ttest_0055 −0.095, 0020 −0.068, 0030 −0.065,
  0029 −0.048). Dördü de sınıflandırıcının "fotoğraf" dediği ama yönlendirmenin bölge motorunda tuttuğu görseller (§6).
- **Kazancın kaynağı (dürüst okuma, bağımsız incelemenin M1 bulgusu)**: ttest çıktılarının 53/67'si VTracer yolundan
  geliyor (34'ü bölge patlaması yedeği, 19'u doğrudan fotoğraf sınıfı). Faz 2 kazancının büyük kısmı bu yolun
  düzeltilmesinden: (1) dokulu yapay zekâ görsellerinin yanlışlıkla "saf gürültü" kaba ayarlarına düşmesi giderildi,
  (2) VTracer yolu 1792 px görselleri 1024 px'e küçültüyordu — artık doğal boyutta (en fazla 1792 px). Bölge motorunda
  kalan dokulu görsellerde ortalama kayıp var. Yani hedef kümede "kendi motorumuz VTracer'ı yendi" değil, "doğru
  görseli doğru motora ve doğru çözünürlükte yolladık" demek doğru.
- Bedel: dosya boyutu +%55 (2.1 → 3.2 MB gzip; dokulu görseller tam çözünürlükte izleniyor), süre (4 paralel işte) medyan
  20 s / p95 48 s. Bu görsellerin çoğu zaten 1 MB üstü — hedef kümede kompaktlık kazancı yok.

Baskı / kesim hazırlık metrikleri (ttest ortalamaları, 100 mm çıktı genişliği, en küçük detay 0.5 mm):

| metrik | VTracer ayarlı | final `auto` | final `print` | final `cut` |
|---|---|---|---|---|
| açık alt yol | 0 | 0 | 0 | 0 |
| kendini kesen yol / görsel | 71.8 | 83.0 | 0.19 | **0** |
| örtüşme oranı (üst üste alan / tuval) | 3.15 | 3.76 | 0.10 | **0.00** |
| farklı renk sayısı | 12 442 | 20 517 | 1 419 | **6.6** |
| küçük adacık (< 0.5 mm) | 15 595 | 28 834 | 5 646 | **2.6** |
| ince detay (< 0.5 mm, açma testi) | 6 270 | 8 282 | 773 | **36** (medyan 25) |

Okuma: `auto` en yüksek görsel doğruluk ama VTracer'ın yığılmış (stacked) çıktısı gibi kesime uygun değil. `cut` kesime
hazır (kapalı, kesişmeyen, örtüşmeyen, az renkli yollar). `print` ikisinin arasında: temiz katmanlı vektör, ama dokulu
görsellerde doğruluğu `auto`dan düşük ve yavaş (§6).

## 2. Faz 1 test kümesi ve aşırı uyum kontrolü (ayrılmış)

| küme | VTracer varsayılan | VTracer ayarlı | phase2-base | **final** |
|---|---|---|---|---|
| test (130) bileşik | 0.7979 | 0.8170 | 0.9012 | **0.9143** |
| proc2 (60, yeni tohum ve aralıklar) | — | 0.7957 | — | **0.8897** |

- test kategorileri (phase2-base → final): ikon 0.937 → **0.955**, logo 0.928 → **0.936**, düz illüstrasyon 0.929 →
  **0.952**, çizim 0.908 → **0.925**, diyagram 0.904 → **0.919**, gradyan 0.878 → **0.893**, **fotoğraf 0.746 → 0.727 (gerileme)**.
- 61 görsel daha iyi, 5 görsel daha kötü (test_0126 −0.083, test_0122 −0.067 fotoğraflar; test_0020 logo −0.065;
  test_0125 −0.039; test_0067 −0.011).
- Faz 1'in iki gerilemesi (madde 8) çözüldü: test_0013 0.851 → **0.948**, test_0048 0.805 → **0.908** (ayarlı VTracer
  0.882 / 0.806).
- proc2: final − ayarlı VTracer = +0.094 (Faz 1'de eski prosedürel sahnelerde +0.10) → kazanç görülmemiş üreteç
  ayarlarına da taşınıyor. **Not (inceleme M6):** A akışı geliştirme sırasında proc2'deki bir hatayı inceleyip düzeltti;
  proc2 bu yüzden tamamen el değmemiş sayılmaz.

## 3. Geometri: primitifler ve köşeler (test, gerçek SVG'li görseller)

| metrik | VTracer ayarlı | phase2-base | **final** | hedef |
|---|---|---|---|---|
| primitif kurtarma | 0.000 | 0.417 | **0.775** | ≥ 0.75 ✅ |
| köşe konum hatası (px, GT'nin kendi Harris tepesine göre) | 0.580 | 0.408 | **0.363** | ≤ 0.5 ✅ |
| köşe konum hatası (px, eski tanım: nominal köşeye göre) | 1.129 | 1.037 | 1.035 | ≤ 0.5 ❌ |
| köşe yakalama | 0.492 | 0.773 | 0.745 | — |
| sınır sapması (px, 4× render) | 0.617 | 0.264 | **0.197** | — |
| boşluk pikseli | 0 | 0 | 0 | — |

- Primitifler artık bölge düzeyinde uyduruluyor (daire, elips, dikdörtgen, yuvarlak dikdörtgen, çokgen/yıldız):
  kavşaklar primitifin üzerine taşınıyor, komşu bölge aynı eğriyi paylaşıyor. proc2'de 0.589 (yeni aralıklarda daha
  zor şekiller).
- **Köşe metriği değişti (dürüstlük notu):** eski metrik, çıktının köşesini *nominal* köşe noktasına göre ölçüyordu;
  ama gerçek SVG'nin kendi render'ı bile bu ölçüye göre 0.44–1.15 px "hatalı" (AA render'da Harris tepesi nominal
  noktada değil). Yeni tanım çıktının Harris tepesini GT render'ın aynı bölgedeki Harris tepesiyle karşılaştırıyor; tüm
  yöntemlere aynı kod uygulandı, eski değer de raporlanıyor. Eski tanımla hedef **tutturulamadı**.
- Geometri onarımı: her halka basit (kendini kesmeyen) — ttest `print`'te kendini kesen yol 0.19/görsel (VTracer 72),
  `cut`'ta 0. İsteğe bağlı `shapely` paketi gerekir (LGPL-2.1 GEOS içerdiği için çekirdek kurulumda değil). Onarım
  olmadan dev bileşik skoru değişmiyor (0.9153 vs 0.9151, primitif 0.860 vs 0.863); fark yalnız kesime uygunlukta.

## 4. Hız (sessiz makine, tek süreç, `python -m eval.bench --split test --n 30`, 1024 px)

| sürüm | medyan | p95 | en fazla |
|---|---|---|---|
| phase2-base | 2.10 s | 2.90 s | 3.00 s |
| **final** | **1.45 s** | **2.30 s** | 2.69 s |

- Hedef medyan ≤ 1.2 s **tutturulamadı** (−%31 iyileşme). Niceleme çekirdeği B akışında −%48 hızlandı; yeni kalite
  aşamaları (MS birleştirme, kenar saçağı temizliği, bölge primitifleri, sıkı uydurma) bunun bir kısmını geri harcıyor.
  Kalan süre ~10 adıma dağılmış durumda; sonraki adım derlenmiş (numba/Rust) bir sınır grafiği + uydurucu olur.
- Hedef kümede süre büyük ölçüde VTracer'ın dokulu görsellerdeki süresi: 1792×1024 dokulu görselde 10–30 s;
  patolojik 3000² doku 121 s / 43 MB (1792 px'e küçültülerek).
- `print` dokulu 1024 px görselde 7–40 s (bölge sayısı 2–4 bin; uydurma + primitif araması). Düşük bölge bütçesi
  (0.002) süreyi −%26 kısaltıyor ama doğruluğu −0.026 düşürüyor → reddedildi.

## 5. Yeniden tasarlanan aşamalar ve nedenleri

| aşama | kök neden | denenen alternatifler | sonuç |
|---|---|---|---|
| **Bölütleme (B)**: OKLab paleti → Mumford–Shah bölge birleştirme (`segment="ms"`) | Dokulu yapay zekâ görsellerinde palet niceleme on binlerce bölgeye "patlıyor" → tdev'in 37/53'ü VTracer'a düşüyordu | SLIC süperpiksel, kenar korumalı ön filtre, MS birleştirme | MS seçildi; tdev +0.020 (C ile birlikte toplanmıyor), dev ±0, gradyanda kenar-F +0.012 |
| **Yönlendirme (C + entegrasyon)**: "saf gürültü" eşiği, grafik geçersiz kılma, fotoğraf kararını önce bölge motorunda deneme, VTracer yolunda doğal çözünürlük | Dokulu görseller kaba "gürültü" ayarlarına ve 1024 px'e düşüyordu | öğrenilmiş aile sınıflandırıcısı, özellik eşikleri, yeniden kurma hatası kapısı | Özellik eşikleri + 1792 px; ttest kazancının asıl kaynağı. Yeniden kurma hatası kapısı ayar verisinde ayrışmadı → kaldırıldı |
| **Primitifler (A)**: zincir düzeyinden bölge düzeyine | Kavşaklarda bölünen dış hatlar tek zincir olarak primitife uymuyordu | zincir birleştirme, RANSAC, bölge halkası + kavşak izdüşümü | Bölge halkası; test primitif 0.42 → 0.78 |
| **Geometri onarımı (A)** | Bézier aşması kavşaklarda halkaları kendine kestiriyordu (kesiciler için hata) | yerel yeniden uydurma, çokgen yedeği, piksel kafesi yedeği | Üçü sırayla; kesen halka → 0 |
| **Kenar saçağı temizliği + sıkı uydurma (C)** | JPEG/yeniden ölçekli düz görsellerde renk saçakları; max modun kazancı aslında yarıya inmiş toleranstan geliyordu | 2× işleme, sıkı tolerans 1×'te | Sıkı 1× (aynı kazanç, ⅓ bayt artışı, primitif kaybı yok); 2× yalnız çizim/diyagramda |
| **Kesim ön ayarı** | — (yeni) | | Bölgeler delikli (cutout), ≤ 8 boya (ΔE < 6 olanlar birleşir), arka plan atılır, < 0.5 mm parçalar azaltılır, opak |
| **Metrikler** | Köşe metriği GT'nin kendisini bile cezalandırıyordu; kapalı yolun tekrar eden son noktası sahte kesişim sayılıyordu | | Düzeltildi, tüm yöntemlere aynı uygulandı |

**Öğrenilmiş bileşen kullanılmadı.** Gerekçe ölçümle: (1) dev'de sınıflandırıcının toplam maliyeti (görsel başına oracle
ön ayar − otomatik) yalnız **0.0012** bileşik puan → öğrenilmiş bir sınıflandırıcının kazanacağı bir şey yok; (2) hedef
kümedeki asıl seçim (bölge motoru mu VTracer mı) için tdev_small'da görsel başına oracle, mevcut kurallardan yalnız
+0.009 yukarıda ve 53 ayar görseli bir model eğitmek için çok az; (3) öğrenilmiş kenar dedektörü / farklılaştırılabilir
render tam boru hattında denenecek kadar olgunlaşmadı (CPU bütçesi). İzin verici lisanslı ağırlık ve veri kısıtı da
seçenekleri daraltıyor.

Paralel çalışma: üç alt ajan (A, B, C) kendi git çalışma ağaçlarında çalıştı, sonra birleştirildi. Ablasyon (dev 130 +
tdev 53): her akış diğerlerinin üstüne kapatıldığında A kapatılırsa primitif 0.86 → 0.48, C kapatılırsa dev −0.007,
B kapatılırsa tdev dosyaları +%7 büyüyor → üçü de tutuldu.

## 6. Bağımsız inceleme ve yapılanlar

Geliştirme gerekçelerini görmemiş bir inceleyici birleşik kodu, ayrılmış metrikleri ve kontak sayfalarını inceledi
([REVIEW_PHASE2.md](REVIEW_PHASE2.md)).

| bulgu | yapılan |
|---|---|
| **B1** `colors=N` MS motorunda yok sayılıyordu (6 istendi → 47 renk) | Düzeltildi: açık renk sayısı kesin üst sınır; test eklendi |
| **B2** `shapely` çalışma zamanında gerekiyordu ama bildirilmemişti; tekerleği LGPL-2.1 GEOS içeriyor | İsteğe bağlı `geometry` ekine taşındı; çekirdek kurulum yalnız izin verici lisanslı; shapely yoksa onarım atlanır, çökme yok; test eklendi |
| **M1** ttest kazancı VTracer ayarlarından geliyor | Doğrulandı, §1'de böyle raporlandı |
| **M2** VTracer yolu 1792 px görselleri 1024'e küçültüyordu | tdev'de ölçüldü (+0.016), 1792 px'e çıkarıldı |
| **M3** test fotoğraflarında gerileme | **Düzeltilmedi** (ayrılmış veride ayar yapılmaz). Ayar verisinde bir kapı denendi, ayrışmadı, kaldırıldı. Sınırlama olarak raporlandı |
| **M4** `cut`: büyük tuvalde arka plan kalıyordu, neredeyse aynı siyahlar ayrı katman, yarı saydamlık | Düzeltildi (arka plan kuralı, CIE76 ΔE < 6 birleştirme, opak dolgu) |
| **M5** `print` "tam doğruluk" iddiası yanlış, yavaş | README düzeltildi; bütçe alternatifi ölçüldü, reddedildi |
| **M6** proc2 geliştirmede kullanıldı | Açıkça belirtildi (§2) |

**Dürüstlük notu:** inceleme düzeltmelerinden sonra ttest ikinci kez çalıştırıldı (`auto` 0.7054 → 0.7273, `cut`
yeniden). Bu değişiklikler (çözünürlük, kesim kuralları, renk sınırı) yalnız tdev/dev üzerinde seçildi; ttest'teki
dört gerileme için hiçbir şey değiştirilmedi.

## 7. Kalan en büyük 3 sınırlama

1. **Dokulu yapay zekâ görsellerinde kendi motorumuz hâlâ kaybediyor.** Hedef kümenin %79'u VTracer yolundan geçiyor;
   bölge motorunda tutulan dokulu görseller (ttest_0055/0020/0030/0029) ve bölge motoruna yönlendirilen fotoğraflar
   (test_0126/0122) geriliyor. Doğru çözüm iki render'ı karşılaştıran görsel başına motor seçimi (~2× süre) ya da
   tdev benzeri veride eğitilmiş bir kalite tahmincisi; ikisi de yapılmadı. Hedef kümede kompaktlık kazancı yok
   (≈ 3 MB gzip).
2. **`print` ön ayarı yavaş ve `auto`dan az doğru.** Temiz katmanlı çıktı (kendini kesen yol ≈ 0, örtüşme ≈ 0.1) için
   dokuyu sadeleştiriyor; dokulu görselde 7–40 s. Yumuşak (bulanık) sınırlar ve ince tarama kaybolabiliyor.
3. **Hız ve kapsam.** 1024 px medyan 1.45 s (hedef 1.2 s). Hedef küme vekil: DALL-E 3 istemlerinden seçildi, sticker
   (4) ve t-shirt (ttest'te 0) az; "kesim dosyası" istemli görsellerin çoğu aslında resimsel. Kullanıcının kendi
   görselleri ve vectorizer.ai çıktılarıyla (data/target) karşılaştırma yapılamadı. Geometri onarımı LGPL'li GEOS'a
   (isteğe bağlı shapely) bağlı.

## 8. Tamamlanma kriterleri (Faz 2)

| kriter | durum |
|---|---|
| Hedef küme ölçüldü, önce raporlandı (vectorizer.ai varsa karşılaştırma) | ✅ ttest; vectorizer.ai verisi yok (altyapı hazır) |
| Baskı/kesim metrikleri ve ön ayarları değerlendirildi | ✅ §1 (print sınırlamalarıyla) |
| Madde 3 primitif ≥ 0.75 | ✅ 0.775 (test) |
| Madde 4 köşe hatası ≤ 0.5 px | ✅ yeni tanımla 0.363; eski tanımla ❌ 1.035 (§3) |
| Madde 5 sınıflandırıcı oracle vs otomatik | ✅ 0.0012 fark; öğrenilmiş sınıflandırıcı gereksiz |
| Madde 6 gradyanlar | ⚠️ parçalı-afin MS + doğrusal gradyan seçenek olarak var (gradyanda kenar-F +0.012, PSNR −0.9 dB → varsayılan değil); test gradyan 0.878 → 0.893 |
| Madde 7 hız medyan ≤ 1.2 s | ❌ 1.45 s (−%31) |
| Madde 8 test_0013 / test_0048 | ✅ 0.948 / 0.908 |
| Madde 9 fast vs max | ✅ max yalnız çizim/diyagram; diğerlerinde 1× sıkı uydurma |
| Gerileme yok | ⚠️ test fotoğraf −0.019, ttest 4 görsel, test 5 görsel (§1, §2) |
| %100 geçerli SVG | ✅ test, ttest, proc2, dev, tdev; uç durumlar (1×1 … 3000×6, saydam, 16-bit, paletli, CMYK) |
| Bağımsız inceleme | ✅ §6 |
| Taze klon kurulumu + testler | ✅ boş dizine klon → yeni venv → `requirements.txt`: 69 test geçti, 2 atlandı (shapely yok), CLI çalıştı; `+ requirements-geometry.txt`: 85/85 |
| Durdurma ölçütü | Son ayar denemeleri (bütçe 0.002, yeniden kurma kapısı) kazanç vermedi; 1792 px düzeltmesi bir hata düzeltmesiydi |

En iyi sürüm: **best-v5** (`main`).

---

# Ek: Faz 1 raporu (değişmedi)

## Faz 1 — RAPOR (raster → SVG)

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
