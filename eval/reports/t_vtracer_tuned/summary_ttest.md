# t_vtracer_tuned — ttest

VTracer with phase-1 dev-tuned parameters, mapped per target category (logo->logo, sticker/tshirt/vector_flat->flat_illustration, poster->gradient, cutfile->line_art). Oracle category.

| cat | n | valid_rate | composite | ssim | psnr | gmsd | de_mean | de_p95 | edge_f | edge_dev | gap_px | corner_recall | corner_err | prim_recovery | n_paths | n_nodes | gz_bytes | time_median | time_p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 67 | 1.0000 | 0.6731 | 0.7812 | 23.5 | 0.1162 | 4.2706 | 13.2 | 0.8481 |  |  |  |  |  | 13462 | 181280 | 2433582 | 29.4 | 85.5 |
| logo | 11 | 1.0000 | 0.6803 | 0.7887 | 23.1 | 0.1314 | 4.0764 | 11.9 | 0.8498 |  |  |  |  |  | 2254 | 82220 | 1379841 | 10.0 | 100.8 |
| sticker | 4 | 1.0000 | 0.6720 | 0.8057 | 23.8 | 0.1118 | 4.6175 | 13.4 | 0.8130 |  |  |  |  |  | 10896 | 141408 | 2026483 | 24.6 | 47.2 |
| cutfile | 19 | 1.0000 | 0.6131 | 0.7110 | 21.1 | 0.1380 | 5.9359 | 17.8 | 0.8044 |  |  |  |  |  | 10828 | 157603 | 2240920 | 24.9 | 79.0 |
| vector_flat | 16 | 1.0000 | 0.6916 | 0.8102 | 23.1 | 0.1141 | 3.7911 | 12.4 | 0.9016 |  |  |  |  |  | 15162 | 185820 | 2614290 | 21.3 | 63.0 |
| poster | 17 | 1.0000 | 0.7184 | 0.8218 | 26.6 | 0.0851 | 2.9047 | 9.4822 | 0.8536 |  |  |  |  |  | 22662 | 276948 | 3256451 | 47.2 | 85.6 |
