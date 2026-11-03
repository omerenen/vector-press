# Result tables (held-out test split, 130 images)

## Per category: VTracer default → VTracer tuned → **final (fast)** → final (max)


### composite

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 0.798 | 0.817 | **0.901** | 0.906 |
| icon | 0.819 | 0.845 | **0.937** | 0.950 |
| logo | 0.842 | 0.841 | **0.928** | 0.929 |
| flat_illustration | 0.846 | 0.845 | **0.929** | 0.932 |
| line_art | 0.801 | 0.805 | **0.912** | 0.924 |
| diagram | 0.817 | 0.821 | **0.904** | 0.916 |
| gradient | 0.715 | 0.777 | **0.878** | 0.873 |
| photo | 0.691 | 0.751 | **0.733** | 0.730 |

### ssim

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 0.934 | 0.944 | **0.966** | 0.970 |
| icon | 0.948 | 0.963 | **0.982** | 0.985 |
| logo | 0.949 | 0.948 | **0.982** | 0.984 |
| flat_illustration | 0.960 | 0.960 | **0.981** | 0.984 |
| line_art | 0.945 | 0.947 | **0.981** | 0.991 |
| diagram | 0.965 | 0.965 | **0.986** | 0.990 |
| gradient | 0.919 | 0.938 | **0.962** | 0.961 |
| photo | 0.774 | 0.829 | **0.816** | 0.817 |

### psnr

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 26.2 | 27.3 | **32.4** | 34.2 |
| icon | 26.8 | 27.0 | **33.3** | 36.1 |
| logo | 27.7 | 27.6 | **34.0** | 35.7 |
| flat_illustration | 29.6 | 29.7 | **34.8** | 37.0 |
| line_art | 23.2 | 23.4 | **29.9** | 32.4 |
| diagram | 26.5 | 26.2 | **30.1** | 32.6 |
| gradient | 23.8 | 29.1 | **34.1** | 34.0 |
| photo | 25.7 | 28.7 | **28.2** | 28.4 |

### gmsd

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 0.095 | 0.089 | **0.051** | 0.042 |
| icon | 0.100 | 0.097 | **0.035** | 0.024 |
| logo | 0.088 | 0.092 | **0.045** | 0.038 |
| flat_illustration | 0.073 | 0.072 | **0.036** | 0.030 |
| line_art | 0.117 | 0.116 | **0.060** | 0.042 |
| diagram | 0.093 | 0.096 | **0.056** | 0.039 |
| gradient | 0.092 | 0.072 | **0.053** | 0.053 |
| photo | 0.117 | 0.068 | **0.097** | 0.100 |

### de_mean

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 2.809 | 2.236 | **1.284** | 1.237 |
| icon | 1.920 | 1.983 | **1.225** | 1.154 |
| logo | 2.077 | 2.112 | **1.087** | 1.050 |
| flat_illustration | 1.273 | 1.266 | **0.723** | 0.692 |
| line_art | 2.071 | 2.038 | **0.914** | 0.732 |
| diagram | 2.220 | 2.241 | **1.617** | 1.555 |
| gradient | 6.956 | 3.531 | **1.381** | 1.461 |
| photo | 3.489 | 2.734 | **2.802** | 2.787 |

### edge_f

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 0.923 | 0.936 | **0.954** | 0.955 |
| icon | 0.942 | 0.943 | **0.999** | 0.999 |
| logo | 0.976 | 0.965 | **0.978** | 0.970 |
| flat_illustration | 0.961 | 0.962 | **0.983** | 0.983 |
| line_art | 0.973 | 0.977 | **0.992** | 0.995 |
| diagram | 0.978 | 0.965 | **0.986** | 0.990 |
| gradient | 0.795 | 0.849 | **0.866** | 0.870 |
| photo | 0.751 | 0.847 | **0.802** | 0.799 |

### edge_dev

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 0.713 | 0.617 | **0.263** | 0.227 |
| icon | 0.715 | 0.496 | **0.239** | 0.153 |
| logo | 0.476 | 0.482 | **0.216** | 0.195 |
| flat_illustration | 0.616 | 0.624 | **0.223** | 0.182 |
| line_art | 0.473 | 0.475 | **0.188** | 0.156 |
| diagram | 0.701 | 0.707 | **0.310** | 0.267 |
| gradient | 1.296 | 0.920 | **0.400** | 0.407 |
| photo | – | – | **–** | – |

### n_paths

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 186 | 371 | **223** | 224 |
| icon | 50 | 5 | **5** | 5 |
| logo | 53 | 17 | **10** | 10 |
| flat_illustration | 107 | 156 | **106** | 107 |
| line_art | 176 | 178 | **7** | 9 |
| diagram | 109 | 99 | **34** | 35 |
| gradient | 75 | 315 | **112** | 112 |
| photo | 1272 | 3286 | **2349** | 2352 |

### gz_bytes

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 37357 | 51404 | **27804** | 30156 |
| icon | 12328 | 5599 | **1492** | 2254 |
| logo | 12904 | 9891 | **2321** | 4089 |
| flat_illustration | 23442 | 24962 | **15292** | 17178 |
| line_art | 39494 | 33804 | **3436** | 6394 |
| diagram | 25628 | 14241 | **2471** | 4236 |
| gradient | 18413 | 54325 | **15872** | 17794 |
| photo | 221216 | 382609 | **279679** | 288131 |

## Geometry (synthetic items with ground-truth SVG)

| metric | VTracer default | VTracer cutout | VTracer tuned | final | final max |
|---|---|---|---|---|---|
| corner_recall | 0.483 | 0.605 | 0.492 | 0.773 | 0.716 |
| corner_err | 1.114 | 1.082 | 1.129 | 1.037 | 1.049 |
| prim_recovery | 0.000 | 0.000 | 0.000 | 0.417 | 0.317 |
| gap_px | 0.000 | 6668.992 | 0.000 | 0.000 | 0.000 |
| edge_dev | 0.713 | 0.679 | 0.617 | 0.263 | 0.227 |

Primitive recovery pooled by type (final): {'circle': '1/2', 'ellipse': '1/3', 'rect': '31/61', 'roundrect': '12/28', 'star': '1/4', 'triangle': '1/1'}

Valid SVG rate: final 1.000, final max 1.000


## Classifier (test): preset-family accuracy 114/130 = 0.88

| true category | detected → count |
|---|---|
| icon | icon: 18, logo: 2 |
| logo | gradient: 1, icon: 10, logo: 9 |
| flat_illustration | gradient: 1, icon: 8, logo: 9, photo: 2 |
| line_art | icon: 1, line_art: 19 |
| diagram | line_art: 20 |
| gradient | gradient: 12, icon: 2, logo: 3, photo: 3 |
| photo | line_art: 1, logo: 2, photo: 7 |

## Speed (1024 px, single process, Intel(R) Xeon(R) Processor @ 2.10GHz)
median 1.92 s, p95 2.89 s, max 3.22 s (n=30); stage medians: load 0.00s, classify 0.02s, quantize 1.12s, gradients 0.07s, graph 0.08s, fit 0.62s, assemble 0.03s, total 1.92s
