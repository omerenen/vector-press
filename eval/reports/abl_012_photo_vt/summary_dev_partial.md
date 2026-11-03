# abl_012_photo_vt — dev

exp_011 + fixes found by unit tests (closed-chain turning-angle wrap bug produced a spurious corner at every loop start; parabola-sagitta straight-line test; fully rounded squares -> circles; empty-image guard) + user option mapping.

| cat | n | valid_rate | composite | ssim | psnr | gmsd | de_mean | de_p95 | edge_f | edge_dev | gap_px | corner_recall | corner_err | prim_recovery | n_paths | n_nodes | gz_bytes | time_median | time_p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 10 | 1.0000 | 0.6958 | 0.7591 | 25.5 | 0.1182 | 3.5882 | 10.6 | 0.7917 |  |  |  |  |  | 735.4 | 10518 | 144172 | 1.7450 | 3.6514 |
| photo | 10 | 1.0000 | 0.6958 | 0.7591 | 25.5 | 0.1182 | 3.5882 | 10.6 | 0.7917 |  |  |  |  |  | 735.4 | 10518 | 144172 | 1.7450 | 3.6514 |
