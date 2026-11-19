# Olist e-commerce analytics (dbt + DuckDB)

## In plain language

Olist is a Brazilian online marketplace. This project takes about 99,000 of its real orders from 2016 to 2018 and turns nine messy spreadsheets into a set of organized, checked tables that a business can trust. The data had several traps. Every order got a new customer ID, so repeat buyers looked like strangers. Orders with several sellers were marked delivered on one date even though the packages arrive separately. Some review surveys went out, and some were answered, before the recorded delivery, because Olist emails the survey on the promised date when the order is late.

The main finding is that late delivery goes with much worse reviews. Orders that arrive late score about 2 stars lower than on-time orders, and only 6.87% of orders are late. That raw comparison alone does not show cause, because late orders may differ in other ways. So [review_cost_causal/](review_cost_causal/README.md) compares each late order with the same seller's orders that arrived just on time, in the same product category and month. Late delivery is the estimated cause of about 3,110 of the 11,635 one- and two-star reviews, about 27%, with a range of 2,880 to 3,350. That is an estimate from past orders, not a randomized test. Only 1.28% of customers place a second order within 90 days.

[recommendation/MEMO.md](recommendation/MEMO.md) turns that into a decision for an operations manager: what late delivery costs, where it clusters, and two changes Olist could test. The cost shows up in ratings. A late first order shows no clear effect on whether people come back.

Those numbers only matter if they are right, so each known data problem has an automatic check, and each check was shown to fail when given bad data. A separate recalculation straight from the original files confirms every headline number. One command rebuilds everything from scratch, and GitHub reruns all checks on every change.

Technical readers: the sections below keep the full detail, with the exact tables, tests and definitions.

### Terms used in this document

| Term | Plain meaning |
|---|---|
| dbt | A tool that builds tables from SQL queries and runs checks on them. |
| DuckDB | A database that runs on one laptop, with no server. |
| Raw, staging, intermediate, mart, metrics | The five steps from original files to final numbers. Raw is the files as published. Staging cleans types and names. Intermediate applies business rules. Marts are the tables analysts query. Metrics are the final numbers, each defined once. |
| Grain | What one row in a table stands for, such as one order or one item line. |
| Star schema | A way to arrange tables: fact tables record events (orders, payments), and dimension tables describe the things involved (customer, seller, product, date). |
| Key, unique key | A column that identifies a row. A unique key never repeats. |
| Fan-out | A table join that accidentally repeats rows, which can inflate counts or money. |
| Hash (sha256) | A fingerprint of a file. If one byte changes, the fingerprint changes. |
| CI (continuous integration) | GitHub automatically rebuilding the project and rerunning every check each time the code changes. |
| Lineage | The map of which table is built from which. |
| Confidence interval (CI in the headline table) | The range the true value probably falls in. A narrow range means a more reliable number. |
| OLS regression | A statistical method that estimates one factor's effect, such as lateness, while holding others (state, product category) fixed. |
| Late rate | The share of delivered orders that arrived on a later calendar day than promised. |
| Repeat rate | The share of customers who ordered again. |

# Technical overview

An analytics-engineering build of the public [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(~99k orders, 2016-2018): raw CSVs pinned by hash, a tested star schema, one metric layer, and a script that
reconciles every headline number to an independent recomputation.

```bash
make            # or, without make:  bash scripts/reproduce.sh
```
That one command (it starts a script that does everything below) creates `.venv`, downloads the nine CSVs from the
[Hugging Face mirror](https://huggingface.co/datasets/bulutttt/olist-raw-data) and checks their sha256, builds and tests every layer
(`dbt build`), reconciles the headline numbers, and generates dbt docs plus [the lineage graph](docs/LINEAGE.md).
About a minute on a laptop. Needs Python 3.12+ (with the `venv` module; on Ubuntu or Debian install `python3-venv`), `curl`, and network access.

## Headline numbers

These are the five numbers the project reports. Each row says what the number is and how it is counted.

| Metric | Value | Definition |
|---|---|---|
| **90-day repeat rate (headline)** | **1.28%** (991 / 77,560) | People (`customer_unique_id`) whose first qualifying order was at least 90 days before the data ends, who ordered again between 24 hours and 90 days later |
| Ever-reordered rate (secondary) | 3.04% (2,887 / 94,983) | People with a second qualifying order at any time, same-day included |
| Late rate | 6.87% (6,518 / 94,931) | Delivered orders (2017-01 to 2018-08) that arrived on a later calendar day than promised; multi-seller orders excluded (their parcels' arrival isn't observable) |
| Review score | 4.156 (95,560 orders) | Mean of the one chosen review per delivered order |
| Late penalty, controlled for state and category | -2.01 stars (CI -2.04 to -1.98) | How many stars lower late orders score, comparing orders from the same state and the same product category. Method: OLS regression, review ~ late + customer state + top-30 category |

A qualifying order is one that was not canceled or unavailable and has at least one item. Every number above is marked VERIFIED, meaning it matches a separate recalculation straight from the raw files, by
`make verify` (see [evidence/verification_report.md](evidence/verification_report.md)), which also rebuilds the metric layer with the
first-pass rules and reproduces the first-pass numbers exactly (6.79% late, 3.04% ever-repeat, 1.24% 90-day second-order, 4.156 stars, -1.992 penalty).

## How the data flows from files to numbers

Each step takes the output of the one before it, does one kind of work, and has its own checks.

```
raw (9 CSVs as published, sha256 pinned)  ->  staging (typed, 1:1 with raw)
  ->  intermediate (business rules)  ->  marts (star schema)  ->  metrics (each metric defined once)
```

| Layer | Models | What it guarantees |
|---|---|---|
| raw | dbt sources over `data/raw/*.csv` | `assert_raw_file_hashes_match_manifest` fails if any file differs from `seeds/raw_file_manifest.csv` |
| staging | `stg_orders`, `stg_order_items`, `stg_payments`, `stg_reviews`, `stg_customers`, `stg_sellers`, `stg_products`, `stg_category_translation`, `stg_geolocation` | Row count equals raw; types cast once; money is exact `DECIMAL(12,2)` |
| intermediate | `int_parcels` (order x seller), `int_order_delivery`, `int_order_payment_recon`, `int_order_review`, `int_geo_zip`, `int_customer_orders` | Each business rule has one owner: one `delivery_state` per order, one `recon_status`, one chosen review, one point per zip |
| marts | `fct_orders`, `fct_order_items`, `fct_payments`, `fct_reviews`, `dim_customer`, `dim_seller`, `dim_product`, `dim_date` | Keys unique, relationships hold, no fan-out (money totals equal raw to the cent) |
| metrics | `metric_late_rate_orders`, `metric_late_rate`, `metric_late_rate_monthly`, `metric_repeat_rate_90d`, `metric_repeat_rate_ever`, `metric_review_score`, `metrics_headline` | One definition per metric |

Design doc with every grain, key and rule: [MODELING.md](MODELING.md).

## Data problems found, and the check that guards each

Each row is a problem in the source data and the automatic test that fails if the problem comes back.

| Problem in the source | Business-rule test |
|---|---|
| `customer_id` is created per order (99,441 ids, 0 with a second order); the person is `customer_unique_id` (96,096) | `assert_repeat_metrics_count_people_not_order_ids` |
| 1,278 orders ship from several sellers but have one delivery date | `assert_multi_seller_orders_never_treated_as_single_parcel` |
| Reviews dated before the recorded delivery (5.19% by calendar day) | `assert_reviews_dated_before_delivery_are_flagged` |
| Paid vs items + freight differs by more than R$1 on 249 orders | `assert_payments_match_items_plus_freight_or_are_labeled`, `assert_payment_mismatch_share_below_threshold` |
| Geolocation: 1,000,163 rows for 19,015 zips, 42 points outside Brazil | unique + Brazil-bounding-box tests on `int_geo_zip` |
| Partial edge months (2016-09..12, 2018-09..10) | `assert_analysis_window_is_full_months_only` |
| Status and delivery date disagree on 14 orders | `assert_delivery_state_agrees_with_status_and_dates` |
| 775 orders have no items | `assert_orders_without_items_are_labeled` |
| 789 review ids sit on several orders; 547 orders have several reviews | `assert_one_chosen_review_per_reviewed_order` |
| Join fan-out would create money | `assert_item_money_matches_raw` |

**Every one of these tests is proven able to fail.** A check that can never fail proves nothing, so each was tested against bad data. `make prove-tests` copies the warehouse, injects known-bad rows for each
rule, and requires that rule's tests to pass before and fail after. Result: [evidence/mutation_report.md](evidence/mutation_report.md).
Two dbt unit tests pin the delivery-state and payment-recon rules on hand-built rows.

## Choices we tested before picking

Where two reasonable options existed, we built both and measured the difference. Each choice is a setting (a dbt var) in `dbt_project.yml`, so every option can be rebuilt and measured. In the table, "C1" to "C6" are just the choice numbers.

`make experiments` reruns them all
and writes [experiments/results.json](experiments/results.json).

| Choice | Pick | Measured |
|---|---|---|
| C1 multi-seller orders in late rate | exclude | Order-level date says 1.02% late vs 6.87% for single-seller, yet 46.9% of their "on-time" reviews are 1-2 stars (8.7% for single-seller) |
| C2 survey sent before delivery | compare by calendar day; keep in review score | `review_creation_date` is the day Olist sent the survey (Olist data card). It has a time part on only 85 of 99,224 rows; timestamp compare flags 3,164 same-day reviews |
| C3 incremental vs full rebuild | full rebuild | Same rows either way; a full rebuild takes seconds and never misses a status change on an old order |
| C4 which review represents an order | latest answer | Changes the score on 188 of 547 multi-review orders; metric moves by at most 0.001 |
| C5 customer address | latest on `dim_customer`, order-time on `fct_orders` | 39 people moved state; geography metrics use the order-time address |
| C6 same-day rule in 90-day repeat | any later order >= 24h | 30 people placed a same-day second order and then came back; "second order only" misses them |

## Ontology: one map of the business

[ontology/ONTOLOGY.md](ontology/ONTOLOGY.md) names every business thing (customer, order, item, parcel, seller, product, payment, review, location, date), how they connect, and what each term and metric means, with examples that do not count. [ontology/ontology.yml](ontology/ontology.yml) holds the definition cards. `make ontology` (part of `make verify`) proves every card against the warehouse: row counts, keys, links, stage-rule exceptions, and each metric through both the dbt metric tables and MetricFlow. The MetricFlow semantic layer in `models/semantic/` answers metric questions by name, for example `mf query --metrics late_rate --group-by metric_time__month`.

## Business recommendation

[recommendation/MEMO.md](recommendation/MEMO.md) is a one-page memo. [recommendation/PLAN.md](recommendation/PLAN.md) holds the analysis plan and the predictions, committed before any outcome was measured, plus a labeled addendum for checks added afterwards. `recommendation/analyze.py` measures each effect two ways (exact matching on state, category, freight band and month, and a regression with the same controls), re-checks findings on held-out months 2018-05 to 2018-08, and writes [evidence/recommendation_report.md](evidence/recommendation_report.md). It runs in `make verify` and fails if any number in the memo is not one it produced, or if a number sits next to the wrong state, month, before/after word or direction (see `recommendation/memo_check.py`).

## Data story

`make story` builds `story/build/story.html`, one static page for an operations manager. The page opens with what late delivery costs, follows the KPI tree down to where late orders come from, and ends at the memo's two tests. [story/QUESTIONS.md](story/QUESTIONS.md) holds the KPI tree and the five questions. [story/TOOLS.md](story/TOOLS.md) records the Evidence, Quarto and Streamlit trials and why the page uses Quarto. `make verify` builds the page and runs four checks. The KPI tree's breakdowns must add up. Every chart count must match the raw CSVs (Part C of `verification/verify_headlines.py`). Every number in the text must be tied to a fact (`story/check_story.py`). Each check has a selftest that plants errors and requires a failure.

## Dashboard data

`make dashboard` writes the tables behind the late-delivery dashboard to `dashboard/data/*.csv`, one file per panel or tile need. Tableau Public cannot read `.hyper` files, and Tableau Desktop reads CSV. Seven dbt models in `models/exports/` make the tables. Reconciliation tests (`tests/business_rules/assert_dash_*`) tie every number the dashboard prints to the analysis, and `verification/verify_dash_exports.py` checks the same numbers in the CSV files. Panel 6 holds invented example numbers, labelled EXAMPLE on every row, because the two fix tests have not run. Details: [dashboard/README.md](dashboard/README.md).

## What is in the repository

```
models/{staging,intermediate,marts,metrics}   dbt models + YAML tests
models/exports/                               tables for the dashboard (one per panel or tile need)
dashboard/                                    export_csv.py and data/*.csv: the files Tableau reads
models/semantic/                              MetricFlow semantic models and metrics
ontology/                                     ontology.yml, check.py, ONTOLOGY.md, order_lifecycle/ (TLA+ model)
tests/business_rules/                         singular business-rule tests
seeds/                                        raw file hashes, category translation patch
scripts/                                      reproduce.sh, fetch_data.sh, prove_tests_fail.py, doctor.sh, lineage_mermaid.py
verification/                                 verify_headlines.py + first-pass baseline; known_answers/ (24-question test for an agent)
experiments/                                  run_experiments.py + results.json
recommendation/                               MEMO.md, PLAN.md, analyze.py (late-delivery cost and the tests to run)
story/                                        data story: QUESTIONS.md (KPI tree), kpi_tree.yml, story.qmd, build_story.py, checks
evidence/                                     latest verification, mutation and ontology reports
analysis_design_phase/                        raw-data checks run before any SQL was written
```

CI (the automatic rebuild and recheck on GitHub, run by GitHub Actions, [`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs setup, `dbt build`, `make verify`,
`make prove-tests` and `make docs` on every push and pull request, and uploads the docs site and evidence as an artifact.

Data: Olist, published on Kaggle; see the Kaggle page for license terms. Raw files are downloaded, not committed.
