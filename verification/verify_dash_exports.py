"""Tie every number the dashboard prints to the analysis, reading the CSV files Tableau will read.

  python verification/verify_dash_exports.py          print the reconciliation table, exit 1 if any number differs
  python verification/verify_dash_exports.py --json   also write evidence/dash_exports_report.json

Each row recomputes one number from dashboard/data/*.csv and compares it with the analysis value (story/data/facts.json,
evidence/review_cost_causal_report.json, story/data/*.csv) at the rounding the dashboard prints, e.g. 21.2% means rounded to
one place. The dbt tests (tests/business_rules/assert_dash_*) do the same inside the warehouse; this one covers the CSV
step and the one thing dbt cannot see, that dash_region_map.csv lists the same 16 north and northeast states as
story/story_data.py. The seller numbers (583 sellers, top 10 hold 19.1%, top seller 06a2c3af with 66) have no analysis file
to compare with, so they are typed here from the prototype run and marked "typed".
verification/selftest_dash_exports.py proves each row can fail.
"""
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "data"
TABLES = ("summary", "review_ramp", "monthly", "handoff", "sellers", "region", "tests_example")


def load(folder=DATA):
    return {t: list(csv.DictReader(open(Path(folder) / f"{t}.csv", newline=""))) for t in TABLES}


def load_analysis():
    story = ROOT / "story" / "data"
    sc = lambda n: {r["segment"]: r for r in csv.DictReader(open(story / f"{n}.csv"))}
    sys.path.insert(0, str(ROOT / "story"))
    from story_data import NNE
    return {
        "facts": json.loads((story / "facts.json").read_text()),
        "evidence": json.loads((ROOT / "evidence" / "review_cost_causal_report.json").read_text()),
        "month": sc("late_by_month"), "region": sc("late_by_region"), "handoff": sc("late_by_handoff"),
        "nne": set(NNE),
        "region_seed": list(csv.DictReader(open(ROOT / "seeds" / "dash_region_map.csv"))),
    }


def f(x):
    return float(x)


def rate(rows, num, den):
    return sum(f(r[num]) for r in rows) / sum(f(r[den]) for r in rows)


def pctile(xs, q):
    """Linear-interpolated percentile, the same rule as duckdb's percentile_cont."""
    xs = sorted(xs); k = (len(xs) - 1) * q; lo = int(k); hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def slope(xs, ys):
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)


def checks(t, a):
    """List of (map row, number, expected, got, digits); digits=None means exact text or whole count."""
    F = a["facts"]; ramp = t["review_ramp"]; mo = t["monthly"]; ho = t["handoff"]; se = t["sellers"]; rg = t["region"]
    S = t["summary"][0]
    pct = lambda x: 100 * x
    day = lambda lo, hi: [r for r in ramp if lo <= int(r["days_past_promise_capped"]) <= hi]
    late_h = next(r for r in ho if r["is_late_handoff"] == "true"); ok_h = next(r for r in ho if r["is_late_handoff"] == "false")
    nne = next(r for r in rg if r["region_group"] == "North and northeast"); rest = next(r for r in rg if r["region_group"] == "Rest of Brazil")
    total_late = sum(f(r["late_orders"]) for r in mo)
    stable = [f(r["late_rate_if_handoffs_ok"]) for r in mo if r["is_stable_month"] == "true"]
    top10 = sorted(se, key=lambda r: int(r["rank_by_late_after_late_handoff"]))[:10]
    lhl = sum(f(r["late_after_late_handoff_orders"]) for r in se)
    worst3 = sorted(mo, key=lambda r: (-f(r["late_orders"]), r["year_month"]))[:3]
    ramp_bad = sum(f(r["bad_reviews"]) for r in ramp)
    ex = F["review_cost_causal"]["extra"]
    c = []
    # 1 review cost
    c += [("1 review cost", "extra 1-2 star reviews, summary tile", ex, f(S["extra_bad_reviews"]), 0),
          ("1 review cost", "share of all 1-2 star reviews, % (tile vs facts.json share)", pct(F["review_cost_causal"]["share"]), pct(f(S["extra_bad_reviews"]) / ramp_bad), 1),
          ("1 review cost", "all 1-2 star reviews, added up from the ramp file", F["low_star_all"], ramp_bad, 0),
          ("1 review cost", "range low (evidence report), nearest 10", a["evidence"]["headline"]["range_across_specifications"][0], f(S["extra_range_low"]), -1),
          ("1 review cost", "range high (evidence report), nearest 10", a["evidence"]["headline"]["range_across_specifications"][1], f(S["extra_range_high"]), -1),
          ("1 review cost", "ramp: 1-2 star share up to the promised day, %", pct(F["ramp"]["on_time_share"]),
           pct(sum(f(r["bad_reviews"]) for r in day(-30, 0)) / sum(f(r["reviewed_orders"]) for r in day(-30, 0))), 1),
          ("1 review cost", "ramp: 1-2 star share from day 6, %", pct(F["ramp"]["plateau_share"]),
           pct(sum(f(r["bad_reviews"]) for r in day(6, 30)) / sum(f(r["reviewed_orders"]) for r in day(6, 30))), 1),
          ("1 review cost", "ramp: points a day over days 0 to 6", pct(F["ramp"]["slope_per_day"]),
           pct(slope([int(r["days_past_promise_capped"]) for r in day(0, 6)], [f(r["bad_review_share"]) for r in day(0, 6)])), 1)]
    # 2 trend and alarm
    c += [("2 trend", "months in the monthly file", 20, len(mo), None),
          ("2 trend", "judged orders", F["judged_orders"], sum(f(r["orders"]) for r in mo), 0),
          ("2 trend", "late orders", F["late_orders"], total_late, 0),
          ("2 trend", "late rate, %", pct(F["late_rate"]), pct(total_late / sum(f(r["orders"]) for r in mo)), 2),
          ("2 trend", "alarm line at a typical month, %", pct(F["targets"]["alarm_line"]), pct(f(mo[0]["typical_month_alarm_line_late_rate"])), 2),
          ("2 trend", "goal line, %, shown 4.4", pct(F["targets"]["goal"]), pct(f(mo[0]["goal_late_rate"])), 1),
          ("2 trend", "goal line, %, exact 4.43", pct(F["targets"]["goal"]), pct(f(mo[0]["goal_late_rate"])), 2),
          ("2 trend", "stretch line = median of the what-if over stable months in the monthly file, %", pct(pctile(stable, 0.5)), pct(f(mo[0]["stretch_goal_late_rate"])), 4),
          ("2 trend", "stretch line, % to 1 place (about 3.4; typed)", 3.4, pct(f(mo[0]["stretch_goal_late_rate"])), 1),
          ("2 trend", "stretch line in the summary = the monthly file's, %", pct(f(mo[0]["stretch_goal_late_rate"])), pct(f(S["stretch_goal_late_rate"])), 6),
          ("2 trend", "stretch line label in the summary", "middle month if late seller handoffs were fixed, a what-if", S["stretch_goal_label"], None),
          ("2 trend", "stable months in the monthly file vs facts.json", F["targets"]["stable_months"], len(stable), None),
          ("2 trend", "typical month order count", F["targets"]["typical_orders"], f(S["typical_month_orders"]), 0),
          ("2 trend", "flagged months", ", ".join(F["targets"]["flagged"]), ", ".join(r["year_month"] for r in mo if r["is_alarm_month"] == "true"), None),
          ("2 trend", "latest month late rate, %", pct(f(a["month"]["2018-08"]["late_rate"])), pct(f(next(r for r in mo if r["year_month"] == "2018-08")["late_rate"])), 1)]
    # 3 handoff
    c += [("3 handoff", "late rate after a late handoff, %", pct(F["handoff_late_rate"]), pct(f(late_h["late_rate"])), 1),
          ("3 handoff", "late rate after an on-time handoff, %", pct(F["handoff_ok_rate"]), pct(f(ok_h["late_rate"])), 1),
          ("3 handoff", "late handoffs' share of all late orders, %", pct(F["handoff_late_share_of_late"]), pct(f(late_h["late_orders"]) / total_late), 1),
          ("3 handoff", "orders handed over late", f(a["handoff"]["Handed over after ship-by"]["orders"]), f(late_h["orders"]), 0),
          ("3 handoff", "of those, late orders", f(a["handoff"]["Handed over after ship-by"]["late"]), f(late_h["late_orders"]), 0)]
    # 4 sellers (typed: no analysis file)
    c += [("4 sellers", "sellers with a late order after a late handoff (typed)", 583, sum(1 for r in se if f(r["late_after_late_handoff_orders"]) > 0), 0),
          ("4 sellers", "late orders after a late handoff, over all sellers, vs handoff bar", f(a["handoff"]["Handed over after ship-by"]["late"]), lhl, 0),
          ("4 sellers", "top 10 sellers' share of those, % (typed)", 19.1, pct(sum(f(r["late_after_late_handoff_orders"]) for r in top10) / lhl), 1),
          ("4 sellers", "top seller code (typed)", "06a2c3af", top10[0]["seller_code"], None),
          ("4 sellers", "top seller's late orders after a late handoff (typed)", 66, f(top10[0]["late_after_late_handoff_orders"]), 0),
          ("4 sellers", "one row per seller", len(se), len({r["seller_id"] for r in se}), None)]
    # 5 where and when
    c += [("5 where/when", "north and northeast late rate, %", pct(f(a["region"]["North and northeast"]["late_rate"])), pct(f(nne["late_rate"])), 1),
          ("5 where/when", "rest of Brazil late rate, %", pct(f(a["region"]["Rest of Brazil"]["late_rate"])), pct(f(rest["late_rate"])), 1),
          ("5 where/when", "north and northeast share of late orders, %", pct(f(a["region"]["North and northeast"]["share_of_late"])), pct(f(nne["late_orders"]) / total_late), 1),
          ("5 where/when", "three worst months' share of late orders, %", pct(F["top3_months_share_of_late"]), pct(sum(f(r["late_orders"]) for r in worst3) / total_late), 1),
          ("5 where/when", "three worst months, in the monthly bars' flags", ", ".join(sorted(F["top3_months"])), ", ".join(sorted(r["year_month"] for r in mo if r["is_worst3_late_month"] == "true")), None),
          ("5 where/when", "three worst months, named in the summary label",
           ", ".join(sorted(F["top3_months"])), ", ".join(sorted({"Nov 2017": "2017-11", "Feb 2018": "2018-02", "Mar 2018": "2018-03"}.get(m.strip(), "?") for m in S["worst3_months_label"].replace(" and ", ", ").split(","))), None),
          ("5 where/when", "region map: states in the north and northeast = story NNE", ", ".join(sorted(a["nne"])),
           ", ".join(sorted(r["state"] for r in a["region_seed"] if r["region_group"] == "North and northeast")), None),
          ("5 where/when", "region map: 27 states, each once", 27, len({r["state"] for r in a["region_seed"]}), None)]
    # 6 example panel
    c += [("6 fixes", "example rows flagged is_example", len(t["tests_example"]), sum(1 for r in t["tests_example"] if r["is_example"] == "true"), None),
          ("6 fixes", "example rows with an asterisk on both values", len(t["tests_example"]),
           sum(1 for r in t["tests_example"] if r["test_group_display"].endswith("*") and r["no_change_group_display"].endswith("*")), None)]
    return c


def judge(rows):
    """[(map row, number, expected, got, digits, ok)]; ok = equal after rounding to `digits` places (None: exact)."""
    out = []
    for m, name, exp, got, d in rows:
        if d is None or isinstance(exp, str):
            ok = exp == got
        else:
            ok = round(float(exp), d) == round(float(got), d)
        out.append((m, name, exp, got, d, ok))
    return out


def fmt(x, d):
    if isinstance(x, str) or d is None:
        return str(x)
    return f"{round(float(x), d):,.{max(d, 0)}f}"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    res = judge(checks(load(), load_analysis()))
    w = max(len(r[1]) for r in res)
    for m, name, exp, got, d, ok in res:
        print(f"{'PASS' if ok else 'FAIL'}  {m:13s} {name:{w}s}  expected {fmt(exp, d):>26s}   got {fmt(got, d):>26s}")
    bad = [r for r in res if not r[5]]
    print(f"{'PASS' if not bad else 'FAIL'}  {len(res) - len(bad)}/{len(res)} dashboard numbers tie to the analysis")
    if "--json" in argv:
        (ROOT / "evidence" / "dash_exports_report.json").write_text(json.dumps(
            [{"row": m, "number": n, "expected": e, "got": g, "rounded_to": d, "ok": ok} for m, n, e, g, d, ok in res], indent=1) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
