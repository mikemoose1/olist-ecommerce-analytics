-- Hand-written answers, one query per question. Written from the marts, NOT from the metric tables,
-- so they are an independent route to each number. Each block starts with "-- q<id>".
-- q01
select round(100.0 * avg((cast(delivered_to_customer_at as date) > estimated_delivery_date)::int), 2)
from marts.fct_orders
where order_status = 'delivered' and delivered_to_customer_at is not null and n_items > 0
  and purchase_date between date '2017-01-01' and date '2018-08-31' and n_parcels = 1;
-- q02
select count(*) from marts.fct_orders
where order_status = 'delivered' and delivered_to_customer_at is not null and n_items > 0
  and purchase_date between date '2017-01-01' and date '2018-08-31' and n_parcels = 1;
-- q03
with q as (
    select o.customer_unique_id cu, o.purchased_at ts
    from marts.fct_orders o
    where o.order_status not in ('canceled', 'unavailable') and o.n_items > 0
),
f as (select cu, min(ts) ts from q group by 1),
e as (select * from f where ts <= (select max(ts) from q) - interval 90 day)
select round(100.0 * avg((exists (select 1 from q where q.cu = e.cu and q.ts >= e.ts + interval 1 day
                                                    and q.ts <= e.ts + interval 90 day))::int), 2)
from e;
-- q04
select round(avg(review_score), 3) from marts.fct_orders
where order_status = 'delivered' and delivered_to_customer_at is not null and n_items > 0
  and purchase_date between date '2017-01-01' and date '2018-08-31' and review_score is not null;
-- q05
select round(100.0 * avg((cast(delivered_to_customer_at as date) > estimated_delivery_date)::int), 2)
from marts.fct_orders
where order_status = 'delivered' and delivered_to_customer_at is not null and n_items > 0
  and n_parcels = 1 and strftime(purchase_date, '%Y-%m') = '2018-03';
-- q06
select count(distinct customer_unique_id) from marts.fct_orders;
-- q07
select count(*) from (select order_id from marts.fct_order_items group by 1 having count(distinct seller_id) > 1);
-- q08
select round(avg(review_score), 3) from marts.fct_orders
where order_status = 'delivered' and delivered_to_customer_at is not null and n_items > 0
  and purchase_date between date '2017-01-01' and date '2018-08-31' and n_parcels = 1
  and review_score is not null and cast(delivered_to_customer_at as date) > estimated_delivery_date;
-- q09
select ship_to_state from marts.fct_orders
where order_status = 'delivered' and delivered_to_customer_at is not null and n_items > 0
  and purchase_date between date '2017-01-01' and date '2018-08-31' and n_parcels = 1
group by 1 having count(*) >= 1000
order by avg((cast(delivered_to_customer_at as date) > estimated_delivery_date)::int) desc limit 1;
-- q10
select round(100.0 * avg((order_status = 'canceled')::int), 2) from marts.fct_orders;
