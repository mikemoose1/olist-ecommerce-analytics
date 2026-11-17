#!/usr/bin/env python3
"""Settle open modeling choices C1-C6 by experiment.

Var-driven choices (C1, C2, C4, C6) are run by rebuilding the affected models on a COPY of the
warehouse with `dbt run --vars`, then measuring the same outputs for every arm. C3 builds a patched
copy of the project with incremental marts. C5 compares two address rules already in the marts.
Usage: python experiments/run_experiments.py   (after `make build`)
Output: experiments/results.json and experiments/RESULTS.md
"""
import json, os, shutil, subprocess, sys, tempfile, time
import duckdb, numpy as np, pandas as pd
import statsmodels.formula.api as smf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(ROOT, "olist.duckdb"))
DBT = os.path.join(os.path.dirname(sys.executable), "dbt")
WORK = tempfile.mkdtemp(prefix="olist-exp-")

def dbt(args, db, cwd=ROOT):
    env = dict(os.environ, OLIST_DB_PATH=db, DBT_PROFILES_DIR=cwd)
    t0 = time.time()
    p = subprocess.run([DBT] + args + ["--target-path", os.path.join(WORK, "target"), "--quiet"], cwd=cwd, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"dbt {' '.join(args)} failed:\n{p.stdout}\n{p.stderr}")
    return time.time() - t0

def arm_db(select, vars_):
    db = os.path.join(WORK, "arm.duckdb"); shutil.copy(DB, db)
    dbt(["run", "--select", select, "--vars", json.dumps(vars_)], db)
    return db

def penalty(con, extra_where=""):
    df = con.execute(f"""
      with cat as (select i.order_id, arg_max(p.category, i.price) category
                   from marts.fct_order_items i join marts.dim_product p using (product_id) group by 1)
      select o.review_score, o.is_late::int late_i, o.ship_to_state state, cat.category
      from metrics.metric_late_rate_orders o join cat using (order_id)
      where o.review_score is not null {extra_where}""").df()
    top = df.category.value_counts().index[:30]
    df["cat30"] = np.where(df.category.isin(top), df.category, "other")
    m = smf.ols("review_score ~ late_i + C(state) + C(cat30)", df).fit()
    return {"coef": round(float(m.params["late_i"]), 3), "ci": [round(float(x), 3) for x in m.conf_int().loc["late_i"]], "n": int(m.nobs)}

def headline(con):
    return {r[0]: {"num": r[2], "den": r[3], "value": float(r[4])} for r in
            con.execute("select metric_name, rule, numerator, denominator, value_pct from metrics.metrics_headline").fetchall()}

R = {}
# ---------------- C1 multi-seller late marking
R["C1"] = {}
for arm in ["trust_order_date", "exclude_multi_seller", "last_parcel_proxy"]:
    db = arm_db("metric_late_rate_orders+", {"multi_seller_late_rule": arm})
    con = duckdb.connect(db, read_only=True)
    h = headline(con)
    ms = con.execute("""select count(*), round(100*avg(is_late::int),2), round(avg(review_score),3)
                        from metrics.metric_late_rate_orders where delivery_evidence='order_level_multi_parcel'""").fetchone()
    ss = con.execute("""select round(100*avg(is_late::int),2), round(avg(review_score),3)
                        from metrics.metric_late_rate_orders where delivery_evidence='order_level_single_parcel'""").fetchone()
    R["C1"][arm] = {"late_rate": h["late_rate"], "review_gap_raw": h["late_review_gap_raw"]["value"], "late_penalty": penalty(con),
                    "multi_seller": {"orders": ms[0], "late_pct": ms[1], "avg_review": ms[2]},
                    "single_seller": {"late_pct": ss[0], "avg_review": ss[1]}}
    if arm == "trust_order_date":
        # within multi-seller orders: does the order-level date still separate good from bad reviews?
        R["C1"]["multi_seller_review_by_late_trust"] = con.execute("""select is_late, count(*), round(avg(review_score),3)
          from metrics.metric_late_rate_orders where delivery_evidence='order_level_multi_parcel' and review_score is not null group by 1 order by 1""").fetchall()
        R["C1"]["on_time_low_score_pct_by_evidence"] = con.execute("""select delivery_evidence, round(100*avg((review_score<=2)::int),2)
          from metrics.metric_late_rate_orders where review_score is not null and not is_late group by 1 order by 1""").fetchall()
    con.close()

# ---------------- C2 reviews dated before delivery
R["C2"] = {}
for arm in ["timestamp", "calendar_day"]:
    db = arm_db("int_order_review+", {"review_before_delivery_compare": arm})
    con = duckdb.connect(db, read_only=True)
    flagged = con.execute("""select count(*) filter (where r.review_before_delivery), count(r.review_before_delivery),
         round(avg(r.review_score) filter (where r.review_before_delivery),3), round(avg(r.review_score) filter (where not r.review_before_delivery),3)
         from marts.fct_reviews r join marts.fct_orders o using(order_id) where r.is_chosen_for_order and o.order_status='delivered' and o.delivered_to_customer_at is not null""").fetchone()
    same_day = con.execute("""select count(*) from marts.fct_reviews r join marts.fct_orders o using(order_id)
         where r.is_chosen_for_order and r.review_before_delivery and r.review_created_on = cast(o.delivered_to_customer_at as date)""").fetchone()[0]
    keep = con.execute("select round(avg(review_score),3), count(*) from metrics.metric_late_rate_orders where review_score is not null").fetchone()
    excl = con.execute("select round(avg(review_score),3), count(*) from metrics.metric_late_rate_orders where review_score is not null and not coalesce(review_before_delivery,false)").fetchone()
    late_share_flagged = con.execute("select round(100*avg(is_late::int),2) from metrics.metric_late_rate_orders where review_before_delivery").fetchone()[0]
    R["C2"][arm] = {"flagged": flagged[0], "of": flagged[1], "flagged_pct": round(100 * flagged[0] / flagged[1], 2),
                    "flagged_avg_score": flagged[2], "unflagged_avg_score": flagged[3], "flagged_same_calendar_day_as_delivery": same_day,
                    "late_pct_among_flagged": late_share_flagged,
                    "review_score_keep": keep[0], "review_score_exclude_flagged": excl[0], "n_exclude": excl[1],
                    "late_penalty_keep": penalty(con), "late_penalty_exclude_flagged": penalty(con, "and not coalesce(o.review_before_delivery,false)")}
    con.close()
con = duckdb.connect(DB, read_only=True)
R["C2"]["review_creation_with_time_part"] = con.execute("select count(*) filter (where review_created_at <> cast(review_created_on as timestamp)), count(*) from marts.fct_reviews").fetchone()
con.close()

# ---------------- C4 which review represents an order
R["C4"] = {}
chosen = {}
for arm in ["latest_answer", "earliest_creation"]:
    db = arm_db("int_order_review+", {"review_pick_rule": arm})
    con = duckdb.connect(db, read_only=True)
    chosen[arm] = dict(con.execute("select order_id, review_score from marts.fct_orders where review_id is not null").fetchall())
    R["C4"][arm] = {"review_score": headline(con)["review_score"], "late_penalty": penalty(con)}
    con.close()
diff = [o for o in chosen["latest_answer"] if chosen["latest_answer"][o] != chosen["earliest_creation"].get(o)]
con = duckdb.connect(DB, read_only=True)
R["C4"]["orders_with_multiple_reviews"] = con.execute("select count(*) from (select order_id from marts.fct_reviews group by 1 having count(*)>1)").fetchone()[0]
R["C4"]["orders_whose_score_changes"] = len(diff)
R["C4"]["mean_review_of_order_avg_rule"] = con.execute("""select round(avg(s),3) from (select r.order_id, avg(r.review_score) s from marts.fct_reviews r
   join metrics.metric_late_rate_orders o using(order_id) group by 1)""").fetchone()[0]
con.close()

# ---------------- C5 customer address: latest-order address (dim) vs order-time address (fact)
con = duckdb.connect(DB, read_only=True)
R["C5"] = {
  "people_with_multiple_states": con.execute("select count(*) from (select customer_unique_id from marts.fct_orders group by 1 having count(distinct ship_to_state)>1)").fetchone()[0],
  "people_with_multiple_zips": con.execute("select count(*) from (select customer_unique_id from marts.fct_orders group by 1 having count(distinct ship_to_zip_code_prefix)>1)").fetchone()[0],
  "orders_where_latest_state_differs": con.execute("select count(*) from marts.fct_orders o join marts.dim_customer c using(customer_unique_id) where o.ship_to_state<>c.state").fetchone()[0],
  "max_abs_change_in_state_late_rate_pp": con.execute("""
     with a as (select o.ship_to_state st, avg(o.is_late::int) r from metrics.metric_late_rate_orders o group by 1),
          b as (select c.state st, avg(o.is_late::int) r from metrics.metric_late_rate_orders o join marts.fct_orders f using(order_id)
                join marts.dim_customer c using(customer_unique_id) group by 1)
     select round(100*max(abs(a.r-b.r)),3) from a join b using(st)""").fetchone()[0],
}
con.close()

# ---------------- C6 same-day rule in the 90-day repeat rate
R["C6"] = {}
for arm in ["any_later_order_24h", "different_calendar_day", "second_order_only"]:
    db = arm_db("metric_repeat_rate_90d+", {"repeat_same_day_rule": arm})
    con = duckdb.connect(db, read_only=True)
    R["C6"][arm] = headline(con)["repeat_rate_90d"]
    con.close()
con = duckdb.connect(DB, read_only=True)
R["C6"]["eligible_with_same_day_second_then_later_return"] = con.execute("""
  with q as (select customer_unique_id cu, purchased_at ts, customer_qualifying_order_seq k from marts.fct_orders where is_qualifying_order),
  f as (select cu, ts from q where k=1 and ts <= (select max(ts) from q) - interval 90 day)
  select count(*) from f
  where exists (select 1 from q where q.cu=f.cu and q.k=2 and q.ts < f.ts + interval 1 day)
    and exists (select 1 from q where q.cu=f.cu and q.ts >= f.ts + interval 1 day and q.ts <= f.ts + interval 90 day)""").fetchone()[0]
con.close()

# ---------------- C3 incremental vs full rebuild
proj = os.path.join(WORK, "proj")
shutil.copytree(ROOT, proj, ignore=shutil.ignore_patterns(".venv", "*.duckdb", "target", ".git", "data", "evidence", "logs"))
os.symlink(os.path.join(ROOT, "data"), os.path.join(proj, "data"))
inc_cfg = "{{ config(materialized='incremental', unique_key=%s, incremental_strategy='delete+insert') }}\n"
for model, key, tcol in [("fct_orders", "'order_id'", "purchased_at"), ("fct_order_items", "['order_id','order_item_id']", "shipping_limit_at")]:
    p = os.path.join(proj, "models", "marts", f"{model}.sql")
    sql = open(p).read()
    open(p, "w").write(inc_cfg % key + "select * from (\n" + sql + "\n) src\n{% if is_incremental() %}where src." + tcol +
                       " > (select max(" + tcol + ") from {{ this }}){% endif %}\n")
full_db = os.path.join(WORK, "full.duckdb"); inc_db = os.path.join(WORK, "inc.duckdb")
dbt(["seed"], full_db); dbt(["seed"], inc_db, cwd=proj)
t_full = dbt(["run"], full_db)
t_full_again = dbt(["run"], full_db)
t_inc_first = dbt(["run"], inc_db, cwd=proj)
t_inc_second = dbt(["run"], inc_db, cwd=proj)
con = duckdb.connect(inc_db); con.execute(f"attach '{full_db}' as fullb (read_only)")
eq = {}
for t in ["fct_orders", "fct_order_items"]:
    a = con.execute(f"select count(*) from (select * from marts.{t} except all select * from fullb.marts.{t})").fetchone()[0]
    b = con.execute(f"select count(*) from (select * from fullb.marts.{t} except all select * from marts.{t})").fetchone()[0]
    eq[t] = {"rows_only_in_incremental": a, "rows_only_in_full": b}
# simulate a late status change on an OLD order: incremental (append by time) misses it
victim = con.execute("select order_id from marts.fct_orders where order_status='shipped' order by purchased_at limit 1").fetchone()[0]
con.close()
R["C3"] = {"full_rebuild_seconds": round(t_full, 1), "full_rebuild_again_seconds": round(t_full_again, 1),
           "incremental_first_seconds": round(t_inc_first, 1), "incremental_second_seconds": round(t_inc_second, 1),
           "row_equality_after_first_build": eq,
           "late_update_risk": f"An incremental model filtered on purchased_at > max(purchased_at) never revisits old orders, so a status change on an order like {victim} (status 'shipped', purchased early) would not reach the mart without a lookback window."}

shutil.rmtree(WORK, ignore_errors=True)
json.dump(R, open(os.path.join(ROOT, "experiments", "results.json"), "w"), indent=1, default=str)
print(json.dumps(R, indent=1, default=str))
