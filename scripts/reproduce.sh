#!/usr/bin/env bash
# One entry point for every step. `make <target>` calls this; machines without make can run it directly:
#   bash scripts/reproduce.sh            # = all: setup build verify docs
#   bash scripts/reproduce.sh build      # any single step: setup data deps build verify ontology story targets dashboard case_study prove-tests experiments docs clean
set -euo pipefail
cd "$(dirname "$0")/.."
export DBT_PROFILES_DIR="$PWD"
PY="${PY:-python3}"; BIN=.venv/bin

venv()        { [ -x "$BIN/dbt" ] || { "$PY" -m venv .venv && "$BIN/pip" install -q --upgrade pip && "$BIN/pip" install -q -r requirements.txt; }; }
data()        { bash scripts/fetch_data.sh; }
deps()        { venv; "$BIN/dbt" deps --quiet; }
setup()       { venv; data; deps; }
build()       { deps; "$BIN/dbt" build --fail-fast; }
verify()      { "$BIN/python" verification/verify_headlines.py; "$BIN/python" verification/selftest_story_numbers.py; ontology; recommendation; dashboard_checks; case_study_checks; }
recommendation() { "$BIN/python" recommendation/analyze.py; "$BIN/python" recommendation/selftest_memo.py
  "$BIN/python" recommendation/check_docs.py; "$BIN/python" recommendation/selftest_docs.py   # retired figures stay out of the untagged docs
  story_checks; }   # numbers tied to facts, then proof that check can fail
story_checks() {   # KPI tree adds up, chart data is fresh, captions are tied to facts; each check proven able to fail; then build the page
  "$BIN/python" story/kpi_tree.py --check; "$BIN/python" story/selftest_kpi_tree.py
  "$BIN/python" story/story_data.py --check
  "$BIN/python" story/check_story.py; "$BIN/python" story/selftest_story.py
  "$BIN/python" story/check_titles.py; "$BIN/python" story/selftest_titles.py
  "$BIN/python" story/build_story.py; }
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
story()       { story_checks; }   # needs a built warehouse and the analysis report (make build, make recommendation)
targets()     { "$BIN/python" late_rate_targets/selftest.py; "$BIN/python" late_rate_targets/analyze.py; "$BIN/python" review_cost_causal/label_agreement.py; }   # alarm line, goal lines, review break point (needs make build)
dashboard_checks() {   # the CSVs Tableau reads match the warehouse, every dashboard number ties to the analysis, and each check is proven able to fail
  "$BIN/python" dashboard/export_csv.py --check
  "$BIN/python" verification/verify_dash_exports.py; "$BIN/python" verification/selftest_dash_exports.py
  "$BIN/python" verification/column_sweep.py --check; }   # every column of every export: one wrong cell at a time, something must fail
dashboard()   { "$BIN/python" dashboard/export_csv.py; "$BIN/python" verification/verify_dash_exports.py --json; dashboard_checks; }   # write dashboard/data/*.csv for Tableau (needs make build)
case_study_checks() {   # every number and key in README.md matches the data, docs/index.md is current, and each check is proven able to fail
  "$BIN/python" case_study/check_case_study.py; "$BIN/python" case_study/selftest_check.py; }
case_study()  { "$BIN/python" case_study/build_figures.py; "$BIN/python" case_study/build_pages.py; case_study_checks; }   # redraw docs/img figures and docs/index.md, then check (needs make build, make recommendation)
prove_tests() { "$BIN/python" scripts/prove_tests_fail.py; }
experiments() { "$BIN/python" experiments/run_experiments.py; }
docs()        { "$BIN/dbt" docs generate --quiet; "$BIN/python" scripts/lineage_mermaid.py; }
clean()       { rm -rf target dbt_packages logs olist.duckdb; }
all()         { setup; build; verify; docs; }

step="${1:-all}"; step="${step//-/_}"
"$step"
