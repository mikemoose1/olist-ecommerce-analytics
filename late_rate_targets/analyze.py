#!/usr/bin/env python3
"""Alarm line, goal lines and review break point for the monthly late-delivery rate.

  python late_rate_targets/analyze.py [--out DIR] [--quick]

Needs a built warehouse (make build). Reads the dbt tables metrics.metric_late_rate_control_chart,
metrics.metric_late_rate_targets, metrics.metric_bad_review_by_days_late and the order-level marts; recomputes the monthly
counts independently from the raw CSVs; fits everything in Python and requires the SQL and Python fits to agree.
Writes evidence/late_rate_targets_report.json (deterministic: fixed seeds) and, with --out, the chart PNGs.
--quick uses fewer simulations (a smoke run; the committed report comes from the full run).
Exit 1 if any reconciliation or proof check fails.
"""
import argparse, json, os, sys
import duckdb, numpy as np
import statsmodels.api as sm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spc, proofs, breakpoint as bp

ROOT = os.path.dirname(HERE)
DB = os.environ.get("OLIST_DB_PATH", os.path.join(ROOT, "olist.duckdb"))
RAW = os.environ.get("OLIST_RAW_DIR", os.path.join(ROOT, "data", "raw"))
STORY = {"judged": 94931, "late": 6518, "late_rate_pct": 6.87, "mar2018_pct": 19.152, "aug2018_pct": 6.3,
         "bad_reviews": 11635, "avg_stars_late": 2.27, "avg_stars_on_time": 4.31,
         "extra_bad": 3335, "extra_bad_share_pct": 28.7}


def independent_monthly():
    """Monthly counts straight from the raw CSVs, no dbt code (same rule as verification/story_numbers.py)."""
    r = duckdb.connect()
    for name, f in {"orders": "olist_orders_dataset", "items": "olist_order_items_dataset", "reviews": "olist_order_reviews_dataset"}.items():
        r.execute(f"create view {name} as select * from read_csv_auto('{RAW}/{f}.csv', header=true)")
    return r.execute("""
    with it as (select order_id, count(*) n_items, count(distinct seller_id) n_sellers from items group by 1),
    rv as (select * from (select *, row_number() over (partition by order_id order by review_answer_timestamp desc, review_id) rn from reviews) where rn = 1),
    j as (select o.order_id, strftime(o.order_purchase_timestamp::date, '%Y-%m') ym,
                 o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date late, rv.review_score
          from orders o join it using (order_id) left join rv using (order_id)
          where o.order_status = 'delivered' and o.order_delivered_customer_date is not null and it.n_sellers = 1
            and o.order_purchase_timestamp::date between date '2017-01-01' and date '2018-08-31')
    select ym year_month, count(*)::bigint orders, sum(late::int)::bigint late_orders, sum((review_score <= 2)::int)::bigint bad_reviews
    from j group by 1 order by 1""").df()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out"); ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    seeds = 300 if a.quick else proofs.SEEDS
    B_days, B_months = (30, 100) if a.quick else (500, 2000)
    con = duckdb.connect(DB, read_only=True)
    m = con.execute("select * from metrics.metric_late_rate_control_chart order by year_month").df()
    t = con.execute("select * from metrics.metric_late_rate_targets").df().iloc[0]
    d = con.execute("select * from metrics.metric_bad_review_by_days_late order by 1").df()
    months, k, n = list(m.year_month), m.late_orders.values.astype(float), m.orders.values.astype(float)
    checks, rep = [], {}

    def check(name, ok, detail=""):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

    # ---- 1. reconcile to the story and to the raw CSVs
    check("judged orders = story", int(t.judged_orders) == STORY["judged"], f"{int(t.judged_orders)}")
    check("late orders = story", int(t.late_orders) == STORY["late"], f"{int(t.late_orders)}")
    check("late rate 6.87%", round(100 * t.late_rate, 2) == STORY["late_rate_pct"])
    mar = m[m.year_month == "2018-03"].iloc[0]; aug = m[m.year_month == "2018-08"].iloc[0]
    check("Mar 2018 = 19.152%", round(100 * mar.late_rate, 3) == STORY["mar2018_pct"], f"{100 * mar.late_rate:.4f}")
    check("Aug 2018 = 6.3%", round(100 * aug.late_rate, 1) == STORY["aug2018_pct"], f"{100 * aug.late_rate:.4f}")
    check("bad reviews = 11,635", int(t.bad_reviews) == STORY["bad_reviews"])
    check("avg stars 2.27 late / 4.31 on time", (round(t.avg_stars_late, 2), round(t.avg_stars_on_time, 2)) == (STORY["avg_stars_late"], STORY["avg_stars_on_time"]))
    ind = independent_monthly()
    same = (list(ind.year_month) == months and (ind.orders.values == m.orders.values).all()
            and (ind.late_orders.values == m.late_orders.values).all() and (ind.bad_reviews.values == m.bad_reviews.values).all())
    check("monthly orders, late orders and bad reviews = independent raw-CSV recount (20 months)", same)
    rr = json.load(open(os.path.join(ROOT, "evidence", "recommendation_report.json")))["money"]["low_star_reviews"]
    check("extra 1-2 star reviews 3,335 and 28.7% = recommendation report",
          round(rr["excess_from_lateness"]["mid"]) == STORY["extra_bad"] and round(rr["share_of_all_low_star_pct"]["mid"], 1) == STORY["extra_bad_share_pct"]
          and rr["all_low_star"] == STORY["bad_reviews"])

    # ---- 2. p-chart: dispersion test, plain vs Laney, thin months
    disp = spc.dispersion_test(k, n)
    plain = spc.fit_plain(k, n)
    plain_iter = spc.fit_laney(k, n, laney=False)
    lan = spc.fit_laney(k, n)
    lan_once = spc.fit_laney(k, n, iterate=False)
    check("Python Laney fit = SQL fit (centre, sigma_z, every limit, every signal)",
          abs(lan["centre"] - t.stable_centre_rate) < 1e-12 and abs(lan["sigma_z"] - t.laney_sigma_z) < 1e-12
          and np.abs(lan["ucl"] - m.laney_ucl.values).max() < 1e-12 and np.abs(lan["lcl"] - m.laney_lcl.values).max() < 1e-12
          and (lan["signal"] == m.laney_signal.values).all())
    check("Python plain fit = SQL plain limits", np.abs(plain["ucl"] - m.plain_ucl.values).max() < 1e-12 and (plain["signal"] == m.plain_signal.values).all())
    typical = float(t.typical_orders)
    lcl_t, ucl_t = spc.limits(lan["centre"], lan["sigma_z"], typical)
    check("alarm line = SQL alarm line", abs(ucl_t - t.alarm_line_late_rate) < 1e-12)
    sig_months = [mm for mm, s in zip(months, lan["signal"]) if s]
    stable = (~lan["signal"]) & (~m.thin_month.values)
    pct = lambda v: float(np.percentile(v, 25))   # linear interpolation, as percentile_cont
    rate = k / n
    safe = pct(rate[stable]); stretch = pct(m.late_rate_if_handoffs_ok.values[stable])
    check("safe and stretch goals = SQL", abs(safe - t.safe_goal_late_rate) < 1e-12 and abs(stretch - t.stretch_goal_late_rate) < 1e-12)
    # pooled-handoff sensitivity for the whole-period stretch rate
    ho_ok = m.on_time_handoff_late_orders.sum() / m.on_time_handoff_orders.sum()
    cf_pooled = (m.late_orders.sum() - m.late_handoff_late_orders.sum() + m.late_handoff_orders.sum() * ho_ok) / n.sum()
    rep["pchart"] = {
        "months": [{"month": mm, "orders": int(nn), "late": int(kk), "rate": float(kk / nn), "thin": bool(th),
                    "plain_lcl": float(pl), "plain_ucl": float(pu), "plain_signal": bool(ps),
                    "laney_lcl": float(ll), "laney_ucl": float(lu), "laney_signal": bool(ls),
                    "rate_if_handoffs_ok": float(cf)}
                   for mm, nn, kk, th, pl, pu, ps, ll, lu, ls, cf in zip(months, n, k, m.thin_month, plain["lcl"], plain["ucl"], plain["signal"],
                                                                         lan["lcl"], lan["ucl"], lan["signal"], m.late_rate_if_handoffs_ok)],
        "dispersion_test": disp,
        "plain_classic": {"centre": plain["centre"], "months_flagged": int(plain["signal"].sum())},
        "plain_refitted_in_passes": {"centre": plain_iter["centre"], "months_flagged": int(plain_iter["signal"].sum()), "passes": plain_iter["passes"]},
        "laney_single_pass_all_months": {"centre": lan_once["centre"], "sigma_z": lan_once["sigma_z"], "months_flagged": int(lan_once["signal"].sum()),
                                          "ucl_at_typical_orders": float(spc.limits(lan_once["centre"], lan_once["sigma_z"], typical)[1])},
        "laney": {"stable_centre": lan["centre"], "sigma_z": lan["sigma_z"], "passes": lan["passes"], "months_flagged": sig_months,
                  "typical_orders": typical, "alarm_line": float(ucl_t), "lower_limit_at_typical_orders": float(lcl_t)},
        "thin_months": [mm for mm, th in zip(months, m.thin_month) if th],
        "stable_months": [mm for mm, s in zip(months, stable) if s],
        "goals": {"safe_25th_pct_of_stable": safe, "best_stable_month": float(rate[stable].min()),
                  "stretch_25th_pct_if_handoffs_ok": stretch,
                  "whole_period_rate_if_handoffs_ok_month_specific": float(t.late_rate_if_handoffs_ok),
                  "whole_period_rate_if_handoffs_ok_pooled": float(cf_pooled),
                  "stable_month_rates_sorted": sorted(float(x) for x in rate[stable]),
                  "median_stable": float(np.median(rate[stable]))},
        "handoff": {"late_handoff_orders": int(t.late_handoff_orders), "late_handoff_late": int(t.late_handoff_late_orders),
                    "late_handoff_late_rate": float(t.late_handoff_late_orders / t.late_handoff_orders),
                    "on_time_handoff_orders": int(t.on_time_handoff_orders), "on_time_handoff_late": int(t.on_time_handoff_late_orders),
                    "on_time_handoff_late_rate": float(ho_ok)},
    }
    print(f"dispersion: chi2={disp['chi2']:.1f} on {disp['df']} df, phi={disp['phi']:.1f}; Laney sigma_z={lan['sigma_z']:.3f}")

    # ---- 3. proofs
    base = lan["centre"]
    proof = {}
    ok, r = proofs.check_dispersion_test_discriminates(n, base, k); proof["dispersion_test"] = r
    check("dispersion test: quiet on chance-only data, loud on the real months", ok, f"noise rejected {r['noise_rejected_at_1pct']:.2%} of the time at 1%")
    for kind in ("plain", "laney"):
        ok, r = proofs.check_pure_noise_is_quiet(n, base, kind, seeds=seeds); proof[f"noise_{kind}"] = r
        check(f"pure noise, {kind} p-chart: false alarms across {seeds} seeds", ok,
              f"{r['series_any_flag']:.1%} of 20-month series had a flag (limit {proofs.MAX_SERIES_FALSE_ALARM:.0%}); {r['point_flag_rate']:.3%} of months flagged")
        ok, r = proofs.check_planted_month_is_flagged(n, base, kind, seeds=seeds); proof[f"planted_{kind}"] = r
        check(f"planted bad month (+{proofs.PLANT_PP * 100:.0f} points), {kind} p-chart: flagged across {seeds} seeds", ok,
              f"planted month flagged {r['planted_flagged']:.1%}; other months flagged {r['other_months_flag_rate']:.2%}")
    sd = lan["sigma_z"] * np.sqrt(base * (1 - base) / typical)   # month-to-month wobble the size of the real stable months
    od = {kind: proofs.rates(n, base, kind, seeds=seeds, seed=5, extra_sd=sd) for kind in ("plain", "laney")}
    proof["overdispersed_noise"] = {"extra_sd": float(sd), **od}
    check("overdispersed noise (no real change, months wobble like the real data): Laney quieter than plain by 5x or more",
          od["laney"]["series_any_flag"] * 5 <= od["plain"]["series_any_flag"],
          f"plain {od['plain']['series_any_flag']:.1%} of series flagged, Laney {od['laney']['series_any_flag']:.1%}")
    hold = {}
    for kind in ("laney", "plain"):
        ok, r = proofs.check_holdout_flags_month(months, k, n, [x for x in months if x < "2018"], "2018-03", kind)
        hold[kind] = {"flags_march_2018": bool(ok), **r}
    proof["holdout_2017_only"] = hold
    h = hold["laney"]
    check("limits fit on 2017 only flag Mar 2018 (Laney)", hold["laney"]["flags_march_2018"],
          f"centre {h['centre']:.2%}, sigma_z {h['sigma_z']:.2f}; Mar 2018 {h['months']['2018-03']['rate']:.2%} vs limit {h['months']['2018-03']['ucl']:.2%}")
    check("limits fit on 2017 only flag Mar 2018 (plain)", hold["plain"]["flags_march_2018"])
    rep["proofs"] = proof

    # ---- 4. review break point
    x = d.days_past_promise_capped.values.astype(float); nr = d.reviewed_orders.values.astype(float); yb = d.bad_reviews.values.astype(float)
    grid = list(range(-20, 26))
    late_flag = (x > 0)
    grouped = np.array([[yb[~late_flag].sum(), nr[~late_flag].sum() - yb[~late_flag].sum()], [yb[late_flag].sum(), nr[late_flag].sum() - yb[late_flag].sum()]])
    (a_ok, b_ok), (a_late, b_late) = grouped[0], grouped[1]   # bad / not bad, on-time row then late row
    orr = float(a_late * b_ok / (b_late * a_ok)); se = float(np.sqrt(1 / a_ok + 1 / b_ok + 1 / a_late + 1 / b_late))
    ci = (orr * np.exp(-1.959964 * se), orr * np.exp(1.959964 * se))
    share_late, share_ok = grouped[1, 0] / grouped[1].sum(), grouped[0, 0] / grouped[0].sum()
    glm_d = sm.GLM(np.column_stack([yb, nr - yb]), sm.add_constant(x), family=sm.families.Binomial()).fit()
    b_lin, ll_lin = bp.logit_fit(x, yb, nr)
    k1, b1, ll1 = bp.logit_search(x, yb, nr, grid, 1)
    k2, b2, ll2 = bp.logit_search(x, yb, nr, grid, 2)
    k3, b3, ll3 = bp.logit_search(x, yb, nr, grid, 3)
    ic = {"straight": bp.aic_bic(ll_lin, 2, len(x)), "one_break": bp.aic_bic(ll1, 4, len(x)), "two_breaks": bp.aic_bic(ll2, 6, len(x)),
          "three_breaks": bp.aic_bic(ll3, 8, len(x))}
    dav = bp.davies_logit(x, yb, nr, grid, B_days, 11)
    check("both logistic models agree with the plain tallies (grouped fit reproduces 11,635 bad reviews)",
          abs(float((nr * bp.logit_predict(x, k2, b2)).sum()) - yb.sum()) < 1.0 and int(yb.sum()) == STORY["bad_reviews"])
    sh = yb / nr
    seg0 = bp.seg_search(x, sh, nr, grid, 0); seg1 = bp.seg_search(x, sh, nr, grid, 1); seg2 = bp.seg_search(x, sh, nr, grid, 2)
    dav_seg = bp.davies_seg(x, sh, nr, grid, B_days, 13, nr)
    curve = lambda kn, bt: {int(v): float(p) for v, p in zip(x, bp.logit_predict(x, kn, bt))}
    p2 = bp.logit_predict(np.arange(-30, 31), k2, b2)
    before = float(np.average(sh[x <= k2[0]], weights=nr[x <= k2[0]])); after = float(np.average(sh[x >= k2[1]], weights=nr[x >= k2[1]]))
    # most reviews of orders more than 2 days late were written BEFORE the parcel arrived (the survey goes out on the promised day)
    sd_ = con.execute("""select greatest(-30, least(30, f.days_past_promise)) d, count(o.review_score) r,
        count(o.review_score) filter (where o.review_before_delivery) r_before, count(*) filter (where o.review_score <= 2) b,
        count(*) filter (where o.review_score <= 2 and o.review_before_delivery) b_before
        from metrics.metric_late_rate_orders o join marts.fct_orders f using (order_id) group by 1 order by 1""").df()
    late_rows = sd_[sd_.d > 0]; early_rows = sd_[sd_.d <= 0]
    before_tbl = {int(r_.d): {"reviews": int(r_.r), "written_before_delivery": int(r_.r_before)} for r_ in sd_[(sd_.d >= 1) & (sd_.d <= 8)].itertuples()}
    # monthly late rate vs monthly bad-review rate
    xm = 100 * rate; rv = m.reviewed_orders.values.astype(float); ym = m.bad_review_rate.values.astype(float)
    mg = list(np.round(np.sort(xm)[2:-2], 3))
    ols = sm.WLS(ym, sm.add_constant(xm), weights=rv).fit()
    ms0 = bp.seg_search(xm, ym, rv, mg, 0); ms1 = bp.seg_search(xm, ym, rv, mg, 1)
    dav_m = bp.davies_seg_wild(xm, ym, rv, mg, B_months, 14)
    grid_m = lambda v: list(np.round(np.sort(v)[2:-2], 3))
    loo = bp.leave_one_out_break(xm, ym, rv, grid_m)
    keep = ~m.thin_month.values
    ols_nt = sm.WLS(ym[keep], sm.add_constant(xm[keep]), weights=rv[keep]).fit()
    dav_m_nt = bp.davies_seg_wild(xm[keep], ym[keep], rv[keep], grid_m(xm[keep]), B_months, 15)
    rep["break_point"] = {
        "days": {
            "bad_review_share_late": float(share_late), "bad_review_share_on_time": float(share_ok),
            "logistic_late_vs_on_time": {"odds_ratio": orr, "ci95": [float(ci[0]), float(ci[1])]},
            "logistic_linear_in_days": {"odds_ratio_per_day": float(np.exp(glm_d.params[1])), "ci95": [float(v) for v in np.exp(glm_d.conf_int()[1])]},
            "model_comparison_AIC_BIC": {kk: [float(v) for v in vv] for kk, vv in ic.items()},
            "three_breaks_logistic": {"break_days": [float(v) for v in k3]},
            "one_break_logistic": {"break_day": float(k1[0]), "p_value_vs_straight_line_bootstrap": dav["p_value"], "bootstrap_B": B_days},
            "two_breaks_logistic": {"first_break_day": float(k2[0]), "second_break_day": float(k2[1]),
                                     "break_days_note": "point estimates on a whole-day grid; a bootstrap interval for them collapsed to a single value, so none is reported",
                                     "logit_slope_between_breaks_per_day": float(b2[1] + b2[2]),
                                     "bad_share_up_to_first_break": before, "bad_share_from_second_break": after,
                                     "model_probability_by_day": {int(dd): float(pp) for dd, pp in zip(np.arange(-30, 31), p2)}},
            "segmented_share_scale": {"straight_rss": float(seg0[2]), "one_break": {"day": float(seg1[0][0]), "rss": float(seg1[2])},
                                       "two_breaks": {"days": [float(v) for v in seg2[0]], "rss": float(seg2[2]),
                                                      "slope_between_breaks_pp_per_day": float(100 * (seg2[1][1] + seg2[1][2]))},
                                       "bootstrap_test_one_break_vs_straight": dav_seg},
            "reviews_written_before_the_parcel_arrived": {
                "late_orders_reviews": int(late_rows.r.sum()), "late_orders_written_before_delivery": int(late_rows.r_before.sum()),
                "on_time_orders_reviews": int(early_rows.r.sum()), "on_time_orders_written_before_delivery": int(early_rows.r_before.sum()),
                "late_bad_reviews": int(late_rows.b.sum()), "late_bad_reviews_written_before_delivery": int(late_rows.b_before.sum()),
                "by_day_1_to_8": before_tbl},
            "observed_share_by_day": {int(dd): float(s) for dd, s in zip(x, sh)},
        },
        "months": {
            "bad_share_pp_per_1pp_late": float(100 * ols.params[1]), "slope_ci95_pp": [float(100 * v) for v in ols.conf_int()[1]],
            "r_squared": float(ols.rsquared), "intercept_bad_share": float(ols.params[0]),
            "straight_rss": float(ms0[2]), "one_break": {"late_rate_pct": float(ms1[0][0]), "rss": float(ms1[2]), "slope_before_pp_per_pp": float(100 * ms1[1][1]),
                                                    "slope_after_pp_per_pp": float(100 * (ms1[1][1] + ms1[1][2])), "leave_one_out_break_positions": sorted(set(round(v, 2) for v in loo))},
            "bootstrap_test_one_break_vs_straight": dav_m,
            "without_thin_months": {"slope": float(ols_nt.params[1]), "r_squared": float(ols_nt.rsquared), "bootstrap_test": dav_m_nt},
            "points": [{"month": mm, "late_rate_pct": float(a_), "bad_review_share": float(b_), "reviewed": int(c_)} for mm, a_, b_, c_ in zip(months, xm, ym, rv)],
        },
    }
    print(f"days: breaks at {k2} (point estimates, no interval); one-break p={dav['p_value']:.4f}; monthly one-break p={dav_m['p_value']:.3f}, R2={ols.rsquared:.3f}")

    # ---- data note: orders bought late in the window that never got a delivery date drop out of the judged population
    note = con.execute("""select strftime(purchase_date, '%Y-%m') ym, count(*) orders, count(*) filter (where delivery_state in ('delivered_on_time','delivered_late')) delivered
        from marts.fct_orders where in_analysis_window and n_items > 0 group by 1 order by 1 desc limit 4""").df()
    rep["data_note_last_months_delivered_share"] = {r.ym: float(r.delivered / r.orders) for r in note.itertuples()}
    rep["checks"] = checks
    rep["story_numbers"] = STORY
    os.makedirs(os.path.join(ROOT, "evidence"), exist_ok=True)
    if not a.quick:
        with open(os.path.join(ROOT, "evidence", "late_rate_targets_report.json"), "w") as fh:
            json.dump(rep, fh, indent=1, sort_keys=True, default=float)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        import charts
        charts.pchart(rep, os.path.join(a.out, "pchart.png"))
        charts.breakpoint_chart(rep, os.path.join(a.out, "breakpoint.png"))
    failed = [c for c in checks if not c["passed"]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
