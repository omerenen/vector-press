# abl_011_centerline — dev

exp_010 (auto presets, denoise 1) + sub-pixel boundary placement from anti-aliasing coverage (4-px profile unmixing per crack).

| cat | n | valid_rate | composite | ssim | psnr | gmsd | de_mean | de_p95 | edge_f | edge_dev | gap_px | corner_recall | corner_err | prim_recovery | n_paths | n_nodes | gz_bytes | time_median | time_p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 40 | 1.0000 | 0.8751 | 0.9691 | 26.9 | 0.0888 | 1.5375 | 3.7709 | 0.9670 | 0.2722 | 0.0000 | 0.6069 | 0.9661 | 0.4463 | 30.2 | 437.3 | 3241 | 1.4788 | 2.3759 |
| line_art | 20 | 1.0000 | 0.8826 | 0.9715 | 27.3 | 0.0831 | 1.7353 | 3.9641 | 0.9703 | 0.2205 | 0.0000 |  |  |  | 11.8 | 396.9 | 3132 | 1.4984 | 2.2510 |
| diagram | 20 | 1.0000 | 0.8676 | 0.9667 | 26.6 | 0.0946 | 1.3398 | 3.5777 | 0.9637 | 0.3239 | 0.0000 | 0.6069 | 0.9661 | 0.4463 | 48.6 | 477.7 | 3350 | 1.4459 | 2.5409 |
