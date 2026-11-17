-- Grain: one row per customer_id. PK: customer_id. 1:1 with raw.
-- customer_id is a per-order surrogate (exactly one order each); customer_unique_id is the person.
select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix   as zip_code_prefix,
    customer_city              as city,
    customer_state             as state
from {{ source('olist_raw', 'olist_customers_dataset') }}
