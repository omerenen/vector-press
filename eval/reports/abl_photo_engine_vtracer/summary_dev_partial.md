# abl_photo_engine_vtracer — dev

exp_007 + gradient detection (soft band boundaries measured over a 5px span) and linear/radial multi-stop gradient fitting.

| cat | n | valid_rate | composite | ssim | psnr | gmsd | de_mean | de_p95 | edge_f | edge_dev | gap_px | corner_recall | corner_err | prim_recovery | n_paths | n_nodes | gz_bytes | time_median | time_p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 10 | 1.0000 | 0.6955 | 0.7603 | 25.2 | 0.1168 | 3.6785 | 11.0 | 0.8033 |  |  |  |  |  | 827.7 | 12240 | 159496 | 2.1795 | 4.6759 |
| photo | 10 | 1.0000 | 0.6955 | 0.7603 | 25.2 | 0.1168 | 3.6785 | 11.0 | 0.8033 |  |  |  |  |  | 827.7 | 12240 | 159496 | 2.1795 | 4.6759 |
