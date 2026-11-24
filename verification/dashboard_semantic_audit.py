"""Which dashboard numbers come from the semantic layer, and which do not.

  python verification/dashboard_semantic_audit.py           write dashboard/SEMANTIC_LAYER.md
  python verification/dashboard_semantic_audit.py --check   fail if the committed file differs from a fresh run, or if a number
                                                             marked as semantic no longer equals what MetricFlow returns

Tableau reads CSVs, not MetricFlow, so no number on the dashboard is read from the semantic layer. This lists every numeric
column of every export table and marks it "semantic" only when a metric in models/semantic/_semantic.yml defines it and
`mf query` returns the same value (to 1e-9) for every row. Everything else is computed in SQL in the export models.
Needs a built warehouse (make build).
"""
import csv, io, os, subprocess, sys, tempfile
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "SEMANTIC_LAYER.md"
DB = os.environ.get("OLIST_DB_PATH", str(ROOT / "olist.duckdb"))
MF = Path(sys.executable).parent / "mf"
sys.path.insert(0, str(ROOT / "dashboard"))
from export_csv import TABLES  # noqa: E402

NUMERIC = ("bigint", "hugeint", "integer", "double", "decimal")


def mf(group_by=None):
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "q.csv"
        cmd = [str(MF), "query", "--metrics", "late_rate,judged_orders,late_orders", "--csv", str(f)] + (["--group-by", group_by] if group_by else [])
        subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, DBT_PROFILES_DIR=str(ROOT)), check=True, capture_output=True)
        return list(csv.DictReader(open(f)))


def semantic_checks(con, total, month, state):
    """{(table, column): (metric, matches)} for the numbers a semantic metric defines."""
    close = lambda a, b: abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(b)))
    out = {}
    s = con.execute("select judged_orders, late_orders, late_rate, latest_month, latest_month_late_rate from exports.export_dash_summary").fetchone()
    for col, metric, v in (("judged_orders", "judged_orders", s[0]), ("late_orders", "late_orders", s[1]), ("late_rate", "late_rate", s[2])):
        out[("summary", col)] = (metric, close(v, total[metric]))
    out[("summary", "latest_month_late_rate")] = ("late_rate by month", close(s[4], month[s[3]]["late_rate"]))
    rows = con.execute("select year_month, orders, late_orders, late_rate from exports.export_dash_monthly").fetchall()
    for i, (col, metric) in enumerate((("orders", "judged_orders"), ("late_orders", "late_orders"), ("late_rate", "late_rate")), start=1):
        out[("monthly", col)] = (f"{metric} by month", all(close(r[i], month[r[0]][metric]) for r in rows))
    groups = con.execute("select region_group, list(state) from seeds.dash_region_map group by 1").fetchall()
    reg = {g: (sum(int(state[x]["judged_orders"]) for x in sts if x in state), sum(int(state[x]["late_orders"]) for x in sts if x in state)) for g, sts in groups}
    rows = con.execute("select region_group, orders, late_orders, late_rate from exports.export_dash_region").fetchall()
    out[("region", "orders")] = ("judged_orders by customer state, summed over the region's states", all(close(r[1], reg[r[0]][0]) for r in rows))
    out[("region", "late_orders")] = ("late_orders by customer state, summed over the region's states", all(close(r[2], reg[r[0]][1]) for r in rows))
    out[("region", "late_rate")] = ("late_orders / judged_orders by customer state, summed over the region's states", all(close(r[3], reg[r[0]][1] / reg[r[0]][0]) for r in rows))
    return out


def build():
    # MetricFlow first: it opens the warehouse itself, so this script must not hold a connection while it runs
    total = mf()[0]
    month = {r["metric_time__month"][:7]: r for r in mf("metric_time__month")}
    state = {r["order__ship_to_state"]: r for r in mf("order__ship_to_state")}
    con = duckdb.connect(DB, read_only=True)
    sem = semantic_checks(con, total, month, state)
    cols = con.execute("select table_name, column_name, lower(data_type) from information_schema.columns where table_schema = 'exports' "
                       "and table_name like 'export_dash_%' order by table_name, ordinal_position").fetchall()
    lines, n_sem, n_not, broken = [], 0, 0, []
    for t, c, ty in cols:
        if not ty.startswith(NUMERIC): continue
        key = (t.replace("export_dash_", ""), c)
        if key in sem:
            metric, ok = sem[key]
            if not ok: broken.append(key)
            n_sem += ok; n_not += not ok
            lines.append(f"| `{key[0]}.csv` | `{c}` | {'semantic: ' + metric if ok else 'NOT matching MetricFlow (' + metric + ')'} |")
        else:
            n_not += 1
            lines.append(f"| `{key[0]}.csv` | `{c}` | not in the semantic layer |")
    head = [
        "# Dashboard numbers and the semantic layer",
        "",
        "Written by `verification/dashboard_semantic_audit.py`; `--check` fails if this file is out of date.",
        "",
        "Tableau reads CSVs, so no dashboard number is read from the semantic layer directly. This table lists every numeric column of",
        "every CSV in `dashboard/data/` and marks it **semantic** only when a metric in `models/semantic/_semantic.yml` defines it and",
        "`mf query` returns the same value on every row. All other numbers are computed in SQL inside the export models and have no",
        "semantic-layer definition. The order-level `orders.csv` that the Tableau scripts build (`dashboard/tableau/export_orders.py`)",
        "is not listed: its rows come from `metric_late_rate_orders`, the table the `late_rate_orders` semantic model is built on, but",
        "Tableau, not MetricFlow, adds them up.",
        "",
        f"**{n_sem} semantic, {n_not} not.**",
        "",
        "| File | Column | Source |",
        "|---|---|---|",
    ]
    return "\n".join(head + lines) + "\n", broken


if __name__ == "__main__":
    text, broken = build()
    for k in broken: print(f"FAIL {k[0]}.{k[1]} is marked semantic but differs from MetricFlow")
    if "--check" in sys.argv:
        same = OUT.exists() and OUT.read_text() == text
        print(("PASS " if same else "FAIL ") + f"{OUT.relative_to(ROOT)} matches a fresh run")
        sys.exit(0 if same and not broken else 1)
    OUT.write_text(text); print(f"wrote {OUT.relative_to(ROOT)}")
    sys.exit(1 if broken else 0)
