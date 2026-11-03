# Result tables (held-out test split, 130 images)

## Per category: VTracer default → VTracer tuned → **final (fast)** → final (max)


### composite

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 0.798 | 0.817 | **0.901** | 0.905 |
| icon | 0.819 | 0.845 | **0.937** | 0.945 |
| logo | 0.842 | 0.841 | **0.928** | 0.928 |
| flat_illustration | 0.846 | 0.845 | **0.929** | 0.929 |
| line_art | 0.801 | 0.805 | **0.908** | 0.924 |
| diagram | 0.817 | 0.821 | **0.904** | 0.910 |
| gradient | 0.715 | 0.777 | **0.878** | 0.875 |
| photo | 0.691 | 0.751 | **0.746** | 0.742 |

### ssim

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 0.934 | 0.944 | **0.967** | 0.970 |
| icon | 0.948 | 0.963 | **0.982** | 0.984 |
| logo | 0.949 | 0.948 | **0.982** | 0.984 |
| flat_illustration | 0.960 | 0.960 | **0.981** | 0.984 |
| line_art | 0.945 | 0.947 | **0.979** | 0.991 |
| diagram | 0.965 | 0.965 | **0.986** | 0.989 |
| gradient | 0.919 | 0.938 | **0.962** | 0.962 |
| photo | 0.774 | 0.829 | **0.824** | 0.826 |

### psnr

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 26.2 | 27.3 | **32.4** | 34.1 |
| icon | 26.8 | 27.0 | **33.3** | 35.8 |
| logo | 27.7 | 27.6 | **34.0** | 35.7 |
| flat_illustration | 29.6 | 29.7 | **34.8** | 36.8 |
| line_art | 23.2 | 23.4 | **29.8** | 32.5 |
| diagram | 26.5 | 26.2 | **30.1** | 32.3 |
| gradient | 23.8 | 29.1 | **34.1** | 34.2 |
| photo | 25.7 | 28.7 | **28.5** | 28.6 |

### gmsd

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 0.095 | 0.089 | **0.050** | 0.041 |
| icon | 0.100 | 0.097 | **0.035** | 0.025 |
| logo | 0.088 | 0.092 | **0.045** | 0.037 |
| flat_illustration | 0.073 | 0.072 | **0.036** | 0.031 |
| line_art | 0.117 | 0.116 | **0.062** | 0.040 |
| diagram | 0.093 | 0.096 | **0.056** | 0.037 |
| gradient | 0.092 | 0.072 | **0.053** | 0.051 |
| photo | 0.117 | 0.068 | **0.078** | 0.091 |

### de_mean

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 2.809 | 2.236 | **1.288** | 1.234 |
| icon | 1.920 | 1.983 | **1.225** | 1.166 |
| logo | 2.077 | 2.112 | **1.087** | 1.070 |
| flat_illustration | 1.273 | 1.266 | **0.723** | 0.697 |
| line_art | 2.071 | 2.038 | **0.960** | 0.733 |
| diagram | 2.220 | 2.241 | **1.617** | 1.572 |
| gradient | 6.956 | 3.531 | **1.381** | 1.403 |
| photo | 3.489 | 2.734 | **2.764** | 2.760 |

### edge_f

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 0.923 | 0.936 | **0.957** | 0.958 |
| icon | 0.942 | 0.943 | **0.999** | 0.999 |
| logo | 0.976 | 0.965 | **0.978** | 0.970 |
| flat_illustration | 0.961 | 0.962 | **0.983** | 0.983 |
| line_art | 0.973 | 0.977 | **0.991** | 0.996 |
| diagram | 0.978 | 0.965 | **0.986** | 0.992 |
| gradient | 0.795 | 0.849 | **0.866** | 0.874 |
| photo | 0.751 | 0.847 | **0.835** | 0.829 |

### edge_dev

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 0.713 | 0.617 | **0.264** | 0.240 |
| icon | 0.715 | 0.496 | **0.239** | 0.165 |
| logo | 0.476 | 0.482 | **0.216** | 0.203 |
| flat_illustration | 0.616 | 0.624 | **0.223** | 0.191 |
| line_art | 0.473 | 0.475 | **0.194** | 0.158 |
| diagram | 0.701 | 0.707 | **0.310** | 0.307 |
| gradient | 1.296 | 0.920 | **0.400** | 0.414 |
| photo | – | – | **–** | – |

### n_paths

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 186 | 371 | **282** | 225 |
| icon | 50 | 5 | **5** | 5 |
| logo | 53 | 17 | **10** | 11 |
| flat_illustration | 107 | 156 | **106** | 107 |
| line_art | 176 | 178 | **33** | 10 |
| diagram | 109 | 99 | **34** | 34 |
| gradient | 75 | 315 | **112** | 113 |
| photo | 1272 | 3286 | **3066** | 2366 |

### gz_bytes

| category | VTracer default | VTracer tuned | final | final max |
|---|---|---|---|---|
| ALL | 37357 | 51404 | **33945** | 31306 |
| icon | 12328 | 5599 | **1492** | 2794 |
| logo | 12904 | 9891 | **2321** | 4766 |
| flat_illustration | 23442 | 24962 | **15280** | 17905 |
| line_art | 39494 | 33804 | **5664** | 8822 |
| diagram | 25628 | 14241 | **2471** | 6006 |
| gradient | 18413 | 54325 | **15856** | 16984 |
| photo | 221216 | 382609 | **355122** | 292425 |

## Geometry (synthetic items with ground-truth SVG)

| metric | VTracer default | VTracer cutout | VTracer tuned | final | final max |
|---|---|---|---|---|---|
| corner_recall | 0.483 | 0.605 | 0.492 | 0.773 | 0.708 |
| corner_err | 1.114 | 1.082 | 1.129 | 1.037 | 1.083 |
| prim_recovery | 0.000 | 0.000 | 0.000 | 0.417 | 0.268 |
| gap_px | 0.000 | 6668.992 | 0.000 | 0.000 | 0.000 |
| edge_dev | 0.713 | 0.679 | 0.617 | 0.264 | 0.240 |

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
median 2.10 s, p95 2.90 s, max 3.00 s (n=30); stage medians: load 0.00s, classify 0.02s, quantize 1.18s, gradients 0.07s, graph 0.08s, fit 0.60s, assemble 0.04s, total 2.10s
