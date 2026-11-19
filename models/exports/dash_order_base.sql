{{ config(materialized='ephemeral') }}
-- One row per judged order, with what the dashboard needs to group it: the seller, the ship-to state, and whether the
-- seller handed the parcel to the carrier after the last ship-by time. Not exported itself; the seller, region and
-- handoff exports are cut from it, so they cannot disagree about which orders count.
-- Population and "late" come from metric_late_rate_orders (the one definition). Handoff uses the repo's own rule
-- (delivered_to_carrier_at > last_shipping_limit_at); an order with no handoff time has handed_over_late = null and
-- is left out of both handoff groups. Every judged order has one seller (the tests below check it).
with judged as (
    select o.order_id, o.is_late, o.ship_to_state,
           f.delivered_to_carrier_at > f.last_shipping_limit_at as handed_over_late
    from {{ ref('metric_late_rate_orders') }} o
    join {{ ref('fct_orders') }} f on f.order_id = o.order_id
),
one_seller as (
    select order_id, min(seller_id) as seller_id, count(distinct seller_id) as n_sellers
    from {{ ref('fct_order_items') }}
    group by 1
)
select j.order_id, s.seller_id, s.n_sellers, j.ship_to_state, j.is_late, j.handed_over_late
from judged j
left join one_seller s on s.order_id = j.order_id
