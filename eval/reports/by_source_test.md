# Test split by data source

| subset | method | n | composite | ssim | psnr | de_mean | edge_f | edge_dev | gz_bytes |
|---|---|---|---|---|---|---|---|---|---|
| real-world sets (icons, logos, emoji; 72 items) | VTracer default | 72 | 0.825 | 0.948 | 27.3 | 1.91 | 0.944 | 0.612 | 16881 |
| real-world sets (icons, logos, emoji; 72 items) | VTracer tuned | 72 | 0.833 | 0.954 | 27.5 | 1.81 | 0.941 | 0.529 | 19389 |
| real-world sets (icons, logos, emoji; 72 items) | final | 72 | 0.919 | 0.977 | 33.5 | 1.08 | 0.966 | 0.256 | 9263 |
| procedural scenes (48 items) | VTracer default | 48 | 0.780 | 0.948 | 24.8 | 4.02 | 0.928 | 0.863 | 29767 |
| procedural scenes (48 items) | VTracer tuned | 48 | 0.806 | 0.954 | 26.6 | 2.77 | 0.948 | 0.749 | 30426 |
| procedural scenes (48 items) | final | 48 | 0.907 | 0.981 | 31.5 | 1.29 | 0.968 | 0.274 | 4058 |
| photos (10 items) | VTracer default | 10 | 0.691 | 0.774 | 25.7 | 3.49 | 0.751 | nan | 221216 |
| photos (10 items) | VTracer tuned | 10 | 0.751 | 0.829 | 28.7 | 2.73 | 0.847 | nan | 382609 |
| photos (10 items) | final | 10 | 0.746 | 0.824 | 28.5 | 2.76 | 0.835 | nan | 355122 |

Real-world items where final < tuned VTracer (composite): 2/72 ['test_0013', 'test_0048']
