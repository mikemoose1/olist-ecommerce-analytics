#!/usr/bin/env python3
"""Prove every business-rule test can fail.

For each rule: copy the built warehouse, inject known-bad rows (a "mutation") into the copy,
run ONLY that rule's tests against the copy, and require them to FAIL. Each rule's tests must
also PASS on an untouched copy (baseline). A test that cannot fail proves nothing.

Usage:  python scripts/prove_tests_fail.py            (needs a built olist.duckdb; run `make build` first)
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
    ("One location per zip",
     "int_geo_zip,test_name:unique",
     {"sql": ["insert into intermediate.int_geo_zip select * from intermediate.int_geo_zip limit 1"]}),
    ("Zip locations are inside Brazil",
     "int_geo_zip,test_name:expect_column_values_to_be_between",
     {"sql": ["update intermediate.int_geo_zip set lat = 40.7 where zip_code_prefix in (select zip_code_prefix from intermediate.int_geo_zip limit 1)"]}),
    ("Payment types are known values",
     "stg_payments,test_name:accepted_values",
     {"sql": ["update staging.stg_payments set payment_type = 'pix' where order_id in (select order_id from staging.stg_payments limit 1)"]}),
    ("Trend metrics never include a partial month",
     "metric_late_rate_monthly,test_name:expect_column_values_to_be_between",
     {"sql": ["insert into metrics.metric_late_rate_monthly values ('2018-09', 1, 16, 6.25)"]}),
]

def run_tests(selector, db, raw):
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
    for rule, selector, mut in CASES:
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
