-- Grain: one row per seller. PK: seller_id. 1:1 with raw.
select
    seller_id,
    seller_zip_code_prefix   as zip_code_prefix,
    seller_city              as city,
    seller_state             as state
from {{ source('olist_raw', 'olist_sellers_dataset') }}
