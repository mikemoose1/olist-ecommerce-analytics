#!/usr/bin/env python3
"""A long-lived `dbt test` runner for scripts/prove_tests_fail.py.

Starting `dbt test` costs about 6 seconds, nearly all of it parsing the project, and the mutation proof starts it
about 150 times. This process parses once, then runs one `dbt test --select ...` per request line on stdin, reusing
the parsed project. Each request is {"selector": "..."}; the reply is one stdout line,
"@@RESULT@@" + {"rc": 0|1, "results": [[unique_id, status, failures, message], ...]} (or {"error": "..."}). dbt's own log
lines are ignored by the reader. The warehouse is the file OLIST_DB_PATH named at start (the caller replaces its contents between
requests; its file name must stay the same, because dbt bakes the database name into the compiled SQL).

Usage: dbt_test_worker.py TARGET_PATH      (run in the repo root, with DBT_PROFILES_DIR, OLIST_DB_PATH and OLIST_RAW_DIR set)
"""
import copy, json, sys
from dbt.adapters.duckdb.connections import DuckDBConnectionManager
from dbt.cli.main import dbtRunner

MARK = "@@RESULT@@"


def release_warehouse():
    """dbt-duckdb keeps its connection (and so the file lock) after a run ends, and the caller must replace the warehouse file
    before the next one. Close it and let the next run open a new one. (Written against dbt-duckdb 1.x, whose manager keeps
    the environment in the class field _ENV.)"""
    with DuckDBConnectionManager._LOCK:
        env, DuckDBConnectionManager._ENV = DuckDBConnectionManager._ENV, None
    if env is not None:
        env.close()


def main(target):
    parsed = dbtRunner().invoke(["parse", "--quiet", "--target-path", target])
    if not parsed.success:
        print(MARK + json.dumps({"error": f"parse failed: {parsed.exception!r}"}), flush=True)
        return 1
    manifest = parsed.result
    for line in sys.stdin:
        selector = json.loads(line)["selector"]
        try:
            # a fresh copy each time: dbt stores compiled SQL on the nodes, and a node compiled once keeps its
            # ephemeral-model CTEs out of the next run's SQL ("__dbt__cte__dash_order_base does not exist")
            res = dbtRunner(manifest=copy.deepcopy(manifest)).invoke(["test", "--select", selector, "--target-path", target, "--quiet"])
            results = [[r.node.unique_id, str(getattr(r.status, "value", r.status)), r.failures, (r.message or "")[:600]]
                       for r in (res.result.results if hasattr(res.result, "results") else [])]
            out = {"rc": 0 if res.success else 1, "results": results}
        except Exception as e:   # reported to the caller, which stops the run
            out = {"error": repr(e)}
        finally:
            release_warehouse()
        print(MARK + json.dumps(out), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
