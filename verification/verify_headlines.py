#!/usr/bin/env python3
"""Reconcile the dbt marts to the headline numbers and give each number one verdict.

Part A - reconcile to the first pass. Rebuilds the metric layer on a COPY of the warehouse with the
first pass's rules (multi-seller orders trusted, 90-day repeat = second order only) and requires every
number to equal BOTH the first-pass value and an independent recomputation from the raw CSVs.
Part B - shipped values. Reads the warehouse as built (the rules picked by experiment) and requires
every published number to equal the independent recomputation under the same rules.

Verdicts: VERIFIED (all compared values agree within the stated tolerance), NOT VERIFIED (a mismatch),
INCONCLUSIVE (something could not be measured).
Part C - story chart numbers. Every count behind a chart in story/ (story/data, drawn by story/build_story.py) must equal an
independent recomputation from the raw CSVs (verification/story_numbers.py). verification/selftest_story_numbers.py proves it can fail.
Usage: python verification/verify_headlines.py   (after `make build`)
Output: evidence/verification_report.json, evidence/verification_report.md; exit 1 on any NOT VERIFIED.
"""
import json, os, shutil, subprocess, sys, tempfile
import duckdb, numpy as np, yaml
import statsmodels.formula.api as smf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(ROOT, "olist.duckdb"))
RAW = os.environ.get("OLIST_RAW_DIR", os.path.join(ROOT, "data", "raw"))
DBT = os.path.join(os.path.dirname(sys.executable), "dbt")
BASE = json.load(open(os.path.join(ROOT, "verification", "first_pass_baseline.json")))
SHIPPED = yaml.safe_load(open(os.path.join(ROOT, "dbt_project.yml")))["vars"]
FIRST_PASS_RULES = {"multi_seller_late_rule": "trust_order_date", "repeat_same_day_rule": "second_order_only"}

def independent(rules):
    """Recompute every headline straight from the raw CSVs (no dbt code)."""
    raw = duckdb.connect()
    for name, f in {"orders": "olist_orders_dataset", "items": "olist_order_items_dataset", "reviews": "olist_order_reviews_dataset",
                    "customers": "olist_customers_dataset"}.items():
        raw.execute(f"create view {name} as select * from read_csv_auto('{RAW}/{f}.csv', header=true)")
    multi = "and n_sellers = 1" if rules["multi_seller_late_rule"] == "exclude_multi_seller" else ""
    if rules["multi_seller_late_rule"] == "last_parcel_proxy":
        return None
    raw.execute(f"""
    create table ia as select order_id, count(*) n_items, count(distinct seller_id) n_sellers from items group by 1;
    create table rev1 as select * from (select *, row_number() over (partition by order_id order by review_answer_timestamp desc, review_id) rn from reviews) where rn = 1;
    create table pop_all as
     select o.order_id, ia.n_sellers, (o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date) late, r.review_score
     from orders o join ia using(order_id) left join rev1 r using(order_id)
     where o.order_status = 'delivered' and o.order_delivered_customer_date is not null
       and o.order_purchase_timestamp >= '2017-01-01' and o.order_purchase_timestamp < '2018-09-01';
    create table pop as select * from pop_all where true {multi};
    create table q as
     select c.customer_unique_id cu, o.order_purchase_timestamp ts,
            row_number() over (partition by c.customer_unique_id order by o.order_purchase_timestamp, o.order_id) k
     from orders o join customers c using(customer_id) join ia using(order_id)
     where o.order_status not in ('canceled', 'unavailable');""")
    out = {}
    n, k = raw.execute("select count(*), sum(late::int) from pop").fetchone()
    out["late_rate"] = {"num": int(k), "den": int(n), "value": round(100 * k / n, 2)}
    s, n = raw.execute("select sum(review_score), count(review_score) from pop_all").fetchone()
    out["review_score"] = {"num": int(s), "den": int(n), "value": round(s / n, 3)}
    out["late_review_gap_raw"] = {"value": round(raw.execute(
        "select avg(review_score) filter (where not late) - avg(review_score) filter (where late) from pop").fetchone()[0], 3)}
    n, k = raw.execute("select count(*), sum((m > 1)::int) from (select cu, max(k) m from q group by 1)").fetchone()
    out["repeat_rate_ever"] = {"num": int(k), "den": int(n), "value": round(100 * k / n, 2)}
    cond = {"any_later_order_24h": "q.ts >= f.ts + interval 1 day and q.ts <= f.ts + interval 90 day",
            "different_calendar_day": "q.ts::date > f.ts::date and q.ts <= f.ts + interval 90 day",
            "second_order_only": "q.k = 2 and q.ts >= f.ts + interval 1 day and q.ts <= f.ts + interval 90 day"}[rules["repeat_same_day_rule"]]
    n, k = raw.execute(f"""select count(*), sum(hit::int) from (
      select f.cu, bool_or({cond}) hit from q f join q using(cu)
      where f.k = 1 and f.ts <= (select max(ts) from q) - interval 90 day group by 1)""").fetchone()
    out["repeat_rate_90d"] = {"num": int(k), "den": int(n), "value": round(100 * k / n, 2)}
    return out

def from_marts(db):
    con = duckdb.connect(db, read_only=True)
    h = {r[0]: {"num": r[2], "den": r[3], "value": float(r[4])} for r in
         con.execute("select metric_name, rule, numerator, denominator, value_pct from metrics.metrics_headline").fetchall()}
    h["late_review_gap_raw"] = {"value": h["late_review_gap_raw"]["value"]}
    df = con.execute("""
      with cat as (select i.order_id, arg_max(p.category, i.price) as category
                   from marts.fct_order_items i join marts.dim_product p using (product_id) group by 1)
      select o.review_score, o.is_late::int as late_i, o.ship_to_state as state, cat.category
      from metrics.metric_late_rate_orders o join cat using (order_id)
      where o.review_score is not null""").df()
    con.close()
    top = df.category.value_counts().index[:30]
    df["cat30"] = np.where(df.category.isin(top), df.category, "other")
    m = smf.ols("review_score ~ late_i + C(state) + C(cat30)", df).fit()
    h["late_penalty_controlled"] = {"value": round(float(m.params["late_i"]), 3),
                                    "ci": [round(float(x), 3) for x in m.conf_int().loc["late_i"]], "n": int(m.nobs)}
    return h

def same(a, b):
    return a is not None and b is not None and a["value"] == b["value"] and a.get("num") == b.get("num") and a.get("den") == b.get("den")

rows = []
def add(part, metric, mart_v, ind_v, fp, tol, note):
    if mart_v is None or (ind_v is None and fp is None):
        v = "INCONCLUSIVE"
    else:
        ok = True
        if ind_v is not None: ok &= same(mart_v, ind_v)
        if fp is not None: ok &= abs(mart_v["value"] - fp) <= tol
        v = "VERIFIED" if ok else "NOT VERIFIED"
    rows.append({"part": part, "metric": metric, "mart": mart_v, "independent": ind_v, "first_pass": fp, "tolerance": tol, "note": note, "verdict": v})

# ---- Part A: first-pass rules on a copy
work = tempfile.mkdtemp(prefix="verify-")
dbA = os.path.join(work, "firstpass.duckdb"); shutil.copy(DB, dbA)
p = subprocess.run([DBT, "run", "--select", "metrics", "--vars", json.dumps(FIRST_PASS_RULES), "--quiet", "--target-path", os.path.join(work, "t")],
                   cwd=ROOT, env=dict(os.environ, OLIST_DB_PATH=dbA, DBT_PROFILES_DIR=ROOT), capture_output=True, text=True)
if p.returncode != 0:
    sys.exit(p.stdout + p.stderr)
A, IA = from_marts(dbA), independent(FIRST_PASS_RULES)
shutil.rmtree(work, ignore_errors=True)
fp_note = "first-pass rules: multi-seller orders trusted; 90-day repeat = second order only"
add("A", "repeat_rate_90d", A["repeat_rate_90d"], IA["repeat_rate_90d"], BASE["repeat_rate_90d_pct_second_order_rule"]["value"], 0.005, fp_note)
add("A", "repeat_rate_ever", A["repeat_rate_ever"], IA["repeat_rate_ever"], BASE["repeat_rate_ever_pct"]["value"], 0.005, fp_note)
add("A", "late_rate", A["late_rate"], IA["late_rate"], BASE["late_rate_pct"]["value"], 0.005, fp_note)
add("A", "review_score", A["review_score"], IA["review_score"], BASE["review_score"]["value"], 0.0005, fp_note)
add("A", "late_review_gap_raw", A["late_review_gap_raw"], IA["late_review_gap_raw"], BASE["late_review_gap_raw"]["value"], 0.0005, fp_note)
add("A", "late_penalty_controlled (OLS)", A["late_penalty_controlled"], None, BASE["late_penalty_controlled"]["value"], 0.01,
    fp_note + "; statsmodels OLS review ~ late + state + top-30 category, from marts")

# ---- Part B: shipped rules
B, IB = from_marts(DB), independent(SHIPPED)
sh_note = f"shipped rules: C1={SHIPPED['multi_seller_late_rule']}, C6={SHIPPED['repeat_same_day_rule']}"
add("B", "repeat_rate_90d (HEADLINE)", B["repeat_rate_90d"], IB["repeat_rate_90d"] if IB else None, None, 0, sh_note)
add("B", "repeat_rate_ever (secondary)", B["repeat_rate_ever"], IB["repeat_rate_ever"] if IB else None, None, 0, sh_note)
add("B", "late_rate", B["late_rate"], IB["late_rate"] if IB else None, None, 0, sh_note)
add("B", "review_score", B["review_score"], IB["review_score"] if IB else None, None, 0, sh_note)
add("B", "late_review_gap_raw", B["late_review_gap_raw"], IB["late_review_gap_raw"] if IB else None, None, 0, sh_note)
rows.append({"part": "B", "metric": "late_penalty_controlled (OLS)", "mart": B["late_penalty_controlled"], "independent": None, "first_pass": None,
             "tolerance": None, "note": sh_note + "; reported, no independent second path", "verdict": "REPORTED"})

# ---- Part C: story chart numbers
sys.path.insert(0, os.path.join(ROOT, "verification"))
import story_numbers
for name, ok, msg in story_numbers.compare(story_numbers.from_story(os.path.join(ROOT, "story", "data")), story_numbers.from_raw(RAW)):
    rows.append({"part": "C", "metric": f"story {name}", "mart": None, "independent": None, "first_pass": None, "tolerance": 0,
                 "note": msg, "verdict": "VERIFIED" if ok else "NOT VERIFIED"})

os.makedirs(os.path.join(ROOT, "evidence"), exist_ok=True)
json.dump(rows, open(os.path.join(ROOT, "evidence", "verification_report.json"), "w"), indent=1)
fmt = lambda x: "-" if x is None else (f"{x['value']} ({x.get('num')}/{x.get('den')})" if x.get("den") else (f"{x['value']} CI {x['ci']}" if "ci" in x else f"{x['value']}"))
with open(os.path.join(ROOT, "evidence", "verification_report.md"), "w") as f:
    f.write("# Headline reconciliation\n\n**Part A** rebuilds the metric layer with the first pass's rules and must reproduce the first pass AND an independent raw-CSV recomputation. "
            "**Part B** checks the shipped numbers (rules picked by experiment) against the independent recomputation under the same rules. "
            "**Part C** checks every count behind a story chart against the raw CSVs (story count and raw count in the Mart column).\n\n")
    f.write("| Part | Metric | Mart | Independent (raw CSVs) | First pass | Verdict |\n|---|---|---|---|---|---|\n")
    for r in rows:
        mart, ind = (r["note"], "-") if r["part"] == "C" else (fmt(r["mart"]), fmt(r["independent"]))
        f.write(f"| {r['part']} | {r['metric']} | {mart} | {ind} | {r['first_pass'] if r['first_pass'] is not None else '-'} | **{r['verdict']}** |\n")
    f.write(f"\nPart A rules: {FIRST_PASS_RULES}. Part B rules: {SHIPPED}.\n")
for r in rows:
    if r["part"] == "C":
        if r["verdict"] != "VERIFIED": print(f"{r['verdict']:13s} [C] {r['metric']}: {r['note']}")
        continue
    print(f"{r['verdict']:13s} [{r['part']}] {r['metric']}: mart={fmt(r['mart'])} independent={fmt(r['independent'])} first_pass={r['first_pass']}")
C = [r for r in rows if r["part"] == "C"]
print(f"[C] {sum(r['verdict'] == 'VERIFIED' for r in C)}/{len(C)} story chart numbers VERIFIED against the raw CSVs")
sys.exit(1 if any(r["verdict"] == "NOT VERIFIED" for r in rows) else 0)
