-- METRIC: late rate = late orders / orders in metric_late_rate_orders (population and C1 rule live there).
select
    'late_rate' as metric_name,
    '{{ var('multi_seller_late_rule') }}' as rule,
    count(*) filter (where is_late) as numerator,
    count(*) as denominator,
    round(100.0 * count(*) filter (where is_late) / count(*), 2) as value_pct
from {{ ref('metric_late_rate_orders') }}
