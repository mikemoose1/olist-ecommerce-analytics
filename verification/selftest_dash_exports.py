"""Prove verification/verify_dash_exports.py and dashboard/export_csv.py --check can fail.

For every number in the reconciliation table, plant one wrong value in an in-memory copy of the exported tables (or the region
map) and require that exact row to turn red. The untouched tables must pass first. Then perturb a copy of the CSV files and
require the freshness check to catch each kind of drift."""
import copy, os, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "dashboard"))
import verify_dash_exports as V
import export_csv as E


def bump(table, where, col, delta):
    def f(t, a):
        hit = [r for r in t[table] if where(r)]
        assert hit, f"no row in {table}"
        hit[0][col] = str(float(hit[0][col]) + delta)
    return f


def setv(table, where, col, value):
    def f(t, a):
        hit = [r for r in t[table] if where(r)]
        assert hit, f"no row in {table}"
        hit[0][col] = value
    return f


def drop(table, where):
    def f(t, a):
        t[table] = [r for r in t[table] if not where(r)]
    return f


def move(table, col, src, dst, amount):
    def f(t, a):
        for r in t[table]:
            if src(r): r[col] = str(float(r[col]) - amount)
            if dst(r): r[col] = str(float(r[col]) + amount)
    return f


day = lambda n: (lambda r: int(r["days_past_promise_capped"]) == n)
month = lambda m: (lambda r: r["year_month"] == m)
any_row = lambda r: True
top1 = lambda r: r["rank_by_late_after_late_handoff"] == "1"
late_h = lambda r: r["is_late_handoff"] == "true"
ok_h = lambda r: r["is_late_handoff"] == "false"
nne = lambda r: r["region_group"] == "North and northeast"
rest = lambda r: r["region_group"] == "Rest of Brazil"


def all_months(col, delta):
    def f(t, a):
        for r in t["monthly"]: r[col] = str(float(r[col]) + delta)
    return f


def one_seller_with_one(t, a):
    r = next(r for r in t["sellers"] if r["late_after_late_handoff_orders"] == "1")
    r["late_after_late_handoff_orders"] = "0"


def region_seed(fn):
    def f(t, a):
        a["region_seed"] = fn([dict(r) for r in a["region_seed"]])
    return f


CASES = {
    "extra 1-2 star reviews, summary tile": bump("summary", any_row, "extra_bad_reviews", 40),
    "share of all 1-2 star reviews, % (tile vs facts.json share)": bump("summary", any_row, "extra_bad_reviews", 60),
    "all 1-2 star reviews, added up from the ramp file": bump("review_ramp", day(3), "bad_reviews", 1),
    "range low (evidence report), nearest 10": bump("summary", any_row, "extra_range_low", 100),
    "range high (evidence report), nearest 10": bump("summary", any_row, "extra_range_high", -100),
    "ramp: 1-2 star share up to the promised day, %": move("review_ramp", "bad_reviews", day(-5), day(10), 400),
    "ramp: 1-2 star share from day 6, %": move("review_ramp", "bad_reviews", day(10), day(-5), 60),
    "ramp: points a day over days 0 to 6": lambda t, a: [setv("review_ramp", day(5), "bad_review_share", str(float(next(r for r in t["review_ramp"] if day(5)(r))["bad_review_share"]) - 0.1))(t, a)],
    "months in the monthly file": drop("monthly", month("2017-05")),
    "judged orders": bump("monthly", month("2018-01"), "orders", 5),
    "late orders": bump("monthly", month("2018-01"), "late_orders", 1),
    "late rate, %": bump("monthly", month("2018-01"), "late_orders", 200),
    "alarm line at a typical month, %": all_months("typical_month_alarm_line_late_rate", 0.002),
    "goal line, %, shown 4.4": all_months("goal_late_rate", 0.002),
    "goal line, %, exact 4.43": all_months("goal_late_rate", 0.0002),
    "stretch line vs facts.json, % to 1 place": all_months("stretch_goal_late_rate", 0.002),
    "stretch line vs facts.json, % to 2 places": all_months("stretch_goal_late_rate", 0.0002),
    "stretch line = 25th percentile of the what-if over stable months in the monthly file, %": all_months("stretch_goal_late_rate", 0.00002),
    "what-if median line = median of the what-if over stable months in the monthly file, %": all_months("handoff_whatif_median_late_rate", 0.00002),
    "what-if median line in the summary = the monthly file's, %": bump("summary", any_row, "handoff_whatif_median_late_rate", 0.0000005),
    "stable months in the monthly file vs facts.json": setv("monthly", month("2017-09"), "is_stable_month", "false"),
    "typical month order count": bump("summary", any_row, "typical_month_orders", 1),
    "flagged months": setv("monthly", month("2018-03"), "is_alarm_month", "false"),
    "latest month late rate, %": setv("monthly", month("2018-08"), "late_rate", "0.0701"),
    "late rate after a late handoff, %": bump("handoff", late_h, "late_rate", 0.002),
    "late rate after an on-time handoff, %": bump("handoff", ok_h, "late_rate", 0.002),
    "late handoffs' share of all late orders, %": bump("handoff", late_h, "late_orders", 30),
    "orders handed over late": bump("handoff", late_h, "orders", 1),
    "of those, late orders": bump("handoff", late_h, "late_orders", 1),
    "sellers with a late order after a late handoff (typed)": one_seller_with_one,
    "late orders after a late handoff, over all sellers, vs handoff bar": bump("sellers", top1, "late_after_late_handoff_orders", 1),
    "top 10 sellers' share of those, % (typed)": bump("sellers", top1, "late_after_late_handoff_orders", 10),
    "top seller code (typed)": setv("sellers", top1, "seller_code", "86a2c3af"),
    "top seller's late orders after a late handoff (typed)": bump("sellers", top1, "late_after_late_handoff_orders", -1),
    "one row per seller": lambda t, a: t["sellers"].append(dict(t["sellers"][5])),
    "north and northeast late rate, %": bump("region", nne, "late_rate", 0.002),
    "rest of Brazil late rate, %": bump("region", rest, "late_rate", 0.002),
    "north and northeast share of late orders, %": bump("region", nne, "late_orders", 20),
    "three worst months' share of late orders, %": bump("monthly", month("2018-03"), "late_orders", 60),
    "three worst months, in the monthly bars' flags": setv("monthly", month("2018-02"), "is_worst3_late_month", "false"),
    "three worst months, named in the summary label": setv("summary", any_row, "worst3_months_label", "Nov 2017, Jan 2018 and Mar 2018"),
    "region map: states in the north and northeast = story NNE": region_seed(lambda rows: [dict(r, region_group="Rest of Brazil") if r["state"] == "BA" else r for r in rows]),
    "region map: 27 states, each once": region_seed(lambda rows: rows[:-1]),
    "example rows flagged is_example": setv("tests_example", lambda r: r["test_id"] == "1", "is_example", "false"),
    "example rows with an asterisk on both values": setv("tests_example", lambda r: r["test_id"] == "2", "no_change_group_display", "3.92"),
}


def selftest_numbers():
    tables, analysis = V.load(), V.load_analysis()
    base = V.judge(V.checks(tables, analysis))
    assert all(r[5] for r in base), f"untouched data must pass first: {[r[1] for r in base if not r[5]]}"
    names = [r[1] for r in base]
    assert sorted(names) == sorted(CASES), f"every number needs a planted case: {sorted(set(names) ^ set(CASES))}"
    missed = []
    for name, mutate in CASES.items():
        t, a = copy.deepcopy(tables), copy.deepcopy(analysis)
        mutate(t, a)
        failed = {r[1] for r in V.judge(V.checks(t, a)) if not r[5]}
        print(f"{'ok  ' if name in failed else 'MISS'} {name}  (red: {len(failed)})")
        if name not in failed:
            missed.append(name)
    return missed


def selftest_csv_check():
    import duckdb
    con = duckdb.connect(str(ROOT / "olist.duckdb"), read_only=True)
    fresh = E.fresh(con)
    work = Path(tempfile.mkdtemp(prefix="dash-csv-"))
    try:
        E.write(fresh, work)
        assert E.compare(fresh, work) == [], "freshly written CSVs must pass"
        def edit(fn):
            def go(folder):
                fn(folder)
            return go
        def sub(table, old, new):
            def go(folder):
                p = folder / f"{table}.csv"; s = p.read_text(); assert old in s; p.write_text(s.replace(old, new, 1))
            return go
        def rm(table):
            return lambda folder: (folder / f"{table}.csv").unlink()
        def add_file(folder):
            (folder / "stray.csv").write_text("a\n1\n")
        def drop_line(folder):
            p = folder / "monthly.csv"; L = p.read_text().splitlines(keepends=True); p.write_text("".join(L[:5] + L[6:]))
        def swap_cols(folder):
            p = folder / "handoff.csv"; L = p.read_text().splitlines(keepends=True); L[0] = L[0].replace("orders,late_orders", "late_orders,orders", 1); p.write_text("".join(L))
        cases = {
            "a number moves in the summary": sub("summary", "3109.916967", "3119.916967"),
            "a flag flips in the monthly file": sub("monthly", ",true,false,", ",false,false,"),
            "a seller count changes": sub("sellers", ",66,", ",65,"),
            "a label changes in the example file": sub("tests_example", "EXAMPLE DATA", "REAL DATA"),
            "a file is missing": rm("region"),
            "a stray file appears": add_file,
            "a row is dropped": drop_line,
            "columns are reordered": swap_cols,
        }
        missed = []
        for name, mutate in cases.items():
            shutil.rmtree(work); E.write(fresh, work)
            mutate(work)
            problems = E.compare(fresh, work)
            print(f"{'ok  ' if problems else 'MISS'} csv check: {name}")
            if not problems: missed.append(name)
        return missed
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    missed = selftest_numbers() + selftest_csv_check()
    n = len(CASES) + 8
    print(f"{'PASS' if not missed else 'FAIL'}  {n - len(missed)}/{n} planted errors caught" + (f"; missed: {missed}" if missed else ""))
    sys.exit(1 if missed else 0)
