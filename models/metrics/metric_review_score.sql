-- METRIC: review score = mean of the ONE chosen review per order (1-5 stars), on the late-rate
-- population (delivered with a date, >= 1 item, analysis window). Also publishes the raw
-- on-time minus late gap. Reviews dated before delivery are kept (see C2).
with p as (
    select delivery_state, review_score
    from {{ ref('fct_orders') }}
    where delivery_state in ('delivered_on_time', 'delivered_late')
      and n_items > 0 and in_analysis_window and review_score is not null
)
select 'review_score' as metric_name, 'chosen_review_per_order' as rule,
       sum(review_score) as numerator, count(*) as denominator, round(avg(review_score), 3) as value_pct
from p
union all
select 'late_review_gap_raw', 'mean(on_time) - mean(late), uncontrolled',
       null, count(*),
       round(avg(review_score) filter (where delivery_state = 'delivered_on_time')
           - avg(review_score) filter (where delivery_state = 'delivered_late'), 3)
from p
