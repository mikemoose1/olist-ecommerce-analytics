# Ontology check: every claim in ontology/ontology.yml against the warehouse

57/57 PASS

| Kind | Claim | Result | Detail |
|---|---|---|---|
| entity | customer | PASS | rows=96096 (card 96096), distinct keys=96096, null keys=0 |
| entity | order | PASS | rows=99441 (card 99441), distinct keys=99441, null keys=0 |
| entity | item | PASS | rows=112650 (card 112650), distinct keys=112650, null keys=0 |
| entity | parcel | PASS | rows=100010 (card 100010), distinct keys=100010, null keys=0 |
| entity | seller | PASS | rows=3095 (card 3095), distinct keys=3095, null keys=0 |
| entity | product | PASS | rows=32951 (card 32951), distinct keys=32951, null keys=0 |
| entity | payment | PASS | rows=103886 (card 103886), distinct keys=103886, null keys=0 |
| entity | review | PASS | rows=99224 (card 99224), distinct keys=99224, null keys=0 |
| entity | location | PASS | rows=19015 (card 19015), distinct keys=19015, null keys=0 |
| entity | date | PASS | rows=791 (card 791), distinct keys=791, null keys=0 |
| relationship | customer places orders | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 1..17 (card 1..many) |
| relationship | order contains items | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 0..21 (card 0..many) |
| relationship | order splits into parcels | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 0..5 (card 0..many) |
| relationship | parcel groups items | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 1..21 (card 1..many) |
| relationship | seller ships parcels | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 1..1854 (card 1..many) |
| relationship | seller sells items | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 1..2033 (card 1..many) |
| relationship | product appears on items | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 1..527 (card 1..many) |
| relationship | order is paid by payments | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 0..29 (card 0..many) |
| relationship | order receives survey responses | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 0..3 (card 0..many) |
| relationship | order has one chosen review | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 0..1 (card 0..1) |
| relationship | order ships to a location | PASS | nulls=0 (card 0), orphans=278 (card 278), children per parent 0..142 (card 0..many) |
| relationship | seller is based at a location | PASS | nulls=0 (card 0), orphans=7 (card 7), children per parent 0..49 (card 0..many) |
| relationship | order is purchased on a date | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 0..1176 (card 0..many) |
| column | terms.person | PASS | marts.dim_customer.customer_unique_id |
| column | terms.order_status | PASS | marts.fct_orders.order_status |
| column | terms.qualifying_order | PASS | marts.fct_orders.is_qualifying_order |
| column | terms.promised_date | PASS | marts.fct_orders.estimated_delivery_date |
| column | terms.delivery_state | PASS | marts.fct_orders.delivery_state |
| column | terms.delivered | PASS | marts.fct_orders.delivered_to_customer_at |
| column | terms.late | PASS | metrics.metric_late_rate_orders.is_late |
| column | terms.multi_seller_order | PASS | marts.fct_orders.n_parcels |
| column | terms.analysis_window | PASS | marts.fct_orders.in_analysis_window |
| column | terms.survey_sent | PASS | marts.fct_reviews.review_created_on |
| column | terms.survey_answered | PASS | marts.fct_reviews.review_answered_at |
| column | terms.chosen_review | PASS | marts.fct_reviews.is_chosen_for_order |
| column | terms.survey_sent_before_delivery | PASS | marts.fct_reviews.review_before_delivery |
| column | terms.ship_to_address | PASS | marts.fct_orders.ship_to_state |
| column | terms.payment_recon | PASS | marts.fct_orders.recon_status |
| column | metrics.late_rate | PASS | metrics.metric_late_rate_orders.is_late |
| column | metrics.late_rate_monthly | PASS | metrics.metric_late_rate_monthly.year_month |
| column | metrics.repeat_rate_90d | PASS | metrics.metric_repeat_rate_90d_people.repeated |
| column | metrics.repeat_rate_ever | PASS | marts.dim_customer.n_qualifying_orders |
| column | metrics.review_score | PASS | marts.fct_orders.review_score |
| column | metrics.late_review_gap_raw | PASS | metrics.metric_late_rate_orders.review_score |
| stage_rule | A late order arrived after the promised day | PASS | count=0 (card 0) |
| stage_rule | A delivery date exists exactly when the status is delivered | PASS | count=14 (card 14) |
| stage_rule | The carrier gets the order after payment approval | PASS | count=1359 (card 1359) |
| stage_rule | The customer gets the order after the carrier does | PASS | count=23 (card 23) |
| stage_rule | The survey goes out only when the order is delivered or the promised date arrives | PASS | count=606 (card 606) |
| stage_rule | Nobody answers the survey before the order is delivered | PASS | count=4367 (card 4367) |
| metric | late_rate | PASS | table 6518/94931=6.87 (card 6518/94931=6.87); MetricFlow 6518/94931=0.068660 -> 6.87 |
| metric | repeat_rate_90d | PASS | table 991/77560=1.28 (card 991/77560=1.28); MetricFlow 991/77560=0.012777 -> 1.28 |
| metric | repeat_rate_ever | PASS | table 2887/94983=3.04 (card 2887/94983=3.04) |
| metric | review_score | PASS | table 397176/95560=4.156 (card 397176/95560=4.156); MetricFlow 397176/95560=4.156300 -> 4.156 |
| metric | late_review_gap_raw | PASS | table None/94302=2.04 (card -/94302=2.04) |
| metric | late_rate_monthly | PASS | MetricFlow by month vs table: 20/20 months identical (numerator and denominator) |
| diagram | ONTOLOGY.md entity diagram | PASS | regenerate with: python ontology/check.py --mermaid |
