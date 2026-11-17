-- METRIC: review score = mean of the ONE chosen review per order (1-5 stars), on the late-rate
-- population (metric_late_rate_orders). Also publishes the raw on-time minus late gap.
-- Reviews dated before delivery are kept (C2).
with p as (
    select is_late, review_score
    from {{ ref('metric_late_rate_orders') }}
    where review_score is not null
)
select 'review_score' as metric_name, 'chosen_review_per_order' as rule,
       sum(review_score) as numerator, count(*) as denominator, round(avg(review_score), 3) as value_pct
from p
union all
select 'late_review_gap_raw', 'mean(on_time) - mean(late), uncontrolled',
       null, count(*),
       round(avg(review_score) filter (where not is_late) - avg(review_score) filter (where is_late), 3)
from p
