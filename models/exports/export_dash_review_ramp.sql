-- Dashboard panel 1 (line): share of reviews that are 1-2 stars, by days past the promised day.
-- Grain: one row per whole day, capped at -30 and +30 (61 rows). PK: days_past_promise_capped.
-- A straight copy of metric_bad_review_by_days_late plus the share and a phase label for the direct labels on the chart.
-- Phases: up to the promised day (day 0 or earlier), climbing (days 1 to 5), levelled (day 6 on).
select
    days_past_promise_capped,
    case when days_past_promise_capped <= 0 then 'up to the promised day'
         when days_past_promise_capped < 6 then 'climbing'
         else 'levelled' end as phase,
    orders,
    reviewed_orders,
    bad_reviews,
    bad_reviews * 1.0 / nullif(reviewed_orders, 0) as bad_review_share
from {{ ref('metric_bad_review_by_days_late') }}
order by days_past_promise_capped
