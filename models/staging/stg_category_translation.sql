-- Grain: one row per Portuguese category name. PK: product_category_name. 1:1 with raw (71 rows).
select product_category_name, product_category_name_english
from {{ source('olist_raw', 'product_category_name_translation') }}
