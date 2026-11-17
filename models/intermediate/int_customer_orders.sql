-- Grain: one row per order. PK: order_id.
-- Maps each order to the PERSON (customer_unique_id) and the ship-to address at order time
-- (the order's own customer_id row). A qualifying order is one that was not canceled/unavailable
-- and has at least one item; repeat metrics count qualifying orders only.
with base as (
    select
        o.order_id,
        c.customer_unique_id,
        o.purchased_at,
        c.zip_code_prefix as ship_to_zip_code_prefix,
        c.city            as ship_to_city,
        c.state           as ship_to_state,
        (o.order_status not in ('canceled', 'unavailable')
            and exists (select 1 from {{ ref('stg_order_items') }} i where i.order_id = o.order_id)) as is_qualifying_order
    from {{ ref('stg_orders') }} o
    join {{ ref('stg_customers') }} c using (customer_id)
)
select
    *,
    row_number() over (partition by customer_unique_id order by purchased_at, order_id) as customer_order_seq,
    case when is_qualifying_order then
        row_number() over (partition by customer_unique_id, is_qualifying_order order by purchased_at, order_id)
    end as customer_qualifying_order_seq
from base
