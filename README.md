# Olist e-commerce analytics (dbt + DuckDB)

An analytics-engineering build of the public [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(~99k orders, 2016-2018): raw CSVs pinned by hash, a tested star schema, one metric layer, and a script that
reconciles every headline number to an independent recomputation.

```bash
make            # or, without make:  bash scripts/reproduce.sh
```
That one command creates `.venv`, downloads the nine CSVs from the
[Hugging Face mirror](https://huggingface.co/datasets/bulutttt/olist-raw-data) and checks their sha256, builds and tests every layer
(`dbt build`), reconciles the headline numbers, and generates dbt docs plus [the lineage graph](docs/LINEAGE.md).
About a minute on a laptop. Needs Python 3.12+, `curl`, and network access.

## Headline numbers

| Metric | Value | Definition |
|---|---|---|
| **90-day repeat rate (headline)** | **1.28%** (991 / 77,560) | People (`customer_unique_id`) whose first qualifying order was at least 90 days before the data ends, who ordered again between 24 hours and 90 days later |
| Ever-reordered rate (secondary) | 3.04% (2,887 / 94,983) | People with a second qualifying order at any time, same-day included |
| Late rate | 6.87% (6,518 / 94,931) | Delivered orders (2017-01 to 2018-08) that arrived on a later calendar day than promised; multi-seller orders excluded (their parcels' arrival isn't observable) |
| Review score | 4.156 (95,560 orders) | Mean of the one chosen review per delivered order |
| Late penalty, controlled | -2.01 stars (CI -2.04 to -1.98) | OLS: review ~ late + customer state + top-30 category |

A qualifying order is one that was not canceled or unavailable and has at least one item. Every number above is VERIFIED by
`make verify` (see [evidence/verification_report.md](evidence/verification_report.md)), which also rebuilds the metric layer with the
first-pass rules and reproduces the first-pass numbers exactly (6.79% late, 3.04% ever-repeat, 1.24% 90-day second-order, 4.156 stars, -1.992 penalty).

## How it's built

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

## Data problems found, and the test that guards each

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

**Every one of these tests is proven able to fail.** `make prove-tests` copies the warehouse, injects known-bad rows for each
rule, and requires that rule's tests to pass before and fail after. Result: [evidence/mutation_report.md](evidence/mutation_report.md).
Two dbt unit tests pin the delivery-state and payment-recon rules on hand-built rows.

## Modeling choices (settled by experiment)

Each choice is a dbt var in `dbt_project.yml`, so every option can be rebuilt and measured. `make experiments` reruns them all
and writes [experiments/results.json](experiments/results.json).

| Choice | Pick | Measured |
|---|---|---|
| C1 multi-seller orders in late rate | exclude | Order-level date says 1.02% late vs 6.87% for single-seller, yet 46.9% of their "on-time" reviews are 1-2 stars (8.7% for single-seller) |
| C2 review dated before delivery | compare by calendar day; keep in review score | Creation dates have a time part on only 85 of 99,224 rows; timestamp compare flags 3,164 same-day reviews |
| C3 incremental vs full rebuild | full rebuild | Same rows either way; a full rebuild takes seconds and never misses a status change on an old order |
| C4 which review represents an order | latest answer | Changes the score on 188 of 547 multi-review orders; metric moves by at most 0.001 |
| C5 customer address | latest on `dim_customer`, order-time on `fct_orders` | 39 people moved state; geography metrics use the order-time address |
| C6 same-day rule in 90-day repeat | any later order >= 24h | 30 people placed a same-day second order and then came back; "second order only" misses them |

## Repo layout

```
models/{staging,intermediate,marts,metrics}   dbt models + YAML tests
tests/business_rules/                         singular business-rule tests
seeds/                                        raw file hashes, category translation patch
scripts/                                      reproduce.sh, fetch_data.sh, prove_tests_fail.py, doctor.sh, lineage_mermaid.py
verification/                                 verify_headlines.py + first-pass baseline
experiments/                                  run_experiments.py + results.json
evidence/                                     latest verification and mutation reports
analysis_design_phase/                        raw-data checks run before any SQL was written
```

CI (GitHub Actions, [`ci/github-actions-ci.yml`](ci/github-actions-ci.yml)) runs setup, `dbt build`, `make verify`,
`make prove-tests` and `make docs` on every push, and uploads the docs site and evidence as an artifact. To enable it, the file
must live at `.github/workflows/ci.yml` (it is kept under `ci/` until it is added with an account that has GitHub's `workflow` permission).

Data: Olist, published on Kaggle; see the Kaggle page for license terms. Raw files are downloaded, not committed.
