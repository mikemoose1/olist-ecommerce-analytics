"""Build every number the story's charts and captions use, from the warehouse and the recommendation report.

  python story/story_data.py           write story/data/*.csv and story/data/facts.json
  python story/story_data.py --check   fail if the committed files differ from a fresh build

Rates carry 95% Wilson intervals. Matched estimates carry the intervals analyze.py reports.
verification/verify_headlines.py Part C recomputes the chart numbers from the raw CSVs.
"""
import csv, io, json, math, sys
from pathlib import Path

import duckdb, yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kpi_tree as K

ROOT = K.ROOT
OUT = ROOT / "story" / "data"
NNE = ("AC", "AL", "AM", "AP", "BA", "CE", "MA", "PA", "PB", "PE", "PI", "RN", "RO", "RR", "SE", "TO")
LAST12_FROM = "2017-09-01"   # the last 12 months of the window: 2017-09 to 2018-08


def wilson(k, n, z=1.959964):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def rate_rows(con, key_sql, where="true"):
    rows = con.execute(f"""select {key_sql} k, count(*) n, sum(is_late::int) l from judged where {where}
                           group by 1 order by 1""").fetchall()
    total_late = con.execute("select sum(is_late::int) from judged").fetchone()[0]
    out = []
    for k, n, l in rows:
        lo, hi = wilson(l, n)
        out.append({"segment": str(k), "orders": n, "late": int(l), "late_rate": round(l / n, 6),
                    "ci_low": round(lo, 6), "ci_high": round(hi, 6), "share_of_late": round(l / total_late, 6)})
    return out


def build():
    tree = yaml.safe_load(K.TREE.read_text())
    rep = json.loads((ROOT / "evidence" / "recommendation_report.json").read_text())
    con = duckdb.connect(str(ROOT / "olist.duckdb"), read_only=True)
    con.execute(f"create temp view judged as {tree['judged_sql']}")
    one = lambda q: con.execute(q).fetchone()
    n, late = one("select count(*), sum(is_late::int) from judged")
    lo, hi = wilson(late, n)
    tables = {
        "late_by_month": rate_rows(con, "strftime(purchase_date, '%Y-%m')"),
        "late_by_state": sorted(rate_rows(con, "ship_to_state"), key=lambda r: -r["late"]),
        "late_by_region": rate_rows(con, f"case when ship_to_state in {NNE} then 'North and northeast' else 'Rest of Brazil' end"),
        "late_by_handoff": rate_rows(con, "case when delivered_to_carrier_at > last_shipping_limit_at then 'Handed over after ship-by' else 'Handed over on time' end",
                                     "delivered_to_carrier_at is not null"),
    }
    ls = rep["money"]["low_star_reviews"]
    com_n, com_k = one(f"""select count(*), sum(regexp_matches(strip_accents(lower(review_comment_message)), '{K.NOT_ARRIVED}')::int)
                           from judged j join marts.fct_reviews r on r.order_id = j.order_id and r.is_chosen_for_order
                           where j.is_late and r.review_comment_message is not null""")
    sv_n, sv_k = one("select count(*), sum(review_before_delivery::int) from judged where is_late and review_score is not null")
    handoff = {r["segment"]: r for r in tables["late_by_handoff"]}
    hl, ho = handoff["Handed over after ship-by"], handoff["Handed over on time"]
    m = rep["repeat90"]["all"]["matched"]
    facts = {
        "judged_orders": n, "late_orders": int(late), "late_rate": round(late / n, 6), "late_rate_ci": [round(lo, 6), round(hi, 6)],
        "low_star_all": ls["all_low_star"],
        "star_penalty": rep["stars"]["all"]["matched"]["effect"], "star_penalty_ci": rep["stars"]["all"]["matched"]["ci"],
        "late_sales_window": round(float(one("select sum(amount_paid) from judged where is_late")[0]), 2),
        "late_sales_last12": round(float(one(f"select sum(amount_paid) from judged where is_late and purchase_date >= date '{LAST12_FROM}'")[0]), 2),
        "total_sales_last12": round(float(one(f"select sum(amount_paid) from judged where purchase_date >= date '{LAST12_FROM}'")[0]), 2),
        "handoff_late_share_of_late": round(hl["late"] / late, 6),
        "handoff_late_rate": hl["late_rate"], "handoff_late_rate_ci": [hl["ci_low"], hl["ci_high"]],
        "handoff_ok_rate": ho["late_rate"], "handoff_ok_rate_ci": [ho["ci_low"], ho["ci_high"]],
        "avoidable_late_upper": round(rep["who_caused"]["avoidable_upper_bound"]["late_orders"], 1),
        "comment_delay_share": round(com_k / com_n, 6), "comment_delay_share_ci": [round(x, 6) for x in wilson(com_k, com_n)], "comments_n": com_n,
        "survey_before_share": round(sv_k / sv_n, 6), "survey_before_share_ci": [round(x, 6) for x in wilson(sv_k, sv_n)],
        "repeat_raw_pts": round(rep["repeat90"]["all"]["raw"]["effect"] * 100, 4),
        "repeat_raw_pts_ci": [round(x * 100, 4) for x in rep["repeat90"]["all"]["raw"]["ci"]],
        "repeat_effect_pts": round(m["effect"] * 100, 4), "repeat_effect_pts_ci": [round(x * 100, 4) for x in m["ci"]],
        "late_first_last12": rep["money"]["late_first_orders_last12"],
        "lost_repeat_last12": [round(rep["money"]["lost_repeat_gmv_last12"][k], 1) for k in ("low", "mid", "high")],
        "label_eval": K.label_eval(),
    }
    facts["review_cost_causal"] = review_cost(con, ls["all_low_star"])
    tables["bad_review_by_days_late"], facts["ramp"] = ramp(con)
    tables["late_rate_control"], facts["targets"] = targets(con)
    facts["repeat"] = repeat(rep)
    top3 = sorted(tables["late_by_month"], key=lambda r: -r["late"])[:3]
    facts["top3_months"] = [r["segment"] for r in top3]
    facts["top3_months_share_of_late"] = round(sum(r["late"] for r in top3) / late, 6)
    facts["captions"] = captions(facts, tables)
    return tables, facts


def review_cost(con, all_low_star):
    """Extra 1-2 star reviews caused by lateness: the dbt total (metric_review_cost_causal) and the spread across the six
    specifications in evidence/review_cost_causal_report.json (assert_review_cost_causal_reconciles ties the two)."""
    head = json.loads((ROOT / "evidence" / "review_cost_causal_report.json").read_text())["headline"]
    extra, rev = con.execute("select sum(extra_bad_reviews), sum(reviewed_late_orders) from metrics.metric_review_cost_causal").fetchone()
    return {"extra": round(float(extra), 1), "reviewed_late": int(rev), "share": round(float(extra) / all_low_star, 6),
            "ci95": [round(x, 1) for x in head["ci95"]], "range": [round(x, 1) for x in head["range_across_specifications"]],
            "seller_bias_reviews": [round(x, 1) for x in head["hidden_seller_bias_if_in_every_late_order"]["reviews"]]}


def ramp(con):
    """1-2 star share by whole days past the promise (metric_bad_review_by_days_late) and the ramp the story describes
    (descriptive, raw shares, not a causal estimate): the share up to the first break day of the segmented fit in
    evidence/late_rate_targets_report.json (day -1, the day before the promise; day 0 gives the same 8.7%), the
    least-squares slope of the daily shares from the first to the second break day (about 11 points a day), and the share
    from the second break day on (about 78%)."""
    seg = json.loads((ROOT / "evidence" / "late_rate_targets_report.json").read_text())["break_point"]["days"]["segmented_share_scale"]
    start, end = (int(x) for x in seg["two_breaks"]["days"])
    rows = [{"segment": str(d), "orders": o, "reviewed": r, "bad": b, "bad_share": round(b / r, 9) if r else None}
            for d, o, r, b in con.execute("""select days_past_promise_capped, orders, reviewed_orders, bad_reviews
                                             from metrics.metric_bad_review_by_days_late order by 1""").fetchall()]
    share = lambda sel: sum(r["bad"] for r in rows if sel(int(r["segment"]))) / sum(r["reviewed"] for r in rows if sel(int(r["segment"])))
    pts = [(int(r["segment"]), r["bad"] / r["reviewed"]) for r in rows if start <= int(r["segment"]) <= end]
    mx, my = sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)
    slope = sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)
    return rows, {"start_day": start, "end_day": end, "on_time_share": round(share(lambda d: d <= start), 6),
                  "slope_per_day": round(slope, 6), "plateau_share": round(share(lambda d: d >= end), 6)}


def targets(con):
    """The trend chart's lines: each month's Laney p-prime upper limit, the alarm line at a typical month, the goal line
    (median stable month) and the stretch line (the median stable month if late handoffs ran late no more often than on-time ones, a what-if), from the dbt target models."""
    rows = [{"segment": ym, "orders": n, "late": int(l), "late_rate": round(r, 6), "laney_ucl": round(u, 6),
             "laney_signal": bool(s), "thin_month": bool(t)}
            for ym, n, l, r, u, s, t in con.execute("""select year_month, orders, late_orders, late_rate, laney_ucl, laney_signal, thin_month
                                                    from metrics.metric_late_rate_control_chart order by 1""").fetchall()]
    t = con.execute("""select alarm_line_late_rate, goal_late_rate, stretch_goal_late_rate, safe_goal_late_rate,
                              late_rate_if_handoffs_ok, typical_orders, stable_months from metrics.metric_late_rate_targets""").fetchone()
    keys = ("alarm_line", "goal", "stretch", "safe_goal", "late_rate_if_handoffs_ok")
    out = {k: round(float(v), 6) for k, v in zip(keys, t)}
    out.update(typical_orders=int(t[5]), stable_months=int(t[6]), flagged=[r["segment"] for r in rows if r["laney_signal"]])
    return rows, out


def repeat(rep):
    """The repeat-customer sentence: 90-day return rates after a late or on-time first order, from the recommendation
    report, next to the separate repeat analysis in evidence/repeat_first_order_report.json (check_story.py ties them)."""
    raw, ev = rep["repeat90"]["all"]["raw"], json.loads((ROOT / "evidence" / "repeat_first_order_report.json").read_text())
    return {"late": raw["late"], "on_time": raw["on_time"], "n_late": raw["n_late"], "n_on_time": raw["n_on_time"],
            "evidence_rep90": {k: ev["rep90"][k] for k in ("late_n", "late_k", "late_rate", "ontime_n", "ontime_k", "ontime_rate")},
            "revenue_high": max(rep["money"]["lost_repeat_gmv_last12"]["high"], *(v for v in ev["revenue_brl"].values())),
            "sentence": ev["story_sentence"]}


def causal_captions(rc, rp, tg, rep_late, rep_on_time):
    """The review cost, ramp, trend-line and repeat numbers as the story and the memo print them
    (recommendation/analyze.py adds these to the memo facts, so both documents state one value per name)."""
    pct = lambda x: f"{100 * x:.1f}"
    return {
        "c_cost_causal": f"{round(rc['extra'], -1):,.0f}", "c_cost_causal_share": f"{100 * rc['share']:.0f}",
        "c_cost_range_lo": f"{round(rc['range'][0], -1):,.0f}", "c_cost_range_hi": f"{round(rc['range'][1], -1):,.0f}",
        "c_cost_bias_hi": f"{round(rc['seller_bias_reviews'][1], -1):,.0f}",
        "c_ramp_on_time": pct(rp["on_time_share"]), "c_ramp_slope": f"{100 * rp['slope_per_day']:.0f}",
        "c_ramp_plateau": f"{100 * rp['plateau_share']:.0f}", "c_ramp_end_day": str(rp["end_day"]),
        "c_alarm_line": f"{100 * tg['alarm_line']:.2f}", "c_typical_orders": f"{tg['typical_orders']:,}",
        **{f"c_flagged_{i}": m for i, m in enumerate(tg["flagged"], 1)}, "c_flagged_n": str(len(tg["flagged"])),
        "c_goal_line": pct(tg["goal"]), "c_goal_exact": f"{100 * tg['goal']:.2f}", "c_stable_months": str(tg["stable_months"]),
        "c_stretch_line": pct(tg["stretch"]), "c_stretch_exact": f"{100 * tg['stretch']:.2f}",
        "c_whatif_gap": pct(tg["goal"] - tg["stretch"]),
        "c_whatif_rate": f"{100 * tg['late_rate_if_handoffs_ok']:.2f}",
        "c_rep_late_1dp": pct(rep_late), "c_rep_on_time_1dp": pct(rep_on_time),
    }


def captions(f, t):
    """Numbers as the story prints them. story/check_story.py ties each printed number to one of these names
    (or to a recommendation/analyze.py memo fact)."""
    pct = lambda x: f"{100 * x:.1f}"
    seg = lambda table, k: next(r for r in t[table] if r["segment"] == k)
    nne, rest = seg("late_by_region", "North and northeast"), seg("late_by_region", "Rest of Brazil")
    mar, nov = seg("late_by_month", "2018-03"), seg("late_by_month", "2017-11")
    lab = f["label_eval"]
    rc, rp, tg = f["review_cost_causal"], f["ramp"], f["targets"]
    bars = yaml.safe_load(K.TREE.read_text())["thresholds"]
    return {
        "c_late_rate_lo": f"{100 * f['late_rate_ci'][0]:.2f}", "c_late_rate_hi": f"{100 * f['late_rate_ci'][1]:.2f}",
        "c_low_star_all": f"{f['low_star_all']:,}",
        "c_late_sales_window": f"R${f['late_sales_window'] / 1e6:.2f} million",
        "c_nne_lo": pct(nne["ci_low"]), "c_nne_hi": pct(nne["ci_high"]), "c_rest_rate": pct(rest["late_rate"]),
        "c_mar_lo": pct(mar["ci_low"]), "c_mar_hi": pct(mar["ci_high"]),
        "c_nov_lo": pct(nov["ci_low"]), "c_nov_hi": pct(nov["ci_high"]),
        "c_handoff_late_n": f"{seg('late_by_handoff', 'Handed over after ship-by')['late']:,}",
        "c_handoff_late_lo": pct(f["handoff_late_rate_ci"][0]), "c_handoff_late_hi": pct(f["handoff_late_rate_ci"][1]),
        "c_handoff_orders": f"{seg('late_by_handoff', 'Handed over after ship-by')['orders']:,}",
        "c_segment_thr": f"{bars['segment_ratio'] * 100 * f['late_rate']:.1f}",
        "c_last12_n": "12",
        "c_late_sales_last12_m": f"R${f['late_sales_last12'] / 1e6:.2f} million",
        "c_total_sales_last12_m": f"R${f['total_sales_last12'] / 1e6:.1f} million",
        "c_late_sales_last12_share": pct(f["late_sales_last12"] / f["total_sales_last12"]),
        "c_avoidable_exact": f"{f['avoidable_late_upper']:,.0f}",
        "c_money_high_exact": f"R${f['lost_repeat_last12'][2]:,.0f}",
        "c_rep_raw": f"{f['repeat_raw_pts']:.2f}", "c_rep_raw_lo": f"{f['repeat_raw_pts_ci'][0]:.2f}",
        "c_rule_negatives_n": str(sum(e["fp"] + e["tn"] for e in lab.values())),
        **causal_captions(rc, rp, tg, f["repeat"]["late"], f["repeat"]["on_time"]),
        "c_handoff_ratio": f"{f['handoff_late_rate'] / f['handoff_ok_rate']:.1f}",
        "c_comment_pct": pct(f["comment_delay_share"]),
        "c_comment_lo": pct(f["comment_delay_share_ci"][0]), "c_comment_hi": pct(f["comment_delay_share_ci"][1]),
        "c_comments_n": f"{f['comments_n']:,}",
        "c_rule_labelled_n": str(sum(e["n"] for e in lab.values())), "c_rule_holdout_n": str(lab["holdout"]["n"]),
        "c_rule_false_matches": str(sum(e["fp"] for e in lab.values())),
        "c_rule_holdout_missed": f"{100 * (1 - lab['holdout']['recall']):.0f}",
        "c_survey_lo": pct(f["survey_before_share_ci"][0]), "c_survey_hi": pct(f["survey_before_share_ci"][1]),
    }


def render(tables, facts):
    files = {}
    for name, rows in tables.items():
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(rows)
        files[f"{name}.csv"] = buf.getvalue()
    files["facts.json"] = json.dumps(facts, indent=1) + "\n"
    return files


def main():
    files = render(*build())
    if "--check" in sys.argv:
        stale = [f for f, t in files.items() if not (OUT / f).exists() or (OUT / f).read_text() != t]
        print(f"{'PASS' if not stale else 'FAIL'}  committed story/data matches the warehouse" + (f" (stale: {stale})" if stale else ""))
        sys.exit(1 if stale else 0)
    OUT.mkdir(exist_ok=True)
    for f, t in files.items():
        (OUT / f).write_text(t)
    print(f"wrote {len(files)} files to story/data")


if __name__ == "__main__":
    main()
