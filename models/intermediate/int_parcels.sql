-- Grain: one row per parcel = the seller-level slice of an order (order x seller).
-- PK: parcel_key. Single owner of seller-level shipping facts. The source has NO parcel-level
-- delivery date, so a parcel's arrival is never observed directly.
select
    {{ dbt_utils.generate_surrogate_key(['order_id', 'seller_id']) }} as parcel_key,
    order_id,
    seller_id,
    min(shipping_limit_at)  as shipping_limit_at,   -- constant within every parcel in the source
    count(*)                as n_items,
    sum(price)              as items_value,
    sum(freight_value)      as freight_value
from {{ ref('stg_order_items') }}
group by order_id, seller_id
