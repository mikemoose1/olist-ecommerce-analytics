-- Share of 1-2 star reviews by how many days after (positive) or before (negative) the promised day the order arrived.
-- Grain: one row per whole day of days_past_promise_capped. PK: days_past_promise_capped.
-- Population: the judged orders of metric_late_rate_orders. Days past promise comes from fct_orders (the repo's own
-- calendar-day difference); an order is late exactly when it is above zero. Days are capped at -30 and +30 so
-- the few extreme orders (about 0.3% beyond either end) share one end row instead of a hundred thin rows.
-- Bad review = chosen review of 1 or 2 stars. Orders with no review count in orders but not in reviewed_orders.
select
    greatest(-30, least(30, f.days_past_promise)) as days_past_promise_capped,
    count(*) as orders,
    count(*) filter (where o.review_score is not null) as reviewed_orders,
    count(*) filter (where o.review_score <= 2) as bad_reviews
from {{ ref('metric_late_rate_orders') }} o
join {{ ref('fct_orders') }} f on f.order_id = o.order_id
group by 1
order by 1
