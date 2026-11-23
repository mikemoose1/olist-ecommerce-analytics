#!/usr/bin/env python3
"""Prove every business-rule test can fail.

For each rule: copy the built warehouse, inject known-bad rows (a "mutation") into the copy,
run ONLY that rule's tests against the copy, and require them to FAIL. Each rule's tests must
also PASS on an untouched copy (baseline). A test that cannot fail proves nothing.

Usage:  python scripts/prove_tests_fail.py [RULE-SUBSTRING] [--merge]   (needs a built olist.duckdb; run `make build` first;
        a substring runs only matching rules and does NOT overwrite evidence/ unless all rules ran;
        with --merge the selected rules are added to (or replaced in) the committed report)
Output: evidence/mutation_report.md and evidence/mutation_report.json

Speed: cases run in parallel (PROVE_JOBS, default the CPU count up to 4). A case that edits neither project files nor raw files
runs its dbt tests in a long-lived worker (scripts/dbt_test_worker.py) that parses the project once, instead of starting
`dbt test` each time. Measured on the whole suite (every case, baselines shared): 248 cases take about 6.5 min here on 4 CPUs,
and the CI step (2 vCPU) fell from about 20-22 min to about 10 min. PROVE_NO_WORKER=1 starts `dbt test` for every run, the slow way,
and must give the same verdicts. A test that errors counts as a broken run, not as a test that caught the mistake.
"""
import concurrent.futures, json, os, shutil, subprocess, sys, tempfile, threading, time
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
    ("Review-cost number ties to the causal analysis and the story (6,366 / 3,110 / 26.7%)",
     "assert_review_cost_causal_reconciles",
     {"sql": ["update metrics.metric_review_cost_causal set extra_bad_reviews = extra_bad_reviews + 5 where days_late_bin = 'late_d1'"]}),
    ("Review-cost bins count the same late orders the analysis saw",
     "metric_review_cost_causal,test_name:expression_is_true",
     {"sql": ["update metrics.metric_review_cost_causal set reviewed_late_orders = reviewed_late_orders - 1 where days_late_bin = 'late_d7_13'"]}),
    ("Late-rate targets tie to the story numbers (94,931 / 6,518 / 11,635 / 2.27 stars)",
     "assert_late_rate_targets_reconcile_to_story",
     {"sql": ["update metrics.metric_late_rate_targets set late_orders = late_orders + 1",
              "update metrics.metric_bad_review_by_days_late set bad_reviews = bad_reviews + 1 where days_past_promise_capped = 3"]}),
    ("Late-rate control limits are fully fitted (the last pass sets aside no further month)",
     "assert_late_rate_limits_fit_has_converged",
     {"sql": ["update metrics.metric_late_rate_control_chart set fit_changed_in_last_pass = true where year_month = '2018-03'"]}),
    # Logic mutations (S1 of the cold review): real edits to the model SQL, rebuilt downstream in a copy of the project
    # against a copy of the warehouse, then every test on the chart and its descendants must fail on at least one.
    ("Limits (S1/M2): sigma_z divides by 1.0 instead of the 1.128 constant of the moving-range method",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_control_chart.sql", "replace": [("over () / 1.128", "over () / 1.0")], "rebuild": "metric_late_rate_control_chart+"}}),
    ("Goals (S1/M3): the goals use the median instead of the 25th percentile of the stable months",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_targets.sql", "replace": [("percentile_cont(0.25)", "percentile_cont(0.50)")], "replace_all": True, "rebuild": "metric_late_rate_targets"}}),
    ("Goals (S1/M4): the stable-month filter is dropped, so thin and flagged months count as stable",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_targets.sql", "replace": [("where not laney_signal and not thin_month", "where true")], "rebuild": "metric_late_rate_targets"}}),
    ("Goals (S1/M4b): only the thin-month part of the stable filter is dropped",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_targets.sql", "replace": [("where not laney_signal and not thin_month", "where not laney_signal")], "rebuild": "metric_late_rate_targets"}}),
    ("Goals (S1/M4c): only the Laney-signal part of the stable filter is dropped",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_targets.sql", "replace": [("where not laney_signal and not thin_month", "where not thin_month")], "rebuild": "metric_late_rate_targets"}}),
    ("Limits (S1/M5): the moving range counts months that were set aside (sigma_z 4.93 -> about 10)",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_control_chart.sql", "replace": [("avg(case when prev_in_fit and before_in_fit then abs(z - z_before) end)", "avg(abs(z - z_before))")], "rebuild": "metric_late_rate_control_chart+"}}),
    # Story update (step 2): every new number the story prints is pinned to the models and can fail.
    ("Goal line (M6): the goal uses the 60th percentile of the stable months instead of the median (4.43%)",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_targets.sql", "replace": [("median(late_rate)", "percentile_cont(0.6) within group (order by late_rate)")], "rebuild": "metric_late_rate_targets"}}),
    ("Review ramp ties to the story: bad reviews moved from day 10 to day -5 (totals unchanged; 8.7% and 78% move)",
     "assert_late_rate_targets_reconcile_to_story",
     {"sql": ["update metrics.metric_bad_review_by_days_late set bad_reviews = bad_reviews + 40 where days_past_promise_capped = -5",
              "update metrics.metric_bad_review_by_days_late set bad_reviews = bad_reviews - 40 where days_past_promise_capped = 10"]}),
    ("Review ramp ties to the story: bad reviews moved from day 1 to day 5 (only the 11-a-day slope moves)",
     "assert_late_rate_targets_reconcile_to_story",
     {"sql": ["update metrics.metric_bad_review_by_days_late set bad_reviews = bad_reviews - 50 where days_past_promise_capped = 1",
              "update metrics.metric_bad_review_by_days_late set bad_reviews = bad_reviews + 50 where days_past_promise_capped = 5"]}),
    ("Review cost: the range the story quotes (2,880 to 3,350) drifts in the causal report",
     "assert_review_cost_causal_reconciles",
     {"model_edit": {"file": "evidence/review_cost_causal_report.json", "replace": [('"range_across_specifications": [\n   2880.4599647367017', '"range_across_specifications": [\n   2780.4599647367017')], "rebuild": "metric_review_cost_causal"}}),
    ("Review cost: the dbt total leaves the range across specifications (and the whole-% share moves off 27)",
     "assert_review_cost_causal_reconciles",
     {"sql": ["update metrics.metric_review_cost_causal set extra_bad_reviews = extra_bad_reviews + 300 where days_late_bin = 'late_d14p'"]}),
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
    # Cards added so that coverage could pass: each card is a checked claim, not just a sentence.
    ("Ontology card: promised_days is the days from purchase to the promised date",
     "ontology:column_fact marts.fct_orders.promised_days",
     {"sql": ["update marts.fct_orders set promised_days = promised_days + 1 where order_id in (select order_id from marts.fct_orders order by order_id limit 1)"]}),
    ("Ontology card: paid_minus_due is amount_paid minus amount_due",
     "ontology:column_fact marts.fct_orders.paid_minus_due",
     {"sql": ["update marts.fct_orders set paid_minus_due = paid_minus_due + 1 where order_id in (select order_id from marts.fct_orders where paid_minus_due is not null order by order_id limit 1)"]}),
    ("Ontology card: amount_due is null only on orders with no items",
     "ontology:column_fact marts.fct_orders.amount_due",
     {"sql": ["update marts.fct_orders set amount_due = null where order_id in (select order_id from marts.fct_orders where n_items > 0 order by order_id limit 1)"]}),
    ("Ontology fact: 5,127 survey responses were sent before delivery",
     "ontology:fact Survey responses sent on an earlier day than the delivery",
     {"sql": ["update marts.fct_reviews set review_before_delivery = false where review_id in (select review_id from marts.fct_reviews where review_before_delivery limit 1)"]}),
    # G7: the metric tables the cards lean on are entities with column contracts, not just names in a `source:` field.
    ("G7 coverage: a metric table cited only as a card's model has no entity",
     "ontology:coverage tables",
     {"yml_drop_card": "late_rate_month"}),
    ("G7 coverage: a column cited only as a metric's source has no contract",
     "ontology:coverage columns",
     {"yml_drop_card": "metrics.metric_late_rate_orders.is_late"}),
    ("G7 entity: the judged-order table has one row per judged order",
     "ontology:entity late_rate_order",
     {"sql": ["delete from metrics.metric_late_rate_orders where order_id in (select order_id from metrics.metric_late_rate_orders order by order_id limit 1)"]}),
    ("G7 entity: the monthly table has one row per month",
     "ontology:entity late_rate_month",
     {"sql": ["insert into metrics.metric_late_rate_monthly select * from metrics.metric_late_rate_monthly limit 1"]}),
    ("G7 entity: a result table has exactly the rows on its card",
     "ontology:entity review_score_result",
     {"sql": ["insert into metrics.metric_review_score values ('stray', 'x', 1, 1, 1.0)"]}),
    ("G7 link: every judged order is an order",
     "ontology:relationship late-rate verdict covers an order",
     {"sql": ["update metrics.metric_late_rate_orders set order_id = 'no-such-order' where order_id in (select order_id from metrics.metric_late_rate_orders order by order_id limit 1)"]}),
    ("G7 card: is_late is exactly delivery_state = delivered_late",
     "ontology:column_fact metrics.metric_late_rate_orders.is_late",
     {"sql": ["update metrics.metric_late_rate_orders set is_late = not is_late where order_id in (select order_id from metrics.metric_late_rate_orders order by order_id limit 1)"]}),
    ("G7 card: a judged order's review score is 1 to 5 or null",
     "ontology:column_fact metrics.metric_late_rate_orders.review_score",
     {"sql": ["update metrics.metric_late_rate_orders set review_score = 6 where order_id in (select order_id from metrics.metric_late_rate_orders where review_score is not null order by order_id limit 1)"]}),
    ("G7 card: the monthly table holds only months inside the window",
     "ontology:column_fact metrics.metric_late_rate_monthly.year_month",
     {"sql": ["update metrics.metric_late_rate_monthly set year_month = '2018-09' where year_month = '2018-08'"]}),
    ("G7 fact: 6,518 judged orders are late",
     "ontology:fact Judged orders marked late",
     {"sql": ["update metrics.metric_late_rate_orders set is_late = true where order_id in (select order_id from metrics.metric_late_rate_orders where not is_late order by order_id limit 1)"]}),
    ("Card: recon_status uses only the six named values",
     "ontology:column_fact marts.fct_orders.recon_status",
     {"sql": ["update marts.fct_orders set recon_status = 'refunded' where order_id in (select order_id from marts.fct_orders order by order_id limit 1)"]}),
    ("Card: review_created_on is the day of review_created_at",
     "ontology:column_fact marts.fct_reviews.review_created_on",
     {"sql": ["update marts.fct_reviews set review_created_on = review_created_on + 1 where review_id in (select review_id from marts.fct_reviews order by review_id limit 1)"]}),
    ("Fact: one chosen response per order that has any",
     "ontology:fact Survey responses chosen for an order (C4)",
     {"sql": ["update marts.fct_reviews set is_chosen_for_order = false where review_id in (select review_id from marts.fct_reviews where is_chosen_for_order order by review_id limit 1)"]}),
    # Coverage (ontology/coverage.py): anything the warehouse or the docs show must be described, or exempted with a reason.
    ("Coverage: removing a column card leaves the column undescribed",
     "ontology:coverage columns",
     {"yml_drop_card": "marts.fct_orders.max_installments"}),
    ("Coverage: a new warehouse column with no card fails",
     "ontology:coverage columns",
     {"sql": ["alter table marts.dim_seller add column seller_tier varchar"]}),
    ("Coverage: a new warehouse table with no card fails",
     "ontology:coverage tables",
     {"sql": ["create table marts.fct_refunds as select 1 as refund_id"]}),
    ("Coverage: a number shown in ONTOLOGY.md that ontology.yml does not hold fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_append": "\nOrders shipped in 2017: 98,765.\n"}),
    ("Coverage (S5): swapping the customer count for the late-rate denominator fails, though 94,931 exists elsewhere in the YAML",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("96,096<!--n:entities.customer.rows-->", "94,931<!--n:entities.customer.rows-->")]}),
    ("Coverage (S5): swapping the late rate for the review average fails, though 4.156 exists elsewhere in the YAML",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("6.87<!--n:metrics.late_rate.verified.value_pct-->", "4.156<!--n:metrics.late_rate.verified.value_pct-->")]}),
    ("Coverage (S5): a number with its marker removed fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("<!--n:entities.order.rows-->", "")]}),
    ("Coverage (S5): a marker that points at nothing fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("<!--n:entities.order.rows-->", "<!--n:entities.order.no_such_value-->")]}),
    ("Coverage (S5): a marker that follows no number fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_append": "\nSome words<!--n:entities.order.rows--> with no number.\n"}),
    ("Model (S6): the Model column says 'holds' for a rule no invariant checks (the reviewer's exact case)",
     "ontology:model_link The carrier gets the order after payment approval",
     {"md_replace": [("| The carrier gets the order after payment approval | not modeled |", "| The carrier gets the order after payment approval | holds |")]}),
    ("Model (S6): a card names an invariant the TLA+ model does not define",
     "ontology:model_link A delivery date exists exactly when the status is delivered",
     {"yml_replace": [("    model: not_modeled\n    sql: \"select count(*) from marts.fct_orders where (order_status = 'delivered')", "    model: {invariant: NoSuchInvariant, result: holds}\n    sql: \"select count(*) from marts.fct_orders where (order_status = 'delivered')")]}),
    ("Model (S6): a card claims a result that TLC's report does not record",
     "ontology:model_link A late order arrived after the promised day",
     {"yml_replace": [("{invariant: LateMeansArrivedAfterPromise, result: holds}", "{invariant: LateMeansArrivedAfterPromise, result: breaks}")]}),
    ("Coverage: a number shown in ONTOLOGY.md that ontology.yml only mentions in prose fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"yml_replace": [("    expected: 547\n", "    expected: 546\n")]}),
    ("Ontology fact: 547 orders have more than one survey response",
     "ontology:fact Orders with more than one survey response",
     {"sql": ["insert into marts.fct_reviews select * from marts.fct_reviews where order_id in (select order_id from marts.fct_reviews group by 1 having count(*) = 1 limit 1)"]}),
    ("Ontology fact: 789 review_ids sit on more than one order",
     "ontology:fact Survey responses (review_id) attached to more than one order",
     {"sql": ["insert into marts.fct_reviews select * replace ('zzz_fake_order' as order_id) from marts.fct_reviews where review_id in (select review_id from marts.fct_reviews group by 1 having count(distinct order_id) = 1) limit 1"]}),
    ("Coverage: an exemption with no written reason fails",
     "ontology:coverage allowlist reasons",
     {"allowlist_append": "  - match: marts.fct_orders.max_installments\n    reason: ''\n"}),
    ("Coverage (M5): a small count is edited (14 exceptions -> 41)",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [('14<!--n:stage_rules.1.expected--> exceptions', '41<!--n:stage_rules.1.expected--> exceptions')]}),
    ("Coverage (M5): a one-digit count is edited (7 sellers -> 70)",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [('7<!--n:relationships.11.orphans--> sellers', '70<!--n:relationships.11.orphans--> sellers')]}),
    ("Coverage (M5): the headline-metric row count is edited (5 -> 6)",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [('5<!--n:entities.headline_metric.rows-->', '6<!--n:entities.headline_metric.rows-->')]}),
    ("Coverage (M5): an exempt number is edited inside its phrase (29 reachable states -> 92)",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [('all 29 reachable states', 'all 92 reachable states')]}),
    ("Coverage (M5): a timestamp is edited (the cohort cutoff)",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [('The cutoff is therefore 2018-06-05 09:06:57', 'The cutoff is therefore 2018-06-06 09:06:57')]}),
    ("Coverage (M5): a duration is edited (at most 90 days -> 60)",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [('at least 24 hours and at most 90 days', 'at least 24 hours and at most 60 days')]}),
    ("Coverage (M5): a duration is edited (24 hours -> 12)",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [('a return must be 24 hours to 90 days later', 'a return must be 12 hours to 90 days later')]}),
    ("Coverage (M5): a month is edited (window end 2018-08 -> 2018-09)",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [('Full months 2017-01 through 2018-08', 'Full months 2017-01 through 2018-09')]}),
    ("Coverage (M5): number AND marker swapped together (96,096 customer -> 99,441 order) fails on the row's owner",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [('96,096<!--n:entities.customer.rows-->', '99,441<!--n:entities.order.rows-->')]}),
    ("Coverage: a new number hidden as a hyphen range (3-5) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept, with 3-5 map points.')]}),
    ("Coverage: a new number hidden as digits glued after letters (top5) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept for the top5 sellers, with no map point.')]}),
    ("Coverage: a new number hidden as a percentile label (p95) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept below p95, with no map point.')]}),
    ("Coverage: a new number hidden as a digit after an underscore (x_7) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept as x_7, with no map point.')]}),
    ("Coverage: a new number hidden as a fraction character (\u00bd) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept for ½ of zips, with no map point.')]}),
    ("Coverage: a new number hidden as a non-ASCII digit (\u0663) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept in ٣ states, with no map point.')]}),
    ("Coverage: a new number hidden as a number glued to a unit (30d) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept for 30d, with no map point.')]}),
    ("Coverage: a new number hidden as an ordinal (2nd) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept as the 2nd group, with no map point.')]}),
    ("Coverage: a new number hidden as a '..' range (3..5) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept (ids up to ..5), with no map point.')]}),
    ("Coverage: a new number hidden as a number after a colon (count:9) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept (count:9), with no map point.')]}),
    ("Coverage: a new number hidden as numbers after a comma (3,9) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept (ids 3,9), with no map point.')]}),
    ("Coverage: a new number hidden as a dotted triple (3.2.1) fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.", 'They are kept in 3.2.1 places, with no map point.')]}),
    ("Coverage: a new number hidden as a line-start 'N. ' outside a numbered list fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [("They are kept, with no map point.\n", "They are kept, with no map point.\n\n9. more orders are dropped.\n")]}),
    ("Coverage (M5): a fact marker moved to a sentence that does not name it",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"md_replace": [('17,423<!--n:facts.1.expected--> people left out', '17,423<!--n:facts.1.expected--> people dropped')]}),
    ("Coverage (M5): an exemption with a bare value and no context phrase fails",
     "ontology:coverage numbers in ONTOLOGY.md",
     {"allowlist_replace": [('context: "TLC checked all 29 reachable states"', 'context: ""')]}),
    ("Coverage: an exemption that matches nothing fails",
     "ontology:coverage allowlist is current",
     {"allowlist_append": "  - match: marts.dim_seller.no_such_column\n    reason: stale on purpose\n"}),

    # Dashboard exports (step 4): every number the dashboard prints is recomputed from the exports and tied to the analysis.
    ("Dashboard exports (review cost): the tile's extra reviews are off by 40",
     "assert_dash_review_cost_reconciles",
     {"sql": ["update exports.export_dash_summary set extra_bad_reviews = extra_bad_reviews + 40"]}),
    ("Dashboard exports (review cost): the tile's whole number reads 3,111 instead of 3,110",
     "assert_dash_review_cost_reconciles",
     {"sql": ["update exports.export_dash_summary set extra_bad_reviews_rounded = 3111"]}),
    ("Dashboard exports (review cost): the high end of the range drops by 100",
     "assert_dash_review_cost_reconciles",
     {"sql": ["update exports.export_dash_summary set extra_range_high = extra_range_high - 100"]}),
    ("Dashboard exports (review cost): 30 bad reviews move from day -5 to day 10 in the ramp (totals unchanged)",
     "assert_dash_review_cost_reconciles",
     {"sql": ["update exports.export_dash_review_ramp set bad_reviews = bad_reviews - 30 where days_past_promise_capped = -5",
              "update exports.export_dash_review_ramp set bad_reviews = bad_reviews + 30 where days_past_promise_capped = 10"]}),
    ("Dashboard exports (review cost): a day is missing from the ramp",
     "assert_dash_review_cost_reconciles",
     {"sql": ["delete from exports.export_dash_review_ramp where days_past_promise_capped = 3"]}),
    ("Dashboard exports (review cost): the points-a-day slope moves by 0.01",
     "assert_dash_review_cost_reconciles",
     {"sql": ["update exports.export_dash_summary set ramp_points_per_day = ramp_points_per_day + 0.01"]}),
    ("Dashboard exports (review cost): the summary's up-to-the-promised-day share counts day 0 as late",
     "assert_dash_review_cost_reconciles",
     {"model_edit": {"file": "models/exports/export_dash_summary.sql", "replace": [("from ramp where days_past_promise_capped <= 0) as ramp_share_up_to_promised_day", "from ramp where days_past_promise_capped < 0) as ramp_share_up_to_promised_day")], "rebuild": "export_dash_summary"}}),
    ("Dashboard exports (trend): a month's late orders are off by 10",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_monthly set late_orders = late_orders + 10 where year_month = '2018-01'"]}),
    ("Dashboard exports (trend): a month's alarm line is off by a point",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_monthly set own_month_alarm_line_late_rate = own_month_alarm_line_late_rate + 0.01 where year_month = '2018-03'"]}),
    ("Dashboard exports (trend): March 2018 loses its alarm flag",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_monthly set is_alarm_month = false where year_month = '2018-03'"]}),
    ("Dashboard exports (trend): a normal month is marked thin",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_monthly set is_thin_month = true where year_month = '2017-03'"]}),
    ("Dashboard exports (trend): a month is missing",
     "assert_dash_monthly_reconciles",
     {"sql": ["delete from exports.export_dash_monthly where year_month = '2017-06'"]}),
    ("Dashboard exports (trend): the goal line in the summary reads 5.0% instead of 4.43%",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_summary set goal_late_rate = 0.05"]}),
    ("Dashboard exports (trend): the stretch line in the summary reads 3.0% instead of the median what-if (about 3.4%)",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_summary set stretch_whatif_late_rate = 0.03"]}),
    ("Dashboard exports (trend): the monthly goal line uses the safe goal (3.04%) instead of the median (4.43%)",
     "assert_dash_monthly_reconciles",
     {"model_edit": {"file": "models/exports/export_dash_monthly.sql", "replace": [("t.goal_late_rate,", "0.03036 as goal_late_rate,")], "rebuild": "export_dash_monthly"}}),
    ("Dashboard exports (trend): the stretch line in the summary is off by a point",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_summary set stretch_whatif_late_rate = stretch_whatif_late_rate + 0.01"]}),
    ("Dashboard exports (trend): the stretch line on the monthly rows is off by a point",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_monthly set stretch_whatif_late_rate = stretch_whatif_late_rate + 0.01"]}),
    ("Dashboard exports (trend): the stretch line label in the summary is the old wording",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_summary set stretch_whatif_label = 'if seller handoffs are fixed'"]}),
    ("Dashboard exports (trend): a stable month is marked unstable",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_monthly set is_stable_month = false where year_month = '2017-09'"]}),
    ("Dashboard exports (trend): a stable month's what-if rate is off by a point",
     "assert_dash_monthly_reconciles",
     {"sql": ["update exports.export_dash_monthly set late_rate_if_handoffs_ok = late_rate_if_handoffs_ok + 0.01 where year_month = '2017-09'"]}),
    ("Dashboard exports (trend): the monthly model computes its own stretch line as the 40th percentile of the what-if instead of reading the targets model",
     "assert_dash_monthly_reconciles",
     {"model_edit": {"file": "models/exports/export_dash_monthly.sql", "replace": [("    t.stretch_goal_late_rate as stretch_whatif_late_rate\nfrom ranked r cross join t", "    (select percentile_cont(0.4) within group (order by late_rate_if_handoffs_ok) from c where not laney_signal and not thin_month) as stretch_whatif_late_rate\nfrom ranked r cross join t")], "rebuild": "export_dash_monthly+"}}),
    ("Dashboard exports (trend): the story's stretch value in facts.json drifts to the retired 2.25% (the export still matches the model, only the facts.json comparison can catch it)",
     "assert_dash_monthly_reconciles",
     {"model_edit": {"file": "story/data/facts.json", "replace": [('"stretch": 0.034251', '"stretch": 0.022520')], "rebuild": "export_dash_monthly"}}),
    ("Dashboard exports (handoff): the late-handoff bar gains 50 late orders",
     "assert_dash_handoff_reconciles",
     {"sql": ["update exports.export_dash_handoff set late_orders = late_orders + 50 where is_late_handoff"]}),
    ("Dashboard exports (handoff): the on-time-handoff bar loses 100 orders",
     "assert_dash_handoff_reconciles",
     {"sql": ["update exports.export_dash_handoff set orders = orders - 100 where not is_late_handoff"]}),
    ("Dashboard exports (handoff): the tile's share of late orders is off by a point",
     "assert_dash_handoff_reconciles",
     {"sql": ["update exports.export_dash_summary set late_handoff_share_of_late = late_handoff_share_of_late + 0.01"]}),
    ("Dashboard exports (handoff): the order with no handoff time is counted as an on-time handoff",
     "assert_dash_handoff_reconciles",
     {"model_edit": {"file": "models/exports/export_dash_handoff.sql", "replace": [("    where handed_over_late is not null\n", "")], "rebuild": "export_dash_handoff"}}),
    ("Dashboard exports (handoff): the handoff rule allows a day of grace in the shared order base",
     "assert_dash_handoff_reconciles",
     {"model_edit": {"file": "models/exports/dash_order_base.sql", "replace": [("f.delivered_to_carrier_at > f.last_shipping_limit_at as", "f.delivered_to_carrier_at > f.last_shipping_limit_at + interval 1 day as")], "rebuild": "dash_order_base+"}}),
    ("Dashboard exports (sellers): the top seller loses one late order",
     "assert_dash_sellers_reconcile",
     {"sql": ["update exports.export_dash_sellers set late_after_late_handoff_orders = late_after_late_handoff_orders - 1 where rank_by_late_after_late_handoff = 1"]}),
    ("Dashboard exports (sellers): a seller is missing",
     "assert_dash_sellers_reconcile",
     {"sql": ["delete from exports.export_dash_sellers where rank_by_late_after_late_handoff = 100"]}),
    ("Dashboard exports (sellers): a seller appears twice",
     "assert_dash_sellers_reconcile",
     {"sql": ["insert into exports.export_dash_sellers select * from exports.export_dash_sellers where rank_by_late_after_late_handoff = 5"]}),
    ("Dashboard exports (sellers): two sellers share an 8-character code",
     "assert_dash_sellers_reconcile",
     {"sql": ["update exports.export_dash_sellers set seller_code = (select seller_code from exports.export_dash_sellers where rank_by_late_after_late_handoff = 1) where rank_by_late_after_late_handoff = 11"]}),
    ("Dashboard exports (sellers): the tile's top-10 share is off by 5 points",
     "assert_dash_sellers_reconcile",
     {"sql": ["update exports.export_dash_summary set top10_share_of_late_after_late_handoff = top10_share_of_late_after_late_handoff + 0.05"]}),
    ("Dashboard exports (sellers): the seller bars count all late orders, not only those after a late handoff",
     "assert_dash_sellers_reconcile",
     {"model_edit": {"file": "models/exports/export_dash_sellers.sql", "replace": [("count(*) filter (where handed_over_late and is_late) as late_after_late_handoff_orders", "count(*) filter (where is_late) as late_after_late_handoff_orders")], "rebuild": "export_dash_sellers+"}}),
    ("Dashboard exports (sellers): the top-10 flag covers 11 sellers",
     "assert_dash_sellers_reconcile",
     {"model_edit": {"file": "models/exports/export_dash_sellers.sql", "replace": [("rank_by_late_after_late_handoff <= 10 as is_top10", "rank_by_late_after_late_handoff <= 11 as is_top10")], "rebuild": "export_dash_sellers"}}),
    ("Dashboard exports (sellers): an order gains a second seller",
     "assert_dash_sellers_reconcile",
     {"sql": ["insert into marts.fct_order_items select * replace ('zzz_second_seller' as seller_id) from marts.fct_order_items where order_id in (select order_id from metrics.metric_late_rate_orders order by order_id limit 1) limit 1"]}),
    ("Dashboard exports (region): the north and northeast lose 100 late orders",
     "assert_dash_region_reconciles",
     {"sql": ["update exports.export_dash_region set late_orders = late_orders - 100 where region_group = 'North and northeast'"]}),
    ("Dashboard exports (region): a state is missing from the region map",
     "assert_dash_region_reconciles",
     {"sql": ["delete from seeds.dash_region_map where state = 'AC'"]}),
    ("Dashboard exports (region): a state is listed twice in the region map",
     "assert_dash_region_reconciles",
     {"sql": ["insert into seeds.dash_region_map select * from seeds.dash_region_map where state = 'SP'"]}),
    ("Dashboard exports (region): Bahia moves to the rest of Brazil in the region map",
     "assert_dash_region_reconciles",
     {"sql": ["update seeds.dash_region_map set region_group = 'Rest of Brazil' where state = 'BA'"]}),
    ("Dashboard exports (region): the tile's north and northeast rate is off by a point",
     "assert_dash_region_reconciles",
     {"sql": ["update exports.export_dash_summary set nne_late_rate = nne_late_rate + 0.01"]}),
    ("Dashboard exports (worst months): the flags name a different month (Feb 2018 out, Apr 2018 in)",
     "assert_dash_worst_months_reconcile",
     {"sql": ["update exports.export_dash_monthly set is_worst3_late_month = not is_worst3_late_month where year_month in ('2018-02', '2018-04')"]}),
    ("Dashboard exports (worst months): the label names Jan 2018 instead of Feb 2018",
     "assert_dash_worst_months_reconcile",
     {"sql": ["update exports.export_dash_summary set worst3_months_label = 'Nov 2017, Jan 2018 and Mar 2018'"]}),
    ("Dashboard exports (worst months): the 48.3% reads 50%",
     "assert_dash_worst_months_reconcile",
     {"sql": ["update exports.export_dash_summary set worst3_share_of_late = 0.5"]}),
    ("Dashboard exports (worst months): a month label is wrong (Nov 2017 reads Dec 2017)",
     "assert_dash_worst_months_reconcile",
     {"sql": ["update exports.export_dash_monthly set month_label = 'Dec 2017' where year_month = '2017-11'"]}),
    ("Dashboard exports (worst months): the worst-months flag covers four months",
     "assert_dash_worst_months_reconcile",
     {"model_edit": {"file": "models/exports/export_dash_monthly.sql", "replace": [("r.late_orders_rank <= 3 as", "r.late_orders_rank <= 4 as")], "rebuild": "export_dash_monthly+"}}),
    ("Dashboard exports (example tests panel): a row loses its example flag",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["update exports.export_dash_tests_example set is_example = false where test_id = 1"]}),
    ("Dashboard exports (example tests panel): a row's example flag is null",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["update exports.export_dash_tests_example set is_example = null where test_id = 2"]}),
    ("Dashboard exports (example tests panel): a value loses its asterisk",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["update exports.export_dash_tests_example set test_group_display = '6.1%' where test_id = 1"]}),
    ("Dashboard exports (example tests panel): the banner stops saying the tests have not run",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["update exports.export_dash_tests_example set banner = 'Fix tests'"]}),
    ("Dashboard exports (example tests panel): a seed row loses its example flag",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["update seeds.dash_tests_example set is_example = false where test_id = 2"]}),
    ("Dashboard exports (example tests panel): a row's status reads passed",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["update exports.export_dash_tests_example set status = 'passed' where test_id = 1"]}),
    ("Dashboard exports (example tests panel): a test label loses the word EXAMPLE",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["update exports.export_dash_tests_example set test_label = 'Seller ship-by reminder test' where test_id = 1"]}),
    ("Dashboard exports (example tests panel): a row is missing from the export",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["delete from exports.export_dash_tests_example where test_id = 2"]}),
    ("Dashboard exports (column sweep, monthly): month_start shifts a month",
     "assert_dash_columns_are_derived",
     {"sql": ["update exports.export_dash_monthly set month_start = date '2017-07-01' where year_month = '2017-06'"]}),
    ("Dashboard exports (column sweep, monthly): a month label reads Jun 2019 on a month that is not the worst",
     "assert_dash_columns_are_derived",
     {"sql": ["update exports.export_dash_monthly set month_label = 'Jun 2019' where year_month = '2017-06'"]}),
    ("Dashboard exports (column sweep, monthly): a month's late-orders rank is off by one",
     "assert_dash_columns_are_derived",
     {"sql": ["update exports.export_dash_monthly set late_orders_rank = late_orders_rank + 1 where year_month = '2017-01'"]}),
    ("Dashboard exports (column sweep, monthly): a month that is not one of the worst three is flagged worst",
     "assert_dash_columns_are_derived",
     {"sql": ["update exports.export_dash_monthly set is_worst3_late_month = true where year_month = '2017-06'"]}),
    ("Dashboard exports (column sweep, monthly): an alarm month is flagged stable",
     "assert_dash_columns_are_derived",
     {"sql": ["update exports.export_dash_monthly set is_stable_month = true where year_month = '2018-03'"]}),
    ("Dashboard exports (column sweep, monthly): a month's late rate is 50%",
     "assert_dash_columns_are_derived",
     {"sql": ["update exports.export_dash_monthly set late_rate = 0.5 where year_month = '2017-06'"]}),
    ("Dashboard exports (column sweep, monthly): a month's share of all late orders is off by a point",
     "assert_dash_columns_are_derived",
     {"sql": ["update exports.export_dash_monthly set share_of_all_late = share_of_all_late + 0.01 where year_month = '2017-06'"]}),
    ("Dashboard exports (column sweep, review_ramp): day 3 is called levelled instead of climbing",
     "assert_dash_columns_are_derived",
     {"sql": ["update exports.export_dash_review_ramp set phase = 'levelled' where days_past_promise_capped = 3"]}),
    ("Dashboard exports (column sweep, review_ramp): a day's bad-review share is off by a point",
     "assert_dash_columns_are_derived",
     {"sql": ['update exports.export_dash_review_ramp set bad_review_share = bad_review_share + 0.01 where days_past_promise_capped = 3']}),
    ("Dashboard exports (column sweep, review_ramp): a day has more bad reviews than reviewed orders",
     "assert_dash_columns_are_derived",
     {"sql": ['update exports.export_dash_review_ramp set bad_reviews = reviewed_orders + 1 where days_past_promise_capped = 3']}),
    ("Dashboard exports (column sweep, summary): the summary's judged orders gain 1,000",
     "assert_dash_columns_are_derived",
     {"sql": ['update exports.export_dash_summary set judged_orders = judged_orders + 1000']}),
    ("Dashboard exports (column sweep, summary): the summary's late orders gain 1",
     "assert_dash_columns_are_derived",
     {"sql": ['update exports.export_dash_summary set late_orders = late_orders + 1']}),
    ("Dashboard exports (column sweep, summary): the summary's late rate is off by 0.2 points",
     "assert_dash_columns_are_derived",
     {"sql": ['update exports.export_dash_summary set late_rate = late_rate + 0.002']}),
    ("Dashboard exports (column sweep, summary): the latest month is not the last month",
     "assert_dash_columns_are_derived",
     {"sql": ["update exports.export_dash_summary set latest_month = '2018-07'"]}),
    ("Dashboard exports (column sweep, summary): the latest month's label reads Aug 2019",
     "assert_dash_columns_are_derived",
     {"sql": ["update exports.export_dash_summary set latest_month_label = 'Aug 2019'"]}),
    ("Dashboard exports (column sweep, sellers): a mid-table seller's late rate is 0",
     "assert_dash_sellers_reconcile",
     {"sql": ['update exports.export_dash_sellers set late_rate = 0 where rank_by_late_after_late_handoff = 500']}),
    ("Dashboard exports (column sweep, sellers): a seller's late-handoff rate is off by a point",
     "assert_dash_sellers_reconcile",
     {"sql": ['update exports.export_dash_sellers set late_handoff_rate = late_handoff_rate + 0.01 where rank_by_late_after_late_handoff = 500']}),
    ("Dashboard exports (column sweep, sellers): a seller's rank is off by one",
     "assert_dash_sellers_reconcile",
     {"sql": ['update exports.export_dash_sellers set rank_by_late_after_late_handoff = rank_by_late_after_late_handoff + 1000 where rank_by_late_after_late_handoff = 500']}),
    ("Dashboard exports (column sweep, sellers): a seller outside the top 10 is flagged top 10",
     "assert_dash_sellers_reconcile",
     {"sql": ['update exports.export_dash_sellers set is_top10 = true where rank_by_late_after_late_handoff = 500']}),
    ("Dashboard exports (column sweep, sellers): a seller's share of late-after-late-handoff orders is off by a point",
     "assert_dash_sellers_reconcile",
     {"sql": ['update exports.export_dash_sellers set share_of_late_after_late_handoff = share_of_late_after_late_handoff + 0.01 where rank_by_late_after_late_handoff = 500']}),
    ("Dashboard exports (column sweep, sellers): a seller's 8-character code is another seller's",
     "assert_dash_sellers_reconcile",
     {"sql": ["update exports.export_dash_sellers set seller_code = '16a2c3af' where rank_by_late_after_late_handoff = 500"]}),
    ("Dashboard exports (column sweep, summary): the summary's top seller count reads 67 instead of 66",
     "assert_dash_sellers_reconcile",
     {"sql": ['update exports.export_dash_summary set top_seller_late_after_late_handoff_orders = 67']}),
    ("Dashboard exports (column sweep, summary): the summary's top 10 count is off by one",
     "assert_dash_sellers_reconcile",
     {"sql": ['update exports.export_dash_summary set top10_late_after_late_handoff_orders = top10_late_after_late_handoff_orders + 1']}),
    ("Dashboard exports (column sweep, handoff): the two handoff groups swap names",
     "assert_dash_handoff_reconciles",
     {"sql": ["update exports.export_dash_handoff set handoff_group = case when is_late_handoff then 'Handed over on time' else 'Handed to carrier after ship-by' end"]}),
    ("Dashboard exports (column sweep, handoff): the on-time handoff bar's share of late orders is off by a point",
     "assert_dash_handoff_reconciles",
     {"sql": ['update exports.export_dash_handoff set share_of_all_late = share_of_all_late + 0.01 where not is_late_handoff']}),
    ("Dashboard exports (column sweep, summary): the three months' share of all orders reads 25%",
     "assert_dash_worst_months_reconcile",
     {"sql": ['update exports.export_dash_summary set worst3_share_of_orders = 0.25']}),
    ("Dashboard exports (column sweep, summary): the three months' share of all orders is off by 0.001",
     "assert_dash_worst_months_reconcile",
     {"sql": ['update exports.export_dash_summary set worst3_share_of_orders = worst3_share_of_orders + 0.001']}),
    ("Dashboard exports (column sweep, summary): the three months' share of all months reads 20%",
     "assert_dash_worst_months_reconcile",
     {"sql": ['update exports.export_dash_summary set worst3_share_of_months = 0.20']}),
    ("Dashboard exports (column sweep, monthly): a worst month holds more orders than the story month table says (orders +1,000)",
     "assert_dash_worst_months_reconcile",
     {"sql": ["update exports.export_dash_monthly set orders = orders + 1000 where year_month = '2018-03'"]}),
    ("Dashboard exports (column sweep, tests_example): a test-group value drifts from the seed",
     "assert_dash_tests_are_labelled_example",
     {"sql": ['update exports.export_dash_tests_example set test_group_value = test_group_value + 0.5 where test_id = 1']}),
    ("Dashboard exports (column sweep, tests_example): a no-change value drifts from the seed",
     "assert_dash_tests_are_labelled_example",
     {"sql": ['update exports.export_dash_tests_example set no_change_group_value = no_change_group_value + 0.5 where test_id = 2']}),
    ("Dashboard exports (column sweep, tests_example): a readout label is not the seed's",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["update exports.export_dash_tests_example set readout_label = 'EXAMPLE: something else' where test_id = 1"]}),
    ("Dashboard exports (column sweep, tests_example): a no-change display reads 3.92 for a percent row",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["update exports.export_dash_tests_example set no_change_group_display = '3.92' where test_id = 1"]}),
    ("Dashboard exports (column sweep, tests_example): the footnote stops saying the numbers are invented",
     "assert_dash_tests_are_labelled_example",
     {"sql": ["update exports.export_dash_tests_example set footnote = '* measured'"]}),
    ("Dashboard exports (shape): the monthly export loses a month (row count 20)",
     "export_dash_monthly,test_name:expect_table_row_count_to_equal",
     {"sql": ["delete from exports.export_dash_monthly where year_month = '2017-06'"]}),
    ("Dashboard exports (shape): a seller appears twice (unique seller_id)",
     "export_dash_sellers,test_name:unique",
     {"sql": ["insert into exports.export_dash_sellers select * from exports.export_dash_sellers where rank_by_late_after_late_handoff = 5"]}),
    ("Dashboard exports (shape): a ramp phase has a name the chart does not know",
     "export_dash_review_ramp,test_name:accepted_values",
     {"sql": ["update exports.export_dash_review_ramp set phase = 'plateau' where days_past_promise_capped = 12"]}),
    ("Dashboard exports (shape): a seller in the export is not in dim_seller",
     "export_dash_sellers,test_name:relationships",
     {"sql": ["update exports.export_dash_sellers set seller_id = 'zzz_unknown_seller' where rank_by_late_after_late_handoff = 7"]}),
]

# Titles: the story and memo titles say "linked to", not cause; story/check_titles.py
CASES += [
    ("Titles: the story title says 'cause' again",
     "titles:story title",
     {"title_replace": [("story", "Late deliveries are linked to about a quarter", "Late deliveries cause about a quarter")]}),
    ("Titles: the story title says 'caused'",
     "titles:story title",
     {"title_replace": [("story", "Late deliveries are linked to about a quarter", "Late deliveries caused about a quarter")]}),
    ("Titles: the story title keeps 'linked to' but adds 'cause'",
     "titles:story title",
     {"title_replace": [("story", "Late deliveries are linked to about a quarter", "Late deliveries are linked to, and cause, about a quarter")]}),
    ("Titles: the story title drops 'linked to' for another verb",
     "titles:story title",
     {"title_replace": [("story", "Late deliveries are linked to about a quarter", "Late deliveries are behind about a quarter")]}),
    ("Titles: the story subtitle says 'causing'",
     "titles:story subtitle",
     {"title_replace": [("story", 'subtitle: "Where they come from,', 'subtitle: "What is causing them,')]}),
    ("Titles: the memo title says 'causes'",
     "titles:memo title",
     {"title_replace": [("memo", "# Late deliveries are linked to about a quarter", "# Late deliveries causes about a quarter")]}),
    # review finding 6: the wider cause wording, and the memo title must say 'linked to' too
    ("Titles: the memo title says 'causal'",
     "titles:memo title",
     {"title_replace": [("memo", "# Late deliveries are linked to about a quarter", "# Late deliveries are a causal link to about a quarter")]}),
    ("Titles: the memo title says 'drives'",
     "titles:memo title",
     {"title_replace": [("memo", "# Late deliveries are linked to about a quarter", "# Late deliveries drives about a quarter")]}),
    ("Titles: the story title says 'driven by'",
     "titles:story title",
     {"title_replace": [("story", "Late deliveries are linked to about a quarter", "Late deliveries are linked to, and driven by, about a quarter")]}),
    ("Titles: the story title says 'results in'",
     "titles:story title",
     {"title_replace": [("story", "Late deliveries are linked to about a quarter", "Late deliveries results in about a quarter")]}),
    ("Titles: the memo title says 'leads to'",
     "titles:memo title",
     {"title_replace": [("memo", "# Late deliveries are linked to about a quarter", "# Late deliveries leads to about a quarter")]}),
    ("Titles: the memo title says 'triggers'",
     "titles:memo title",
     {"title_replace": [("memo", "# Late deliveries are linked to about a quarter", "# Late deliveries triggers about a quarter")]}),
    ("Titles: the story title says 'responsible for'",
     "titles:story title",
     {"title_replace": [("story", "Late deliveries are linked to about a quarter", "Late deliveries are linked to, and responsible for, about a quarter")]}),
    ("Titles: the memo title drops 'linked to' for a neutral verb",
     "titles:memo title",
     {"title_replace": [("memo", "# Late deliveries are linked to about a quarter", "# Late deliveries go with about a quarter")]}),
]

# Stretch line: the median stable month under the handoff what-if, like for like with the 4.4% goal.
STRETCH = "(select percentile_cont(0.5) within group (order by late_rate_if_handoffs_ok) from stable) as stretch_goal_late_rate"
CASES += [
    ("Stretch: the stretch line goes back to the retired 25th percentile (2.25%)",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_targets.sql", "replace": [(STRETCH, STRETCH.replace("0.5", "0.25"))], "rebuild": "metric_late_rate_targets"}}),
    ("Stretch: the stretch line uses the real late rate, so the what-if is gone",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_targets.sql", "replace": [(STRETCH, STRETCH.replace("late_rate_if_handoffs_ok", "late_rate"))], "rebuild": "metric_late_rate_targets"}}),
    ("Stretch: the stretch line takes every month, not just the stable ones",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_targets.sql", "replace": [(STRETCH, STRETCH.replace("from stable", "from months"))], "rebuild": "metric_late_rate_targets"}}),
    ("Stretch: the Python refit report's stretch value drifts from the dbt model (3.4251% -> 2.2520%)",
     "assert_late_rate_targets_match_the_python_refit",
     {"model_edit": {"file": "evidence/late_rate_targets_report.json", "replace": [('"stretch_median_if_handoffs_ok": 0.03425141242937853', '"stretch_median_if_handoffs_ok": 0.02251969271900082')], "rebuild": "metric_late_rate_targets"}}),
    ("Stretch: the stretch line uses the 60th percentile of the what-if months",
     "metric_late_rate_control_chart+",
     {"model_edit": {"file": "models/metrics/metric_late_rate_targets.sql", "replace": [(STRETCH, STRETCH.replace("0.5", "0.6"))], "rebuild": "metric_late_rate_targets"}}),
]

DOC_EDITS = ("yml_drop_card", "yml_replace", "md_replace", "md_append", "allowlist_append", "allowlist_replace")   # every key edited_docs reads


def edited_docs(mut, work):
    """Env vars pointing the ontology check at edited copies of ontology.yml, ONTOLOGY.md and the coverage allowlist."""
    o = os.path.join(ROOT, "ontology")
    yml, md, allow = (open(os.path.join(o, f)).read() for f in ("ontology.yml", "ONTOLOGY.md", "coverage_allowlist.yml"))
    if "yml_drop_card" in mut:                       # remove one `columns:` card (its key line and indented body)
        key = mut["yml_drop_card"]
        lines, out, skip = yml.splitlines(keepends=True), [], False
        for l in lines:
            if l.startswith(f"  {key}:"):
                skip = True
                continue
            if skip and l.startswith("    "):
                continue
            skip = False
            out.append(l)
        assert len(out) < len(lines), f"no card {key}"
        yml = "".join(out)
    for old, new in mut.get("yml_replace", []):      # edit a value in the copy of ontology.yml
        assert old in yml, f"no {old!r} in ontology.yml"
        yml = yml.replace(old, new, 1)
    for old, new in mut.get("md_replace", []):       # edit the prose in the copy of ONTOLOGY.md
        assert old in md, f"no {old!r} in ONTOLOGY.md"
        md = md.replace(old, new, 1)
    md += mut.get("md_append", "")
    allow += mut.get("allowlist_append", "")
    for old, new in mut.get("allowlist_replace", []):  # edit an exemption in the copy of the allowlist
        assert old in allow, f"no {old!r} in coverage_allowlist.yml"
        allow = allow.replace(old, new, 1)
    env = {}
    for var, name, text in (("ONTOLOGY_YML", "ontology.yml", yml), ("ONTOLOGY_MD", "ONTOLOGY.md", md), ("COVERAGE_ALLOWLIST", "allow.yml", allow)):
        path = os.path.join(work, name)
        open(path, "w").write(text)
        env[var] = path
    return env

def run_ontology_claim(claim, db, extra_env=None):
    env = dict(os.environ, OLIST_DB_PATH=db, ONTOLOGY_NO_REPORT="1", **(extra_env or {}))
    p = subprocess.run([sys.executable, os.path.join(ROOT, "ontology", "check.py"), "--skip-semantic"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    kind, name = claim.split(" ", 1)
    hits = [l for l in p.stdout.splitlines() if l[6:].startswith(f"{kind:12s} {name}:")]
    res = [(claim, "pass" if l.startswith("PASS") else "fail", l.split(": ", 1)[1]) for l in hits]
    return (0 if res and all(r[1] == "pass" for r in res) else 1), res

TITLE_FILES = {"story": ("STORY_QMD", os.path.join("story", "story.qmd")), "memo": ("MEMO_MD", os.path.join("recommendation", "MEMO.md"))}

def edited_titles(mut, work):
    """Env vars pointing story/check_titles.py at edited copies of story.qmd and MEMO.md."""
    env = {}
    for which, old, new in mut["title_replace"]:
        var, rel = TITLE_FILES[which]
        path = env.get(var) or os.path.join(ROOT, rel)
        text = open(path).read()
        assert old in text, f"no {old!r} in {rel}"
        out = os.path.join(work, os.path.basename(rel))
        open(out, "w").write(text.replace(old, new, 1))
        env[var] = out
    return env

def run_title_check(name, extra_env=None):
    env = dict(os.environ, **(extra_env or {}))
    p = subprocess.run([sys.executable, os.path.join(ROOT, "story", "check_titles.py")], cwd=ROOT, env=env, capture_output=True, text=True)
    hits = [l for l in p.stdout.splitlines() if l[6:].startswith(f"title {name}:")]
    res = [(f"title {name}", "pass" if l.startswith("PASS") else "fail", l.split(": ", 1)[1]) for l in hits]
    return (0 if res and all(r[1] == "pass" for r in res) else 1), res

WORKER_SCRIPT = os.path.join(ROOT, "scripts", "dbt_test_worker.py")
USE_WORKER = os.environ.get("PROVE_NO_WORKER", "") == ""   # PROVE_NO_WORKER=1: one `dbt test` process per run, the slow way (to compare)

def wants_worker(selector, mut):
    """dbt-test cases that leave the project files and the raw files alone can share a parsed project (see dbt_test_worker.py)."""
    return USE_WORKER and not selector.startswith(("ontology:", "titles:")) and "raw_edit" not in mut and "model_edit" not in mut

class DbtWorker:
    """One warm `dbt test` process with its own warehouse file, named olist.duckdb so every run compiles against the same database name."""
    def __init__(self, slot):
        os.makedirs(slot)
        self.db = os.path.join(slot, "olist.duckdb")
        self.fresh_db()
        env = dict(os.environ, OLIST_DB_PATH=self.db, OLIST_RAW_DIR=os.path.abspath(RAW), DBT_PROFILES_DIR=ROOT)
        self.proc = subprocess.Popen([sys.executable, WORKER_SCRIPT, os.path.join(slot, "target")], cwd=ROOT, env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def fresh_db(self):
        """An untouched copy of the warehouse at this worker's fixed path."""
        shutil.copy(DB, self.db)
        return self.db

    def run(self, selector):
        self.proc.stdin.write(json.dumps({"selector": selector}) + "\n"); self.proc.stdin.flush()
        for line in self.proc.stdout:
            if line.startswith("@@RESULT@@"):
                out = json.loads(line[len("@@RESULT@@"):])
                assert "error" not in out, f"dbt worker failed on {selector!r}: {out['error']}"
                # same shape as run_tests: the test's name, its status, its failing-row count
                for uid, st, fl, msg in out["results"]:
                    if st == "error":   # an error is not a failing check: show why, so a broken run is not mistaken for a proof
                        print(f"  dbt error in {uid} ({selector}): {msg}", file=sys.stderr, flush=True)
                return out["rc"], [(uid.split(".")[-2] if uid.count(".") > 2 else uid, st, fl) for uid, st, fl, _ in out["results"]]
        raise RuntimeError(f"dbt worker exited while running {selector!r}")

    def close(self):
        self.proc.stdin.close(); self.proc.wait(timeout=60)

def run_tests(selector, db, raw, extra_env=None, proj=None):
    proj = proj or ROOT
    if selector.startswith("titles:"):
        return run_title_check(selector[len("titles:"):], extra_env)
    if selector.startswith("ontology:"):
        return run_ontology_claim(selector[len("ontology:"):], db, extra_env)
    env = dict(os.environ, OLIST_DB_PATH=db, OLIST_RAW_DIR=raw, DBT_PROFILES_DIR=proj)
    tp = tempfile.mkdtemp(prefix="dbt-target-")
    p = subprocess.run([DBT, "test", "--select", selector, "--target-path", tp, "--quiet"],
                       cwd=proj, env=env, capture_output=True, text=True)
    try:
        res = json.load(open(os.path.join(tp, "run_results.json")))["results"]
    except Exception:
        res = []
    shutil.rmtree(tp, ignore_errors=True)
    return p.returncode, [(r["unique_id"].split(".")[-2] if r["unique_id"].count(".") > 2 else r["unique_id"], r["status"], r.get("failures")) for r in res]

PROJECT_FILES = ("dbt_project.yml", "profiles.yml", "packages.yml", "package-lock.yml", "models", "macros", "tests", "seeds", "evidence", "story/data", "dbt_packages")

def project_copy(edit, work):
    """A copy of the dbt project (only what dbt needs) with one model file edited; the real files are never touched."""
    d = tempfile.mkdtemp(prefix="proj-mut-", dir=work)
    for name in PROJECT_FILES:
        src = os.path.join(ROOT, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(d, name), symlinks=True)
        elif os.path.exists(src):
            shutil.copy(src, os.path.join(d, name))
    path = os.path.join(d, edit["file"]); text = open(path).read()
    for old, new in edit["replace"]:
        assert old in text, f"no {old!r} in {edit['file']}"
        text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    assert text != open(os.path.join(ROOT, edit["file"])).read(), "the edit changed nothing"
    open(path, "w").write(text)
    return d

def rebuild_models(proj, selector, db, raw):
    """Rebuild the edited model (and what depends on it) inside the project copy, against the copied warehouse."""
    env = dict(os.environ, OLIST_DB_PATH=db, OLIST_RAW_DIR=raw, DBT_PROFILES_DIR=proj)
    p = subprocess.run([DBT, "run", "--select", selector, "--target-path", os.path.join(proj, "target"), "--quiet"],
                       cwd=proj, env=env, capture_output=True, text=True)
    assert p.returncode == 0, f"rebuild of {selector} failed:\n{p.stdout[-1500:]}"

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

def write_evidence(report):
    os.makedirs(os.path.join(ROOT, "evidence"), exist_ok=True)
    json.dump(report, open(os.path.join(ROOT, "evidence", "mutation_report.json"), "w"), indent=1)
    with open(os.path.join(ROOT, "evidence", "mutation_report.md"), "w") as f:
        f.write("# Business-rule tests: proof that each one can fail\n\n")
        f.write("Each rule's tests pass on the real warehouse (baseline) and fail after known-bad rows are injected into a copy (mutant).\n\n")
        f.write("| Rule | Tests | Known-bad rows injected | Baseline | Mutant (failing rows) | Verdict |\n|---|---|---|---|---|---|\n")
        for r in report:
            m = r["mutation"]
            mut = m.get("sql") or [f"{k}: {m[k]}" for k in ("raw_edit", "model_edit", "title_replace") + DOC_EDITS if k in m]
            f.write(f"| {r['rule']} | `{r['selector']}` | {'<br>'.join('`'+m.replace('|','\\|')+'`' for m in mut)} | "
                    f"{', '.join(s for _, s, _ in r['baseline'])} | {', '.join(f'{s} ({n})' for _, s, n in r['mutant'])} | **{r['verdict']}** |\n")

MERGE = "--merge" in sys.argv   # with a filter: write the selected rules into evidence/ instead of leaving it alone


def main():
    if not os.path.exists(DB):
        sys.exit(f"no warehouse at {DB}; run `make build` first")
    work = tempfile.mkdtemp(prefix="mutation-")
    only = next((a for a in sys.argv[1:] if not a.startswith("--")), "")   # optional substring filter on the rule name (quick reruns)
    selected = [c for c in CASES if only in c[0]]
    # The baseline (real warehouse, real raw files) does not depend on the mutation, so each selector is run once and shared.
    baselines, locks, guard = {}, {}, threading.Lock()
    mine, workers = threading.local(), []   # each pool thread owns one warm dbt process and its warehouse file

    def my_worker():
        if getattr(mine, "w", None) is None:
            with guard:
                mine.w = DbtWorker(os.path.join(work, f"slot-{len(workers)}")); workers.append(mine.w)
        return mine.w

    def baseline(selector):
        with guard:
            lock = locks.setdefault(selector, threading.Lock())
        with lock:
            if selector not in baselines:
                if wants_worker(selector, {}):
                    w = my_worker(); w.fresh_db()
                    baselines[selector] = w.run(selector)
                else:
                    d = tempfile.mkdtemp(prefix="base-", dir=work)
                    base_db = os.path.join(d, "baseline.duckdb"); shutil.copy(DB, base_db)
                    raw_clean = raw_copy(None)
                    baselines[selector] = run_tests(selector, base_db, raw_clean)
                    os.remove(base_db); shutil.rmtree(raw_clean, ignore_errors=True)
            return baselines[selector]

    def run_case(case):
        rule, selector, mut = case
        t0 = time.time()
        b_rc, b_res = baseline(selector)
        cdir = tempfile.mkdtemp(prefix="case-", dir=work)
        w = my_worker() if wants_worker(selector, mut) else None
        if w:
            mut_db, raw_mut = w.fresh_db(), None
        else:
            mut_db = os.path.join(cdir, "mutant.duckdb"); shutil.copy(DB, mut_db)
            raw_mut = raw_copy(mut.get("raw_edit"))
        doc_env = edited_docs(mut, cdir) if set(DOC_EDITS) & set(mut) else None
        if "title_replace" in mut:
            doc_env = edited_titles(mut, cdir)
        if "sql" in mut:
            con = duckdb.connect(mut_db)
            for stmt in mut["sql"]:
                con.execute(stmt)
            con.close()
        proj = None
        if "model_edit" in mut:
            proj = project_copy(mut["model_edit"], cdir)
            rebuild_models(proj, mut["model_edit"]["rebuild"], mut_db, raw_mut)
        m_rc, m_res = w.run(selector) if w else run_tests(selector, mut_db, raw_mut, doc_env, proj)
        shutil.rmtree(cdir, ignore_errors=True)
        if raw_mut: shutil.rmtree(raw_mut, ignore_errors=True)
        base_ok = b_rc == 0 and b_res and all(st == "pass" for _, st, _ in b_res)
        mut_fail = m_rc != 0 and any(st == "fail" for _, st, _ in m_res)   # an error is a broken run, not a test that caught the mistake
        verdict = "PROVEN" if (base_ok and mut_fail) else "NOT PROVEN"
        print(f"{verdict:11s} {time.time() - t0:5.1f}s {rule}  baseline={len(b_res)} tests, all pass: {base_ok} | mutant failing: {[(n, st, f) for n, st, f in m_res if st != 'pass']}", flush=True)
        return {"rule": rule, "selector": selector, "mutation": mut, "baseline": sorted(b_res),
                "mutant": sorted(m_res), "verdict": verdict}   # sorted, and no timings, so a rerun writes the same file

    # Cases are independent (own warehouse copy, own project copy, own dbt target path), so run a few at once.
    # PROVE_JOBS=1 runs them one by one. The report keeps the order of CASES.
    jobs = max(1, int(os.environ.get("PROVE_JOBS", min(4, os.cpu_count() or 1))))
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        report = list(pool.map(run_case, selected))
    for w in workers: w.close()
    shutil.rmtree(work, ignore_errors=True)
    if only and MERGE:
        # Add or replace just these rules in the committed report, keeping the order of CASES (what a full run would write).
        path = os.path.join(ROOT, "evidence", "mutation_report.json")
        old_report = {r["rule"]: r for r in json.load(open(path))}
        new_report = {r["rule"]: r for r in report}
        merged = [new_report.get(rule) or old_report[rule] for rule, _, _ in CASES if rule in new_report or rule in old_report]
        for r, (_, _, mut) in zip(merged, [c for c in CASES if c[0] in new_report or c[0] in old_report]):
            r["mutation"] = mut   # JSON turns tuples into lists; keep the text of the rows already in the report unchanged
        write_evidence(merged)
        bad = [r for r in report if r["verdict"] != "PROVEN"]
        print(f"\n{len(report) - len(bad)}/{len(report)} selected rules proven; merged into evidence/ ({len(merged)} rules in the report)")
        sys.exit(1 if bad else 0)
    if only:
        bad = [r for r in report if r["verdict"] != "PROVEN"]
        print(f"\n{len(report) - len(bad)}/{len(report)} selected rules proven (evidence/ not rewritten)")
        sys.exit(1 if bad else 0)
    write_evidence(report)
    bad = [r for r in report if r["verdict"] != "PROVEN"]
    print(f"\n{len(report) - len(bad)}/{len(report)} rules proven able to fail")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
