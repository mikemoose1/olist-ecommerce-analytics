"""Check every number in README.md (the short summary), docs/CASE_STUDY.md (the full case study), docs/HOW_I_CHECK_AI_WORK.md
and the Model card section of recommendation/delivery_range/README.md against the data.

Each CLAIM is a sentence fragment as the page prints it, rebuilt here from a query on the warehouse (source "warehouse"),
from the analysis report (source "report", numbers that the recommendation analysis produces and `make verify` already
reconciles) or from another repo file (source "repo"). A claim names the pages it must appear in ("f" full, "s" short, "d" model card, "w" the checks write-up).
The check fails when
  - a fragment is missing from a page it belongs to, or differs from what the data gives,
  - any number or number word left in a page's prose is not inside a checked fragment,
  - the ERD in docs/CASE_STUDY.md differs from case_study/erd.py, or the ERD fails its data checks,
  - docs/index.md is not the current output of case_study/build_pages.py.
Needs `make build` and `make recommendation` first. Selftest: case_study/selftest_check.py.
"""
import json
import re
import sys

from common import ROOT, connect, facts, row
import erd
import ontology_view

README = ROOT / "README.md"                      # the short summary
MODEL_CARD = ROOT / "recommendation" / "delivery_range" / "README.md"   # only its Model card section is checked (page "d")
WRITEUP = ROOT / "docs" / "HOW_I_CHECK_AI_WORK.md"   # how the AI-written work is checked (page "w")
FULL = ROOT / "docs" / "CASE_STUDY.md"           # the full case study; docs/index.md (Pages) is built from it
DEFINITION_PHRASES = ["one- and two-star", "one or two stars", "one- or two-star", "Test 1", "test 1"]  # review_score <= 2 and the Test 1 label


def pct(x, d=1):
    return f"{x:.{d}f}"


def build_claims(con):
    F = facts()
    one = lambda q: row(con, q)
    out = []   # (fragment, source, pages): pages holds "f" (full case study), "s" (short README), "d" (model card), "w" (checks write-up)

    def add(fragment, source, pages="f"):
        out.append((fragment, source, pages))

    # --- the data behind the sentences
    orders_raw = one("select count(*) from staging.stg_orders")[0]
    ids, people = one("select count(*), count(distinct customer_unique_id) from (select customer_id, customer_unique_id from staging.stg_customers)")
    multi = one("select count(*) from (select order_id from marts.fct_order_items group by 1 having count(distinct seller_id) > 1)")[0]
    survey_n, survey_before = one("select count(*), sum(review_before_delivery::int) from marts.fct_orders where delivery_state like 'delivered%' and review_id is not null")
    judged, late = one("select count(*), sum(is_late::int) from metrics.metric_late_rate_orders")
    s_late, s_ok = one("select avg(review_score) filter (where is_late), avg(review_score) filter (where not is_late) from metrics.metric_late_rate_orders")
    bad_late, bad_ok = one(
        "select 100.0*avg((review_score<=2)::int) filter (where is_late and review_score is not null), "
        "100.0*avg((review_score<=2)::int) filter (where not is_late and review_score is not null) from metrics.metric_late_rate_orders")
    total_bad = one("select count(*) from metrics.metric_late_rate_orders where review_score <= 2")[0]
    caused = one("select sum(extra_bad_reviews) from metrics.metric_review_cost_causal")[0]
    y0, y1 = one("select min(year(purchase_date)), max(year(purchase_date)) from marts.fct_orders")
    repeat90 = one("select value_pct from metrics.metric_repeat_rate_90d")[0]
    ev90_n, ev90_d = one("select numerator, denominator from metrics.metric_repeat_rate_90d")
    ever_pct, ever_n, ever_d = one("select value_pct, numerator, denominator from metrics.metric_repeat_rate_ever")
    win0, win1 = one("select min(year_month), max(year_month) from marts.dim_date where in_analysis_window")
    top_months = sorted(r[0] for r in con.sql("select year_month from metrics.metric_late_rate_monthly order by value_pct desc limit 3").fetchall())
    top_late, top_orders = one(
        "select sum(numerator), sum(denominator) from (select * from metrics.metric_late_rate_monthly order by value_pct desc limit 3)")
    all_late, all_orders = one("select sum(numerator), sum(denominator) from metrics.metric_late_rate_monthly")
    nne = one(
        "select 100.0*avg(is_late::int) from metrics.metric_late_rate_orders o join seeds.dash_region_map r on r.state = o.ship_to_state "
        "where r.region_group = 'North and northeast'")[0]
    hl_share, late_if_hl, late_if_ok, seller_side = one(
        "with b as (select l.is_late, o.delivered_to_carrier_at > o.last_shipping_limit_at as hl from metrics.metric_late_rate_orders l "
        "join marts.fct_orders o using (order_id) where o.delivered_to_carrier_at is not null) "
        "select 100.0*avg(hl::int), 100.0*avg(is_late::int) filter (where hl), 100.0*avg(is_late::int) filter (where not hl), "
        "100.0*sum(hl::int) filter (where is_late)/sum(is_late::int) from b")
    survey_before_late = one("select 100.0*avg(review_before_delivery::int) from metrics.metric_late_rate_orders where is_late and review_score is not null")[0]
    n_months = {f"{y}-{m:02d}": f"{name} {y}" for y in (2016, 2017, 2018) for m, name in enumerate(
        "January February March April May June July August September October November December".split(), 1)}
    mut = json.loads((ROOT / "evidence" / "mutation_report.json").read_text())
    proven = sum(r["verdict"] == "PROVEN" for r in mut)
    erd_res = erd.check_data()
    erd_ok = sum(ok for _, ok, _ in erd_res)
    rep = json.loads((ROOT / "evidence" / "recommendation_report.json").read_text())
    hold = rep["stars"]["holdout"]["matched"]["effect"]
    disc = rep["stars"]["discovery"]["matched"]["effect"]
    manifest_n = one(f"select count(*) from read_csv_auto('{ROOT / 'seeds' / 'raw_file_manifest.csv'}')")[0]
    rate = 100 * late / judged
    caused_r = round(caused)

    add(f"about {round(orders_raw, -3):,} real orders", "warehouse", "fs")
    add(f"about {caused_r:,} of the {total_bad:,} one- and two-star reviews on {judged:,} delivered orders, about {100 * caused / total_bad:.0f}%, with a range of {F['c_cost_range_lo']} to {F['c_cost_range_hi']}", "warehouse+report", "fs")
    add(f"nine tables from {y0} to {y1}" if manifest_n == 9 else "NINE_MISMATCH", "warehouse")
    add(f"{ids:,} IDs for {people:,} people", "warehouse")
    add(f"{multi:,} orders ship from several sellers", "warehouse")
    add(f"{pct(100 * survey_before / survey_n, 2)}% of the reviews on delivered orders are dated before delivery", "warehouse")
    add(f"{pct(rate, 2)}% of delivered orders bought from {n_months[win0]} to {n_months[win1]} ({late:,} of {judged:,}) arrived late. Late orders average {s_late:.2f} stars and on-time orders {s_ok:.2f}", "warehouse", "fs")
    add(f"{pct(bad_late)}% of late ones get", "warehouse")
    add(f"against {pct(bad_ok)}% of on-time ones", "warehouse")
    add(f"climb about {F['c_ramp_slope']} percentage points for each day late and level off near {F['c_ramp_plateau']}% from day {F['c_ramp_end_day']}", "report")
    add(f"The estimate is about {caused_r:,} of {total_bad:,} ({100 * caused / total_bad:.0f}%)", "warehouse")
    add(f"{F['c_cost_range_lo']} to {F['c_cost_range_hi']}", "report", "fs")
    add(f"The {F['c_cost_range_lo']} to {F['c_cost_range_hi']} range is the spread of six comparison methods, not a confidence interval", "report", "fs")
    causal = json.loads((ROOT / "evidence" / "review_cost_causal_report.json").read_text())
    ci_lo, ci_hi = causal["headline"]["ci95"]
    add(f"The preferred method's own 95% interval is {round(ci_lo):,} to {round(ci_hi):,}", "report", "fs")
    add(f"Roughly one bad review in four" if 0.23 <= caused / total_bad <= 0.30 else "QUARTER_MISMATCH", "warehouse")
    add(f"About a quarter of the bad reviews" if 0.23 <= caused / total_bad <= 0.30 else "QUARTER_MISMATCH", "warehouse")
    memo = (ROOT / "recommendation" / "MEMO.md").read_text()
    window = "90" if "90<!--d:repeat_window_days-->" in memo else "WINDOW_MISMATCH"
    add(f"{repeat90:.2f}% of customers ({int(ev90_n):,} of {int(ev90_d):,}) order again within {window} days", "warehouse")
    add(f"Only {ever_pct:.2f}% ({int(ever_n):,} of {int(ever_d):,}) ever ordered twice", "warehouse")
    add(f"came back {abs(float(F['rep_matched'])):.2f} percentage points less often, with a range of {F['rep_matched_lo']} to {F['rep_matched_hi']} percentage points", "report", "fs")
    add(f"Three months ({n_months[top_months[0]]}, {n_months[top_months[1]]} and {n_months[top_months[2]]}) hold {pct(100 * top_late / all_late)}% of late orders and {pct(100 * top_orders / all_orders)}% of all orders", "warehouse")
    add(f"run {pct(nne)}% late", "warehouse")
    add(f"On {pct(hl_share)}% of orders the seller handed the parcel to the carrier after the ship-by date. Those orders were late {pct(late_if_hl)}% of the time, against {pct(late_if_ok)}% when the handoff was on time", "warehouse", "fs")
    ratio = late_if_hl / late_if_ok
    add("about four times as likely" if round(ratio) == 4 else "RATIO_MISMATCH", "warehouse")
    add(f"they make up {pct(seller_side)}% of late orders", "warehouse")
    add(f"About {F['avoidable_late']} fewer late orders ({F['avoidable_share']}% of them) would take the late rate from {pct(rate, 2)}% to {F['c_whatif_rate']}%" if abs(100 * (late - int(F['avoidable_late'].replace(',', ''))) / judged - float(F['c_whatif_rate'])) < 0.1 else "WHATIF_MISMATCH", "report+warehouse")
    add(f"{pct(survey_before_late)}% of late orders' surveys went out before delivery", "warehouse")
    add(f"about {F['c_cost_bias_hi']} of the reviews at the top of its range", "report")
    n_hold = int(F["holdout_last_month"][-2:]) - int(F["holdout_first_month"][-2:]) + 1
    words = {3: "three", 4: "four", 5: "five", 6: "six"}
    add(f"The star penalty for a late order was smaller in the last {words[n_hold]} months of the window: {abs(hold):.2f} stars, against {abs(disc):.2f} earlier" if F["holdout_first_month"][:4] == F["holdout_last_month"][:4] else "HOLDOUT_MISMATCH", "report", "fs")
    add(f"It was {abs(hold):.2f} stars in the last {words[n_hold]} months, against {abs(disc):.2f} earlier" if F["holdout_first_month"][:4] == F["holdout_last_month"][:4] else "HOLDOUT_MISMATCH", "report")
    add(f"Late delivery is estimated to account for about {caused_r:,} bad reviews", "warehouse")
    # the goal line, the warning line and the what-if rates, from the targets table and the memo's own figures
    t = one("select 100*alarm_line_late_rate, 100*goal_late_rate, 100*stretch_goal_late_rate, 100*late_rate_if_handoffs_ok, stable_months, laney_signal_months, typical_orders, thin_months "
            "from metrics.metric_late_rate_targets")
    alarm, goal, stretch, whatif_pooled, stable, flagged_n, typical, thin_n_t = t
    in_fit_n, thin_in_fit = one(
        "select count(*) filter (where not laney_signal), "
        "count(*) filter (where not laney_signal and thin_month) "
        "from metrics.metric_late_rate_control_chart"
    )
    chart_sql = (ROOT / "models" / "metrics" / "metric_late_rate_control_chart.sql").read_text()
    if "sum(late_orders) filter (where in_fit)" not in chart_sql:
        raise SystemExit("Laney centre is not fitted on in_fit months in metric_late_rate_control_chart.sql")
    if int(in_fit_n) != 17 or int(thin_in_fit) != 2 or int(thin_n_t) != 2:
        raise SystemExit(f"unexpected in-fit/thin counts: in_fit={in_fit_n}, thin_in_fit={thin_in_fit}, thin_months={thin_n_t}")
    flagged = sorted(F[f"c_flagged_{i}"] for i in (1, 2, 3))
    assert flagged_n == 3 and len(flagged) == 3
    assert f"{goal:.1f}" == F["c_goal_line"] and f"{stretch:.1f}" == F["c_stretch_line"] and f"{whatif_pooled:.2f}" == F["c_whatif_rate"]
    assert f"{alarm:.2f}" == F["c_alarm_line"] and int(stable) == int(F["c_stable_months"]) and f"{typical:,.0f}" == F["c_typical_orders"]
    gap = f"{goal - stretch:.1f}"
    assert gap == F["c_whatif_gap"], (gap, F["c_whatif_gap"])
    spc = (ROOT / "late_rate_targets" / "spc.py").read_text()
    memo = (ROOT / "recommendation" / "MEMO.md").read_text()
    add(f"The {goal:.1f}% goal and the {alarm:.1f}% warning line", "warehouse")
    add(f"It sits at {alarm:.1f}% for a typical month of {typical:,.0f} orders", "warehouse")
    add(f"the average late rate of the {int(in_fit_n)} months left in the fit, including the {int(thin_in_fit)} thin months, plus three standard deviations" if "centre + 3 * sigma_z * sig" in spc else "SPC_MISMATCH", "repo")
    add(f"Three months crossed it: {n_months[flagged[0]]}, {n_months[flagged[1]]} and {n_months[flagged[2]]}", "warehouse")
    add(f"The goal, {goal:.1f}%, is the median late rate of the {int(stable)} stable months", "warehouse", "fs")
    add(f"and the warning line, {alarm:.1f}%,", "warehouse", "s")
    add("so half of them already beat it" if "so half of them already beat it" in memo else "HALF_MISMATCH", "repo")
    add("it includes the three spike months" if flagged_n == 3 else "SPIKE_MISMATCH", "warehouse")
    add("Three months crossed the line", "warehouse", "s")
    add(f"The {whatif_pooled:.2f}% is the pooled version: it takes all {judged:,} orders and moves the late rate from {rate:.2f}% to {whatif_pooled:.2f}%", "warehouse")
    add(f"The {stretch:.1f}% is the dashboard's version for a typical stable month: it moves the median stable month from the {goal:.1f}% goal down to {stretch:.1f}%, a drop of about {gap} percentage point", "warehouse")
    add(f"Why the dashboard says {stretch:.1f}% and this page says {whatif_pooled:.2f}%", "warehouse")
    add(f"The what-if rate of {stretch:.1f}% on the dashboard moves a typical stable month down from the goal by about {gap} percentage point", "warehouse", "s")
    add(f"The {whatif_pooled:.2f}% on the full page is the same what-if on all {judged:,} orders pooled, from {rate:.2f}%", "warehouse", "s")
    add(f"The estimated effect is about {caused_r:,} of {total_bad:,} ({100 * caused / total_bad:.0f}%)", "warehouse", "s")
    readme = FULL.read_text()
    after = readme.split("Three problems in the tables would have skewed the results.\n", 1)[1].split("\n\n", 1)[0]
    add("Three problems in the tables" if len([l for l in after.splitlines() if l.startswith("- ")]) == 3 else "THREE_MISMATCH", "repo")
    add("the nine source tables" if manifest_n == 9 else "NINE_MISMATCH", "repo")
    add(f"pass {erd_ok} of {len(erd_res)} checks against the raw files, including that every column marked FK has a unique parent and no orphans", "warehouse")
    add(f"All {proven} rules in the check suite", "repo" if proven == len(mut) else "MUTATION_MISMATCH")
    add(f"all {proven} rules in the check suite are proven able to fail on planted bad data" if proven == len(mut) else "MUTATION_MISMATCH", "repo", "s")
    # the six named methods in the case study must match the specifications in the causal report
    SPEC_PHRASES = (
        ("V2_preferred", "just-on-time baseline"),
        ("V1_baseline_all_on_time", "any on-time baseline"),
        ("V3_product_fe", "same product"),
        ("V5_plus_state_fe", "plus customer state"),
        ("V4_same_actual_delivery_time", "same actual delivery time"),
        ("V0_no_seller_fe", "no seller matching"),
    )
    fe_keys = set(causal["fe"])
    want_keys = {k for k, _ in SPEC_PHRASES}
    six_ok = (
        fe_keys == want_keys
        and len(SPEC_PHRASES) == 6
        and "six specifications" in (ROOT / "review_cost_causal" / "README.md").read_text()
    )
    add("the spread of six comparison methods" if six_ok else "SIX_MISMATCH", "repo", "fs")
    for key, phrase in SPEC_PHRASES:
        add(phrase if key in fe_keys else f"SPEC_MISSING_{key}", "report")
    # per-route printed-date backtest (locked display figures from recommendation/promise_backtest/expected.json)
    exp_all = json.loads((ROOT / "recommendation" / "promise_backtest" / "expected.json").read_text())
    P = exp_all["display"]
    burn = exp_all["integrity"]["burn_in"]
    min_cell = exp_all["integrity"]["min_cell"]
    p90_fail = exp_all["bar"]["p90"]["overall_pass"] is False
    add(
        f"On the {P['n_reviewed']:,} reviewed orders from April 2017 onward, the stricter 19-out-of-20 per-route date would likely have cut the extra one- and two-star reviews attributed to late delivery by about {P['p95_share_rounded_pct']}% (about {P['p95_reduction_rounded']} of {P['olist_extra_rounded']:,}), with a realistic range of about {P['range_lo_pct']}% to {P['range_hi_pct']}%, or about {P['bootstrap_reduction_lo_rounded']} to {P['bootstrap_reduction_hi_rounded']} reviews, from {P['bootstrap_n']:,} resamples of orders",
        "report",
    )
    add(
        f"about {P['newly_on_time_n']:,} orders that had been late would have been on time, avoiding about {P['newly_on_time_avoided_rounded']} bad reviews, while about {P['newly_late_n']:,} orders that had been on time would have been late, adding about {P['newly_late_added_rounded']}, plus about {P['still_late_reduction_rounded']} fewer from orders late either way",
        "report",
    )
    add(
        f"A looser 9-out-of-10 date failed the pre-declared pass bar and would have added about {P['p90_added_rounded']:,} extra bad reviews" if p90_fail else "P90_PASS_MISMATCH",
        "report",
    )
    add("The first promise-backtest model, a simpler per-order model, did not beat the per-route rule on accuracy", "report")
    density_fail = causal["rd_density_passed"] is False
    burn_month = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
                  7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
    by, bm, bd = (int(x) for x in burn.split("-"))
    add(
        f"after an {burn_month[bm]} {by} burn-in, with a fallback from the route to the customer's state to a global date and a minimum of {min_cell} orders",
        "report",
    )
    add(
        f"If even the global history is thinner than that, a global date with no {min_cell}-order floor is used as a last resort",
        "report",
    )
    add(f"Only {ever_pct:.2f}% of customers ({int(ever_n):,} of {int(ever_d):,}) ever ordered twice", "warehouse")
    add(
        "the cutoff check failed its density test" if density_fail else "DENSITY_MISMATCH",
        "report",
    )
    add("There are no seller operations or carrier files", "repo")
    add("Olist's commission and conversion are not in the data", "repo")
    add(
        "The per-route 19-out-of-20 date was the one that was judged",
        "report",
    )
    add("A 19-out-of-20 date is the 95th percentile of past delivery times on that route: 19 times out of 20", "report")
    pass_bar = (ROOT / "recommendation" / "promise_backtest" / "PASS_BAR.md").read_text()
    add(
        "On 20 November 2026, pass-bar items 3 and 5 were reworded after the totals were known"
        if "On 20 November 2026, items 3 and 5 were reworded after the totals" in pass_bar
        else "PASSBAR_NOTE_MISMATCH",
        "repo",
    )
    add(
        "which dates passed did not change"
        if "which dates pass did not change" in pass_bar
        else "PASSBAR_OUTCOME_MISMATCH",
        "repo",
    )
    thin_sql = (ROOT / "models" / "metrics" / "metric_late_rate_control_chart.sql").read_text()
    thin_n = 2000
    if f"orders < {thin_n} as thin_month" not in thin_sql:
        raise SystemExit("thin_month cutoff missing from metric_late_rate_control_chart.sql")
    add(f"has at least {thin_n:,} orders, the cutoff used to drop thin months from the goal", "warehouse")
    add(
        f"Sales values are in the orders; late orders in the last {F['last12_n']} months of the window carried {F['late_gmv_last12']} of sales",
        "report",
    )
    ever_sql = (ROOT / "models" / "metrics" / "metric_repeat_rate_ever.sql").read_text()
    if "all time, no window" not in ever_sql or "is_qualifying_order" not in ever_sql or "in_analysis_window" in ever_sql or "metric_late_rate" in ever_sql:
        raise SystemExit("metric_repeat_rate_ever.sql is not an all-time qualifying-order count")
    add(
        f"The {int(ever_d):,} is every customer with a qualifying order, all time, not limited to the late-rate window, and counts a same-day second order as a repeat; the {int(ev90_d):,} is the customers who had a full {window} days of follow-up",
        "warehouse",
    )
    add("The data can't support that design", "repo")
    add("bunching at the promised date", "repo")
    # the couldn't-answer 90-day clause uses a slightly different lead-in
    add(f"and {repeat90:.2f}% ({int(ev90_n):,} of {int(ev90_d):,}) did so within {window} days among customers with {window} days of follow-up", "warehouse")
    add(
        f"A per-route 19-out-of-20 date cuts extra late-delivery bad reviews from about {P['olist_extra_rounded']:,} to about {P['p95_extra_rounded']:,}, a net of about {P['p95_reduction_rounded']} (about {P['newly_on_time_avoided_rounded']} avoided, minus about {P['newly_late_added_rounded']} added, plus about {P['still_late_reduction_rounded']} fewer from orders late either way)",
        "report",
    )
    # the per-order delivery-date model (locked results from recommendation/delivery_date_model/expected.json, rebuilt
    # from the warehouse by its check_headlines.py) and the as-of seller flags
    ddm = json.loads((ROOT / "recommendation" / "delivery_date_model" / "expected.json").read_text())
    D, H = ddm["display"], ddm["holdout"]
    hm = H["integrity"]["holdout_months"]
    tm = H["integrity"]["tune_months"]
    hold_span = f"{n_months[hm[0]].split()[0]} to {n_months[hm[-1]]}"
    if H["decision"]["model_adopted"] or H["bar"]["model"]["overall_pass"] or H["decision"]["route_p95_meets_1_to_3"]:
        raise SystemExit("delivery-date model outcome changed; the recommendation text says the model and the route date both fail")
    cap = [c for c in H["bar"]["model"]["checks"] if c["id"] == 2][0]
    if cap["pass"] or "1.0 day" not in cap["name"]:
        raise SystemExit("length-cap check changed")
    add(f"Scored once on held-out orders from {hold_span}, it would have cut extra late-delivery bad reviews by about {D['model_reduction_pct']}% (about {D['model_reduction']} of {D['olist_extra']:,}), but only by printing dates {D['model_extra_days_1dp']} days longer than Olist's on average", "report", "fs")
    add(f"Scored once on {D['n_reviewed']:,} reviewed orders from {hold_span}, it cut extra late-delivery bad reviews from about {D['olist_extra']:,} under Olist's promise to about {D['model_extra']} and held up in the {n_months[hm[0]]} spike, but its dates were {D['model_extra_days_1dp']} days longer than Olist's on average, against a cap of 1 day", "report", "s")
    add(f"flagged sellers' orders ran late {D['sellers_late_flagged_1dp']}% of the time, against {D['sellers_late_other_1dp']}% for the rest", "report", "s")
    ty, tmo = int(tm[0][:4]), int(tm[0][5:])
    train_last = f"{ty}-{tmo - 1:02d}" if tmo > 1 else f"{ty - 1}-12"
    train_span = f"{n_months[H['integrity']['train_from'][:7]].split()[0]} to {n_months[train_last]}"
    add(f"trained on orders bought {train_span}, tuned on {n_months[tm[0]]} to {n_months[tm[-1]]}, and scored once on a holdout of {hold_span}", "report")
    add(f"about {D['olist_extra']:,} under Olist's printed promise, about {D['route_extra']} under the per-route date and about {D['model_extra']} under the model. In {n_months[hm[0]]}: {D['march_olist']}, {D['march_route']} and {D['march_model']}", "report")
    add(f"On the {D['n_reviewed']:,} reviewed holdout orders, extra late-delivery bad reviews fall from about {D['olist_extra']:,} under Olist's printed promise to about {D['model_extra']}, a cut of about {D['model_reduction']} ({D['model_reduction_pct']}%), with a range of {D['model_boot_lo']} to {D['model_boot_hi']} from {H['model']['bootstrap_vs_olist']['n_boot']:,} resamples of orders", "report")
    add(f"That is about {D['model_per_1000']} fewer per 1,000 reviewed orders, and about {D['model_vs_route']} fewer than the simpler per-route date (range {D['model_vs_route_lo']} to {D['model_vs_route_hi']})", "report")
    add(f"{D['model_coverage_1dp']}% of orders arrive by the model's date, against {D['olist_coverage_1dp']}% for Olist's and {D['route_coverage_1dp']}% for the per-route date", "report")
    add(f"In tuning the same setting was only {D['tune_info_extra_days_1dp']} days longer than Olist's; the gap grew because Olist shortened its own promise from an average of {D['tune_olist_mean_lead_1dp']} days in the tuning block to {D['olist_mean_lead_1dp']} on the holdout" if D["olist_mean_lead_1dp"] < D["tune_olist_mean_lead_1dp"] else "OLIST_LEAD_MISMATCH", "report")
    add(f"so the first model learns only from orders bought {train_span}", "report")
    add(f"The model's dates are {D['model_extra_days_1dp']} days longer than Olist's on average (median {D['model_median_lead']} days against {D['olist_median_lead']})", "report")
    add("The cap on extra length, 1 day, was missed by a wide margin", "report")
    add(f"In tuning, none of the {D['n_configs']} settings passed: every setting short enough for the cap did worse than Olist in {n_months[tm[0]]}" if D["tune_info_nov_model"] > D["tune_info_nov_olist"] else "TUNE_NOV_MISMATCH", "report")
    add(f"cost fewer sales than the commercial lead will trade for about {D['model_per_1000']} fewer bad reviews per 1,000 orders", "report")
    add(f"dates about {D['model_extra_days_1dp']} days longer", "report")
    sf = ddm["seller_flags"]
    add(f"with sellers who had orders both handed to the carrier late and delivered late in {sf['min_months']} or more earlier months, the list holds {D['sellers_flagged_first']} sellers in {n_months[hm[0]]} and {D['sellers_flagged_last']} by {n_months[hm[-1]].split()[0]}", "report")
    add(f"those sellers handed parcels over late more often ({D['sellers_handoff_flagged_1dp']}% of orders, against {D['sellers_handoff_other_1dp']}%), but their orders did not arrive late more often ({D['sellers_late_flagged_1dp']}%, against {D['sellers_late_other_1dp']}%)" if D["sellers_late_flagged_1dp"] <= D["sellers_late_other_1dp"] else "SELLER_MISMATCH", "report")
    add(f"They carried {D['sellers_late_share_1dp']}% of late orders on {D['sellers_order_share_1dp']}% of orders", "report")
    tr = [x["summary"] for x in json.loads((ROOT / "recommendation" / "delivery_date_model" / "tune_results.json").read_text())["results"]]
    best_in = max(x["reduction_v2"] for x in tr if x["mean_extra_days_vs_olist"] <= 1.0)
    shape_ok = (len(tr) == D["n_configs"] and round(best_in) == D["tune_info_reduction"]
                and all(x["mean_extra_days_vs_olist"] > 1.0 for x in tr if x["reduction_v2"] > best_in) and D["tune_route_reduction"] < 0)
    add(f"Left, all {len(tr)} settings tried on the tuning block: the best within the 1-day cap cut about {D['tune_info_reduction']} at {D['tune_info_extra_days_1dp']} days longer, every setting that cut more was over the cap, and the per-route date did worse than Olist there (about {-D['tune_route_reduction']} more)" if shape_ok else "TRADEOFF_MISMATCH", "report")
    add(f"Right, the holdout shows only the dates already scored on it, the model and the per-route baseline, with Olist's promise at the origin: the model cut about {D['model_reduction']} at {D['model_extra_days_1dp']} days longer and the per-route date about {D['route_reduction']} at {D['route_extra_days_1dp']}", "report")
    add(f"On the {hold_span} holdout above, the same per-route date cut about {D['route_reduction']} extra bad reviews (range {D['route_boot_lo']} to {D['route_boot_hi']}) but printed dates {D['route_extra_days_1dp']} days longer than Olist's on average, missing the same 1-day cap", "report")
    add(f"In tuning, the model met {n_months[tm[0]]} with no earlier November to learn from" if tm[0].endswith("-11") else "NOV_MISMATCH", "report")
    novembers = one("select count(distinct year_month) from marts.dim_date where in_analysis_window and year_month like '%-11'")[0]
    add("The window holds a single November peak" if novembers == 1 and "2017-11" in flagged else "PEAK_MISMATCH", "warehouse")

    # README top: the stress tests and the delivery-range rule, read from their evidence files; each rule's limit is
    # read from the pre-registration (or from the rule's own id), so a changed result or a changed rule changes the text
    ev = lambda name: json.loads((ROOT / "evidence" / f"{name}.json").read_text())
    rule = lambda rep, prefix: next(r for r in rep["pass_rules"] if r["id"].startswith(prefix))
    prereg = (ROOT / "docs" / "preregistration_v2.md").read_text()
    mr, sens, ka, dr = ev("missing_reviews_report"), ev("sensitivity_report"), ev("known_answer_real_report"), ev("delivery_range_report")
    a1, b1, c1, d2 = rule(mr, "A-1"), rule(sens, "B-1"), rule(ka, "C-1 S1_half"), rule(dr, "D-2")
    b1_min = re.search(r">= ([\d.]+)", b1["id"]).group(1)
    c1_min, c1_of = map(int, re.search(r"covers the planted truth in at least (\d+) of (\d+) seeds", prereg).groups())
    c1_seeds = ka["summary"]["S1_half"]["V2_preferred"]["seeds"]
    d2_max = int(re.search(r"calibration error at most (\d+) points", d2["id"]).group(1))
    c1_cov = c1["observed"]["covered"]
    if c1_seeds != c1_of or not (a1["pass"] and b1["pass"] and not c1["pass"] and c1_cov < c1_min and not d2["pass"] and d2["observed"] > d2_max):
        raise SystemExit("a stress-test outcome changed; the README top says A-1 and B-1 pass, C-1 and D-2 fail")
    ipw = f"{a1['observed']['ipw']:,.0f}"
    e_half = f"{b1['observed']:.1f}"
    d2_err = f"{d2['observed']:.1f}"
    # recommendation/delivery_range/README.md, Model card (page "d"): read from the same delivery-range report
    lgb, base = dr["holdout"][dr["selected_on_tune"]], dr["holdout"]["route_history"]
    gaps = {lv: abs(100 * c - 100 * float(lv)) for lv, c in lgb["coverage"].items() if 0.5 <= float(lv) <= 0.95}
    worst = max(gaps, key=gaps.get)
    if abs(gaps[worst] - d2["observed"]) > 1e-9 or abs(lgb["max_gap_0.5_to_0.95_pp"] - d2["observed"]) > 1e-9:
        raise SystemExit("delivery-range calibration error changed")
    d1 = rule(dr, "D-1")
    sp = dr["split"]
    add(f"tuned on {n_months[sp['tune_months'][0]]} to {n_months[sp['tune_months'][-1]]}, scored once on {n_months[sp['holdout_months'][0]]} to {n_months[sp['holdout_months'][-1]]}", "report", "d")
    add(f"Holdout CRPS {lgb['crps_days']:.3f} days, against {base['crps_days']:.3f} for the route-history baseline" if d1["pass"] else "D1_MISMATCH", "report", "d")
    add(f"{100 * lgb['coverage'][worst]:.1f}% of orders arrived by the date labelled {100 * float(worst):.0f}%, a calibration error of {d2_err} points, against a pre-registered limit of {d2_max}", "report", "df")
    add(f"Late delivery is the estimated cause of about {caused_r:,} of the {total_bad:,} one- and two-star reviews on delivered orders ({100 * caused / total_bad:.0f}%)", "warehouse", "s")
    add(f"Reweighting for missing reviews gives {ipw}, and a hidden confounder would need an E-value of {e_half} to halve it", "report", "s")
    add(f"failed its own calibration rule: a calibration error of {d2_err} points, against a limit of {d2_max}", "report", "s")
    add(f"| about {caused_r:,} of {total_bad:,} ({100 * caused / total_bad:.0f}%); range across {words[6]} specifications", "warehouse", "s")   # the range itself is the "fs" fragment above
    add(", not a confidence interval |", "repo", "s")
    add(f"| {ipw} |", "report", "s")
    add(f"| {e_half} (rule: at least {b1_min}) |", "report", "s")
    add(f"| the 95% interval covered the planted number in {c1_cov} of {c1_seeds} draws at half effect (rule: at least {c1_min}) |", "report", "s")
    add(f"| {d2_err} points (rule: at most {d2_max}) |", "report", "s")

    # docs/CASE_STUDY.md, Stress tests: the same four reports, with every rule limit read from the rule or the pre-registration
    four = [mr["worst_case_bounds"][k][b] for k in ("all_unreviewed_bad", "all_unreviewed_not_bad")
            for b in ("extra_on_all_judged_late", "extra_on_6366_reviewed_late")]
    add(f"| {ipw}, against {mr['v2_unweighted']['extra']:,.0f} unweighted; the {words[len(four)]} all-bad and none-bad scenarios give {min(four):,.0f} to {max(four):,.0f} |", "report")
    a1_pct, a1_of = re.search(r"A-1 .*?within (\d+)% of ([\d,]+)", prereg).groups()
    if a1_of != f"{caused_r:,}" or not rule(mr, "A-2")["pass"]:
        raise SystemExit("A-1 or A-2 changed")
    add(f"Within {a1_pct}% of {a1_of} and inside the published range | Pass |", "repo")
    ev_pt = sens["e_value_point"]
    add(f"| a hidden confounder would need an E-value of {e_half} to halve the estimate and {ev_pt['e_value_explain_away']:.1f} to explain it away | at least {b1_min} to halve | Pass |", "report")
    b2 = rule(sens, "B-2")
    b2_rmax, b2_min = re.search(r"Rmax = ([\d.]+) R_c\) >= (\d+)", b2["id"]).groups()
    osd = sens["oster"]
    if not (b2["pass"] and abs(osd["rmax_1.3x"]["delta_to_halve"] - b2["observed"]["delta"]) < 1e-9 and b2_rmax == "1.3"):
        raise SystemExit("Oster rule or result changed")
    add(f"| the Oster delta to halve it is {osd['rmax_1.3x']['delta_to_halve']:.2f} with Rmax at {b2_rmax} times the controlled R², and {osd['rmax_1']['delta_to_halve']:.2f} with Rmax at 1 | at least {b2_min} | Pass |", "report")
    cov = {r["id"].split()[1]: r["observed"]["covered"] for r in ka["pass_rules"] if r["id"].startswith("C-1 ")}
    add(f"| the preferred estimate's 95% interval covered the planted number in {cov['S0_null']}, {cov['S1_half']} and {cov['S2_full']} of {c1_seeds} draws with no, half and full effect | at least {c1_min} of {c1_of} in each | Fail (half effect: {cov['S1_half']} of {c1_seeds}) |", "report")
    add(f"| holdout calibration error {d2_err} points; holdout CRPS {lgb['crps_days']:.3f} days, against {base['crps_days']:.3f} for the route-history baseline | at most {d2_max} points | Fail |", "report")
    # the planted-effect miss: the preferred interval over the no, half and full effect draws, and the spread of the six specifications
    planted = [r for r in ka["runs"] if r["scenario"] in ("S0_null", "S1_half", "S2_full")]
    specs = [k for k in planted[0] if isinstance(planted[0][k], dict) and "extra" in planted[0][k]]
    if len(specs) != 6 or sum(cov[k] for k in ("S0_null", "S1_half", "S2_full")) != sum(r["V2_preferred"]["lo"] <= r["truth"] <= r["V2_preferred"]["hi"] for r in planted):
        raise SystemExit("known-answer runs changed")
    in_ci = sum(cov[k] for k in ("S0_null", "S1_half", "S2_full"))
    add(f"Across the no, half and full effect draws, the preferred method's 95% interval covered the planted number in {in_ci} of {len(planted)} draws ({100 * in_ci / len(planted):.0f}%), so do not quote {round(ci_lo):,} to {round(ci_hi):,} as a 95% range", "report")
    spread = {sc: sum(min(r[k]["extra"] for k in specs) <= r["truth"] <= max(r[k]["extra"] for k in specs) for r in planted if r["scenario"] == sc) for sc in ("S0_null", "S1_half", "S2_full")}
    add(f"in the same draws the spread of the {words[len(specs)]} estimates covered the planted number in only {spread['S0_null']}, {spread['S1_half']} and {spread['S2_full']} of {c1_seeds} (no, half and full effect)", "report")
    guard = float(re.search(r"mean at most ([\d.]+) day", prereg).group(1))
    pts = [v for k, v in dr["decision_points"].items() if k != "olist" and v.get("within_guardrail")]
    best = max(pts, key=lambda v: v["reduction_vs_olist"])
    add(f"Within the {guard:.0f}-day guardrail, the best decision rule is projected to cut {best['reduction_vs_olist']:.0f} extra late-delivery bad reviews against Olist's date (95% bootstrap range {best['reduction_p025']:.0f} to {best['reduction_p975']:.0f}) for {best['mean_days_added_vs_olist']:.1f} more promise days on average", "report")

    # docs/HOW_I_CHECK_AI_WORK.md (page "w"): the stress-test count and outcomes, the mutation count and the planted-answer miss
    outcomes = [a1["pass"], b1["pass"], c1["pass"], d2["pass"]]
    add(f"The pass rules for the {words[len(outcomes)]} stress tests", "repo", "w")
    add(f"reports all {words[len(outcomes)]} tests", "repo", "w")
    add("Two passed and two failed" if sum(outcomes) == 2 else "PASSFAIL_MISMATCH", "report", "w")
    add(f"All {proven} rules in the check suite pass this test" if proven == len(mut) else "MUTATION_MISMATCH", "repo", "w")
    add(f"95% interval must cover the planted number in at least {c1_min} of {c1_of} draws", "repo", "w")
    add(f"With the effect at half size, the interval covered it in {cov['S1_half']} of {c1_seeds} draws", "report", "w")
    add(f"Without a rule fixed in advance, {cov['S1_half']} of {c1_seeds} is easy", "report", "w")
    add(f"Across the draws with no, half and full effect it covered the planted number in {in_ci} of {len(planted)}", "report", "w")
    add(f"no longer calls {round(ci_lo):,} to {round(ci_hi):,} a 95% range", "report", "w")
    return out


NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?|\b(?:three|four|five|six|seven|eight|nine|ten|half|quarter|two)\b", re.I)


def prose(text):
    """Page text without code blocks, link targets, image files and list numbers."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"(?m)^\s*\d+\.\s", "", text)
    return text


def problems(page_text, claims, which, erd_text=None, ontology_section=None):
    """Problems on one page. which is "f" (docs/CASE_STUDY.md) or "s" (README.md). The ERD is checked on the full page only."""
    out = []
    if which == "f" and ontology_section is not None:
        if ontology_section not in page_text:
            out.append("ontology section differs from case_study/ontology_view.py")
        page_text = page_text.replace(ontology_section, "\n")
    text = original = prose(page_text)
    for frag, src, pages in claims:
        if which in pages and frag not in original:
            out.append(f"claim fragment not in page (or the data disagrees): {frag!r} [{src}]")
        text = text.replace(frag, " ") if which in pages else text
    for ph in DEFINITION_PHRASES:
        text = text.replace(ph, " ")
    for m in NUMBER.finditer(text):
        s = max(0, m.start() - 30)
        out.append(f"unchecked number {m.group(0)!r} near: {text[s:m.end() + 20]!r}")
    if erd_text is not None:
        block = re.search(r"```mermaid\n(.*?)\n```", page_text, re.S)
        if not block or block.group(1) != erd_text:
            out.append("the page's erDiagram differs from case_study/erd.py")
    return out


def model_card(text=None):
    """The Model card section of recommendation/delivery_range/README.md, the part of that page this check covers."""
    text = MODEL_CARD.read_text() if text is None else text
    return re.search(r"(?ms)^## Model card\n.*?(?=^## )", text).group(0)


def pages_problems(index_text, pages_text):
    return [] if index_text == pages_text else ["docs/index.md is stale: run python case_study/build_pages.py"]


def main():
    con = connect()
    claims = build_claims(con)
    index = ROOT / "docs" / "index.md"
    import build_pages
    current = index.read_text() if index.exists() else ""
    full_text = FULL.read_text()
    found = [f"[README.md] {p}" for p in problems(README.read_text(), claims, "s")]
    found += [f"[recommendation/delivery_range/README.md] {p}" for p in problems(model_card(), claims, "d")]
    found += [f"[docs/HOW_I_CHECK_AI_WORK.md] {p}" for p in problems(WRITEUP.read_text(), claims, "w")]
    found += [f"[docs/CASE_STUDY.md] {p}" for p in problems(full_text, claims, "f", erd.mermaid(), ontology_view.case_study_section(con))]
    found += pages_problems(current, build_pages.render(full_text, build_pages.embedded_url(current)))
    for p in found:
        print("FAIL ", p)
    erd_bad = [d for d, ok, _ in erd.check_data() if not ok]
    for d in erd_bad:
        print("FAIL  ERD:", d)
    n = len(claims)
    print(f"{'FAIL' if found or erd_bad else 'PASS'}  case study: {n} fragments checked against the data on README.md, docs/CASE_STUDY.md, docs/HOW_I_CHECK_AI_WORK.md and the delivery-range model card, {len(found)} problems, {len(erd_bad)} ERD check failures")
    sys.exit(1 if found or erd_bad else 0)


if __name__ == "__main__":
    main()
