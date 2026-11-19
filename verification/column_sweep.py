"""Column sweep: set every column the dashboard reads wrong, one cell at a time, and require some check to fail.

  python verification/column_sweep.py            run the sweep, print the table, exit 1 if any column has a cell nobody checks
  python verification/column_sweep.py --write    also write evidence/column_coverage.json (the per-column result)
  python verification/column_sweep.py --check    the quick run CI uses: the verifier first, dbt only for a cell the verifier misses. Exit 1 if
                                                 a column has an unchecked cell or the columns and cells differ from evidence/column_coverage.json

For each export table and each column, a cell is changed to a plausible wrong value (a boolean flipped, a whole number plus 1, a
rate plus 0.2 points, a larger number plus 1%, a date a month later, a label swapped with another row's, else a stray suffix).
Tables of up to 61 rows are swept row by row; sellers (2,925 rows) at ranks 1, 2, 5, 10, 11, 50, 500 and the last one. The wrong
cell goes through two independent layers, and a cell is covered when either fails:
  dbt      the wrong value is written into the exports schema of a warehouse copy, then every dbt test on the exports runs
  verifier the wrong value is written into the CSV rows Tableau reads, then verification/verify_dash_exports.py judges them
(`dashboard/export_csv.py --check` is not a layer here: it catches any CSV that differs from the warehouse, which says nothing
about whether the warehouse value is right.) Output is sorted and has no timings, so a rerun gives the same file.
"""
import concurrent.futures, copy, datetime, json, os, sys, threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "dashboard")); sys.path.insert(0, str(ROOT / "scripts"))
import duckdb
import export_csv as E
import verify_dash_exports as V
import prove_tests_fail as P

EVIDENCE = ROOT / "evidence" / "column_coverage.json"
SELECTOR = "assert_dash_* export_dash_*"
KEY = {"summary": None, "review_ramp": "days_past_promise_capped", "monthly": "year_month", "handoff": "is_late_handoff",
       "sellers": "seller_id", "region": "region_group", "tests_example": "test_id"}
SELLER_RANKS = (1, 2, 5, 10, 11, 50, 500, 2925)


def wrong(value, dtype, others):
    """A plausible wrong value for one cell."""
    if value is None:
        return 0 if dtype != "VARCHAR" else "x"
    if dtype == "BOOLEAN":
        return not value
    if dtype == "DATE":
        return value + datetime.timedelta(days=31)
    if dtype in ("BIGINT", "INTEGER", "HUGEINT", "SMALLINT"):
        return value + 1
    if dtype == "DOUBLE" or dtype.startswith("DECIMAL"):
        v = float(value)
        return v + 0.002 if abs(v) <= 1 else v * 1.01
    swap = sorted({o for o in others if o is not None and o != value})
    return swap[0] if swap else str(value) + " (wrong)"


def csv_wrong(value, dtype, others):
    """The same change written the way the CSV writer writes it."""
    return E.cell(wrong(value, dtype, others))


def cells(con):
    """[(table, column, dtype, key, row_label, value, others)] for every cell the sweep changes."""
    out = []
    for t, order in E.TABLES.items():
        cur = con.execute(f"select * from exports.export_dash_{t} order by {order}")
        cols = [d[0] for d in cur.description]; types = [str(d[1]) for d in cur.description]
        rows = cur.fetchall()
        if t == "sellers":
            ri = cols.index("rank_by_late_after_late_handoff")
            rows = [r for r in rows if r[ri] in SELLER_RANKS]
        key = KEY[t]; ki = cols.index(key) if key else None
        for ci, (c, ty) in enumerate(zip(cols, types)):
            if c == key:
                continue   # a key is what finds the row; it is swept through the other columns' rows
            for r in rows:
                others = [x[ci] for x in rows]
                out.append((t, c, ty, None if ki is None else r[ki], "all" if ki is None else str(r[ki])[:12], r[ci], others))
    return out


def sweep(jobs=None, quick=False):
    con = duckdb.connect(str(E.DB), read_only=True)
    todo = cells(con)
    tables_csv = V.load(); analysis = V.load_analysis()
    con.close()
    base_bad = [r[1] for r in V.judge(V.checks(tables_csv, analysis)) if not r[5]]
    assert not base_bad, f"the untouched CSVs must pass the verifier first: {base_bad}"
    jobs = jobs or max(1, int(os.environ.get("PROVE_JOBS", min(4, os.cpu_count() or 1))))
    mine, workers, guard = threading.local(), [], threading.Lock()
    work = Path(__import__("tempfile").mkdtemp(prefix="colsweep-"))

    def worker():
        if getattr(mine, "w", None) is None:
            with guard:
                mine.w = P.DbtWorker(str(work / f"slot-{len(workers)}")); workers.append(mine.w)
                mine.base = mine.w.run(SELECTOR)
                assert mine.base[0] == 0 and all(s == "pass" for _, s, _ in mine.base[1]), \
                    f"the untouched warehouse must pass every export test first: {[x for x in mine.base[1] if x[1] != 'pass']}"
        return mine.w

    def run(cell):
        t, c, ty, key, label, value, others = cell
        new = wrong(value, ty, others)
        # verifier layer, on a copy of just the rows that change
        tt = {k: list(v) for k, v in tables_csv.items()}
        tt[t] = [dict(r) for r in tables_csv[t]]
        keyname = KEY[t]
        for r in tt[t]:
            if keyname is None or r[keyname] == E.cell(key):
                r[c] = csv_wrong(value, ty, others); break
        ver_hits = sorted(x[1] for x in V.judge(V.checks(tt, analysis)) if not x[5])
        if quick and ver_hits:
            return t, c, label, None, ver_hits
        w = worker()
        where = f"where {KEY[t]} = ?" if key is not None else ""
        args = [new] + ([key] if key is not None else [])
        db = duckdb.connect(w.db)
        db.execute(f'update exports.export_dash_{t} set "{c}" = ? {where}', args)
        db.close()
        try:
            rc, res = w.run(SELECTOR)
        finally:
            db = duckdb.connect(w.db)
            db.execute(f'update exports.export_dash_{t} set "{c}" = ? {where}', [value] + ([key] if key is not None else []))
            db.close()
        dbt_hits = sorted(n for n, s, _ in res if s == "fail")
        errs = [n for n, s, _ in res if s == "error"]
        assert not errs, f"dbt test errored on {t}.{c}: {errs}"
        return t, c, label, dbt_hits, ver_hits

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(run, todo))
    for w in workers:
        w.close()
    import shutil; shutil.rmtree(work, ignore_errors=True)
    return results, todo


def summarize(results):
    out = {}
    for t, c, label, dbt_hits, ver_hits in results:
        dbt_hits = dbt_hits or []   # None: the quick run did not ask dbt, the verifier had already caught the cell
        e = out.setdefault(t, {}).setdefault(c, {"cells_tested": 0, "caught_by_dbt": 0, "caught_by_verifier": 0, "caught_by_either": 0,
                                                    "unchecked_cells": [], "checks_that_caught": set()})
        e["cells_tested"] += 1
        e["caught_by_dbt"] += bool(dbt_hits); e["caught_by_verifier"] += bool(ver_hits); e["caught_by_either"] += bool(dbt_hits or ver_hits)
        if not (dbt_hits or ver_hits):
            e["unchecked_cells"].append(label)
        e["checks_that_caught"].update(dbt_hits); e["checks_that_caught"].update(ver_hits)
    for t in out:
        for c, e in out[t].items():
            e["unchecked_cells"] = sorted(set(e["unchecked_cells"]))
            e["checks_that_caught"] = sorted(e["checks_that_caught"])
    return {t: dict(sorted(cols.items())) for t, cols in sorted(out.items())}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    quick = "--check" in argv and "--write" not in argv
    results, todo = sweep(quick=quick)
    cov = summarize(results)
    gaps = [(t, c, e["unchecked_cells"]) for t, cols in cov.items() for c, e in cols.items() if e["unchecked_cells"]]
    n_cols = sum(len(c) for c in cov.values()); n_cells = sum(e["cells_tested"] for c in cov.values() for e in c.values())
    for t, cols in cov.items():
        for c, e in cols.items():
            tag = "ok  " if not e["unchecked_cells"] else "GAP "
            print(f"{tag}{t:14s} {c:44s} cells {e['cells_tested']:3d}  dbt {e['caught_by_dbt']:3d}  verifier {e['caught_by_verifier']:3d}"
                  + (f"  UNCHECKED rows: {e['unchecked_cells']}" if e["unchecked_cells"] else ""))
    doc = {"what": "every column of every dashboard export, one wrong cell at a time; a cell is covered when a dbt test or the CSV verifier fails",
           "columns": n_cols, "cells_changed": n_cells, "columns_with_an_unchecked_cell": len(gaps), "tables": cov}
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if quick:
        text = None
    print(f"{'PASS' if not gaps else 'FAIL'}  {n_cols - len(gaps)}/{n_cols} columns fully checked ({n_cells} wrong cells tried)")
    rc = 1 if gaps else 0
    if "--write" in argv:
        EVIDENCE.write_text(text)
    if quick:
        old = json.loads(EVIDENCE.read_text())["tables"] if EVIDENCE.exists() else {}
        shape = lambda tables: {t: {c: (e["cells_tested"], e["unchecked_cells"]) for c, e in cols.items()} for t, cols in tables.items()}
        if shape(old) != shape(cov):
            print(f"FAIL  the columns or cells swept differ from {EVIDENCE.relative_to(ROOT)}; run verification/column_sweep.py --write"); rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
