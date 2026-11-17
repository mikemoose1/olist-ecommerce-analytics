-- Grain: one row per order. PK: order_id. 1:1 with raw (99,441 rows).
-- estimated_delivery_date is a date in the source (no row carries a time part), so it is typed as DATE.
select
    order_id,
    customer_id,
    order_status,
    cast(order_purchase_timestamp as timestamp)                    as purchased_at,
    cast(order_approved_at as timestamp)                           as approved_at,
    cast(order_delivered_carrier_date as timestamp)                as delivered_to_carrier_at,
    cast(order_delivered_customer_date as timestamp)               as delivered_to_customer_at,
    cast(cast(order_estimated_delivery_date as timestamp) as date) as estimated_delivery_date
from {{ source('olist_raw', 'olist_orders_dataset') }}
