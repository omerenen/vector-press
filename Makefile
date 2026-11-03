# vector-press — common tasks. Use inside the project venv (see README).
PY ?= python
EXP ?= final
SPLIT ?= test

.PHONY: setup data test eval eval-all report bench sheets clean

setup:
	$(PY) -m pip install -r requirements.txt

data:            ## build dev + held-out test sets (needs npm for the Iconify packages)
	$(PY) -m data.build

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
