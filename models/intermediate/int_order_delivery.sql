-- Grain: one row per order. PK: order_id.
-- Gives every order exactly ONE delivery_state (an enum instead of booleans that must agree):
--   not_delivered | status_date_conflict | delivered_on_time | delivered_late
-- "Late" is judged by calendar day because the promise (estimated_delivery_date) is a date.
-- delivery_evidence says how much the delivery date can be trusted:
--   order_level_single_parcel | order_level_multi_parcel (date is per order, not per parcel) | no_parcels
with parcels as (
    select order_id, count(*) as n_parcels, max(shipping_limit_at) as last_shipping_limit_at
    from {{ ref('int_parcels') }}
    group by order_id
)
select
    o.order_id,
    o.order_status,
    o.purchased_at,
    o.delivered_to_carrier_at,
    o.delivered_to_customer_at,
    o.estimated_delivery_date,
    coalesce(p.n_parcels, 0) as n_parcels,
    p.last_shipping_limit_at,
    case
        when coalesce(p.n_parcels, 0) = 0 then 'no_parcels'
        when p.n_parcels = 1 then 'order_level_single_parcel'
        else 'order_level_multi_parcel'
    end as delivery_evidence,
    case
        when o.order_status = 'delivered' and o.delivered_to_customer_at is null then 'status_date_conflict'
        when o.order_status <> 'delivered' and o.delivered_to_customer_at is not null then 'status_date_conflict'
        when o.order_status <> 'delivered' then 'not_delivered'
        when cast(o.delivered_to_customer_at as date) > o.estimated_delivery_date then 'delivered_late'
        else 'delivered_on_time'
    end as delivery_state,
    date_diff('day', o.estimated_delivery_date, cast(o.delivered_to_customer_at as date)) as days_past_promise
from {{ ref('stg_orders') }} o
left join parcels p using (order_id)
