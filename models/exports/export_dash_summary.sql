-- Dashboard number tiles and reference lines: every headline number the dashboard prints, one row.
-- Grain: one row. Built from the other exports (and the targets and review-cost models), so a tile cannot differ from
-- the chart beside it. The reconciliation tests recompute each number from the detail exports and the analysis files.
-- Fix 1 (reader test): worst3_months_label names the three months and worst3_share_of_late is their share of all late orders.
with ramp as (select * from {{ ref('export_dash_review_ramp') }}),
monthly as (select * from {{ ref('export_dash_monthly') }}),
handoff as (select * from {{ ref('export_dash_handoff') }}),
sellers as (select * from {{ ref('export_dash_sellers') }}),
region as (select * from {{ ref('export_dash_region') }}),
targets as (select * from {{ ref('metric_late_rate_targets') }}),
cost as (select sum(extra_bad_reviews) as extra, sum(reviewed_late_orders) as reviewed_late from {{ ref('metric_review_cost_causal') }}),
evidence as (
    select json_extract(headline, '$.range_across_specifications[0]')::double as range_low,
           json_extract(headline, '$.range_across_specifications[1]')::double as range_high
    from read_json('evidence/review_cost_causal_report.json', format = 'auto', columns = {headline: 'JSON'})
),
worst3 as (select list(month_label order by month_start) as months, sum(late_orders) as late_orders from monthly where is_worst3_late_month),
alarms as (select string_agg(year_month, ', ' order by year_month) as months, count(*) as n from monthly where is_alarm_month),
latest as (select * from monthly order by year_month desc limit 1)
select
    -- the population
    (select sum(orders) from monthly) as judged_orders,
    (select sum(late_orders) from monthly) as late_orders,
    (select sum(late_orders) * 1.0 / sum(orders) from monthly) as late_rate,
    -- panel 1: review cost
    cost.extra as extra_bad_reviews,
    round(cost.extra) as extra_bad_reviews_rounded,
    cost.reviewed_late as reviewed_late_orders,
    (select sum(bad_reviews) from ramp) as bad_reviews_all,
    cost.extra / (select sum(bad_reviews) from ramp) as extra_share_of_bad_reviews,
    evidence.range_low as extra_range_low,
    evidence.range_high as extra_range_high,
    round(evidence.range_low, -1) as extra_range_low_rounded,
    round(evidence.range_high, -1) as extra_range_high_rounded,
    (select sum(bad_reviews) * 1.0 / sum(reviewed_orders) from ramp where days_past_promise_capped <= 0) as ramp_share_up_to_promised_day,
    (select sum(bad_reviews) * 1.0 / sum(reviewed_orders) from ramp where days_past_promise_capped >= 6) as ramp_share_from_day_6,
    (select regr_slope(bad_review_share, days_past_promise_capped) from ramp where days_past_promise_capped between 0 and 6) as ramp_points_per_day,
    -- panel 2: trend and alarm
    latest.year_month as latest_month,
    latest.month_label as latest_month_label,
    latest.late_rate as latest_month_late_rate,
    latest.alarm_line_late_rate as latest_month_alarm_line,
    targets.typical_orders as typical_month_orders,
    targets.alarm_line_late_rate as alarm_line_late_rate,
    targets.goal_late_rate as goal_late_rate,
    targets.stretch_goal_late_rate as stretch_goal_late_rate,
    alarms.n as alarm_months,
    alarms.months as alarm_months_list,
    -- panel 3: handoff
    (select orders from handoff where is_late_handoff) as late_handoff_orders,
    (select late_orders from handoff where is_late_handoff) as late_handoff_late_orders,
    (select late_rate from handoff where is_late_handoff) as late_handoff_late_rate,
    (select late_rate from handoff where not is_late_handoff) as on_time_handoff_late_rate,
    (select share_of_all_late from handoff where is_late_handoff) as late_handoff_share_of_late,
    -- panel 4: sellers
    (select count(*) from sellers where late_after_late_handoff_orders > 0) as sellers_with_late_after_late_handoff,
    (select sum(late_after_late_handoff_orders) from sellers where is_top10) as top10_late_after_late_handoff_orders,
    (select sum(share_of_late_after_late_handoff) from sellers where is_top10) as top10_share_of_late_after_late_handoff,
    (select seller_code from sellers where rank_by_late_after_late_handoff = 1) as top_seller_code,
    (select late_after_late_handoff_orders from sellers where rank_by_late_after_late_handoff = 1) as top_seller_late_after_late_handoff_orders,
    -- panel 5: where and when
    (select late_rate from region where region_group = 'North and northeast') as nne_late_rate,
    (select late_rate from region where region_group = 'Rest of Brazil') as rest_late_rate,
    (select share_of_all_late from region where region_group = 'North and northeast') as nne_share_of_late,
    worst3.late_orders * 1.0 / (select sum(late_orders) from monthly) as worst3_share_of_late,
    worst3.months[1] || ', ' || worst3.months[2] || ' and ' || worst3.months[3] as worst3_months_label
from cost, evidence, targets, worst3, alarms, latest
