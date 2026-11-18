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
# the revision the append-only guard compares with: unset = a local run, compare with the last commit;
# a commit = CI's base; set but empty = the first push of a new branch, compare with origin/main; nothing to compare with = ""
# (append_only.py fails closed on an empty revision). An empty value never quietly becomes HEAD.
append_base() {
  if [ -z "${APPEND_ONLY_BASE+set}" ]; then echo HEAD
  elif [ -n "$APPEND_ONLY_BASE" ]; then echo "$APPEND_ONLY_BASE"
  elif git rev-parse -q --verify origin/main >/dev/null; then echo origin/main
  else echo ""; fi
}
ontology()    {
  "$BIN/python" ontology/check.py                                          # claims + coverage
  "$BIN/python" verification/known_answers/selftest.py                    # scorer
  "$BIN/python" verification/known_answers/append_only.py --against "$(append_base)"   # questions never change silently
  "$BIN/python" verification/known_answers/selftest_append_only.py        # ...and that guard can fail
}
prove_tests() { "$BIN/python" scripts/prove_tests_fail.py; }
experiments() { "$BIN/python" experiments/run_experiments.py; }
docs()        { "$BIN/dbt" docs generate --quiet; "$BIN/python" scripts/lineage_mermaid.py; }
clean()       { rm -rf target dbt_packages logs olist.duckdb; }
all()         { setup; build; verify; docs; }

step="${1:-all}"; step="${step//-/_}"
"$step"
