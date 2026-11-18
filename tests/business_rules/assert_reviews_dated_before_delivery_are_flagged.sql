-- Rule: a review whose survey was sent (review_creation_date) before its order's recorded delivery is flagged, never silently mixed in.
-- The comparison grain follows the project's chosen rule (var review_before_delivery_compare).
-- Fails on any review whose flag disagrees with its dates, or that is unflagged on a delivered order.
select r.review_id, r.order_id, r.review_before_delivery
from {{ ref('fct_reviews') }} r
join {{ ref('fct_orders') }} o using (order_id)
where o.delivered_to_customer_at is not null
  and (
        r.review_before_delivery is null
     {% if var('review_before_delivery_compare') == 'timestamp' %}
     or r.review_before_delivery <> (r.review_created_at < o.delivered_to_customer_at)
     {% else %}
     or r.review_before_delivery <> (r.review_created_on < cast(o.delivered_to_customer_at as date))
     {% endif %}
  )
