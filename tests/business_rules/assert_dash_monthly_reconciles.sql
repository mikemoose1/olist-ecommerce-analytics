-- Rule (dashboard panels 2 and 5): the monthly export has all 20 months, and each month matches the story's month table
-- (story/data/late_by_month.csv: orders, late orders, late rate to 6 places, share of all late) and the control chart
-- (alarm line, alarm flag, thin flag). The lines match facts.json: alarm 8.38%, goal 4.43% (shown 4.4%), stretch 2.25% (shown 2.3%),
-- flagged months 2017-11, 2018-02 and 2018-03, latest month 2018-08 at 6.3%.
-- One row per number that differs; passes when it returns nothing.
with m as (select * from {{ ref('export_dash_monthly') }}),
s as (select * from {{ ref('export_dash_summary') }}),
c as (select * from {{ ref('metric_late_rate_control_chart') }}),
f as (select * from read_json('story/data/facts.json', format = 'auto', columns = {targets: 'JSON', judged_orders: 'BIGINT', late_orders: 'BIGINT'})),
story_month as (select * from read_csv('story/data/late_by_month.csv', header = true,
    columns = {segment: 'VARCHAR', orders: 'BIGINT', late: 'BIGINT', late_rate: 'DOUBLE', ci_low: 'DOUBLE', ci_high: 'DOUBLE', share_of_late: 'DOUBLE'})),
expected_flagged as (select unnest(['2017-11', '2018-02', '2018-03']) as year_month),
totals as (select count(*) as months, sum(orders) as orders, sum(late_orders) as late, sum(share_of_all_late) as share_sum from m),
checks_ran as (
    select 'months in the export (20)' as what, t.months::double as got, 20::double as expected, 0 as tolerance from totals t
    union all select 'orders add up to facts.json', t.orders::double, f.judged_orders::double, 0 from totals t, f
    union all select 'late orders add up to facts.json', t.late::double, f.late_orders::double, 0 from totals t, f
    union all select 'shares of all late add up to 1', t.share_sum, 1, 0.000000001 from totals t
    union all select 'alarm line (typical month) vs facts.json (6 places)', round(s.alarm_line_late_rate, 6), json_extract(f.targets, '$.alarm_line')::double, 0.0000006 from s, f
    union all select 'goal line vs facts.json (6 places)', round(s.goal_late_rate, 6), json_extract(f.targets, '$.goal')::double, 0.0000006 from s, f
    union all select 'stretch line vs facts.json (6 places)', round(s.stretch_goal_late_rate, 6), json_extract(f.targets, '$.stretch')::double, 0.0000006 from s, f
    union all select 'typical month order count vs facts.json', s.typical_month_orders::double, json_extract(f.targets, '$.typical_orders')::double, 0 from s, f
    union all select 'line on every month row equals the summary: alarm', (select max(abs(typical_month_alarm_line_late_rate - s.alarm_line_late_rate)) from m), 0, 0.0000000001 from s
    union all select 'line on every month row equals the summary: goal', (select max(abs(goal_late_rate - s.goal_late_rate)) from m), 0, 0.0000000001 from s
    union all select 'line on every month row equals the summary: stretch', (select max(abs(stretch_goal_late_rate - s.stretch_goal_late_rate)) from m), 0, 0.0000000001 from s
    union all select 'tile: alarm line, % to 2 places (8.38)', round(100 * s.alarm_line_late_rate, 2), 8.38, 0 from s
    union all select 'tile: goal line, % to 1 place (4.4)', round(100 * s.goal_late_rate, 1), 4.4, 0 from s
    union all select 'tile: goal line, % to 2 places (4.43)', round(100 * s.goal_late_rate, 2), 4.43, 0 from s
    union all select 'tile: stretch line, % to 1 place (2.3)', round(100 * s.stretch_goal_late_rate, 1), 2.3, 0 from s
    union all select 'tile: stretch line, % to 2 places (2.25)', round(100 * s.stretch_goal_late_rate, 2), 2.25, 0 from s
    union all select 'tile: late rate, % to 2 places (6.87)', round(100 * s.late_rate, 2), 6.87, 0 from s
    union all select 'tile: latest month is 2018-08', (s.latest_month = '2018-08')::int, 1, 0 from s
    union all select 'tile: latest month late rate, % to 1 place (6.3)', round(100 * s.latest_month_late_rate, 1), 6.3, 0 from s
    union all select 'tile: latest month alarm line, % to 2 places (8.43)', round(100 * s.latest_month_alarm_line, 2), 8.43, 0 from s
    union all select 'tile: flagged months (3)', s.alarm_months::double, 3, 0 from s
    union all select 'tile: flagged months list (2017-11, 2018-02, 2018-03)', (s.alarm_months_list = '2017-11, 2018-02, 2018-03')::int, 1, 0 from s
),
checks as (
    select * from checks_ran
    union all select 'checks that ran (expected 22; a check with no input row would otherwise vanish)', (select count(*) from checks_ran)::double, 22::double, 0
),
problems as (select what, got, expected from checks where got is null or expected is null or abs(got - expected) > tolerance),
month_problems as (
    select 'month ' || coalesce(m.year_month, sm.segment) || ': differs from the story month table or is missing' as what, m.late_orders::double as got, sm.late::double as expected
    from m full outer join story_month sm on sm.segment = m.year_month
    where m.year_month is null or sm.segment is null
       or m.orders <> sm.orders or m.late_orders <> sm.late
       or abs(m.late_rate - sm.late_rate) > 0.0000006
       or abs(m.share_of_all_late - sm.share_of_late) > 0.0000006
),
chart_problems as (
    select 'month ' || m.year_month || ': alarm line, alarm flag or thin flag differs from the control chart' as what, m.alarm_line_late_rate as got, c.laney_ucl as expected
    from m join c on c.year_month = m.year_month
    where m.alarm_line_late_rate is distinct from c.laney_ucl or m.is_alarm_month is distinct from c.laney_signal
       or m.is_thin_month is distinct from c.thin_month or abs(m.late_rate - c.late_rate) > 0.0000000001
),
flag_problems as (
    select 'flagged but not expected: ' || year_month as what, null::double as got, null::double as expected
    from (select year_month from m where is_alarm_month except select year_month from expected_flagged)
    union all
    select 'expected but not flagged: ' || year_month, null, null
    from (select year_month from expected_flagged except select year_month from m where is_alarm_month)
)
select * from problems union all select * from month_problems union all select * from chart_problems union all select * from flag_problems
