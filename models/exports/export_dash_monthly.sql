-- Dashboard panels 2 (trend and alarm) and 5 (late orders by month).
-- Grain: one row per purchase month (20 rows). PK: year_month.
-- Each month's own alarm line (Laney upper limit, it moves with the month's order count), the late rate, and the flags
-- that colour the marks. The goal and stretch lines are the same on every row, so Tableau can draw them as lines.
-- late_rate_if_handoffs_ok is the month's late rate if late handoffs were late no more often than on-time ones (a mix-shift
-- what-if, not a tested cause). stretch_whatif_late_rate is the middle month (median) of the stable months under that what-if,
-- the like-for-like partner of goal_late_rate (it comes from metric_late_rate_targets), the median of the months as they were. Stable = not an alarm
-- month and not thin.
-- Panel 5: late_orders is the bar, share_of_all_late is that month's slice of all late orders, and the three months
-- with the most late orders carry is_worst3_late_month (ties go to the later month).
with c as (select * from {{ ref('metric_late_rate_control_chart') }}),
t as (select alarm_line_late_rate, goal_late_rate, stretch_goal_late_rate from {{ ref('metric_late_rate_targets') }}),
ranked as (
    select *, row_number() over (order by late_orders desc, year_month desc) as late_orders_rank,
           sum(late_orders) over () as all_late_orders
    from c
)
select
    r.year_month,
    cast(r.year_month || '-01' as date) as month_start,
    strftime(cast(r.year_month || '-01' as date), '%b %Y') as month_label,
    r.orders,
    r.late_orders,
    r.late_rate,
    r.late_rate_if_handoffs_ok,
    not r.laney_signal and not r.thin_month as is_stable_month,
    r.laney_ucl as own_month_alarm_line_late_rate,
    r.laney_signal as is_alarm_month,
    r.thin_month as is_thin_month,
    r.late_handoff_orders,
    r.late_handoff_late_orders,
    r.on_time_handoff_orders,
    r.on_time_handoff_late_orders,
    r.late_orders * 1.0 / r.all_late_orders as share_of_all_late,
    r.late_orders_rank,
    r.late_orders_rank <= 3 as is_worst3_late_month,
    t.alarm_line_late_rate as typical_month_alarm_line_late_rate,
    t.goal_late_rate,
    t.stretch_goal_late_rate as stretch_whatif_late_rate
from ranked r cross join t
order by r.year_month
