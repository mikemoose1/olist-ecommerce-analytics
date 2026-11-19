-- Rule (dashboard panel 5, the monthly bars; reader-test fix 1): the export names the three worst months and states their
-- share of all late orders. The three months with the most late orders are 2017-11, 2018-02 and 2018-03, and together they
-- hold 48.3% of the 6,518 late orders. The share is recomputed here from the monthly export (late orders by month) and
-- compared with facts.json (top3_months, top3_months_share_of_late) and with the summary the label is printed from.
-- One row per number that differs; passes when it returns nothing.
with m as (select * from {{ ref('export_dash_monthly') }}),
s as (select * from {{ ref('export_dash_summary') }}),
f as (select * from read_json('story/data/facts.json', format = 'auto', columns = {top3_months: 'VARCHAR[]', top3_months_share_of_late: 'DOUBLE'})),
-- the comparators for the 48.3%: what share of ALL orders and of all MONTHS those three months are (from the story's month table)
story_month as (select * from read_csv('story/data/late_by_month.csv', header = true,
    columns = {segment: 'VARCHAR', orders: 'BIGINT', late: 'BIGINT', late_rate: 'DOUBLE', ci_low: 'DOUBLE', ci_high: 'DOUBLE', share_of_late: 'DOUBLE'})),
top3 as (select year_month, late_orders from m order by late_orders desc limit 3),
expected_months as (select unnest(top3_months) as year_month from f),
checks_ran as (
    select 'three months are flagged as the worst' as what, (select count(*) from m where is_worst3_late_month)::double as got, 3::double as expected, 0 as tolerance
    union all select 'share of late held by the three months vs facts.json (6 places)', round((select sum(late_orders) from top3) * 1.0 / (select sum(late_orders) from m), 6), f.top3_months_share_of_late, 0.000000001 from f
    union all select 'summary share equals the recompute', s.worst3_share_of_late, (select sum(late_orders) from top3) * 1.0 / (select sum(late_orders) from m), 0.0000000001 from s
    union all select 'text: three worst months hold, % to 1 place (48.3)', round(100 * s.worst3_share_of_late, 1), 48.3, 0 from s
    union all select 'text: the month label names the three months in order', (s.worst3_months_label = 'Nov 2017, Feb 2018 and Mar 2018')::int, 1, 0 from s
    union all select 'the three are 2017-11, 2018-02 and 2018-03 at the same share on every flagged month row', (select count(*) from m where is_worst3_late_month and year_month in ('2017-11', '2018-02', '2018-03'))::double, 3, 0
    union all select 'three months hold this share of all orders (story month table, 6 places)', round((select sum(orders) from story_month where segment in (select unnest(top3_months) from f)) * 1.0 / (select sum(orders) from story_month), 6),
                      round((select sum(orders) from m where is_worst3_late_month) * 1.0 / (select sum(orders) from m), 6), 0.000000001
    union all select 'summary: share of all orders held by the three months equals the story table', s.worst3_share_of_orders, (select sum(orders) from story_month where segment in (select unnest(top3_months) from f)) * 1.0 / (select sum(orders) from story_month), 0.0000000001 from s
    union all select 'summary: share of all months those three are (3 of 20)', s.worst3_share_of_months, 3.0 / (select count(*) from story_month), 0.0000000001 from s
    union all select 'text: the three months hold, % of orders to 1 place (21.7)', round(100 * s.worst3_share_of_orders, 1), 21.7, 0 from s
    union all select 'text: the three months are this % of all months (15)', round(100 * s.worst3_share_of_months), 15, 0 from s
    union all select 'month label of 2017-11 is Nov 2017', (select (month_label = 'Nov 2017')::int from m where year_month = '2017-11'), 1, 0
    union all select 'month label of 2018-02 is Feb 2018', (select (month_label = 'Feb 2018')::int from m where year_month = '2018-02'), 1, 0
    union all select 'month label of 2018-03 is Mar 2018', (select (month_label = 'Mar 2018')::int from m where year_month = '2018-03'), 1, 0
),
checks as (
    select * from checks_ran
    union all select 'checks that ran (expected 14; a check with no input row would otherwise vanish)', (select count(*) from checks_ran)::double, 14::double, 0
),
problems as (select what, got, expected from checks where got is null or expected is null or abs(got - expected) > tolerance),
month_problems as (
    select 'worst month flag differs from facts.json for ' || coalesce(m.year_month, e.year_month) as what, null::double as got, null::double as expected
    from m full outer join expected_months e on e.year_month = m.year_month
    where (m.is_worst3_late_month and e.year_month is null) or (not m.is_worst3_late_month and e.year_month is not null)
)
select * from problems union all select * from month_problems
