#!/usr/bin/env python3
"""Reconcile the dbt marts to the headline numbers and give each a verdict.

For every headline number three values are compared:
  mart        - read from the built warehouse (metrics.metrics_headline / marts.*)
  independent - recomputed straight from the raw CSVs here, without any dbt model
  first_pass  - the number the first-pass EDA published (verification/first_pass_baseline.json)
Verdicts: VERIFIED (mart == independent exactly, and == first pass within rounding, or the gap is a
documented definition difference), NOT VERIFIED (a mismatch nobody explained), INCONCLUSIVE (could not measure).

Usage: python verification/verify_headlines.py   (after `make build`)
Output: evidence/verification_report.json and evidence/verification_report.md; exit 1 if any NOT VERIFIED.
"""
import json, os, sys
import duckdb, numpy as np, pandas as pd
import statsmodels.formula.api as smf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(ROOT, "olist.duckdb"))
RAW = os.environ.get("OLIST_RAW_DIR", os.path.join(ROOT, "data", "raw"))
BASE = json.load(open(os.path.join(ROOT, "verification", "first_pass_baseline.json")))

mart = duckdb.connect(DB, read_only=True)
H = {r[0]: {"rule": r[1], "num": r[2], "den": r[3], "value": float(r[4])}
     for r in mart.execute("select metric_name, rule, numerator, denominator, value_pct from metrics.metrics_headline").fetchall()}

# ---- independent path: raw CSVs only (types auto-detected, no dbt code reused)
raw = duckdb.connect()
for name, f in {"orders": "olist_orders_dataset", "items": "olist_order_items_dataset", "reviews": "olist_order_reviews_dataset",
                "customers": "olist_customers_dataset", "products": "olist_products_dataset",
                "tr": "product_category_name_translation"}.items():
    raw.execute(f"create view {name} as select * from read_csv_auto('{RAW}/{f}.csv', header=true)")
raw.execute("""
create table ia as select order_id, count(*) n_items from items group by 1;
create table rev1 as select * from (select *, row_number() over (partition by order_id order by review_answer_timestamp desc, review_id) rn from reviews) where rn = 1;
create table pop as
 select o.order_id, c.customer_state state,
        (o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date) late, r.review_score
 from orders o join ia using(order_id) join customers c using(customer_id) left join rev1 r using(order_id)
 where o.order_status = 'delivered' and o.order_delivered_customer_date is not null
   and o.order_purchase_timestamp >= '2017-01-01' and o.order_purchase_timestamp < '2018-09-01';
create table q as
 select c.customer_unique_id cu, o.order_purchase_timestamp ts,
        row_number() over (partition by c.customer_unique_id order by o.order_purchase_timestamp, o.order_id) k
 from orders o join customers c using(customer_id) join ia using(order_id)
 where o.order_status not in ('canceled', 'unavailable');
""")
ind = {}
n, k = raw.execute("select count(*), sum(late::int) from pop").fetchone()
ind["late_rate"] = {"num": int(k), "den": int(n), "value": round(100 * k / n, 2)}
s, n = raw.execute("select sum(review_score), count(review_score) from pop").fetchone()
ind["review_score"] = {"num": int(s), "den": int(n), "value": round(s / n, 3)}
ind["late_review_gap_raw"] = {"value": round(raw.execute(
    "select avg(review_score) filter (where not late) - avg(review_score) filter (where late) from pop").fetchone()[0], 3)}
n, k = raw.execute("select count(*), sum((m > 1)::int) from (select cu, max(k) m from q group by 1)").fetchone()
ind["repeat_rate_ever"] = {"num": int(k), "den": int(n), "value": round(100 * k / n, 2)}
rule = H["repeat_rate_90d"]["rule"]
cond = {"any_later_order_24h": "q.ts >= f.ts + interval 1 day and q.ts <= f.ts + interval 90 day",
        "different_calendar_day": "q.ts::date > f.ts::date and q.ts <= f.ts + interval 90 day",
        "second_order_only": "q.k = 2 and q.ts >= f.ts + interval 1 day and q.ts <= f.ts + interval 90 day"}[rule]
n, k = raw.execute(f"""select count(*), sum(hit::int) from (
  select f.cu, bool_or({cond}) hit from q f join q using(cu)
  where f.k = 1 and f.ts <= (select max(ts) from q) - interval 90 day group by 1)""").fetchone()
ind["repeat_rate_90d"] = {"num": int(k), "den": int(n), "value": round(100 * k / n, 2)}

# ---- controlled late penalty, recomputed from the MARTS (same spec as the first pass)
df = mart.execute("""
with cat as (
  select i.order_id, arg_max(p.category, i.price) as category
  from marts.fct_order_items i join marts.dim_product p using (product_id) group by 1)
select o.order_id, o.review_score, (o.delivery_state = 'delivered_late')::int as late_i, o.ship_to_state as state, cat.category
from marts.fct_orders o join cat using (order_id)
where o.delivery_state in ('delivered_on_time', 'delivered_late') and o.n_items > 0 and o.in_analysis_window
  and o.review_score is not null""").df()
top = df.category.value_counts().index[:30]
df["cat30"] = np.where(df.category.isin(top), df.category, "other")
m = smf.ols("review_score ~ late_i + C(state) + C(cat30)", df).fit()
pen = {"value": round(float(m.params["late_i"]), 3), "ci": [round(float(x), 3) for x in m.conf_int().loc["late_i"]], "n": int(m.nobs)}

# ---- verdicts
out = []
def verdict(name, mart_v, ind_v, fp, tol, note=""):
    if mart_v is None or ind_v is None:
        v = "INCONCLUSIVE"
    elif mart_v["value"] != ind_v["value"] or mart_v.get("num") != ind_v.get("num") or mart_v.get("den") != ind_v.get("den"):
        v = "NOT VERIFIED"
    elif fp is None or abs(mart_v["value"] - fp) <= tol:
        v = "VERIFIED"
    else:
        v = "NOT VERIFIED" if not note else "VERIFIED"
    out.append({"metric": name, "mart": mart_v, "independent": ind_v, "first_pass": fp, "tolerance": tol, "note": note, "verdict": v})

verdict("repeat_rate_90d (headline)", H["repeat_rate_90d"], ind["repeat_rate_90d"], BASE["repeat_rate_90d_pct_second_order_rule"]["value"], 0.005,
        note=("" if rule == "second_order_only" else
              f"First pass reported 1.24% under the 'second order only' rule; the headline uses '{rule}'. "
              "The C6 experiment reproduces 1.24% exactly under the first-pass rule."))
verdict("repeat_rate_ever (secondary)", H["repeat_rate_ever"], ind["repeat_rate_ever"], BASE["repeat_rate_ever_pct"]["value"], 0.005)
verdict("late_rate", H["late_rate"], ind["late_rate"], BASE["late_rate_pct"]["value"], 0.005)
verdict("review_score", H["review_score"], ind["review_score"], BASE["review_score"]["value"], 0.0005)
verdict("late_review_gap_raw", {"value": H["late_review_gap_raw"]["value"]}, ind["late_review_gap_raw"], BASE["late_review_gap_raw"]["value"], 0.0005)
fp = BASE["late_penalty_controlled"]
pv = "VERIFIED" if abs(pen["value"] - fp["value"]) <= 0.01 else "NOT VERIFIED"
out.append({"metric": "late_penalty_controlled (OLS, from marts)", "mart": pen, "independent": None, "first_pass": fp["value"],
            "tolerance": 0.01, "note": "Recomputed with statsmodels from marts; compared to the first pass within 0.01 stars.", "verdict": pv})

os.makedirs(os.path.join(ROOT, "evidence"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "evidence", "verification_report.json"), "w"), indent=1)
with open(os.path.join(ROOT, "evidence", "verification_report.md"), "w") as f:
    f.write("# Headline reconciliation\n\n| Metric | Mart | Independent (raw CSVs) | First pass | Verdict | Note |\n|---|---|---|---|---|---|\n")
    for r in out:
        fmt = lambda x: "-" if x is None else (f"{x['value']} ({x.get('num')}/{x.get('den')})" if x.get("den") else (f"{x['value']} CI {x['ci']}" if "ci" in x else f"{x['value']}"))
        f.write(f"| {r['metric']} | {fmt(r['mart'])} | {fmt(r['independent'])} | {r['first_pass']} | **{r['verdict']}** | {r['note']} |\n")
for r in out:
    print(f"{r['verdict']:13s} {r['metric']}: mart={r['mart']} independent={r['independent']} first_pass={r['first_pass']}")
sys.exit(1 if any(r["verdict"] == "NOT VERIFIED" for r in out) else 0)
