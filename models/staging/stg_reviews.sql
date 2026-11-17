-- Grain: one row per review-on-order. PK: (review_id, order_id); review_id alone is NOT unique
-- (789 review_ids appear on more than one order). 1:1 with raw.
-- review_creation_date is effectively a date (only 85 of 99,224 rows have a non-midnight time),
-- so both the raw timestamp and the date are kept; the comparison rule is chosen downstream (C2).
select
    review_id,
    order_id,
    cast(review_score as integer)                     as review_score,
    review_comment_title,
    review_comment_message,
    cast(review_creation_date as timestamp)           as review_created_at,
    cast(cast(review_creation_date as timestamp) as date) as review_created_on,
    cast(review_answer_timestamp as timestamp)        as review_answered_at
from {{ source('olist_raw', 'olist_order_reviews_dataset') }}
