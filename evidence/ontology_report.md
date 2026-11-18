# Ontology check: every claim in ontology/ontology.yml against the warehouse

216/216 PASS

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
| entity | repeat_cohort | PASS | rows=77560 (card 77560), distinct keys=77560, null keys=0 |
| entity | headline_metric | PASS | rows=5 (card 5), distinct keys=5, null keys=0 |
| entity | late_rate_order | PASS | rows=94931 (card 94931), distinct keys=94931, null keys=0 |
| entity | late_rate_month | PASS | rows=20 (card 20), distinct keys=20, null keys=0 |
| entity | late_rate_result | PASS | rows=1 (card 1), distinct keys=1, null keys=0 |
| entity | repeat_rate_90d_result | PASS | rows=1 (card 1), distinct keys=1, null keys=0 |
| entity | repeat_rate_ever_result | PASS | rows=1 (card 1), distinct keys=1, null keys=0 |
| entity | review_score_result | PASS | rows=2 (card 2), distinct keys=2, null keys=0 |
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
| relationship | customer is in the repeat cohort | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 0..1 (card 0..1) |
| relationship | late-rate verdict covers an order | PASS | nulls=0 (card 0), orphans=0 (card 0), children per parent 0..1 (card 0..1) |
| column | terms.person | PASS | marts.dim_customer.customer_unique_id |
| column | terms.order_status | PASS | marts.fct_orders.order_status |
| column | terms.canceled_order | PASS | marts.fct_orders.order_status |
| column | terms.qualifying_order | PASS | marts.fct_orders.is_qualifying_order |
| column | terms.promised_date | PASS | marts.fct_orders.estimated_delivery_date |
| column | terms.delivery_state | PASS | marts.fct_orders.delivery_state |
| column | terms.delivered | PASS | marts.fct_orders.delivery_state |
| column | terms.late | PASS | metrics.metric_late_rate_orders.is_late |
| column | terms.multi_seller_order | PASS | marts.fct_orders.n_parcels |
| column | terms.analysis_window | PASS | marts.fct_orders.in_analysis_window |
| column | terms.survey_sent | PASS | marts.fct_reviews.review_created_on |
| column | terms.survey_answered | PASS | marts.fct_reviews.review_answered_at |
| column | terms.chosen_review | PASS | marts.fct_reviews.is_chosen_for_order |
| column | terms.survey_sent_before_delivery | PASS | marts.fct_reviews.review_before_delivery |
| column | terms.ship_to_address | PASS | marts.fct_orders.ship_to_state |
| column | terms.payment_recon | PASS | marts.fct_orders.recon_status |
| column | terms.purchase_time | PASS | marts.fct_orders.purchased_at |
| column | terms.qualifying_order_seq | PASS | marts.fct_orders.customer_qualifying_order_seq |
| column | terms.repeat_return | PASS | metrics.metric_repeat_rate_90d_people.repeated |
| column | terms.repeat_cohort_member | PASS | metrics.metric_repeat_rate_90d_people.customer_unique_id |
| column | terms.repeat_slice | PASS | metrics.metric_repeat_rate_90d_people.first_order_date |
| column | terms.placed_an_order | PASS | marts.dim_customer.n_orders |
| column | terms.parcel_count | PASS | marts.fct_orders.n_parcels |
| column | terms.order_review_score | PASS | marts.fct_orders.review_score |
| column | metrics.late_rate | PASS | metrics.metric_late_rate_orders.is_late |
| column | metrics.late_rate_monthly | PASS | metrics.metric_late_rate_monthly.year_month |
| column | metrics.repeat_rate_90d | PASS | metrics.metric_repeat_rate_90d_people.repeated |
| column | metrics.repeat_rate_ever | PASS | marts.dim_customer.n_qualifying_orders |
| column | metrics.review_score | PASS | marts.fct_orders.review_score |
| column | metrics.late_review_gap_raw | PASS | metrics.metric_late_rate_orders.review_score |
| term_count | order_status | PASS | {'approved': 2, 'canceled': 625, 'created': 5, 'delivered': 96478, 'invoiced': 314, 'processing': 301, 'shipped': 1107, 'unavailable': 609} |
| term_count | canceled_order | PASS | order_status = 'canceled': 625 (card 625); order_status = 'canceled' and delivered_to_customer_at is not null: 6 (card 6); order_status = 'canceled' and delivery_state = 'status_date_conflict': 6 (card 6); order_status = 'canceled' and delivery_state = 'not_delivered': 619 (card 619); order_status = 'canceled' and n_items = 0: 164 (card 164) |
| term_count | qualifying_order | PASS | is_qualifying_order: 98199 (card 98199); not is_qualifying_order: 1242 (card 1242) |
| term_count | delivery_state | PASS | {'delivered_late': 6534, 'delivered_on_time': 89936, 'not_delivered': 2957, 'status_date_conflict': 14} |
| term_count | delivered | PASS | delivery_state in ('delivered_on_time', 'delivered_late'): 96470 (card 96470) |
| term_count | multi_seller_order | PASS | n_parcels > 1: 1278 (card 1278) |
| term_count | analysis_window | PASS | in_analysis_window: 99092 (card 99092); not in_analysis_window: 349 (card 349) |
| term_count | placed_an_order | PASS | n_orders >= 1: 96096 (card 96096); n_qualifying_orders >= 1: 94983 (card 94983); n_qualifying_orders = 0: 1113 (card 1113) |
| term_count | parcel_count | PASS | n_parcels = 0: 775 (card 775); n_parcels = 1: 97388 (card 97388); n_parcels > 1: 1278 (card 1278) |
| term_count | order_review_score | PASS | review_score is null: 768 (card 768) |
| column_fact | marts.fct_orders.purchased_at | PASS | type TIMESTAMP (card TIMESTAMP); nulls 0 (card 0); holds [purchase_date = cast(purchased_at as date)]: 0 violations |
| column_fact | marts.fct_orders.purchase_date | PASS | type DATE (card DATE); nulls 0 (card 0); holds [purchase_date = cast(purchased_at as date)]: 0 violations |
| column_fact | marts.fct_orders.is_qualifying_order | PASS | type BOOLEAN (card BOOLEAN); nulls 0 (card 0); holds [is_qualifying_order = (order_status not in ('canceled', 'unavailable') and n_items > 0)]: 0 violations |
| column_fact | marts.fct_orders.customer_qualifying_order_seq | PASS | type BIGINT (card BIGINT); nulls 1242 (card 1242); null exactly when [not is_qualifying_order]: 0 violations; holds [customer_qualifying_order_seq is null or customer_qualifying_order_seq >= 1]: 0 violations |
| column_fact | marts.fct_orders.n_items | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | marts.fct_orders.n_parcels | PASS | type BIGINT (card BIGINT); nulls 0 (card 0); holds [(n_parcels = 0) = (n_items = 0)]: 0 violations |
| column_fact | marts.fct_orders.in_analysis_window | PASS | type BOOLEAN (card BOOLEAN); nulls 0 (card 0); holds [in_analysis_window = (purchase_date between date '2017-01-01' and date '2018-08-31')]: 0 violations |
| column_fact | marts.fct_orders.review_score | PASS | type INTEGER (card INTEGER); nulls 768 (card 768); null exactly when [review_id is null]: 0 violations; holds [review_score is null or review_score between 1 and 5]: 0 violations |
| column_fact | marts.fct_orders.delivered_to_customer_at | PASS | type TIMESTAMP (card TIMESTAMP); nulls 2965 (card 2965) |
| column_fact | marts.dim_customer.n_orders | PASS | type BIGINT (card BIGINT); nulls 0 (card 0); holds [n_orders >= 1]: 0 violations |
| column_fact | marts.dim_customer.n_qualifying_orders | PASS | type BIGINT (card BIGINT); nulls 0 (card 0); holds [n_qualifying_orders <= n_orders]: 0 violations |
| column_fact | marts.dim_customer.first_qualifying_order_at | PASS | type TIMESTAMP (card TIMESTAMP); nulls 1113 (card 1113); null exactly when [n_qualifying_orders = 0]: 0 violations |
| column_fact | metrics.metric_repeat_rate_90d_people.customer_unique_id | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_90d_people.first_order_at | PASS | type TIMESTAMP (card TIMESTAMP); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_90d_people.first_order_date | PASS | type DATE (card DATE); nulls 0 (card 0); holds [first_order_date = cast(first_order_at as date)]: 0 violations |
| column_fact | metrics.metric_repeat_rate_90d_people.repeated | PASS | type BOOLEAN (card BOOLEAN); nulls 0 (card 0) |
| column_fact | metrics.metrics_headline.metric_name | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metrics_headline.numerator | PASS | type HUGEINT (card HUGEINT); nulls 1 (card 1); null exactly when [metric_name = 'late_review_gap_raw']: 0 violations |
| column_fact | metrics.metrics_headline.denominator | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | metrics.metrics_headline.value_pct | PASS | type DOUBLE (card DOUBLE); nulls 0 (card 0) |
| column_fact | marts.dim_customer.zip_code_prefix | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | marts.dim_customer.city | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | marts.dim_customer.state | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | marts.dim_customer.lat | PASS | type DOUBLE (card DOUBLE); nulls 269 (card 269) |
| column_fact | marts.dim_customer.lng | PASS | type DOUBLE (card DOUBLE); nulls 269 (card 269) |
| column_fact | marts.dim_customer.first_order_at_any_status | PASS | type TIMESTAMP (card TIMESTAMP); nulls 0 (card 0) |
| column_fact | marts.dim_date.month_start | PASS | type DATE (card DATE); nulls 0 (card 0); holds [month_start = date_trunc('month', date_day)]: 0 violations |
| column_fact | marts.dim_date.year_month | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0); holds [year_month = strftime(date_day, '%Y-%m')]: 0 violations |
| column_fact | marts.dim_date.day_of_week | PASS | type BIGINT (card BIGINT); nulls 0 (card 0); holds [day_of_week between 0 and 6]: 0 violations |
| column_fact | marts.dim_date.in_analysis_window | PASS | type BOOLEAN (card BOOLEAN); nulls 0 (card 0) |
| column_fact | marts.dim_product.product_category_name | PASS | type VARCHAR (card VARCHAR); nulls 610 (card 610) |
| column_fact | marts.dim_product.category | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | marts.dim_seller.city | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | marts.dim_seller.state | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | marts.dim_seller.lat | PASS | type DOUBLE (card DOUBLE); nulls 7 (card 7) |
| column_fact | marts.dim_seller.lng | PASS | type DOUBLE (card DOUBLE); nulls 7 (card 7) |
| column_fact | marts.fct_order_items.shipping_limit_at | PASS | type TIMESTAMP (card TIMESTAMP); nulls 0 (card 0) |
| column_fact | marts.fct_order_items.price | PASS | type DECIMAL(12,2) (card DECIMAL(12,2)); nulls 0 (card 0); holds [price > 0]: 0 violations |
| column_fact | marts.fct_order_items.freight_value | PASS | type DECIMAL(12,2) (card DECIMAL(12,2)); nulls 0 (card 0); holds [freight_value >= 0]: 0 violations |
| column_fact | marts.fct_orders.delivery_evidence | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | marts.fct_orders.delivered_to_carrier_at | PASS | type TIMESTAMP (card TIMESTAMP); nulls 1783 (card 1783) |
| column_fact | marts.fct_orders.last_shipping_limit_at | PASS | type TIMESTAMP (card TIMESTAMP); nulls 775 (card 775); null exactly when [n_items = 0]: 0 violations |
| column_fact | marts.fct_orders.days_past_promise | PASS | type BIGINT (card BIGINT); nulls 2965 (card 2965); null exactly when [delivered_to_customer_at is null]: 0 violations; holds [days_past_promise is null or days_past_promise = date_diff('day', estimated_delivery_date, cast(delivered_to_customer_at as date))]: 0 violations |
| column_fact | marts.fct_orders.promised_days | PASS | type BIGINT (card BIGINT); nulls 0 (card 0); holds [promised_days = date_diff('day', purchase_date, estimated_delivery_date)]: 0 violations |
| column_fact | marts.fct_orders.amount_due | PASS | type DECIMAL(38,2) (card DECIMAL(38,2)); nulls 775 (card 775); null exactly when [n_items = 0]: 0 violations |
| column_fact | marts.fct_orders.amount_paid | PASS | type DECIMAL(38,2) (card DECIMAL(38,2)); nulls 1 (card 1) |
| column_fact | marts.fct_orders.paid_minus_due | PASS | type DECIMAL(38,2) (card DECIMAL(38,2)); nulls 776 (card 776); holds [paid_minus_due is null or paid_minus_due = amount_paid - amount_due]: 0 violations |
| column_fact | marts.fct_orders.max_installments | PASS | type INTEGER (card INTEGER); nulls 1 (card 1) |
| column_fact | marts.fct_orders.ship_to_city | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | marts.fct_orders.ship_to_lat | PASS | type DOUBLE (card DOUBLE); nulls 279 (card 279) |
| column_fact | marts.fct_orders.ship_to_lng | PASS | type DOUBLE (card DOUBLE); nulls 279 (card 279) |
| column_fact | marts.fct_orders.review_id | PASS | type VARCHAR (card VARCHAR); nulls 768 (card 768); null exactly when [review_score is null]: 0 violations |
| column_fact | marts.fct_orders.review_before_delivery | PASS | type BOOLEAN (card BOOLEAN); nulls 3611 (card 3611) |
| column_fact | marts.fct_payments.payment_type | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | marts.fct_payments.payment_installments | PASS | type INTEGER (card INTEGER); nulls 0 (card 0) |
| column_fact | marts.fct_payments.payment_value | PASS | type DECIMAL(12,2) (card DECIMAL(12,2)); nulls 0 (card 0); holds [payment_value >= 0]: 0 violations |
| column_fact | marts.fct_reviews.review_score | PASS | type INTEGER (card INTEGER); nulls 0 (card 0); holds [review_score between 1 and 5]: 0 violations |
| column_fact | marts.fct_reviews.review_comment_message | PASS | type VARCHAR (card VARCHAR); nulls 58247 (card 58247) |
| column_fact | marts.fct_reviews.review_created_at | PASS | type TIMESTAMP (card TIMESTAMP); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate.metric_name | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate.rule | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate.numerator | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate.denominator | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate.value_pct | PASS | type DOUBLE (card DOUBLE); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate_monthly.numerator | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate_monthly.denominator | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate_monthly.value_pct | PASS | type DOUBLE (card DOUBLE); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate_orders.order_id | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate_orders.purchase_date | PASS | type DATE (card DATE); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate_orders.delivery_state | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate_orders.delivery_evidence | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate_orders.ship_to_state | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_late_rate_orders.review_before_delivery | PASS | type BOOLEAN (card BOOLEAN); nulls 629 (card 629) |
| column_fact | metrics.metric_repeat_rate_90d.metric_name | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_90d.rule | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_90d.numerator | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_90d.denominator | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_90d.value_pct | PASS | type DOUBLE (card DOUBLE); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_ever.metric_name | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_ever.rule | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_ever.numerator | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_ever.denominator | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | metrics.metric_repeat_rate_ever.value_pct | PASS | type DOUBLE (card DOUBLE); nulls 0 (card 0) |
| column_fact | metrics.metric_review_score.metric_name | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_review_score.rule | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metric_review_score.numerator | PASS | type HUGEINT (card HUGEINT); nulls 1 (card 1) |
| column_fact | metrics.metric_review_score.denominator | PASS | type BIGINT (card BIGINT); nulls 0 (card 0) |
| column_fact | metrics.metric_review_score.value_pct | PASS | type DOUBLE (card DOUBLE); nulls 0 (card 0) |
| column_fact | metrics.metrics_headline.rule | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0) |
| column_fact | metrics.metrics_headline.is_headline | PASS | type BOOLEAN (card BOOLEAN); nulls 0 (card 0) |
| column_fact | marts.fct_orders.estimated_delivery_date | PASS | type DATE (card DATE); nulls 0 (card 0); holds [promised_days >= 0]: 0 violations |
| column_fact | marts.fct_orders.recon_status | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0); holds [recon_status in ('match', 'minor', 'overpaid', 'underpaid', 'no_items', 'no_payment')]: 0 violations; holds [(recon_status = 'no_items') = (n_items = 0)]: 0 violations |
| column_fact | marts.fct_orders.ship_to_state | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0); holds [length(ship_to_state) = 2]: 0 violations |
| column_fact | marts.fct_reviews.review_created_on | PASS | type DATE (card DATE); nulls 0 (card 0); holds [review_created_on = cast(review_created_at as date)]: 0 violations |
| column_fact | marts.fct_reviews.review_answered_at | PASS | type TIMESTAMP (card TIMESTAMP); nulls 0 (card 0); holds [review_answered_at >= review_created_at]: 0 violations |
| column_fact | marts.fct_reviews.is_chosen_for_order | PASS | type BOOLEAN (card BOOLEAN); nulls 0 (card 0) |
| column_fact | marts.fct_reviews.review_before_delivery | PASS | type BOOLEAN (card BOOLEAN); nulls 2865 (card 2865) |
| column_fact | metrics.metric_late_rate_orders.is_late | PASS | type BOOLEAN (card BOOLEAN); nulls 0 (card 0); holds [is_late = (delivery_state = 'delivered_late')]: 0 violations |
| column_fact | metrics.metric_late_rate_orders.review_score | PASS | type INTEGER (card INTEGER); nulls 629 (card 629); holds [review_score is null or review_score between 1 and 5]: 0 violations |
| column_fact | metrics.metric_late_rate_monthly.year_month | PASS | type VARCHAR (card VARCHAR); nulls 0 (card 0); holds [year_month between '2017-01' and '2018-08']: 0 violations |
| fact | People with a qualifying order | PASS | count=94983 (card 94983) |
| fact | People whose first qualifying order is too recent for a full 90 days | PASS | count=17423 (card 17423) |
| fact | The repeat cohort is exactly the people whose first qualifying order is old enough | PASS | count=0 (card 0) |
| fact | The newest qualifying purchase in the data is 2018-09-03 09:06:57, so the cohort cutoff is 2018-06-05 09:06:57 | PASS | count=1 (card 1) |
| fact | first_order_at is the purchased_at of the person's seq = 1 order | PASS | count=0 (card 0) |
| fact | Each person has exactly one seq = 1 order, so joining the cohort to it gives one row per person (the first-order state is unambiguous) | PASS | count=77560 (card 77560) |
| fact | The sequence number follows purchased_at, so seq = 1 is the person's earliest qualifying order | PASS | count=0 (card 0) |
| fact | Orders with more than one survey response | PASS | count=547 (card 547) |
| fact | Survey responses (review_id) attached to more than one order | PASS | count=789 (card 789) |
| fact | Survey responses chosen for an order (C4) | PASS | count=98673 (card 98673) |
| fact | Judged orders marked late | PASS | count=6518 (card 6518) |
| fact | Survey responses sent on an earlier day than the delivery | PASS | count=5127 (card 5127) |
| fact | Of those, responses sent on or after the promised date | PASS | count=4713 (card 4713) |
| fact | Of those, responses on orders whose delivery_state is delivered_late | PASS | count=4777 (card 4777) |
| fact | Pairs of one person's qualifying orders placed in the same second | PASS | count=281 (card 281) |
| fact | review_score on the order equals the score of the chosen response, and an order with no chosen response has a null score | PASS | count=0 (card 0) |
| stage_rule | A late order arrived after the promised day | PASS | count=0 (card 0) |
| stage_rule | A delivery date exists exactly when the status is delivered | PASS | count=14 (card 14) |
| stage_rule | The carrier gets the order after payment approval | PASS | count=1359 (card 1359) |
| stage_rule | The customer gets the order after the carrier does | PASS | count=23 (card 23) |
| stage_rule | The survey goes out only when the order is delivered or the promised date arrives | PASS | count=606 (card 606) |
| stage_rule | The survey goes out on or after the purchase day | PASS | count=64 (card 64) |
| stage_rule | Nobody answers the survey before the order is delivered | PASS | count=4367 (card 4367) |
| model_link | A late order arrived after the promised day | PASS | invariant LateMeansArrivedAfterPromise: defined=True in cfg=True report says holds=True; ONTOLOGY.md Model column shows 'holds', card says 'holds' |
| model_link | A delivery date exists exactly when the status is delivered | PASS | no invariant in the model; ONTOLOGY.md Model column shows 'not modeled', card says 'not modeled' |
| model_link | The carrier gets the order after payment approval | PASS | no invariant in the model; ONTOLOGY.md Model column shows 'not modeled', card says 'not modeled' |
| model_link | The customer gets the order after the carrier does | PASS | no invariant in the model; ONTOLOGY.md Model column shows 'not modeled', card says 'not modeled' |
| model_link | The survey goes out only when the order is delivered or the promised date arrives | PASS | invariant SurveyFollowsPolicy: defined=True in cfg=True report says holds=True; ONTOLOGY.md Model column shows 'holds', card says 'holds' |
| model_link | The survey goes out on or after the purchase day | PASS | no invariant in the model; ONTOLOGY.md Model column shows 'not modeled', card says 'not modeled' |
| model_link | Nobody answers the survey before the order is delivered | PASS | invariant NoReviewBeforeDelivery: defined=True in cfg=True report says breaks=True; ONTOLOGY.md Model column shows '**breaks**', card says '**breaks**' |
| model_link | every invariant TLC checks backs a rule | PASS | invariants in the cfg that no rule claims: none |
| coverage | allowlist reasons | PASS | 44 exemptions, each with a reason |
| coverage | tables | PASS | 16 tables; undescribed: none |
| coverage | columns | PASS | 127 columns; undescribed: none |
| coverage | numbers in ONTOLOGY.md | PASS | 71 numbers each bound to the ontology.yml value they state; problems: none |
| coverage | allowlist is current | PASS | entries matching nothing: none |
| metric | late_rate | PASS | table 6518/94931=6.87 (card 6518/94931=6.87); MetricFlow 6518/94931=0.068660 -> 6.87 |
| metric | repeat_rate_90d | PASS | table 991/77560=1.28 (card 991/77560=1.28); MetricFlow 991/77560=0.012777 -> 1.28 |
| metric | repeat_rate_ever | PASS | table 2887/94983=3.04 (card 2887/94983=3.04) |
| metric | review_score | PASS | table 397176/95560=4.156 (card 397176/95560=4.156); MetricFlow 397176/95560=4.156300 -> 4.156 |
| metric | late_review_gap_raw | PASS | table None/94302=2.04 (card -/94302=2.04) |
| metric | late_rate_monthly | PASS | MetricFlow by month vs table: 20/20 months identical (numerator and denominator) |
| diagram | ONTOLOGY.md entity diagram | PASS | regenerate with: python ontology/check.py --mermaid |
