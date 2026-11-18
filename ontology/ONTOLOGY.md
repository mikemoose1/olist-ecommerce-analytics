# Olist ontology

## In plain language

This folder is the official map of the Olist business. It names each business thing, says how the things connect, and defines every term and metric. People, dashboards and AI agents read the same definitions, so they get the same answers.

- **ontology.yml** is the single source of truth. Every definition card lives there.
- **check.py** proves every claim in ontology.yml against the built database. A wrong count, a broken link or a changed metric fails the check, and CI runs it.
- **order_lifecycle/** is a small model of the stages an order moves through, checked with a model checker (TLC).
- The MetricFlow semantic layer in `models/semantic/_semantic.yml` lets anyone ask for a metric by name, sliced by month or state, without writing SQL.

Four facts matter most:

1. A customer is a real person (`customer_unique_id`). Olist's `customer_id` is new on every order, like a receipt number.
2. An order can hold items from several sellers. Each seller's share is a parcel, but Olist records only one delivery date per order.
3. Late means delivered on a later calendar day than promised. Multi-seller orders are left out of the late rate (decision C1).
4. Olist's `review_creation_date` is the day it emailed the survey, not the day the customer wrote it. Olist emails the survey when the order arrives or when the promised date comes, whichever is first. That is why some reviews come before delivery.

## The business things and how they connect

Read each line as "one of the left thing has zero or more (o{), one or more (|{), or at most one (|o) of the right thing". This diagram is generated from ontology.yml (`python ontology/check.py --mermaid`), and the check fails if this copy drifts.

```mermaid
erDiagram
    CUSTOMER {
        string customer_unique_id PK
    }
    ORDER {
        string order_id PK
    }
    ITEM {
        string order_id PK
        string order_item_id PK
    }
    PARCEL {
        string parcel_key PK
    }
    SELLER {
        string seller_id PK
    }
    PRODUCT {
        string product_id PK
    }
    PAYMENT {
        string order_id PK
        string payment_sequential PK
    }
    REVIEW {
        string review_id PK
        string order_id PK
    }
    LOCATION {
        string zip_code_prefix PK
    }
    DATE {
        string date_day PK
    }
    REPEAT_COHORT {
        string customer_unique_id PK
    }
    HEADLINE_METRIC {
        string metric_name PK
    }
    CUSTOMER ||--|{ ORDER : "customer places orders"
    ORDER ||--o{ ITEM : "order contains items"
    ORDER ||--o{ PARCEL : "order splits into parcels"
    PARCEL ||--|{ ITEM : "parcel groups items"
    SELLER ||--|{ PARCEL : "seller ships parcels"
    SELLER ||--|{ ITEM : "seller sells items"
    PRODUCT ||--|{ ITEM : "product appears on items"
    ORDER ||--o{ PAYMENT : "order is paid by payments"
    ORDER ||--o{ REVIEW : "order receives survey responses"
    ORDER ||--|o REVIEW : "order has one chosen review"
    LOCATION ||--o{ ORDER : "order ships to a location"
    LOCATION ||--o{ SELLER : "seller is based at a location"
    DATE ||--o{ ORDER : "order is purchased on a date"
    CUSTOMER ||--|o REPEAT_COHORT : "customer is in the repeat cohort"
```

| Thing | One row is | Key | Rows |
|---|---|---|---|
| customer | one real person | customer_unique_id | 96,096 |
| order | one checkout, any status | order_id | 99,441 |
| item | one item line on an order | order_id + order_item_id | 112,650 |
| parcel | one seller's share of one order | parcel_key (order + seller) | 100,010 |
| seller | one merchant | seller_id | 3,095 |
| product | one catalog product | product_id | 32,951 |
| payment | one payment line on an order | order_id + payment_sequential | 103,886 |
| review | one survey response on one order | review_id + order_id | 99,224 |
| location | one 5-digit zip prefix | zip_code_prefix | 19,015 |
| date | one calendar day | date_day | 791 |
| repeat cohort (supporting) | one person eligible for the 90-day repeat rate | customer_unique_id | 77,560 |
| headline metric (supporting) | one headline number with its numerator and denominator | metric_name | 5 |

Known gaps in the links, each counted and checked:

- 775 orders have no items and 1 order has no payment row.
- 768 orders have no survey response, and 547 have more than one. Decision C4 picks the latest-answered one, so each order has at most one chosen review.
- 278 orders and 7 sellers sit in a zip prefix that Olist's geolocation file does not have. They are kept, with no map point.
- The repeat cohort has 77,560 people, one row each. Another 17,423 of the 94,983 people with a real purchase are left out. Their first purchase falls in the last 90 days of the data, so they had no full 90 days to come back.
- 789 survey responses (`review_id`) are attached to more than one order, so a review's key is the response plus the order.

## The stages of an order

The model in `order_lifecycle/OrderLifecycle.tla` has three parts that move at the same time: the order's stage, whether the promised date has passed, and the survey. TLC checked all 29 reachable states.

```mermaid
stateDiagram-v2
  direction LR
  state "Legend" as legend {
    lg0: Breaks NoReviewBeforeDelivery in some cases
    lg1: Path to the NoReviewBeforeDelivery bug
  }
  class lg0 mayBreak
  class lg1 bugPath
  state "At the same time" as all {
    state "Order" as r0 {
      s0: Placed
      s1: Paid
      s2: Canceled
      s3: Unavailable
      s4: With carrier
      s5: Delivered on time
      s6: Delivered late
      [*] --> s0
      s0 --> s1: payment is approved
      s0 --> s2: order is canceled
      s1 --> s2: order is canceled
      s1 --> s3: seller can't fill it
      s1 --> s4: seller hands it to the carrier
      s4 --> s2: order is canceled
      s4 --> s5: carrier delivers [when Promise is Before promise date and Survey is No survey]
      s4 --> s6: carrier delivers [when Promise is Promise date passed]
    }
    --
    state "Promise" as r1 {
      s7: Before promise date
      s8: Promise date passed
      [*] --> s7
      s7 --> s8: the promised date arrives
    }
    --
    state "Survey" as r2 {
      s9: No survey
      s10: Survey sent
      s11: Survey answered
      [*] --> s9
      s9 --> s10: Olist emails the survey [when Order is one of Delivered late, Delivered on time or Promise is Promise date passed]
      s10 --> s11: customer answers the survey
    }
  }
  classDef mayBreak fill:#fff3e6,stroke:#e8730c,stroke-width:2.5px,color:#b85a06
  class s0 mayBreak
  class s0 bugPath
  class s1 mayBreak
  class s2 mayBreak
  class s3 mayBreak
  class s4 mayBreak
  class s7 bugPath
  class s8 mayBreak
  class s8 bugPath
  class s9 bugPath
  class s10 bugPath
  class s11 mayBreak
  class s11 bugPath
```

The chart hides the final "nothing more happens" step. Rules checked in the model and recounted in the data by check.py:

| Rule | Model | Data | What happens to the exceptions |
|---|---|---|---|
| A late order arrived after the promised day | holds | 0 exceptions | none needed |
| A delivery date exists exactly when the status is delivered | holds | 14 exceptions (8 delivered with no date, 6 canceled with a date) | labeled `status_date_conflict`, left out of delivery metrics |
| The carrier gets the order after payment approval | holds | 1,359 exceptions | raw timestamps out of order; no metric uses this gap |
| The customer gets the order after the carrier does | holds | 23 exceptions | raw timestamps out of order; lateness uses only delivery date and promise |
| The survey goes out only when the order is delivered or the promised date arrives | holds | 606 of 99,224 responses | kept; flagged when a delivery date exists |
| The survey goes out on or after the purchase day | holds | 64 responses (part of the 606) | source data error; kept |
| Nobody answers the survey before delivery | **breaks** | 4,367 responses answered on an earlier day than delivery | not a real rule, see below |

The last rule is how people first state it, and the model shows why it is wrong. TLC's shortest path: the order is placed, the promised date passes, Olist emails the survey, and the customer answers, all before the parcel arrives. In the data, 4,713 of the 5,127 responses sent before delivery went out on or after the promised date, and 4,777 of those 5,127 belong to late orders. The early review is a symptom of lateness, which is why decision C2 keeps these reviews in the review score.

Rebuild the chart: `node --experimental-strip-types <path-to>/statechart.ts ontology/order_lifecycle/OrderLifecycle.tla --view ontology/order_lifecycle/view.ts --out /tmp/new-chart`.

## Column facts

`ontology.yml` has a `columns:` section. For each column the cards depend on, it gives the data type, the exact null count and the row rules. For example, `purchased_at` is a TIMESTAMP and never null. `n_parcels` is 0, not null, on an order with no items. `review_score` is null on the 768 orders with no response. It also has a `facts:` section of counts that span tables, such as the 17,423 people left out of the repeat cohort. `check.py` proves every line of both against the warehouse.

## Glossary

Every term below has a full card in ontology.yml with its source column, grain, population, time rule and examples that do not count.

| Term | Plain meaning | Does not count |
|---|---|---|
| person | A real buyer (`customer_unique_id`). "Customer" in every metric means person. | `customer_id`, which is one per order |
| qualifying order | An order that counts as a real purchase. Not canceled or unavailable, with at least one item. | canceled, unavailable, or empty orders |
| purchase time | The second the order was placed. The column is `purchased_at`, a TIMESTAMP that is never null. `purchase_date` is only its day. The 24-hour rule in the repeat rate uses `purchased_at`. | `purchase_date`, which has no time |
| qualifying order sequence | `customer_qualifying_order_seq` is 1 on the person's first qualifying order, 2 on the next, and null on a non-qualifying order. | a canceled order (null) |
| repeat return | A later qualifying order whose `purchased_at` is at least 24 hours and at most 90 days after the first one's. Both ends count. | an order 3 hours later, a canceled order, day 91 |
| repeat cohort member | A person whose first qualifying order is at least 90 days older than the newest qualifying purchase, 2018-09-03 09:06:57. The cutoff is therefore 2018-06-05 09:06:57. The members are the rows of `metrics.metric_repeat_rate_90d_people`. | people with only recent first purchases, people with only canceled orders |
| repeat slice | The first-order month is the month of `first_order_date`. The first-order state is the `ship_to_state` of the person's `seq = 1` order, joined on `customer_unique_id`. | `dim_customer.state`, which is the latest address, and the month of the second order |
| placed an order | A person with at least one order of any status. That is every row of `dim_customer`, 96,096 people. | counting only qualifying orders. That gives 94,983 people and drops 1,113 whose orders were all canceled, unavailable or empty |
| canceled order | An order with `order_status = 'canceled'`. There are 625, including 6 that still carry a delivery date and also show `status_date_conflict`. The denominator for a share is every order. | status `unavailable`, or "not delivered" in general |
| parcel count | `n_parcels` is 0 on an order with no items (775 orders) and never null. It is 1 on a normal order and 2 or more on a multi-seller order. | treating it as null for empty orders |
| order review score | `fct_orders.review_score` holds the stars, 1 to 5, of the chosen response. It is null on the 768 orders with no response. | an earlier answer on the same order |
| promised date | The delivery date promised at purchase. A date with no time. | |
| delivered | Status is delivered and a delivery date exists (96,470 orders). Use `delivery_state`, not "has a delivery date", which also catches 6 canceled orders. | delivered status without a date, shipped orders |
| late | Delivered on a later calendar day than promised. | same-day delivery at 23:00, multi-seller orders, undelivered orders |
| multi-seller order | An order with items from 2 or more sellers (1,278 orders). | one seller shipping 3 items |
| analysis window | Full months 2017-01 through 2018-08. `in_analysis_window` is true or false and never null. 349 orders are outside. | partial edge months |
| survey sent | The day Olist emailed the survey (`review_creation_date`). | the day the customer answered |
| chosen review | The one response used per order: the latest answered. | earlier answers on the same order |
| survey sent before delivery | The survey went out on an earlier day than the delivery (column `review_before_delivery`). | same-day survey; responses on undelivered orders (null) |
| ship-to address | Where this order shipped, at order time. Geography metrics use it. | the person's latest address on dim_customer |
| payment recon | Whether paid equals items plus freight. | |

## Metrics

| Metric | Value | Numerator / denominator | Population |
|---|---|---|---|
| repeat_rate_90d (headline) | 1.28% | 991 / 77,560 people | people with a full 90 days after their first real purchase; a return must be 24 hours to 90 days later |
| repeat_rate_ever | 3.04% | 2,887 / 94,983 people | anyone with a real purchase; any second order counts |
| late_rate | 6.87% | 6,518 / 94,931 orders | delivered orders with items, in the window, single-seller only |
| review_score | 4.156 stars | 397,176 / 95,560 orders | delivered orders with items and a review, in the window; multi-seller included |
| late_review_gap_raw | 2.04 stars | 94,302 orders | on-time minus late average, late-rate population, unadjusted |

check.py confirms each value three ways: the card, the dbt metric table, and MetricFlow's own sum of row-level numbers. `make verify` also recomputes the first four from the raw CSVs.

## Asking questions

```sh
mf query --metrics late_rate,judged_orders --group-by metric_time__month
mf query --metrics late_rate --group-by order__ship_to_state --order -late_rate
mf query --metrics repeat_rate_90d,review_score
```

Run `dbt parse` (or `make build`) first. MetricFlow reads `target/semantic_manifest.json`, and a stale one gives "no matching group-by" errors.

## Why MetricFlow plus YAML cards

Both options were built and run on this warehouse (2026-11-17).

| | (a) MetricFlow semantic models + cards | (b) YAML cards + existing metric tables |
|---|---|---|
| Setup | 1 package (dbt-metricflow 0.16.0, same dbt/duckdb pins, 13 s install), 75-line YAML, a time spine on dim_date, and one refactor so the repeat population has a row per person | no new package |
| Reproduces the numbers | yes: 6,518/94,931, 991/77,560, 397,176/95,560 and all 20 months, summed from rows | yes, but only by reading the same rows it is compared to |
| New questions | any metric by month, by state or by order field, no new SQL | only what a metric table already holds; anything else needs hand SQL |
| CI | `make verify` runs check.py, which calls `mf query`; no workflow change | same script without the MetricFlow calls |
| Gotchas | needs a fresh `target/semantic_manifest.json`; cannot query while another process holds the DuckDB file | none |

MetricFlow ships. Its numbers are an independent recomputation, and it answers sliced questions that (b) cannot. The cards ship in both options, because MetricFlow has no field for "does not count" examples, cardinality or stage rules.
