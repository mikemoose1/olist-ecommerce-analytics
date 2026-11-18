#!/usr/bin/env python3
"""What late delivery costs Olist: stars, repeat purchases, money; where late orders cluster.

Every number in recommendation/MEMO.md comes from this script. It writes
evidence/recommendation_report.json and .md, then checks that every number printed in MEMO.md
is one this run produced (exit 1 if not). Plan and predictions: recommendation/PLAN.md.
Definitions come from ontology/ontology.yml: late-rate population (C1), chosen review (C4),
repeat_rate_90d (C6), person = customer_unique_id.
Usage: python recommendation/analyze.py   (after `make build`; OLIST_DB_PATH picks the warehouse)
"""
import json, os, re, sys
import duckdb, numpy as np, pandas as pd
import statsmodels.formula.api as smf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(ROOT, "olist.duckdb"))
HOLDOUT_START = "2018-05-01"          # fixed in PLAN.md before measuring
WINDOW_MONTHS = 20                    # 2017-01..2018-08 (D6)
LAST12_FROM = "2017-09-01"            # the last 12 months of the window, for figures stated per year
BOOT, SEED = 1000, 20261117
CELL = ["ship_to_state", "cat30", "freight_q", "month"]

# ---------------------------------------------------------------- data: one row per judged order
con = duckdb.connect(DB, read_only=True)
orders = con.execute("""
  with items as (
    select order_id, arg_max(p.category, i.price) as category, sum(i.freight_value) as freight,
           any_value(i.seller_id) as seller_id
    from marts.fct_order_items i join marts.dim_product p using (product_id) group by 1)
  select l.order_id, o.customer_unique_id, o.purchase_date, strftime(o.purchase_date, '%Y-%m') as month,
         o.ship_to_state, s.state as seller_state, it.seller_id, it.category, cast(it.freight as double) as freight,
         cast(o.amount_paid as double) as amount_paid, l.review_score, l.is_late::int as late,
         o.days_past_promise, o.promised_days, l.review_before_delivery as survey_before_delivery, o.customer_qualifying_order_seq as seq,
         case when o.delivered_to_carrier_at is null then null
              else (o.delivered_to_carrier_at > o.last_shipping_limit_at)::int end as seller_handoff_late
  from metrics.metric_late_rate_orders l
  join marts.fct_orders o using (order_id)
  join items it using (order_id)
  join marts.dim_seller s on s.seller_id = it.seller_id
  order by l.order_id""").df()   # fixed row order: quintile ties and bootstrap weights depend on it
people90 = con.execute("select customer_unique_id, repeated::int as repeated90 from metrics.metric_repeat_rate_90d_people").df()
ever = con.execute("select customer_unique_id, (n_qualifying_orders > 1)::int as repeated_ever from marts.dim_customer").df()
# GMV a returning person spends in their 90-day return window (the C6 window: 24h..90d after the first order)
repeat_gmv = con.execute("""
  with q as (select customer_unique_id, purchased_at, amount_paid from marts.fct_orders where is_qualifying_order),
       f as (select customer_unique_id, first_order_at from metrics.metric_repeat_rate_90d_people where repeated)
  select avg(spend), count(*) from (
    select f.customer_unique_id, sum(q.amount_paid) as spend from f join q using (customer_unique_id)
    where q.purchased_at >= f.first_order_at + interval 1 day and q.purchased_at <= f.first_order_at + interval 90 day
    group by 1)""").fetchone()
headline = {r[0]: (r[1], r[2], float(r[3])) for r in con.execute(
    "select metric_name, numerator, denominator, value_pct from metrics.metrics_headline").fetchall()}

top30 = orders.category.value_counts().index[:30]
orders["cat30"] = np.where(orders.category.isin(top30), orders.category, "other")
orders["freight_q"] = pd.qcut(orders.freight.rank(method="first"), 5, labels=False).astype(int)
orders["split"] = np.where(orders.purchase_date.astype(str) >= HOLDOUT_START, "holdout", "discovery")
orders["low_star"] = (orders.review_score <= 2).astype(float).where(orders.review_score.notna())
firsts = orders[orders.seq == 1].merge(people90, on="customer_unique_id", how="inner").merge(ever, on="customer_unique_id")
assert len(orders) == headline["late_rate"][1] and int(orders.late.sum()) == headline["late_rate"][0], "population drifted from late_rate"
assert int(firsts.repeated90.sum()) <= headline["repeat_rate_90d"][0]

# ---------------------------------------------------------------- estimators
def matched(df, y):
    """Exact matching on CELL; effect on the late orders = late-weighted mean of within-cell (late - on time).
    Interval: 1,000 Poisson-bootstrap resamples (each row gets a Poisson(1) weight), fixed seed."""
    d = df[df[y].notna()]
    code = d.groupby(CELL, sort=False).ngroup().to_numpy()
    k, t, v = code.max() + 1, d.late.to_numpy(), d[y].to_numpy(float)
    def est(w):
        nl = np.bincount(code, w * t, k); no = np.bincount(code, w * (1 - t), k)
        sl = np.bincount(code, w * t * v, k); so = np.bincount(code, w * (1 - t) * v, k)
        ok = (nl > 0) & (no > 0)
        return np.sum(nl[ok] * (sl[ok] / nl[ok] - so[ok] / no[ok])) / nl[ok].sum(), nl[ok].sum(), ok
    point, n_late_matched, ok = est(np.ones(len(d)))
    rng = np.random.default_rng(SEED)
    boots = np.array([est(rng.poisson(1.0, len(d)).astype(float))[0] for _ in range(BOOT)])
    return {"effect": float(point), "ci": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "late_matched": int(n_late_matched), "late_total": int(t.sum()), "cells": int(ok.sum())}

def regression(df, y):
    d = df[df[y].notna()]
    m = smf.ols(f"{y} ~ late + C(ship_to_state) + C(cat30) + C(freight_q) + C(month)", d).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d.seller_id)[0]})
    lo, hi = m.conf_int().loc["late"]
    return {"effect": float(m.params["late"]), "ci": [float(lo), float(hi)], "n": int(m.nobs)}

def raw(df, y):
    d = df[df[y].notna()]
    a, b = d[d.late == 1][y], d[d.late == 0][y]
    se = np.sqrt(a.var() / len(a) + b.var() / len(b))
    diff = a.mean() - b.mean()
    return {"late": float(a.mean()), "on_time": float(b.mean()), "n_late": len(a), "n_on_time": len(b),
            "effect": float(diff), "ci": [float(diff - 1.96 * se), float(diff + 1.96 * se)]}

def effects(df, y):
    return {"raw": raw(df, y), "matched": matched(df, y), "regression": regression(df, y)}

R = {"population": {"orders": len(orders), "late": int(orders.late.sum()), "reviewed": int(orders.review_score.notna().sum()),
                    "eligible_people": len(firsts), "eligible_late_first": int(firsts.late.sum())}}
disc, hold = orders[orders.split == "discovery"], orders[orders.split == "holdout"]
fdisc, fhold = firsts[firsts.split == "discovery"], firsts[firsts.split == "holdout"]

R["stars"] = {"all": effects(orders, "review_score"), "discovery": effects(disc, "review_score"), "holdout": effects(hold, "review_score")}
R["low_star"] = {"all": effects(orders, "low_star")}
R["repeat90"] = {"all": effects(firsts, "repeated90"), "discovery": effects(fdisc, "repeated90"), "holdout": effects(fhold, "repeated90")}
R["repeat_ever"] = {"all": effects(firsts, "repeated_ever")}

# stars by days late (raw means, the dose response)
bins = [-1e9, 0, 1, 3, 7, 14, 1e9]; labels = ["on time", "1 day", "2-3 days", "4-7 days", "8-14 days", "15+ days"]
rv = orders[orders.review_score.notna()].copy()
rv["days_late_bucket"] = pd.cut(rv.days_past_promise.clip(lower=0).where(rv.late == 1, 0), bins, labels=labels)
R["stars_by_days_late"] = [{"bucket": b, "orders": int(len(g)), "avg_stars": float(g.review_score.mean()),
                            "low_star_pct": float(100 * g.low_star.mean()),
                            "survey_before_pct": float(100 * g.survey_before_delivery.astype(float).mean())}
                           for b, g in rv.groupby("days_late_bucket", observed=True)]

# ---------------------------------------------------------------- money
late_first_all = int(orders[(orders.seq == 1) & (orders.late == 1)].shape[0])
per_year = late_first_all * 12 / WINDOW_MONTHS
avg_repeat_spend = float(repeat_gmv[0])
m90 = R["repeat90"]["all"]["matched"]
drop = {"low": max(0.0, -m90["ci"][1]), "mid": max(0.0, -m90["effect"]), "high": max(0.0, -m90["ci"][0])}
R["money"] = {"late_first_orders_window": late_first_all, "late_first_orders_per_year": per_year,
              "avg_90d_repeat_spend": avg_repeat_spend, "repeaters_for_spend": int(repeat_gmv[1]),
              "repeat_drop_pts": {k: 100 * v for k, v in drop.items()},
              "lost_repeat_gmv_per_year": {k: per_year * v * avg_repeat_spend for k, v in drop.items()},
              "repeat_ci_includes_zero": bool(m90["ci"][0] <= 0 <= m90["ci"][1]),
              "late_order_gmv_window": float(orders[orders.late == 1].amount_paid.sum()),
              "late_order_gmv_per_year": float(orders[orders.late == 1].amount_paid.sum() * 12 / WINDOW_MONTHS),
              "total_gmv_window": float(orders.amount_paid.sum())}
# Per-year money on the last 12 months, not the 20-month count times 12/20: sales grew, so the window average understates a year.
recent = orders.purchase_date.astype(str) >= LAST12_FROM
late_first_12 = int(orders[(orders.seq == 1) & (orders.late == 1) & recent].shape[0])
R["money"].update({"late_first_orders_last12": late_first_12,
                   "lost_repeat_gmv_last12": {k: late_first_12 * v * avg_repeat_spend for k, v in drop.items()},
                   "late_order_gmv_last12": float(orders[(orders.late == 1) & recent].amount_paid.sum()),
                   "total_gmv_last12": float(orders[recent].amount_paid.sum())})
ls = R["low_star"]["all"]["matched"]
n_late_rev = int(orders[(orders.late == 1) & orders.review_score.notna()].shape[0])
n_low_all = int(orders.low_star.sum())
R["money"]["low_star_reviews"] = {
    "late_reviewed": n_late_rev, "all_low_star": n_low_all,
    "excess_from_lateness": {"low": n_late_rev * ls["ci"][0], "mid": n_late_rev * ls["effect"], "high": n_late_rev * ls["ci"][1]},
    "share_of_all_low_star_pct": {k: 100 * n_late_rev * x / n_low_all for k, x in zip(["low", "mid", "high"], [ls["ci"][0], ls["effect"], ls["ci"][1]])}}

# ---------------------------------------------------------------- where late orders cluster
def table(df, keys, min_orders):
    g = df.groupby(keys).agg(orders=("late", "size"), late=("late", "sum")).reset_index()
    g = g[g.orders >= min_orders]
    g["late_rate_pct"] = 100 * g.late / g.orders
    g["share_of_late_pct"] = 100 * g.late / df.late.sum()
    return g

def as_rows(g, n, by):
    return json.loads(g.sort_values(by, ascending=False).head(n).to_json(orient="records"))

total_late = int(orders.late.sum())
st = table(orders, ["ship_to_state"], 300)
rt = table(orders, ["seller_state", "ship_to_state"], 300)
R["clusters"] = {"states_by_rate": as_rows(st, 8, "late_rate_pct"), "states_by_late_count": as_rows(st, 5, "late"),
                 "routes_by_rate": as_rows(rt, 8, "late_rate_pct"), "routes_by_late_count": as_rows(rt, 5, "late")}
ne = {"AL", "MA", "SE", "CE", "PI", "BA", "PB", "PE", "RN"}
north_ne = orders.ship_to_state.isin(ne | {"PA", "AM", "RR", "AP", "AC", "RO", "TO"})
R["clusters"]["north_northeast"] = {"orders": int(north_ne.sum()), "late": int(orders[north_ne].late.sum()),
                                    "late_rate_pct": float(100 * orders[north_ne].late.mean()),
                                    "share_of_orders_pct": float(100 * north_ne.mean()),
                                    "share_of_late_pct": float(100 * orders[north_ne].late.sum() / total_late)}
sl = table(orders, ["seller_id"], 20).sort_values("late", ascending=False)
n10 = int(np.ceil(0.10 * len(sl)))
avg_rate = 100 * orders.late.mean()
bad = sl[sl.late_rate_pct >= 2 * avg_rate]
R["clusters"]["sellers"] = {"sellers_20plus_orders": len(sl), "top10pct_sellers": n10,
                            "top10pct_share_of_late_pct": float(100 * sl.head(n10).late.sum() / total_late),
                            "top10pct_share_of_orders_pct": float(100 * sl.head(n10).orders.sum() / len(orders)),
                            "double_rate_sellers": len(bad), "double_rate_share_of_late_pct": float(100 * bad.late.sum() / total_late),
                            "double_rate_share_of_orders_pct": float(100 * bad.orders.sum() / len(orders))}

def who(df):
    k = df[df.seller_handoff_late.notna()]
    late = k[k.late == 1]
    return {"late_orders": int(len(late)), "seller_side": int(late.seller_handoff_late.sum()),
            "seller_side_pct": float(100 * late.seller_handoff_late.mean()),
            "late_rate_if_handoff_late_pct": float(100 * k[k.seller_handoff_late == 1].late.mean()),
            "late_rate_if_handoff_on_time_pct": float(100 * k[k.seller_handoff_late == 0].late.mean()),
            "handoff_late_share_of_orders_pct": float(100 * k.seller_handoff_late.mean())}
R["who_caused"] = {"all": who(orders), "discovery": who(disc), "holdout": who(hold)}

pb = pd.cut(orders.promised_days, [-1, 14, 21, 28, 35, 1e9], labels=["0-14", "15-21", "22-28", "29-35", "36+"])
R["by_promise_days"] = [{"promised_days": str(b), "orders": int(len(g)), "late_rate_pct": float(100 * g.late.mean())}
                        for b, g in orders.groupby(pb, observed=True)]
okt = orders[orders.late == 0].copy()
okt["pb"] = pd.cut(okt.promised_days, [-1, 14, 21, 28, 35, 1e9], labels=["0-14", "15-21", "22-28", "29-35", "36+"])
R["on_time_stars_by_promise_days"] = [{"promised_days": str(b), "orders": int(g.review_score.notna().sum()),
                                       "avg_stars": float(g.review_score.mean())} for b, g in okt.groupby("pb", observed=True)]

def top_states(df, n=5, min_orders=100):
    return list(table(df, ["ship_to_state"], min_orders).sort_values("late_rate_pct", ascending=False).ship_to_state.head(n))
R["holdout_check"] = {"top5_states_discovery": top_states(disc), "top5_states_holdout": top_states(hold),
                      "orders": {"discovery": len(disc), "holdout": len(hold)},
                      "late": {"discovery": int(disc.late.sum()), "holdout": int(hold.late.sum())},
                      "late_rate_pct": {"discovery": float(100 * disc.late.mean()), "holdout": float(100 * hold.late.mean())},
                      "eligible_people": {"discovery": len(fdisc), "holdout": len(fhold)}}
ov = lambda a, b: a[0] <= b[1] and b[0] <= a[1]
for name, blk in [("stars", R["stars"]), ("repeat90", R["repeat90"])]:
    d, h = blk["discovery"]["matched"], blk["holdout"]["matched"]
    R["holdout_check"][name] = {"same_sign": bool(np.sign(d["effect"]) == np.sign(h["effect"])), "intervals_overlap": bool(ov(d["ci"], h["ci"])),
                                "holdout_excludes_zero": bool(not (h["ci"][0] <= 0 <= h["ci"][1]))}


# ---------------------------------------------------------------- added after first run (see PLAN.md addendum): when, and what held out
mo = table(orders, ["month"], 1).sort_values("late", ascending=False)
R["clusters"]["months_by_late_count"] = as_rows(mo, 3, "late")
R["clusters"]["top3_months_share_of_late_pct"] = float(mo.head(3).late.sum() / total_late * 100)
R["clusters"]["top3_months_share_of_orders_pct"] = float(mo.head(3).orders.sum() / len(orders) * 100)
def split_rates(df):
    nne = df.ship_to_state.isin(ne | {"PA", "AM", "RR", "AP", "AC", "RO", "TO"})
    return {"nne_late_rate_pct": float(100 * df[nne].late.mean()), "rest_late_rate_pct": float(100 * df[~nne].late.mean()),
            "rj_late_rate_pct": float(100 * df[df.ship_to_state == "RJ"].late.mean()),
            "sp_to_rj_late_rate_pct": float(100 * df[(df.ship_to_state == "RJ") & (df.seller_state == "SP")].late.mean()),
            "median_days_late": float(df[df.late == 1].days_past_promise.median())}
R["holdout_check"]["rates"] = {"discovery": split_rates(disc), "holdout": split_rates(hold)}
dl = orders[orders.late == 1].days_past_promise
R["late_within_days_pct"] = {"3": float(100 * (dl <= 3).mean()), "7": float(100 * (dl <= 7).mean())}
w = R["who_caused"]["all"]; n_handoff_late = int(orders.seller_handoff_late.fillna(0).sum())
R["who_caused"]["avoidable_upper_bound"] = {"handoff_late_orders": n_handoff_late,
    "late_orders": n_handoff_late * (w["late_rate_if_handoff_late_pct"] - w["late_rate_if_handoff_on_time_pct"]) / 100,
    "share_of_late_pct": n_handoff_late * (w["late_rate_if_handoff_late_pct"] - w["late_rate_if_handoff_on_time_pct"]) / total_late}


# ---------------------------------------------------------------- added by the adversarial review (see PLAN.md addendum)
lr = orders[(orders.late == 1) & orders.review_score.notna()]
R["survey_timing"] = {"late_reviewed": len(lr), "sent_before_delivery_pct": float(100 * lr.survey_before_delivery.astype(float).mean()),
                      "stars_late_sent_before": float(lr[lr.survey_before_delivery == True].review_score.mean()),
                      "stars_late_sent_after": float(lr[lr.survey_before_delivery == False].review_score.mean()),
                      # the two groups differ mainly in how late the parcel was, so compare them within the same lateness
                      "mean_days_late_sent_before": float(lr[lr.survey_before_delivery == True].days_past_promise.mean()),
                      "mean_days_late_sent_after": float(lr[lr.survey_before_delivery == False].days_past_promise.mean())}
near = lr[lr.days_past_promise.between(1, 3)]
R["survey_timing"]["within_1_3_days_late"] = {
    "stars_sent_before": float(near[near.survey_before_delivery == True].review_score.mean()),
    "stars_sent_after": float(near[near.survey_before_delivery == False].review_score.mean())}
# the same gap compared only between orders equally late: at each whole days-late value where both groups exist, after minus
# before, weighted by the orders at that value
by_day = lr.groupby(["days_past_promise", "survey_before_delivery"]).review_score.agg(["mean", "size"]).unstack("survey_before_delivery").dropna()
w_day = by_day["size"][True] + by_day["size"][False]
same = float(((by_day["mean"][False] - by_day["mean"][True]) * w_day).sum() / w_day.sum())
raw_gap = R["survey_timing"]["stars_late_sent_after"] - R["survey_timing"]["stars_late_sent_before"]
R["survey_timing"]["same_days_late"] = {"days": [int(by_day.index.min()), int(by_day.index.max())], "gap": same, "raw_gap": raw_gap,
                                        "share_of_raw_pct": 100 * same / raw_gap}
# the share depends on how the days are weighted: by the after-delivery group, by both, by the before group
gap_day = by_day["mean"][False] - by_day["mean"][True]
shares = {w: float(100 * (gap_day * wt).sum() / wt.sum() / raw_gap) for w, wt in
          (("after_group", by_day["size"][False]), ("both", w_day), ("before_group", by_day["size"][True]))}
R["survey_timing"]["same_days_late"]["share_by_weighting_pct"] = shares
R["survey_timing"]["same_days_late"]["before_lower_every_day"] = bool((gap_day > 0).all())
# thin cells: per day, the smaller of the two groups; the memo says how few orders some days rest on
thin = by_day["size"].min(axis=1)
R["survey_timing"]["same_days_late"]["smaller_group_by_day"] = {int(d): int(n) for d, n in thin.items()}
# the gap is the difference of the two figures as printed, so the memo's 2.38, 3.53 and gap always add up
R["survey_timing"]["within_1_3_days_late"]["gap"] = (round(R["survey_timing"]["within_1_3_days_late"]["stars_sent_after"], 2)
                                                      - round(R["survey_timing"]["within_1_3_days_late"]["stars_sent_before"], 2))
SPIKE = ["2017-11", "2017-12", "2018-01", "2018-02", "2018-03"]   # window chosen after seeing which months were worst (PLAN.md addendum): descriptive, not a tested hypothesis
rj = orders[orders.ship_to_state == "RJ"]; xr = orders[orders.ship_to_state != "RJ"]
R["clusters"]["rj_episode"] = {"months": SPIKE, "rj_spike_pct": float(100 * rj[rj.month.isin(SPIKE)].late.mean()),
                               "rj_other_pct": float(100 * rj[~rj.month.isin(SPIKE)].late.mean()),
                               "rest_spike_pct": float(100 * xr[xr.month.isin(SPIKE)].late.mean()),
                               "rest_other_pct": float(100 * xr[~xr.month.isin(SPIKE)].late.mean())}

# ---------------------------------------------------------------- memo facts: the only numbers MEMO.md may print
THIN_CELL = 10   # a day where either group has fewer orders than this is called thin in the memo (memo_check DESIGN thin_cell)
f1 = lambda x: f"{x:.1f}"; f2 = lambda x: f"{x:.2f}"; n0 = lambda x: f"{x:,.0f}"
def rs(x):  # R$ rounded to the nearest 500: the middle estimate moves by about R$100 under small changes in how matches are built
    return f"R${round(x / 500) * 500:,.0f}"
S, M = R["stars"], R["money"]
facts = {
    "late_rate": f2(100 * R["population"]["late"] / R["population"]["orders"]), "late_orders": n0(R["population"]["late"]),
    "orders": n0(R["population"]["orders"]),
    "stars_raw_late": f2(S["all"]["raw"]["late"]), "stars_raw_on_time": f2(S["all"]["raw"]["on_time"]),
    "stars_matched_rounded": f"{abs(round(S['all']['matched']['effect']))}",
    "stars_matched": f2(S["all"]["matched"]["effect"]), "stars_matched_lo": f2(S["all"]["matched"]["ci"][0]), "stars_matched_hi": f2(S["all"]["matched"]["ci"][1]),
    "stars_reg": f2(S["all"]["regression"]["effect"]), "stars_reg_lo": f2(S["all"]["regression"]["ci"][0]), "stars_reg_hi": f2(S["all"]["regression"]["ci"][1]),
    "stars_hold": f2(S["holdout"]["matched"]["effect"]), "stars_hold_lo": f2(S["holdout"]["matched"]["ci"][0]), "stars_hold_hi": f2(S["holdout"]["matched"]["ci"][1]),
    "stars_disc": f2(S["discovery"]["matched"]["effect"]), "stars_hold_1dp": f1(S["holdout"]["matched"]["effect"]),
    "matched_pct": f1(100 * S["all"]["matched"]["late_matched"] / S["all"]["matched"]["late_total"]),
    "low_star_late_pct": f1(100 * R["low_star"]["all"]["raw"]["late"]), "low_star_on_time_pct": f1(100 * R["low_star"]["all"]["raw"]["on_time"]),
    "low_star_excess_mid": n0(round(M["low_star_reviews"]["excess_from_lateness"]["mid"], -2)),
    "low_star_share_lo": f1(M["low_star_reviews"]["share_of_all_low_star_pct"]["low"]),
    "low_star_share_mid": f1(M["low_star_reviews"]["share_of_all_low_star_pct"]["mid"]),
    "low_star_share_hi": f1(M["low_star_reviews"]["share_of_all_low_star_pct"]["high"]),
    "rep_on_time": f2(100 * R["repeat90"]["all"]["raw"]["on_time"]), "rep_late": f2(100 * R["repeat90"]["all"]["raw"]["late"]),
    "rep_matched": f2(100 * m90["effect"]), "rep_matched_lo": f2(100 * m90["ci"][0]), "rep_matched_hi": f2(100 * m90["ci"][1]),
    "rep_reg": f2(100 * R["repeat90"]["all"]["regression"]["effect"]),
    "rep_reg_lo": f2(100 * R["repeat90"]["all"]["regression"]["ci"][0]), "rep_reg_hi": f2(100 * R["repeat90"]["all"]["regression"]["ci"][1]),
    "rep_eligible": n0(R["population"]["eligible_people"]), "rep_eligible_late": n0(R["population"]["eligible_late_first"]),
    "repever_matched": f2(100 * R["repeat_ever"]["all"]["matched"]["effect"]),
    "repever_lo": f2(100 * R["repeat_ever"]["all"]["matched"]["ci"][0]), "repever_hi": f2(100 * R["repeat_ever"]["all"]["matched"]["ci"][1]),
    "last12_n": str(len(pd.period_range(LAST12_FROM, "2018-08", freq="M"))),
    "late_first_last12": n0(M["late_first_orders_last12"]), "repeat_spend": f"R${M['avg_90d_repeat_spend']:,.0f}",
    "money12_low": rs(M["lost_repeat_gmv_last12"]["low"]), "money12_mid": rs(M["lost_repeat_gmv_last12"]["mid"]),
    "money12_high": rs(M["lost_repeat_gmv_last12"]["high"]),
    "late_gmv_last12": f"R${M['late_order_gmv_last12'] / 1e6:.1f} million",
    "late_gmv_last12_pct": f1(100 * M["late_order_gmv_last12"] / M["total_gmv_last12"]),
    "seller_side_pct": f1(R["who_caused"]["all"]["seller_side_pct"]), "seller_side_hold_pct": f1(R["who_caused"]["holdout"]["seller_side_pct"]),
    "late_if_handoff_late": f1(R["who_caused"]["all"]["late_rate_if_handoff_late_pct"]),
    "late_if_handoff_ok": f1(R["who_caused"]["all"]["late_rate_if_handoff_on_time_pct"]),
    "handoff_late_share": f1(R["who_caused"]["all"]["handoff_late_share_of_orders_pct"]),
    "nne_share_orders": f1(R["clusters"]["north_northeast"]["share_of_orders_pct"]), "nne_share_late": f1(R["clusters"]["north_northeast"]["share_of_late_pct"]),
    "nne_rate": f1(R["clusters"]["north_northeast"]["late_rate_pct"]),
    "top10_share_late": f1(R["clusters"]["sellers"]["top10pct_share_of_late_pct"]), "top10_share_orders": f1(R["clusters"]["sellers"]["top10pct_share_of_orders_pct"]),
    "top10_n": n0(R["clusters"]["sellers"]["top10pct_sellers"]),
    "dbl_n": n0(R["clusters"]["sellers"]["double_rate_sellers"]), "dbl_share_late": f1(R["clusters"]["sellers"]["double_rate_share_of_late_pct"]),
    "dbl_share_orders": f1(R["clusters"]["sellers"]["double_rate_share_of_orders_pct"]),
}
H = R["holdout_check"]["rates"]
facts.update({
    "top3_months_late": f1(R["clusters"]["top3_months_share_of_late_pct"]), "top3_months_orders": f1(R["clusters"]["top3_months_share_of_orders_pct"]),
    "rj_rate": f1(next(r for r in R["clusters"]["states_by_late_count"] if r["ship_to_state"] == "RJ")["late_rate_pct"]),
    "rj_share_late": f1(next(r for r in R["clusters"]["states_by_late_count"] if r["ship_to_state"] == "RJ")["share_of_late_pct"]),
    "rj_disc": f1(H["discovery"]["rj_late_rate_pct"]), "rj_hold": f1(H["holdout"]["rj_late_rate_pct"]),
    "nne_disc": f1(H["discovery"]["nne_late_rate_pct"]), "nne_hold": f1(H["holdout"]["nne_late_rate_pct"]),
    "rest_disc": f1(H["discovery"]["rest_late_rate_pct"]), "rest_hold": f1(H["holdout"]["rest_late_rate_pct"]),
    "med_late_disc": n0(H["discovery"]["median_days_late"]), "med_late_hold": n0(H["holdout"]["median_days_late"]),
    "handoff_disc_late": f1(R["who_caused"]["discovery"]["late_rate_if_handoff_late_pct"]), "handoff_disc_ok": f1(R["who_caused"]["discovery"]["late_rate_if_handoff_on_time_pct"]),
    "handoff_hold_late": f1(R["who_caused"]["holdout"]["late_rate_if_handoff_late_pct"]), "handoff_hold_ok": f1(R["who_caused"]["holdout"]["late_rate_if_handoff_on_time_pct"]),
    "avoidable_late": n0(round(R["who_caused"]["avoidable_upper_bound"]["late_orders"], -2)),
    "avoidable_share": f1(R["who_caused"]["avoidable_upper_bound"]["share_of_late_pct"]),
    "late_within_3": f1(R["late_within_days_pct"]["3"]), "late_within_7": f1(R["late_within_days_pct"]["7"]),
    "promise_short_stars": f2(R["on_time_stars_by_promise_days"][0]["avg_stars"]), "promise_long_stars": f2(R["on_time_stars_by_promise_days"][-1]["avg_stars"]),
})
ST, RJE = R["survey_timing"], R["clusters"]["rj_episode"]
facts.update({"survey_before_pct": f1(ST["sent_before_delivery_pct"]), "stars_sent_before": f2(ST["stars_late_sent_before"]),
              "stars_sent_after": f2(ST["stars_late_sent_after"]),
              "days_late_sent_before": f1(ST["mean_days_late_sent_before"]), "days_late_sent_after": f1(ST["mean_days_late_sent_after"]),
              "survey_near_before": f2(ST["within_1_3_days_late"]["stars_sent_before"]),
              "survey_near_after": f2(ST["within_1_3_days_late"]["stars_sent_after"]),
              "survey_near_gap": f2(ST["within_1_3_days_late"]["gap"]),
              "survey_gap_raw": f2(ST["same_days_late"]["raw_gap"]), "survey_gap_same_days": f2(ST["same_days_late"]["gap"]),
              "survey_gap_same_days_pct": f"{round(ST['same_days_late']['share_of_raw_pct'] / 5) * 5:.0f}",   # "about 75%"
              "survey_gap_share_lo": f"{min(ST['same_days_late']['share_by_weighting_pct'].values()):.0f}",
              "survey_gap_share_hi": f"{max(ST['same_days_late']['share_by_weighting_pct'].values()):.0f}",
              "matched_pct_all_late": f1(100 * S["all"]["matched"]["late_matched"] / total_late),
              "survey_thin_min_n": str(min(ST["same_days_late"]["smaller_group_by_day"].values())),
              "survey_thin_days": str(sum(n < THIN_CELL for n in ST["same_days_late"]["smaller_group_by_day"].values())),
              "survey_days_n": str(len(ST["same_days_late"]["smaller_group_by_day"])),
              "late_unreviewed_n": n0(total_late - S["all"]["matched"]["late_total"]),
              "survey_same_days_min": str(ST["same_days_late"]["days"][0]), "survey_same_days_max": str(ST["same_days_late"]["days"][1]),
              "low_star_matched_n": n0(R["low_star"]["all"]["matched"]["late_matched"]),
              "low_star_matched_pct": f1(100 * R["low_star"]["all"]["matched"]["late_matched"] / R["low_star"]["all"]["matched"]["late_total"]),
              "late_reviewed_n": n0(R["money"]["low_star_reviews"]["late_reviewed"]),
              "rj_spike": f1(RJE["rj_spike_pct"]), "rj_other": f1(RJE["rj_other_pct"]),
              "rest_spike": f1(RJE["rest_spike_pct"]), "rest_other": f1(RJE["rest_other_pct"]),
              # months the memo names
              "window_first_month": str(orders.month.min()), "window_last_month": str(orders.month.max()),
              "holdout_first_month": HOLDOUT_START[:7], "holdout_last_month": str(orders.month.max()),
              "spike_first_month": SPIKE[0], "spike_last_month": SPIKE[-1]})
for r in R["clusters"]["months_by_late_count"]:
    facts[f"month_{r['month']}"] = f1(r["late_rate_pct"])
for r in R["stars_by_days_late"]:
    facts[f"days_{r['bucket']}"] = f2(r["avg_stars"])
    facts[f"before_pct_{r['bucket']}"] = f1(r["survey_before_pct"])
for r in R["clusters"]["states_by_rate"][:5]:
    facts[f"state_{r['ship_to_state']}"] = f1(r["late_rate_pct"])
R["memo_facts"] = facts

out = os.path.join(ROOT, "evidence"); os.makedirs(out, exist_ok=True)
def rounded(x, nd=6):
    """Last-digit float noise differs between machines (BLAS, numpy). Six decimals keeps every reported figure and makes reruns byte-identical."""
    if isinstance(x, dict):
        return {k: rounded(v, nd) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rounded(v, nd) for v in x]
    if isinstance(x, (np.floating, float)):
        return round(float(x), nd)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x
json.dump(rounded(R), open(os.path.join(out, "recommendation_report.json"), "w"), indent=1, default=float)
with open(os.path.join(out, "recommendation_report.md"), "w") as f:
    f.write("# Late-delivery cost: computed numbers\n\nGenerated by `recommendation/analyze.py`. Raw values in `recommendation_report.json`.\n\n")
    f.write("| Fact | Value |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in facts.items()))

# ---------------------------------------------------------------- memo check: every number in MEMO.md is tied to the fact it states (see memo_check.py)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from memo_check import check_memo
memo_path = os.path.join(ROOT, "recommendation", "MEMO.md")
problems = []
if os.path.exists(memo_path):
    n_numbers, problems = check_memo(open(memo_path).read(), facts)
    print(f"memo check: {n_numbers} numbers each tied to a named fact or design constant, {len(problems)} problems" + (f": {problems}" if problems else ""))
bad_tokens = problems
for k, v in facts.items():
    print(f"{k:24s} {v}")
sys.exit(1 if bad_tokens else 0)
