-- Grain: one row per review-on-order (same as stg_reviews). PK: (review_id, order_id).
-- Adds two decisions, each owned here and set by a project var:
--   is_chosen_for_order: exactly one review per reviewed order (C4, var review_pick_rule)
--   review_before_delivery: review created before the order's recorded delivery (C2, var review_before_delivery_compare)
with ranked as (
    select
        r.*,
        row_number() over (
            partition by r.order_id
            order by
            {% if var('review_pick_rule') == 'earliest_creation' %}
                r.review_created_at asc, r.review_answered_at asc, r.review_id
            {% else %}
                r.review_answered_at desc, r.review_id
            {% endif %}
        ) as pick_rank
    from {{ ref('stg_reviews') }} r
)
select
    ranked.review_id,
    ranked.order_id,
    ranked.review_score,
    ranked.review_comment_title,
    ranked.review_comment_message,
    ranked.review_created_at,
    ranked.review_created_on,
    ranked.review_answered_at,
    ranked.pick_rank = 1 as is_chosen_for_order,
    case
        when o.delivered_to_customer_at is null then null
        {% if var('review_before_delivery_compare') == 'timestamp' %}
        else ranked.review_created_at < o.delivered_to_customer_at
        {% else %}
        else ranked.review_created_on < cast(o.delivered_to_customer_at as date)
        {% endif %}
    end as review_before_delivery
from ranked
left join {{ ref('stg_orders') }} o using (order_id)
