-- Grain: one row per person. PK: customer_unique_id.
-- first_qualifying_order_at is the start of the repeat-rate clock; first_order_at_any_status includes
-- canceled/unavailable orders (they differ for 45 people).
-- Address = the ship-to address of the person's most recent order (C5). Order-time addresses
-- stay on fct_orders (ship_to_*), so geography metrics never depend on this choice.
with ranked as (
    select *, row_number() over (partition by customer_unique_id order by purchased_at desc, order_id desc) as rn
    from {{ ref('int_customer_orders') }}
)
select
    r.customer_unique_id,
    r.ship_to_zip_code_prefix as zip_code_prefix,
    r.ship_to_city            as city,
    r.ship_to_state           as state,
    g.lat, g.lng,
    agg.first_order_at_any_status,
    agg.first_qualifying_order_at,
    agg.n_orders,
    agg.n_qualifying_orders
from ranked r
join (
    select customer_unique_id, min(purchased_at) as first_order_at_any_status,
           min(purchased_at) filter (where is_qualifying_order) as first_qualifying_order_at,
           count(*) as n_orders,
           count(*) filter (where is_qualifying_order) as n_qualifying_orders
    from {{ ref('int_customer_orders') }} group by 1
) agg using (customer_unique_id)
left join {{ ref('int_geo_zip') }} g on g.zip_code_prefix = r.ship_to_zip_code_prefix
where r.rn = 1
