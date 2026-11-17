-- Late rate by purchase month, same population and rule as metric_late_rate (full months only).
select
    dt.year_month,
    count(*) filter (where o.is_late) as numerator,
    count(*) as denominator,
    round(100.0 * count(*) filter (where o.is_late) / count(*), 2) as value_pct
from {{ ref('metric_late_rate_orders') }} o
join {{ ref('dim_date') }} dt on dt.date_day = o.purchase_date
group by 1
order by 1
