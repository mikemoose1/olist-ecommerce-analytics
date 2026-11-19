"""Write the dashboard export tables to CSV for Tableau (Desktop reads CSV; Tableau Public cannot read .hyper).

  python dashboard/export_csv.py           write dashboard/data/<table>.csv from the exports schema of olist.duckdb
  python dashboard/export_csv.py --check   fail if the committed CSVs differ from a fresh build (numbers compared to 1e-9)

One file per export model, same name without the export_dash_ prefix. Rows are sorted so a rerun gives the same file.
Booleans are written true/false, dates as YYYY-MM-DD, missing values as empty cells.
Needs a built warehouse: `make build` first. OLIST_DB_PATH names another warehouse file; a path that does not exist is an error.
"""
import csv, math, os, sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "data"
DB = Path(os.environ.get("OLIST_DB_PATH", ROOT / "olist.duckdb"))   # same variable dbt and the other scripts read
# export model -> order of rows in the file
TABLES = {
    "summary": "1",
    "review_ramp": "days_past_promise_capped",
    "monthly": "year_month",
    "handoff": "is_late_handoff desc",
    "sellers": "rank_by_late_after_late_handoff",
    "region": "region_group desc",
    "tests_example": "test_id",
}


def fresh(con):
    """{table: (columns, rows)} straight from the warehouse, rows as lists of Python values."""
    out = {}
    for t, order in TABLES.items():
        cur = con.execute(f"select * from exports.export_dash_{t} order by {order}")
        out[t] = ([d[0] for d in cur.description], cur.fetchall())
    return out


def cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def write(tables, out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    for t, (cols, rows) in tables.items():
        with open(out / f"{t}.csv", "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cols)
            w.writerows([[cell(v) for v in r] for r in rows])


def same_cell(a, b):
    if a == b:
        return True
    try:
        x, y = float(a), float(b)
    except ValueError:
        return False
    return math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12)


def compare(tables, folder=OUT):
    """List of problems between fresh tables and the CSV files in folder (empty = they agree)."""
    problems = []
    for t, (cols, rows) in tables.items():
        p = folder / f"{t}.csv"
        if not p.exists():
            problems.append(f"{t}.csv is missing")
            continue
        got = list(csv.reader(open(p, newline="")))
        if got[0] != cols:
            problems.append(f"{t}.csv columns differ: {got[0]} vs {cols}")
            continue
        if len(got) - 1 != len(rows):
            problems.append(f"{t}.csv has {len(got) - 1} rows, the warehouse has {len(rows)}")
            continue
        for i, (g, r) in enumerate(zip(got[1:], rows), start=2):
            for c, a, b in zip(cols, g, r):
                if not same_cell(a, cell(b)):
                    problems.append(f"{t}.csv line {i}, {c}: file {a!r}, warehouse {cell(b)!r}")
                    break
            else:
                continue
            break
    extra = sorted(x.name for x in folder.glob("*.csv") if x.stem not in tables)
    if extra:
        problems.append(f"unexpected files: {extra}")
    return problems


def main():
    if not DB.exists():
        sys.exit(f"no warehouse at {DB}; run `make build` first")
    con = duckdb.connect(str(DB), read_only=True)
    tables = fresh(con)
    if "--check" in sys.argv:
        problems = compare(tables)
        for p in problems:
            print("FAIL ", p)
        print(f"{'PASS' if not problems else 'FAIL'}  dashboard/data/*.csv {'match' if not problems else 'differ from'} the warehouse ({len(tables)} files)")
        sys.exit(1 if problems else 0)
    write(tables)
    for t, (cols, rows) in tables.items():
        print(f"wrote dashboard/data/{t}.csv  {len(rows)} rows, {len(cols)} columns")


if __name__ == "__main__":
    main()
