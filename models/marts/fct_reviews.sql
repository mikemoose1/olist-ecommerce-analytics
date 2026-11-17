-- Grain: one row per review-on-order. PK: (review_id, order_id). FK: order_id -> fct_orders.
-- is_chosen_for_order marks the one review that represents the order in metrics.
select
    review_id, order_id, review_score, review_comment_title, review_comment_message,
    review_created_at, review_created_on, review_answered_at,
    is_chosen_for_order, review_before_delivery
from {{ ref('int_order_review') }}
