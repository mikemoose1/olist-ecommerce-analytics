-- Grain: one row per item line. PK: (order_id, order_item_id).
-- FKs: order_id -> fct_orders, parcel_key -> int_parcels, product_id -> dim_product, seller_id -> dim_seller.
select
    i.order_id,
    i.order_item_id,
    p.parcel_key,
    i.product_id,
    i.seller_id,
    i.shipping_limit_at,
    i.price,
    i.freight_value
from {{ ref('stg_order_items') }} i
join {{ ref('int_parcels') }} p using (order_id, seller_id)
