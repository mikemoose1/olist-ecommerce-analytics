"""Tie every number the dashboard prints to the analysis, reading the CSV files Tableau will read.

  python verification/verify_dash_exports.py          print the reconciliation table, exit 1 if any number differs
  python verification/verify_dash_exports.py --json   also write evidence/dash_exports_report.json

Each row recomputes one number from dashboard/data/*.csv and compares it with the analysis value (story/data/facts.json,
evidence/review_cost_causal_report.json, story/data/*.csv) at the rounding the dashboard prints, e.g. 21.2% means rounded to
one place. The dbt tests (tests/business_rules/assert_dash_*) do the same inside the warehouse; this one covers the CSV
step and the one thing dbt cannot see, that dash_region_map.csv lists the same 16 north and northeast states as
story/story_data.py. The seller numbers (583 sellers, top 10 hold 19.1%, top seller 06a2c3af with 66) have no analysis file
to compare with, so they are rebuilt from data/raw/*.csv by verification/dash_raw_rebuild.py (Python and DuckDB, no dbt model) and every
seller, month, handoff and region row is compared with that rebuild; the typed values are checked against the rebuild too.
Columns that are worked out from other columns (labels, dates, ranks, phases) are recomputed on every row.
Rows that compare a number with a copy of itself are named "consistency": they catch a copy that drifted, they are not evidence.
verification/selftest_dash_exports.py proves each row can fail; verification/column_sweep.py proves every column is checked.
"""
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "data"
TABLES = ("summary", "review_ramp", "monthly", "handoff", "sellers", "region", "tests_example")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
sys.path.insert(0, str(ROOT / "verification"))


def load(folder=DATA):
    return {t: list(csv.DictReader(open(Path(folder) / f"{t}.csv", newline=""))) for t in TABLES}


def load_analysis():
    story = ROOT / "story" / "data"
    sc = lambda n: {r["segment"]: r for r in csv.DictReader(open(story / f"{n}.csv"))}
    sys.path.insert(0, str(ROOT / "story"))
    from story_data import NNE
    from dash_raw_rebuild import rebuild
    return {
        "raw": rebuild(NNE),
        "example_seed": list(csv.DictReader(open(ROOT / "seeds" / "dash_tests_example.csv", newline=""))),
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
          ("1 review cost", "range low (evidence report), nearest 10 (consistency: the same number read from the report, not an independent recompute)", a["evidence"]["headline"]["range_across_specifications"][0], f(S["extra_range_low"]), -1),
          ("1 review cost", "range high (evidence report), nearest 10 (consistency: the same number read from the report, not an independent recompute)", a["evidence"]["headline"]["range_across_specifications"][1], f(S["extra_range_high"]), -1),
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
          ("2 trend", "stretch line = median of the what-if over stable months in the monthly file, %", pct(pctile(stable, 0.5)), pct(f(mo[0]["stretch_whatif_late_rate"])), 4),
          ("2 trend", "stretch line vs facts.json, %", pct(F["targets"]["stretch"]), pct(f(mo[0]["stretch_whatif_late_rate"])), 4),
          ("2 trend", "stretch line, % to 1 place (about 3.4; typed)", 3.4, pct(f(mo[0]["stretch_whatif_late_rate"])), 1),
          ("2 trend", "stretch line in the summary = the monthly file's, %", pct(f(mo[0]["stretch_whatif_late_rate"])), pct(f(S["stretch_whatif_late_rate"])), 6),
          ("2 trend", "stretch line label in the summary", "middle month if late seller handoffs were fixed, a what-if", S["stretch_whatif_label"], None),
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
    R = a["raw"]
    raw_h = R["handoff"]; raw_m = R["months"]; raw_r = R["region"]
    top10_share = pct(R["top10_late_after_late_handoff"] / R["late_after_late_handoff"])
    hrow = lambda r: raw_h.get(r["is_late_handoff"] == "true")
    # 0 raw files: the figures the dashboard prints, rebuilt from data/raw/*.csv with no dbt model
    c += [("0 raw files", "judged orders: the rebuild gives 94,931 (typed)", 94931, R["judged_orders"], 0),
          ("0 raw files", "late orders: the rebuild gives 6,518 (typed)", 6518, R["late_orders"], 0),
          ("0 raw files", "late orders after a late handoff: the rebuild gives 1,809 (typed)", 1809, R["late_after_late_handoff"], 0),
          ("0 raw files", "sellers with a late order after a late handoff: the rebuild gives 583 (typed)", 583, R["sellers_with_late_after_late_handoff"], 0),
          ("0 raw files", "top 10 sellers' share of those, %: the rebuild gives 19.1 (typed)", 19.1, top10_share, 1),
          ("0 raw files", "top seller: the rebuild gives 06a2c3af (typed)", "06a2c3af", R["sellers"][0]["seller_code"], None),
          ("0 raw files", "top seller's late orders after a late handoff: the rebuild gives 66 (typed)", 66, R["sellers"][0]["late_after_late_handoff_orders"], 0),
          ("0 raw files", "judged orders, summary vs the rebuild", R["judged_orders"], f(S["judged_orders"]), 0),
          ("0 raw files", "late orders, summary vs the rebuild", R["late_orders"], f(S["late_orders"]), 0),
          ("0 raw files", "late orders after a late handoff, summary vs the rebuild", R["late_after_late_handoff"], f(S["late_handoff_late_orders"]), 0),
          ("0 raw files", "late handoff orders, summary vs the rebuild", R["late_handoff_orders"], f(S["late_handoff_orders"]), 0),
          ("0 raw files", "sellers with a late order after a late handoff, summary vs the rebuild", R["sellers_with_late_after_late_handoff"], f(S["sellers_with_late_after_late_handoff"]), 0),
          ("0 raw files", "top 10 sellers' late orders after a late handoff, summary vs the rebuild", R["top10_late_after_late_handoff"], f(S["top10_late_after_late_handoff_orders"]), 0),
          ("0 raw files", "top 10 sellers' share of those, %, summary vs the rebuild", top10_share, pct(f(S["top10_share_of_late_after_late_handoff"])), 4),
          ("0 raw files", "top seller code, summary vs the rebuild", R["sellers"][0]["seller_code"], S["top_seller_code"], None),
          ("0 raw files", "top seller's late orders after a late handoff, summary vs the rebuild", R["sellers"][0]["late_after_late_handoff_orders"], f(S["top_seller_late_after_late_handoff_orders"]), 0),
          ("0 raw files", "seller rows that differ from the rebuild (all 2,925: counts, rates, rank, top-10 flag, share, code)", 0, differing_sellers(se, R), 0),
          ("0 raw files", "month rows whose orders or late orders differ from the rebuild (all 20)", 0,
           len(set(raw_m) ^ {r["year_month"] for r in mo}) + sum(1 for r in mo if raw_m.get(r["year_month"]) != (f(r["orders"]), f(r["late_orders"]))), 0),
          ("0 raw files", "handoff rows whose name, orders, late orders, late rate or share of late differ from the rebuild", 0,
           abs(len(ho) - len(raw_h)) + sum(1 for r in ho if not (
               r["handoff_group"] == ("Handed to carrier after ship-by" if r["is_late_handoff"] == "true" else "Handed over on time")
               and hrow(r) == (f(r["orders"]), f(r["late_orders"])) and abs(f(r["late_rate"]) - hrow(r)[1] / hrow(r)[0]) < 1e-9
               and abs(f(r["share_of_all_late"]) - hrow(r)[1] / R["late_orders"]) < 1e-9)), 0),
          ("0 raw files", "region rows whose states, orders, late orders, late rate or share of late differ from the rebuild", 0,
           abs(len(rg) - len(raw_r)) + sum(1 for r in rg if not (
               raw_r.get(r["region_group"]) == (f(r["orders"]), f(r["late_orders"])) and abs(f(r["late_rate"]) - raw_r[r["region_group"]][1] / raw_r[r["region_group"]][0]) < 1e-9
               and abs(f(r["share_of_all_late"]) - raw_r[r["region_group"]][1] / R["late_orders"]) < 1e-9
               and f(r["states"]) == len([x for x in a["region_seed"] if x["region_group"] == r["region_group"]]))), 0)]
    # columns worked out from other columns, recomputed on every row
    rank_of = {r["year_month"]: i for i, r in enumerate(sorted(sorted(mo, key=lambda r: r["year_month"], reverse=True), key=lambda r: -f(r["late_orders"])), start=1)}
    last = max(r["year_month"] for r in mo)
    c += [("2 trend", "month_start is the first day of year_month (rows that differ)", 0, sum(1 for r in mo if r["month_start"] != r["year_month"] + "-01"), 0),
          ("2 trend", "month_label is the month name and year (rows that differ)", 0, sum(1 for r in mo if r["month_label"] != label(r["year_month"])), 0),
          ("2 trend", "late_orders_rank orders the months by late orders, a tie to the later month (rows that differ)", 0, sum(1 for r in mo if f(r["late_orders_rank"]) != rank_of[r["year_month"]]), 0),
          ("2 trend", "is_worst3_late_month is rank 3 or better (rows that differ)", 0, sum(1 for r in mo if (r["is_worst3_late_month"] == "true") != (rank_of[r["year_month"]] <= 3)), 0),
          ("2 trend", "is_stable_month is not alarm and not thin (rows that differ)", 0, sum(1 for r in mo if (r["is_stable_month"] == "true") != (r["is_alarm_month"] == "false" and r["is_thin_month"] == "false")), 0),
          ("2 trend", "late_rate and share_of_all_late are late orders over orders and over all late orders (rows that differ)", 0,
           sum(1 for r in mo if abs(f(r["late_rate"]) - f(r["late_orders"]) / f(r["orders"])) > 1e-9 or abs(f(r["share_of_all_late"]) - f(r["late_orders"]) / total_late) > 1e-9), 0),
          ("2 trend", "summary: judged orders vs facts.json", F["judged_orders"], f(S["judged_orders"]), 0),
          ("2 trend", "summary: late orders vs facts.json", F["late_orders"], f(S["late_orders"]), 0),
          ("2 trend", "summary: late rate vs facts.json, %", pct(F["late_rate"]), pct(f(S["late_rate"])), 3),
          ("2 trend", "summary: latest month is the last month", last, S["latest_month"], None),
          ("2 trend", "summary: latest month label is that month's name and year", label(last), S["latest_month_label"], None),
          ("2 trend", "summary: latest month's own alarm line equals its row in the monthly file, %", pct(f(next(r for r in mo if r["year_month"] == last)["own_month_alarm_line_late_rate"])), pct(f(S["latest_month_own_alarm_line_late_rate"])), 6),
          ("1 review cost", "phase is up to the promised day, climbing (1 to 5) or levelled (6 on) (days that differ)", 0,
           sum(1 for r in ramp if r["phase"] != ("up to the promised day" if int(r["days_past_promise_capped"]) <= 0 else "climbing" if int(r["days_past_promise_capped"]) <= 5 else "levelled")), 0),
          ("1 review cost", "bad_review_share is bad reviews over reviewed orders (days that differ)", 0,
           sum(1 for r in ramp if abs(f(r["bad_review_share"]) - f(r["bad_reviews"]) / f(r["reviewed_orders"])) > 1e-9), 0),
          ("3 handoff", "on-time handoffs' share of all late orders, % (from the monthly file)", pct(sum(f(r["on_time_handoff_late_orders"]) for r in mo) / total_late), pct(f(ok_h["share_of_all_late"])), 1),
          ("5 where/when", "three worst months' share of all orders, % (story month table)", pct(sum(f(a["month"][m]["orders"]) for m in F["top3_months"]) / sum(f(r["orders"]) for r in a["month"].values())), pct(f(S["worst3_share_of_orders"])), 4),
          ("5 where/when", "three worst months' share of all orders, % to 1 place (about 21.7; typed)", 21.7, pct(f(S["worst3_share_of_orders"])), 1),
          ("5 where/when", "three worst months' share of all months, % (3 of 20)", 15.0, pct(f(S["worst3_share_of_months"])), 4)]
    seed = {r["test_id"]: r for r in a["example_seed"]}
    shown = lambda v, u: f"{f(v):.1f}%*" if u == "percent" else f"{f(v):.2f}*"
    same_example = lambda r: (r["test_id"] in seed and abs(f(r["test_group_value"]) - f(seed[r["test_id"]]["test_group_value"])) < 1e-9
                              and abs(f(r["no_change_group_value"]) - f(seed[r["test_id"]]["no_change_group_value"])) < 1e-9
                              and r["test_label"] == "EXAMPLE test: " + seed[r["test_id"]]["test_name"] and r["readout_label"] == "EXAMPLE: " + seed[r["test_id"]]["readout_metric"]
                              and r["test_group_display"] == shown(seed[r["test_id"]]["test_group_value"], seed[r["test_id"]]["unit"])
                              and r["no_change_group_display"] == shown(seed[r["test_id"]]["no_change_group_value"], seed[r["test_id"]]["unit"])
                              and r["banner"] == "EXAMPLE DATA · these tests have not run yet" and r["footnote"] == "* invented, only to show the layout" and r["status"] == "not run")
    c += [("6 fixes", "example rows that differ from the seed: values, labels, displayed values, banner, footnote, status", 0,
           sum(1 for r in t["tests_example"] if not same_example(r)) + abs(len(t["tests_example"]) - len(seed)), 0)]
    return c


def label(ym):
    return f"{MONTHS[int(ym[5:]) - 1]} {ym[:4]}"


def differing_sellers(se, raw):
    """How many seller rows differ from the raw-file rebuild (a missing or extra seller counts as one)."""
    f = float
    mine = {r["seller_id"]: r for r in raw["sellers"]}
    bad = len(set(mine) ^ {r["seller_id"] for r in se})
    for r in se:
        m = mine.get(r["seller_id"])
        if m is None:
            continue
        same = (r["seller_code"] == m["seller_code"] and f(r["orders"]) == m["orders"] and f(r["late_handoff_orders"]) == m["late_handoff_orders"]
                and f(r["late_after_late_handoff_orders"]) == m["late_after_late_handoff_orders"] and f(r["late_orders"]) == m["late_orders"]
                and f(r["rank_by_late_after_late_handoff"]) == m["rank"] and (r["is_top10"] == "true") == m["is_top10"]
                and all(abs(f(r[c]) - m[k]) < 1e-9 for c, k in (("late_handoff_rate", "late_handoff_rate"), ("late_rate", "late_rate"), ("share_of_late_after_late_handoff", "share"))))
        bad += not same
    return bad


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
