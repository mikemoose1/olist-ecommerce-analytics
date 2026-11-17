-- Rule: modeling never creates or loses money. Item price and freight totals in the mart
-- equal the raw file totals to the cent (catches fan-out from a bad join).
with mart as (
    select sum(price) as price, sum(freight_value) as freight from {{ ref('fct_order_items') }}
),
raw as (
    select sum(cast(price as decimal(12, 2))) as price, sum(cast(freight_value as decimal(12, 2))) as freight
    from {{ source('olist_raw', 'olist_order_items_dataset') }}
)
select mart.*, raw.price as raw_price, raw.freight as raw_freight
from mart, raw
where mart.price <> raw.price or mart.freight <> raw.freight
