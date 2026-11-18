-- METRIC (headline): 90-day repeat rate, excluding same-day reorders.
-- Population and C6 rule live in metric_repeat_rate_90d_people (one row per eligible person).
select
    'repeat_rate_90d' as metric_name,
    '{{ var('repeat_same_day_rule') }}' as rule,
    count(*) filter (where repeated) as numerator,
    count(*) as denominator,
    round(100.0 * count(*) filter (where repeated) / count(*), 2) as value_pct
from {{ ref('metric_repeat_rate_90d_people') }}
