#!/usr/bin/env python3
"""Prove every business-rule test can fail.

For each rule: copy the built warehouse, inject known-bad rows (a "mutation") into the copy,
run ONLY that rule's tests against the copy, and require them to FAIL. Each rule's tests must
also PASS on an untouched copy (baseline). A test that cannot fail proves nothing.

Usage:  python scripts/prove_tests_fail.py [RULE-SUBSTRING]   (needs a built olist.duckdb; run `make build` first;
        a substring runs only matching rules and does NOT overwrite evidence/ unless all rules ran)
Output: evidence/mutation_report.md and evidence/mutation_report.json
"""
import json, os, shutil, subprocess, sys, tempfile, time
import duckdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(ROOT, "olist.duckdb"))
RAW = os.environ.get("OLIST_RAW_DIR", os.path.join(ROOT, "data", "raw"))
DBT = os.path.join(os.path.dirname(sys.executable), "dbt")

# (rule, dbt selector for the rule's tests, mutation: list of SQL statements OR a raw-file edit)
CASES = [
    ("Raw files are the exact published files",
     "assert_raw_file_hashes_match_manifest",
     {"raw_edit": ("olist_sellers_dataset.csv", "append_row")}),
    ("Raw row counts are as published",
     "source:olist_raw.olist_orders_dataset",
     {"raw_edit": ("olist_orders_dataset.csv", "drop_last_row")}),
    ("Staging keeps every raw row",
     "stg_orders,test_name:expect_table_row_count_to_equal_other_table",
     {"sql": ["delete from staging.stg_orders where order_id in (select order_id from staging.stg_orders limit 1)"]}),
    ("Modeling never creates or loses money (no fan-out)",
     "assert_item_money_matches_raw",
     {"sql": ["insert into marts.fct_order_items select * from marts.fct_order_items limit 1"]}),
    ("Repeat metrics count people, not per-order ids",
     "assert_repeat_metrics_count_people_not_order_ids",
     {"sql": ["update marts.fct_orders o set customer_unique_id = c.customer_id from staging.stg_customers c "
              "where c.customer_unique_id = o.customer_unique_id and o.order_id in (select order_id from marts.fct_orders order by order_id limit 5)"]}),
    ("A multi-seller order is never treated as a single observed parcel",
     "assert_multi_seller_orders_never_treated_as_single_parcel",
     {"sql": ["update marts.fct_orders set delivery_evidence = 'order_level_single_parcel' "
              "where order_id in (select order_id from marts.fct_orders where delivery_evidence = 'order_level_multi_parcel' limit 1)"]}),
    ("A review dated before delivery is flagged",
     "assert_reviews_dated_before_delivery_are_flagged",
     {"sql": ["update marts.fct_reviews set review_before_delivery = false "
              "where review_id in (select review_id from marts.fct_reviews where review_before_delivery limit 1)"]}),
    ("Paid equals items + freight, or the order is labeled",
     "assert_payments_match_items_plus_freight_or_are_labeled",
     {"sql": ["update marts.fct_payments set payment_value = payment_value + 50 "
              "where order_id in (select order_id from marts.fct_orders where recon_status = 'match' order by order_id limit 1)"]}),
    ("Real payment gaps stay under 0.5% of orders",
     "assert_payment_mismatch_share_below_threshold",
     {"sql": ["create temp table victims as select order_id from marts.fct_orders where recon_status = 'match' order by order_id limit 600",
              "update marts.fct_payments p set payment_value = payment_value + 50 from (select order_id, min(payment_sequential) s from marts.fct_payments group by 1) m "
              "where p.order_id = m.order_id and p.payment_sequential = m.s and p.order_id in (select order_id from victims)",
              "update marts.fct_orders set recon_status = 'overpaid' where order_id in (select order_id from victims)"]}),
    ("Only full months are in the analysis window",
     "assert_analysis_window_is_full_months_only",
     {"sql": ["update marts.fct_orders set in_analysis_window = true where purchase_date >= date '2018-09-01'"]}),
    ("Delivery state agrees with status and dates",
     "assert_delivery_state_agrees_with_status_and_dates",
     {"sql": ["update marts.fct_orders set delivery_state = 'delivered_late' where delivery_state = 'status_date_conflict'"]}),
    ("Orders without items are labeled no_items",
     "assert_orders_without_items_are_labeled",
     {"sql": ["update marts.fct_orders set recon_status = 'match' where recon_status = 'no_items'"]}),
    ("Exactly one chosen review per reviewed order",
     "assert_one_chosen_review_per_reviewed_order",
     {"sql": ["update marts.fct_reviews set is_chosen_for_order = true where order_id in "
              "(select order_id from marts.fct_reviews group by 1 having count(*) > 1 order by 1 limit 1)"]}),
    ("Every order's purchase date exists in dim_date",
     "fct_orders,test_name:relationships",
     {"sql": ["delete from marts.dim_date where date_day >= date '2018-10-01'"]}),
    ("One location per zip",
     "int_geo_zip,test_name:unique",
     {"sql": ["insert into intermediate.int_geo_zip select * from intermediate.int_geo_zip limit 1"]}),
    ("Zip locations are inside Brazil",
     "int_geo_zip,test_name:expect_column_values_to_be_between",
     {"sql": ["update intermediate.int_geo_zip set lat = 40.7 where zip_code_prefix in (select zip_code_prefix from intermediate.int_geo_zip where lat is not null limit 1)"]}),
    ("Payment types are known values",
     "stg_payments,test_name:accepted_values",
     {"sql": ["update staging.stg_payments set payment_type = 'pix' where order_id in (select order_id from staging.stg_payments limit 1)"]}),
    ("Trend metrics never include a partial month",
     "metric_late_rate_monthly,test_name:expect_column_values_to_be_between",
     {"sql": ["insert into metrics.metric_late_rate_monthly values ('2018-09', 1, 16, 6.25)"]}),
    # Ontology claims (ontology/check.py): a broken link between business things must fail the check.
    ("Ontology: an order has exactly one row (no order with two customers)",
     "ontology:entity order",
     {"sql": ["insert into marts.fct_orders select * replace ('ghost-person' as customer_unique_id) from marts.fct_orders order by order_id limit 1"]}),
    ("Ontology: every customer has at least one order",
     "ontology:relationship customer places orders",
     {"sql": ["insert into marts.dim_customer select * replace ('ghost-person' as customer_unique_id) from marts.dim_customer order by customer_unique_id limit 1"]}),
    ("Ontology: every item's product exists",
     "ontology:relationship product appears on items",
     {"sql": ["update marts.fct_order_items set product_id = 'ghost-product' where (order_id, order_item_id) in (select (order_id, order_item_id) from marts.fct_order_items order by 1 limit 1)"]}),
    ("Ontology: every survey response belongs to a real order",
     "ontology:relationship order receives survey responses",
     {"sql": ["update marts.fct_reviews set order_id = 'ghost-order' where (review_id, order_id) in (select (review_id, order_id) from marts.fct_reviews order by 1 limit 1)"]}),
    ("Ontology: an order never has two chosen reviews",
     "ontology:relationship order has one chosen review",
     {"sql": ["update marts.fct_reviews set is_chosen_for_order = true where order_id in "
              "(select order_id from marts.fct_reviews group by 1 having count(*) > 1 order by 1 limit 1)"]}),
    ("Ontology: no new unknown ship-to locations beyond the documented 278",
     "ontology:relationship order ships to a location",
     {"sql": ["update marts.fct_orders set ship_to_zip_code_prefix = '00000' where order_id in (select order_id from marts.fct_orders order by order_id limit 1)"]}),
    ("Ontology stage rule: late always means delivered after the promised day",
     "ontology:stage_rule A late order arrived after the promised day",
     {"sql": ["update marts.fct_orders set delivery_state = 'delivered_late' where order_id in "
              "(select order_id from marts.fct_orders where delivery_state = 'delivered_on_time' order by order_id limit 1)"]}),
    # Ontology gap fixes (column facts, populations, the canceled rule): each new claim must fail on a broken warehouse.
    ("Ontology: the repeat cohort has one row per person (no duplicate person)",
     "ontology:entity repeat_cohort",
     {"sql": ["insert into metrics.metric_repeat_rate_90d_people select * from metrics.metric_repeat_rate_90d_people order by customer_unique_id limit 1"]}),
    ("Ontology: every cohort person is a real customer",
     "ontology:relationship customer is in the repeat cohort",
     {"sql": ["update metrics.metric_repeat_rate_90d_people set customer_unique_id = 'ghost-person' where customer_unique_id in (select customer_unique_id from metrics.metric_repeat_rate_90d_people order by 1 limit 1)"]}),
    ("Ontology: purchased_at is never null",
     "ontology:column_fact marts.fct_orders.purchased_at",
     {"sql": ["update marts.fct_orders set purchased_at = null where order_id in (select order_id from marts.fct_orders order by order_id limit 1)"]}),
    ("Ontology: purchased_at keeps its TIMESTAMP type (a DATE would lose the 24-hour rule)",
     "ontology:column_fact marts.fct_orders.purchased_at",
     {"sql": ["alter table marts.fct_orders alter column purchased_at set data type date"]}),
    ("Ontology: n_parcels is 0, not null, for an order with no items",
     "ontology:column_fact marts.fct_orders.n_parcels",
     {"sql": ["update marts.fct_orders set n_parcels = null where order_id in (select order_id from marts.fct_orders where n_items = 0 order by order_id limit 1)"]}),
    ("Ontology: in_analysis_window is never null",
     "ontology:column_fact marts.fct_orders.in_analysis_window",
     {"sql": ["update marts.fct_orders set in_analysis_window = null where order_id in (select order_id from marts.fct_orders order by order_id limit 1)"]}),
    ("Ontology: review_score is null only when the order has no response",
     "ontology:column_fact marts.fct_orders.review_score",
     {"sql": ["update marts.fct_orders set review_score = null where order_id in (select order_id from marts.fct_orders where review_score is not null order by order_id limit 1)"]}),
    ("Ontology: review_score never holds a value outside 1 to 5",
     "ontology:column_fact marts.fct_orders.review_score",
     {"sql": ["update marts.fct_orders set review_score = 9 where order_id in (select order_id from marts.fct_orders where review_score is not null order by order_id limit 1)"]}),
    ("Ontology: the repeat flag is never null",
     "ontology:column_fact metrics.metric_repeat_rate_90d_people.repeated",
     {"sql": ["update metrics.metric_repeat_rate_90d_people set repeated = null where customer_unique_id in (select customer_unique_id from metrics.metric_repeat_rate_90d_people order by 1 limit 1)"]}),
    ("Ontology: the canceled count and the 6 canceled orders with a delivery date",
     "ontology:term_count canceled_order",
     {"sql": ["update marts.fct_orders set delivered_to_customer_at = null where order_id in (select order_id from marts.fct_orders where order_status = 'canceled' and delivered_to_customer_at is not null order by order_id limit 1)"]}),
    ("Ontology: placed an order versus qualifying order (1,113 people with no qualifying order)",
     "ontology:term_count placed_an_order",
     {"sql": ["update marts.dim_customer set n_qualifying_orders = 0 where customer_unique_id in (select customer_unique_id from marts.dim_customer where n_qualifying_orders > 0 order by 1 limit 1)"]}),
    ("Ontology: the order count with no parcels (n_parcels = 0)",
     "ontology:term_count parcel_count",
     {"sql": ["update marts.fct_orders set n_parcels = 1 where order_id in (select order_id from marts.fct_orders where n_parcels = 0 order by order_id limit 1)"]}),
    ("Ontology: the analysis-window flag counts (349 outside)",
     "ontology:term_count analysis_window",
     {"sql": ["update marts.fct_orders set in_analysis_window = false where order_id in (select order_id from marts.fct_orders where in_analysis_window order by order_id limit 1)"]}),
    ("Ontology: the repeat cohort is everyone old enough (77,560 and the 17,423 left out)",
     "ontology:fact The repeat cohort is exactly the people whose first qualifying order is old enough",
     {"sql": ["delete from metrics.metric_repeat_rate_90d_people where customer_unique_id in (select customer_unique_id from metrics.metric_repeat_rate_90d_people order by 1 limit 1)"]}),
    ("Ontology: first_order_at is the purchased_at of the seq = 1 order",
     "ontology:fact first_order_at is the purchased_at of the person's seq = 1 order",
     {"sql": ["update metrics.metric_repeat_rate_90d_people set first_order_at = first_order_at + interval 1 hour where customer_unique_id in (select customer_unique_id from metrics.metric_repeat_rate_90d_people order by 1 limit 1)"]}),
    ('Ontology: the headline metric table has its 5 rows',
     'ontology:entity headline_metric',
     {"sql": ["delete from metrics.metrics_headline where metric_name = 'late_rate'"]}),
    ('Ontology: is_qualifying_order follows its rule (status and items)',
     'ontology:column_fact marts.fct_orders.is_qualifying_order',
     {"sql": ['update marts.fct_orders set is_qualifying_order = not is_qualifying_order where order_id in (select order_id from marts.fct_orders order by order_id limit 1)']}),
    ('Ontology: qualifying order counts (98,199 qualifying, 1,242 not)',
     'ontology:term_count qualifying_order',
     {"sql": ['update marts.fct_orders set is_qualifying_order = true where order_id in (select order_id from marts.fct_orders where not is_qualifying_order order by order_id limit 1)']}),
    ('Ontology: the sequence number is null exactly for non-qualifying orders',
     'ontology:column_fact marts.fct_orders.customer_qualifying_order_seq',
     {"sql": ['update marts.fct_orders set customer_qualifying_order_seq = 1 where order_id in (select order_id from marts.fct_orders where customer_qualifying_order_seq is null order by order_id limit 1)']}),
    ('Ontology: purchase_date is the calendar day of purchased_at',
     'ontology:column_fact marts.fct_orders.purchase_date',
     {"sql": ['update marts.fct_orders set purchase_date = purchase_date + 1 where order_id in (select order_id from marts.fct_orders order by order_id limit 1)']}),
    ('Ontology: n_items is never null',
     'ontology:column_fact marts.fct_orders.n_items',
     {"sql": ['update marts.fct_orders set n_items = null where order_id in (select order_id from marts.fct_orders order by order_id limit 1)']}),
    ('Ontology: delivered_to_customer_at has exactly 2,965 nulls',
     'ontology:column_fact marts.fct_orders.delivered_to_customer_at',
     {"sql": ['update marts.fct_orders set delivered_to_customer_at = null where order_id in (select order_id from marts.fct_orders where delivered_to_customer_at is not null order by order_id limit 1)']}),
    ('Ontology: every person has at least one order (n_orders >= 1)',
     'ontology:column_fact marts.dim_customer.n_orders',
     {"sql": ['update marts.dim_customer set n_orders = 0 where customer_unique_id in (select customer_unique_id from marts.dim_customer order by 1 limit 1)']}),
    ('Ontology: qualifying orders never exceed orders',
     'ontology:column_fact marts.dim_customer.n_qualifying_orders',
     {"sql": ['update marts.dim_customer set n_qualifying_orders = n_orders + 1 where customer_unique_id in (select customer_unique_id from marts.dim_customer order by 1 limit 1)']}),
    ('Ontology: first_qualifying_order_at is null exactly when a person has no qualifying order',
     'ontology:column_fact marts.dim_customer.first_qualifying_order_at',
     {"sql": ['update marts.dim_customer set first_qualifying_order_at = null where customer_unique_id in (select customer_unique_id from marts.dim_customer where n_qualifying_orders > 0 order by 1 limit 1)']}),
    ('Ontology: the cohort person id is never null',
     'ontology:column_fact metrics.metric_repeat_rate_90d_people.customer_unique_id',
     {"sql": ['update metrics.metric_repeat_rate_90d_people set customer_unique_id = null where customer_unique_id in (select customer_unique_id from metrics.metric_repeat_rate_90d_people order by 1 limit 1)']}),
    ('Ontology: first_order_at is never null',
     'ontology:column_fact metrics.metric_repeat_rate_90d_people.first_order_at',
     {"sql": ['update metrics.metric_repeat_rate_90d_people set first_order_at = null where customer_unique_id in (select customer_unique_id from metrics.metric_repeat_rate_90d_people order by 1 limit 1)']}),
    ('Ontology: first_order_date is the calendar day of first_order_at',
     'ontology:column_fact metrics.metric_repeat_rate_90d_people.first_order_date',
     {"sql": ['update metrics.metric_repeat_rate_90d_people set first_order_date = first_order_date + 1 where customer_unique_id in (select customer_unique_id from metrics.metric_repeat_rate_90d_people order by 1 limit 1)']}),
    ('Ontology: the headline numerator is null only for the review gap',
     'ontology:column_fact metrics.metrics_headline.numerator',
     {"sql": ["update metrics.metrics_headline set numerator = null where metric_name = 'late_rate'"]}),
    ('Ontology: the headline denominator is never null',
     'ontology:column_fact metrics.metrics_headline.denominator',
     {"sql": ["update metrics.metrics_headline set denominator = null where metric_name = 'late_rate'"]}),
    ('Ontology: the headline value is never null',
     'ontology:column_fact metrics.metrics_headline.value_pct',
     {"sql": ["update metrics.metrics_headline set value_pct = null where metric_name = 'late_rate'"]}),
    ('Ontology: the headline metric name is never null',
     'ontology:column_fact metrics.metrics_headline.metric_name',
     {"sql": ["update metrics.metrics_headline set metric_name = null where metric_name = 'late_rate'"]}),
    ('Ontology: the review score count (768 orders with none)',
     'ontology:term_count order_review_score',
     {"sql": ['update marts.fct_orders set review_score = 3 where order_id in (select order_id from marts.fct_orders where review_score is null order by order_id limit 1)']}),
    ('Ontology fact: people with a qualifying order (94,983)',
     'ontology:fact People with a qualifying order',
     {"sql": ['update marts.dim_customer set n_qualifying_orders = 0 where customer_unique_id in (select customer_unique_id from marts.dim_customer where n_qualifying_orders > 0 order by 1 limit 1)']}),
    ('Ontology fact: people left out of the cohort as too recent (17,423)',
     'ontology:fact People whose first qualifying order is too recent for a full 90 days',
     {"sql": ["update marts.fct_orders set purchased_at = timestamp '2018-09-03 09:06:56' where order_id in (select order_id from marts.fct_orders where customer_qualifying_order_seq = 1 and purchased_at < timestamp '2017-02-01' order by order_id limit 1)"]}),
    ('Ontology fact: the newest qualifying purchase and the cohort cutoff',
     'ontology:fact The newest qualifying purchase in the data is 2018-09-03 09:06:57, so the cohort cutoff is 2018-06-05 09:06:57',
     {"sql": ["update marts.fct_orders set purchased_at = timestamp '2018-09-04 00:00:00' where order_id in (select order_id from marts.fct_orders where is_qualifying_order order by purchased_at desc limit 1)"]}),
    ('Ontology fact: one seq = 1 order per cohort person (the first-order state is unambiguous)',
     'ontology:fact Each person has exactly one seq = 1 order, so joining the cohort to it gives one row per person (the first-order state is unambiguous)',
     {"sql": ['update marts.fct_orders set customer_qualifying_order_seq = 2 where order_id in (select o.order_id from marts.fct_orders o join metrics.metric_repeat_rate_90d_people p on p.customer_unique_id = o.customer_unique_id and o.customer_qualifying_order_seq = 1 order by o.order_id limit 1)']}),
    ("Ontology fact: seq = 1 is the earliest qualifying order",
     "ontology:fact The sequence number follows purchased_at, so seq = 1 is the person's earliest qualifying order",
     {"sql": ["update marts.fct_orders set purchased_at = purchased_at + interval 3650 day where order_id in (select order_id from marts.fct_orders where customer_qualifying_order_seq = 1 and customer_unique_id in (select customer_unique_id from marts.fct_orders where customer_qualifying_order_seq = 2) order by order_id limit 1)"]}),
    ('Ontology fact: same-second qualifying orders (281 pairs)',
     "ontology:fact Pairs of one person's qualifying orders placed in the same second",
     {"sql": ['update marts.fct_orders set purchased_at = purchased_at + interval 1 second where order_id in (select max(order_id) from marts.fct_orders where is_qualifying_order group by customer_unique_id, purchased_at having count(*) > 1 order by 1 limit 1)']}),
    ("Ontology fact: the order's review_score equals the chosen response's score",
     'ontology:fact review_score on the order equals the score of the chosen response, and an order with no chosen response has a null score',
     {"sql": ['update marts.fct_orders set review_score = 6 - review_score where order_id in (select order_id from marts.fct_orders where review_score is not null order by order_id limit 1)']}),
]

def run_ontology_claim(claim, db):
    env = dict(os.environ, OLIST_DB_PATH=db, ONTOLOGY_NO_REPORT="1")
    p = subprocess.run([sys.executable, os.path.join(ROOT, "ontology", "check.py"), "--skip-semantic"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    kind, name = claim.split(" ", 1)
    hits = [l for l in p.stdout.splitlines() if l[6:].startswith(f"{kind:12s} {name}:")]
    res = [(claim, "pass" if l.startswith("PASS") else "fail", l.split(": ", 1)[1]) for l in hits]
    return (0 if res and all(r[1] == "pass" for r in res) else 1), res

def run_tests(selector, db, raw):
    if selector.startswith("ontology:"):
        return run_ontology_claim(selector[len("ontology:"):], db)
    env = dict(os.environ, OLIST_DB_PATH=db, OLIST_RAW_DIR=raw, DBT_PROFILES_DIR=ROOT)
    tp = tempfile.mkdtemp(prefix="dbt-target-")
    p = subprocess.run([DBT, "test", "--select", selector, "--target-path", tp, "--quiet"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    try:
        res = json.load(open(os.path.join(tp, "run_results.json")))["results"]
    except Exception:
        res = []
    shutil.rmtree(tp, ignore_errors=True)
    return p.returncode, [(r["unique_id"].split(".")[-2] if r["unique_id"].count(".") > 2 else r["unique_id"], r["status"], r.get("failures")) for r in res]

def raw_copy(edit):
    d = tempfile.mkdtemp(prefix="raw-mut-")
    for f in os.listdir(RAW):
        os.symlink(os.path.join(os.path.abspath(RAW), f), os.path.join(d, f))
    if edit:
        name, how = edit
        os.unlink(os.path.join(d, name))
        lines = open(os.path.join(RAW, name), encoding="utf-8").read().splitlines(keepends=True)
        if how == "append_row":
            lines.append(lines[-1])
        elif how == "drop_last_row":
            lines = lines[:-1]
        open(os.path.join(d, name), "w", encoding="utf-8").writelines(lines)
    return d

def main():
    if not os.path.exists(DB):
        sys.exit(f"no warehouse at {DB}; run `make build` first")
    work = tempfile.mkdtemp(prefix="mutation-")
    report = []
    only = sys.argv[1] if len(sys.argv) > 1 else ""   # optional substring filter on the rule name (quick reruns)
    for rule, selector, mut in CASES:
        if only not in rule:
            continue
        t0 = time.time()
        base_db = os.path.join(work, "baseline.duckdb"); shutil.copy(DB, base_db)
        raw_clean = raw_copy(None)
        b_rc, b_res = run_tests(selector, base_db, raw_clean)
        mut_db = os.path.join(work, "mutant.duckdb"); shutil.copy(DB, mut_db)
        raw_mut = raw_copy(mut.get("raw_edit"))
        if "sql" in mut:
            con = duckdb.connect(mut_db)
            for s in mut["sql"]:
                con.execute(s)
            con.close()
        m_rc, m_res = run_tests(selector, mut_db, raw_mut)
        for p in (base_db, mut_db): os.remove(p)
        shutil.rmtree(raw_clean, ignore_errors=True); shutil.rmtree(raw_mut, ignore_errors=True)
        base_ok = b_rc == 0 and b_res and all(s == "pass" for _, s, _ in b_res)
        mut_fail = m_rc != 0 and any(s in ("fail", "error") for _, s, _ in m_res)
        verdict = "PROVEN" if (base_ok and mut_fail) else "NOT PROVEN"
        report.append({"rule": rule, "selector": selector, "mutation": mut, "baseline": b_res,
                       "mutant": m_res, "verdict": verdict, "seconds": round(time.time() - t0, 1)})
        print(f"{verdict:11s} {rule}  baseline={[s for _, s, _ in b_res]} mutant={[(s, f) for _, s, f in m_res]}", flush=True)
    shutil.rmtree(work, ignore_errors=True)
    if only:
        bad = [r for r in report if r["verdict"] != "PROVEN"]
        print(f"\n{len(report) - len(bad)}/{len(report)} selected rules proven (evidence/ not rewritten)")
        sys.exit(1 if bad else 0)
    os.makedirs(os.path.join(ROOT, "evidence"), exist_ok=True)
    json.dump(report, open(os.path.join(ROOT, "evidence", "mutation_report.json"), "w"), indent=1)
    with open(os.path.join(ROOT, "evidence", "mutation_report.md"), "w") as f:
        f.write("# Business-rule tests: proof that each one can fail\n\n")
        f.write("Each rule's tests pass on the real warehouse (baseline) and fail after known-bad rows are injected into a copy (mutant).\n\n")
        f.write("| Rule | Tests | Known-bad rows injected | Baseline | Mutant (failing rows) | Verdict |\n|---|---|---|---|---|---|\n")
        for r in report:
            mut = r["mutation"].get("sql") or [f"raw file edit: {r['mutation']['raw_edit']}"]
            f.write(f"| {r['rule']} | `{r['selector']}` | {'<br>'.join('`'+m.replace('|','\\|')+'`' for m in mut)} | "
                    f"{', '.join(s for _, s, _ in r['baseline'])} | {', '.join(f'{s} ({n})' for _, s, n in r['mutant'])} | **{r['verdict']}** |\n")
    bad = [r for r in report if r["verdict"] != "PROVEN"]
    print(f"\n{len(report) - len(bad)}/{len(report)} rules proven able to fail")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
