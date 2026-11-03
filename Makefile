# vector-press — common tasks. Use inside the project venv (see README).
PY ?= python
EXP ?= final
SPLIT ?= test

.PHONY: setup data target eval-target test eval eval-all report bench sheets clean

setup:
	$(PY) -m pip install -r requirements.txt

data:            ## build dev + held-out test sets (needs npm for the Iconify packages)
	$(PY) -m data.build

target:          ## AI-generated target benchmark (DALL-E 3, CC0) -> splits tdev / ttest (~5 GB download, cached captions)
	$(PY) -m data.target_dalle3 --n 120
	$(PY) -m data.build --proc2
	$(PY) -m data.fetch_lpips

eval-target:     ## primary score: held-out target split (ttest), baselines + presets
	for c in t_vtracer_default t_vtracer_tuned t_final t_print t_cut; do $(PY) -m eval.run --config eval/configs/$$c.yaml --split ttest; done

test:
	$(PY) -m pytest -q

eval:            ## make eval EXP=final SPLIT=test
	$(PY) -m eval.run --config eval/configs/$(EXP).yaml --split $(SPLIT)

eval-all:        ## everything REPORT.md is built from (held-out test split)
	$(PY) -m eval.run --config eval/configs/exp_000_baseline.yaml --split test
	$(PY) -m eval.run --config eval/configs/exp_000b_cutout.yaml --split test
	$(PY) -m eval.run --config eval/configs/exp_001_baseline_tuned.yaml --split test
	$(PY) -m eval.run --config eval/configs/final.yaml --split test
	$(PY) -m eval.run --config eval/configs/final_max.yaml --split test
	$(PY) -m eval.sheets --exp final --base exp_001_baseline_tuned --split test --n 5
	$(PY) -m eval.bench --split test --n 30 --out eval/reports/bench_test.json
	$(PY) -m eval.report > eval/reports/report_tables.md

report:
	$(PY) -m eval.report > eval/reports/report_tables.md

bench:
	$(PY) -m eval.bench --n 30

sheets:
	$(PY) -m eval.sheets --exp $(EXP) --base exp_001_baseline_tuned --split $(SPLIT)

clean:
	rm -rf eval/runs
