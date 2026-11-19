-- The alarm line and the goal lines for the monthly late rate, one row.
-- Grain: one row. Built only from metric_late_rate_control_chart (Laney p-prime limits).
--   alarm_line_late_rate   : the upper control limit at a typical month's order count (median of the last 12 months).
--                            A month above it is a real change, not luck. The chart itself uses each month's own limit.
--   safe_goal_late_rate    : 25th percentile of the stable months (inside the limits, not thin): rates Olist already hit
--                            (about 3%, hit in about one month in four; bootstrap uncertainty about 2.8-4.4%).
--                            "Stable" means "not an extreme month", not "healthy": the stable months still average 4.5% late.
--   goal_late_rate         : the median stable month (about 4.4%), the goal line the story draws: half
--                            the stable months already beat it. The safe goal stays in this table but is not drawn.
--   stretch_goal_late_rate : the median stable month if late seller handoffs ran late no more often than on-time ones in
--                            the same month (about 3.4%). Same measure as the goal line, on the same stable months, so
--                            goal minus stretch (about 1 point) is the what-if's effect alone. A what-if, not a tested cause.
--                            Retired: the 25th percentile of this series (about 2.25%) mixed the what-if with a better
--                            month, so it is no longer the stretch line.
-- The story reconciliation columns repeat the headline numbers so a test can tie this table to the story.
with months as (
    select * from {{ ref('metric_late_rate_control_chart') }}
),
last12 as (
    select median(orders) as typical_orders
    from (select orders from months order by year_month desc limit 12)
),
final_fit as (
    select laney_centre_rate, laney_sigma_z from months limit 1
),
stable as (
    select * from months where not laney_signal and not thin_month
)
select
    (select sum(orders) from months) as judged_orders,
    (select sum(late_orders) from months) as late_orders,
    (select sum(late_orders) * 1.0 / sum(orders) from months) as late_rate,
    (select count(*) from months) as months_in_window,
    (select count(*) from months where thin_month) as thin_months,
    (select count(*) from months where laney_signal) as laney_signal_months,
    (select count(*) from months where plain_signal) as plain_signal_months,
    (select count(*) from stable) as stable_months,
    f.laney_centre_rate as stable_centre_rate,
    f.laney_sigma_z,
    l.typical_orders,
    f.laney_centre_rate + 3 * f.laney_sigma_z * sqrt(f.laney_centre_rate * (1 - f.laney_centre_rate) / l.typical_orders) as alarm_line_late_rate,
    (select percentile_cont(0.25) within group (order by late_rate) from stable) as safe_goal_late_rate,
    (select median(late_rate) from stable) as goal_late_rate,
    (select min(late_rate) from stable) as best_stable_month_late_rate,
    (select percentile_cont(0.5) within group (order by late_rate_if_handoffs_ok) from stable) as stretch_goal_late_rate,
    (select sum(late_rate_if_handoffs_ok * orders) / sum(orders) from months) as late_rate_if_handoffs_ok,
    (select sum(late_handoff_orders) from months) as late_handoff_orders,
    (select sum(late_handoff_late_orders) from months) as late_handoff_late_orders,
    (select sum(on_time_handoff_orders) from months) as on_time_handoff_orders,
    (select sum(on_time_handoff_late_orders) from months) as on_time_handoff_late_orders,
    (select sum(reviewed_orders) from months) as reviewed_orders,
    (select sum(bad_reviews) from months) as bad_reviews,
    (select sum(stars_sum_late) * 1.0 / sum(reviewed_late) from months) as avg_stars_late,
    (select sum(stars_sum_on_time) * 1.0 / sum(reviewed_on_time) from months) as avg_stars_on_time
from final_fit f cross join last12 l
