"""Correct answers written other ways, across layers (staging, intermediate, marts, metrics) and SQL idioms.
selftest.py requires every one to score RIGHT, so a scorer change that rejects honest work fails the selftest."""
# correct alternative formulations, one (qid, sql) per entry; every one must score RIGHT
J = "order_status = 'delivered' and delivered_to_customer_at is not null and n_items > 0 and n_parcels = 1"
W = "purchase_date between date '2017-01-01' and date '2018-08-31'"
ALTS = [
    # q01 late rate
    ("q01", "select value_pct from metrics.metric_late_rate"),
    ("q01", "select round(100.0 * avg(is_late::int), 2) from metrics.metric_late_rate_orders"),
    ("q01", f"select round(100.0 * sum((cast(delivered_to_customer_at as date) > estimated_delivery_date)::int) / count(1), 2) from marts.fct_orders where {J} and purchase_date >= date '2017-01-01' and purchase_date < date '2018-09-01'"),
    ("q01", f"select round(100.0 * avg(case when days_past_promise > 0 then 1 else 0 end), 2) from marts.fct_orders where {J} and {W}"),
    ("q01", f"select round(100.0 * avg((cast(o.delivered_to_customer_at as date) > o.estimated_delivery_date)::int), 2) from marts.fct_orders o join marts.dim_date d on d.date_day = o.purchase_date where d.in_analysis_window and o.order_status = 'delivered' and o.delivered_to_customer_at is not null and o.n_items > 0 and o.n_parcels = 1"),
    # q02 judged count
    ("q02", "select denominator from metrics.metric_late_rate"),
    ("q02", "select count(*) from metrics.metric_late_rate_orders"),
    ("q02", f"select sum(1) from marts.fct_orders where {J} and extract(year from purchase_date) * 100 + extract(month from purchase_date) between 201701 and 201808"),
    ("q02", f"select count(*) from marts.fct_orders, marts.dim_date d where d.date_day = purchase_date and d.in_analysis_window and {J}"),
    ("q02", f"select max(n) from (select count(*) over () n from marts.fct_orders where {J} and {W})"),
    # q03 / q11 repeat rate
    ("q03", "select value_pct from metrics.metric_repeat_rate_90d"),
    ("q03", "select round(100.0 * avg(repeated::int), 2) from metrics.metric_repeat_rate_90d_people"),
    ("q03", "select value_pct from metrics.metrics_headline where metric_name = 'repeat_rate_90d'"),
    ("q11", "with q as (select customer_unique_id cu, purchased_at ts from intermediate.int_customer_orders where is_qualifying_order), f as (select cu, min(ts) ts from q group by 1), e as (select * from f where ts <= (select max(ts) from q) - interval 90 day) select round(100.0 * avg((exists (select 1 from q where q.cu = e.cu and q.ts >= e.ts + interval 1 day and q.ts <= e.ts + interval 90 day))::int), 2) from e"),
    # q04 review score
    ("q04", "select value_pct from metrics.metric_review_score where metric_name = 'review_score'"),
    ("q04", f"select round(sum(review_score) / count(review_score), 3) from marts.fct_orders where order_status = 'delivered' and delivered_to_customer_at is not null and n_items > 0 and {W}"),
    # q05 March 2018
    ("q05", "select value_pct from metrics.metric_late_rate_monthly where year_month = '2018-03'"),
    ("q05", f"select round(100.0 * avg((cast(delivered_to_customer_at as date) > estimated_delivery_date)::int), 2) from marts.fct_orders where {J} and date_trunc('month', purchase_date) = date '2018-03-01'"),
    ("q05", f"select round(100.0 * avg((cast(delivered_to_customer_at as date) > estimated_delivery_date)::int), 2) from marts.fct_orders where {J} and extract(year from purchase_date) = 2018 and extract(month from purchase_date) = 3"),
    ("q05", "select round(100.0 * avg(is_late::int), 2) from metrics.metric_late_rate_orders where purchase_date >= date '2018-03-01' and purchase_date < date '2018-04-01'"),
    # q06 distinct customers
    ("q06", "select count(*) from marts.dim_customer"),
    ("q06", "select count(distinct customer_unique_id) from staging.stg_customers"),
    ("q06", "select count(distinct c.customer_unique_id) from staging.stg_orders o join staging.stg_customers c using (customer_id)"),
    ("q06", "select count(distinct customer_unique_id) from intermediate.int_customer_orders"),
    # q07 multi-seller orders
    ("q07", "select count(*) from (select order_id from staging.stg_order_items group by 1 having count(distinct seller_id) > 1)"),
    ("q07", "select count(*) from (select order_id from intermediate.int_parcels group by 1 having count(*) > 1)"),
    ("q07", "select count(*) from marts.fct_orders where n_parcels > 1"),
    # q08
    ("q08", "select round(avg(review_score), 3) from metrics.metric_late_rate_orders where is_late and review_score is not null"),
    # q09 top state (text)
    ("q09", "select arg_max(ship_to_state, r) from (select ship_to_state, avg(is_late::int) r from metrics.metric_late_rate_orders group by 1 having count(*) >= 1000)"),
    ("q09", f"select ship_to_state from marts.fct_orders where {J} and {W} group by 1 having count(*) >= 1000 qualify row_number() over (order by avg((cast(delivered_to_customer_at as date) > estimated_delivery_date)::int) desc) = 1"),
    # q10 canceled share, cross-layer
    ("q10", "select round(100.0 * avg((order_status = 'canceled')::int), 2) from staging.stg_orders"),
    ("q10", "select round(100.0 * avg((order_status = 'canceled')::int), 2) from intermediate.int_order_delivery"),
    ("q10", "select round(100.0 * sum((order_status = 'canceled')::int) / count(1), 2) from marts.fct_orders"),
    ("q10", "select round(100.0 * \"canceled\" / (select count(*) from marts.fct_orders), 2) from (pivot (select order_status from marts.fct_orders) on order_status in ('canceled') using count(*))"),
    # q12 / q13
    ("q12", "select count(*) from marts.dim_customer c where first_qualifying_order_at <= (select max(purchased_at) from intermediate.int_customer_orders where is_qualifying_order) - interval 90 day and exists (select 1 from intermediate.int_customer_orders o where o.is_qualifying_order and o.customer_unique_id = c.customer_unique_id and o.purchased_at between c.first_qualifying_order_at + interval 1 day and c.first_qualifying_order_at + interval 90 day)"),
    ("q13", "select count(*) from marts.dim_customer where first_qualifying_order_at <= (select max(purchased_at) from marts.fct_orders where is_qualifying_order) - interval 90 day"),
    # q16 / q17
    ("q16", "select count(*) from staging.stg_orders where order_status = 'canceled'"),
    ("q16", "select sum((order_status = 'canceled')::int) from intermediate.int_order_delivery"),
    ("q17", "select round(100.0 * count(delivered_to_customer_at) / count(*), 2) from staging.stg_orders where order_status = 'canceled'"),
    # q18 no parcels
    ("q18", "select count(*) from marts.fct_orders where n_items = 0"),
    ("q18", "select count(*) from staging.stg_orders o left join staging.stg_order_items i using (order_id) where i.order_id is null"),
    # q19 / q20
    ("q19", "select count(*) from marts.fct_orders where not in_analysis_window"),
    ("q19", "select count(*) from marts.fct_orders o join marts.dim_date d on d.date_day = o.purchase_date where not d.in_analysis_window"),
    ("q20", "select count(*) from marts.fct_orders where in_analysis_window and review_id is null"),
    # q21 / q22
    ("q21", "select count(*) from marts.dim_customer where n_qualifying_orders = 0"),
    ("q22", "select count(distinct customer_unique_id) from intermediate.int_customer_orders where is_qualifying_order"),
    ("q22", "select count(*) from marts.dim_customer where first_qualifying_order_at is not null"),
    # q23
    ("q23", "select count(*) from metrics.metric_late_rate_orders where is_late and review_score is null"),
    # q24 top month (text)
    ("q24", "select arg_max(year_month, value_pct) from metrics.metric_late_rate_monthly"),
    ("q24", f"select strftime(date_trunc('month', purchase_date), '%Y-%m') from marts.fct_orders where {J} and {W} group by 1 order by avg((cast(delivered_to_customer_at as date) > estimated_delivery_date)::int) desc limit 1"),
    # q14 / q15 cohort repeat rates
    ("q14", "with q as (select customer_unique_id cu, purchased_at ts from intermediate.int_customer_orders where is_qualifying_order), e as (select customer_unique_id cu, first_qualifying_order_at ts from marts.dim_customer where first_qualifying_order_at >= timestamp '2017-03-01' and first_qualifying_order_at < timestamp '2017-04-01' and first_qualifying_order_at <= (select max(ts) from q) - interval 90 day) select round(100.0 * avg((exists (select 1 from q where q.cu = e.cu and q.ts between e.ts + interval 1 day and e.ts + interval 90 day))::int), 2) from e"),
    ("q15", "with q as (select customer_unique_id cu, purchased_at ts from intermediate.int_customer_orders where is_qualifying_order), e as (select customer_unique_id cu, purchased_at ts from intermediate.int_customer_orders where customer_qualifying_order_seq = 1 and ship_to_state = 'GO' and purchased_at <= (select max(ts) from q) - interval 90 day) select round(100.0 * sum((exists (select 1 from q where q.cu = e.cu and q.ts between e.ts + interval 1 day and e.ts + interval 90 day))::int) / count(1), 2) from e"),
    # nested pivot
    ("q16", "select \"canceled\" from (select * from (pivot (select order_status from staging.stg_orders) on order_status in ('canceled', 'delivered') using count(*)))"),
]
