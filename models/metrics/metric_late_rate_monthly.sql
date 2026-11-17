-- Late rate by purchase month, same population and rule as metric_late_rate (full months only).
select
    dt.year_month,
    count(*) filter (where o.delivery_state = 'delivered_late') as numerator,
    count(*) as denominator,
    round(100.0 * count(*) filter (where o.delivery_state = 'delivered_late') / count(*), 2) as value_pct
from {{ ref('fct_orders') }} o
join {{ ref('dim_date') }} dt on dt.date_day = o.purchase_date
where o.delivery_state in ('delivered_on_time', 'delivered_late') and o.n_items > 0 and o.in_analysis_window
group by 1
order by 1
