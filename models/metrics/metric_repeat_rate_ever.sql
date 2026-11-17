-- METRIC (secondary): share of people who EVER placed a second qualifying order, all time, no window.
-- Same-day reorders count. This is the first-pass "3.04%"; it is NOT the 90-day headline.
with people as (
    select customer_unique_id, count(*) as n
    from {{ ref('fct_orders') }}
    where is_qualifying_order
    group by 1
)
select
    'repeat_rate_ever' as metric_name,
    'all_time_including_same_day' as rule,
    count(*) filter (where n > 1) as numerator,
    count(*) as denominator,
    round(100.0 * count(*) filter (where n > 1) / count(*), 2) as value_pct
from people
