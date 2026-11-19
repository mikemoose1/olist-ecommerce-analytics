-- Extra 1-2 star reviews CAUSED by late delivery, by how late the order was.
-- Grain: one row per days-late bin (6 rows). PK: days_late_bin.
-- Counts come from this warehouse: reviewed late orders in the judged population, binned by whole days past the promise.
-- Effects come from seed review_cost_effects (review_cost_causal/analyze.py): the rise in the chance of a bad review at
-- that lateness, against the same seller's on-time orders in the same category and month, baseline 'arrived just on time'.
-- extra_bad_reviews = reviewed late orders in the bin x effect. The total is the dashboard's review-cost number.
with late_reviewed as (
    select f.days_past_promise
    from {{ ref('metric_late_rate_orders') }} o
    join {{ ref('fct_orders') }} f on f.order_id = o.order_id
    where o.is_late and o.review_score is not null
),
binned as (
    select e.days_late_bin, e.min_days_late, e.max_days_late, e.effect_on_bad_share, e.effect_se,
           e.reviewed_late_orders_at_estimation,
           count(l.days_past_promise) as reviewed_late_orders
    from {{ ref('review_cost_effects') }} e
    left join late_reviewed l on l.days_past_promise between e.min_days_late and e.max_days_late
    group by all
)
select
    days_late_bin, min_days_late, max_days_late, reviewed_late_orders, reviewed_late_orders_at_estimation,
    effect_on_bad_share, effect_se,
    reviewed_late_orders * effect_on_bad_share as extra_bad_reviews
from binned
order by min_days_late
