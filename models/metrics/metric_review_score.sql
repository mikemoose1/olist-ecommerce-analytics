-- METRIC: review score = mean of the ONE chosen review per order (1-5 stars).
-- Population: orders delivered with a delivery date, >= 1 item, purchased in the analysis window.
-- This population does NOT depend on the C1 lateness rule: multi-seller orders' reviews are fully observed
-- even though their parcel arrivals are not. Grain is the order: a survey response that the source attaches
-- to several orders counts once per order (467 such repeats in 95,560 orders; per-response mean differs by 0.001).
-- The late-vs-on-time gap uses the late-rate population (metric_late_rate_orders), where "late" is defined.
with all_delivered as (
    select review_score
    from {{ ref('fct_orders') }}
    where delivery_state in ('delivered_on_time', 'delivered_late')
      and n_items > 0 and in_analysis_window and review_score is not null
),
judged as (
    select is_late, review_score
    from {{ ref('metric_late_rate_orders') }}
    where review_score is not null
)
select 'review_score' as metric_name, 'chosen_review_per_order' as rule,
       sum(review_score) as numerator, count(*) as denominator, round(avg(review_score), 3) as value_pct
from all_delivered
union all
select 'late_review_gap_raw', 'mean(on_time) - mean(late), uncontrolled, late-rate population',
       null, count(*),
       round(avg(review_score) filter (where not is_late) - avg(review_score) filter (where is_late), 3)
from judged
