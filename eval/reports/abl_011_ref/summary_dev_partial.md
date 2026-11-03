# abl_011_ref — dev

exp_010 (auto presets, denoise 1) + sub-pixel boundary placement from anti-aliasing coverage (4-px profile unmixing per crack).

| cat | n | valid_rate | composite | ssim | psnr | gmsd | de_mean | de_p95 | edge_f | edge_dev | gap_px | corner_recall | corner_err | prim_recovery | n_paths | n_nodes | gz_bytes | time_median | time_p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 40 | 1.0000 | 0.8943 | 0.9773 | 28.8 | 0.0703 | 1.3727 | 3.1317 | 0.9751 | 0.2388 | 0.0000 | 0.8531 | 1.0584 | 0.4463 | 25.3 | 462.0 | 3277 | 1.1804 | 2.0156 |
| line_art | 20 | 1.0000 | 0.8964 | 0.9770 | 28.8 | 0.0697 | 1.5950 | 3.3003 | 0.9743 | 0.1967 | 0.0000 |  |  |  | 7.5000 | 416.5 | 3209 | 1.2551 | 2.0156 |
| diagram | 20 | 1.0000 | 0.8923 | 0.9776 | 28.9 | 0.0708 | 1.1503 | 2.9631 | 0.9759 | 0.2808 | 0.0000 | 0.8531 | 1.0584 | 0.4463 | 43.1 | 507.6 | 3345 | 1.1571 | 1.7274 |
