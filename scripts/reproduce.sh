#!/usr/bin/env bash
# One entry point for every step. `make <target>` calls this; machines without make can run it directly:
#   bash scripts/reproduce.sh            # = all: setup build verify docs
#   bash scripts/reproduce.sh build      # any single step: setup data deps build verify ontology prove-tests experiments docs clean
set -euo pipefail
cd "$(dirname "$0")/.."
export DBT_PROFILES_DIR="$PWD"
PY="${PY:-python3}"; BIN=.venv/bin

venv()        { [ -x "$BIN/dbt" ] || { "$PY" -m venv .venv && "$BIN/pip" install -q --upgrade pip && "$BIN/pip" install -q -r requirements.txt; }; }
data()        { bash scripts/fetch_data.sh; }
deps()        { venv; "$BIN/dbt" deps --quiet; }
setup()       { venv; data; deps; }
build()       { deps; "$BIN/dbt" build --fail-fast; }
verify()      { "$BIN/python" verification/verify_headlines.py; ontology; recommendation; }
recommendation() { "$BIN/python" recommendation/analyze.py; "$BIN/python" recommendation/selftest_memo.py; }   # numbers tied to facts, then proof that check can fail
ontology()    {
  "$BIN/python" ontology/check.py                                          # claims + coverage
  "$BIN/python" verification/known_answers/selftest.py                    # scorer
  "$BIN/python" verification/known_answers/append_only.py --against "${APPEND_ONLY_BASE:-HEAD}"   # questions never change silently (default: compare with the last commit)
  "$BIN/python" verification/known_answers/selftest_append_only.py        # ...and that guard can fail
}
prove_tests() { "$BIN/python" scripts/prove_tests_fail.py; }
experiments() { "$BIN/python" experiments/run_experiments.py; }
docs()        { "$BIN/dbt" docs generate --quiet; "$BIN/python" scripts/lineage_mermaid.py; }
clean()       { rm -rf target dbt_packages logs olist.duckdb; }
all()         { setup; build; verify; docs; }

step="${1:-all}"; step="${step//-/_}"
"$step"
