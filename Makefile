# One command reproduces everything:  make
# (creates .venv, downloads + hash-checks the raw CSVs, builds and tests every layer,
#  reconciles the headline numbers, and generates dbt docs with the lineage graph)
PY      ?= python3
VENV    := .venv
BIN     := $(VENV)/bin
export DBT_PROFILES_DIR := $(CURDIR)

.PHONY: all setup data deps build verify prove-tests experiments docs lineage clean

all: setup build verify docs

$(BIN)/dbt: requirements.txt
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -r requirements.txt
	touch $(BIN)/dbt

setup: $(BIN)/dbt data deps

data:
	bash scripts/fetch_data.sh

deps: $(BIN)/dbt
	$(BIN)/dbt deps --quiet

build: deps
	$(BIN)/dbt build --fail-fast

verify:
	$(BIN)/python verification/verify_headlines.py

prove-tests:
	$(BIN)/python scripts/prove_tests_fail.py

experiments:
	$(BIN)/python experiments/run_experiments.py

docs:
	$(BIN)/dbt docs generate --quiet
	$(BIN)/python scripts/lineage_mermaid.py

clean:
	rm -rf target dbt_packages logs olist.duckdb
