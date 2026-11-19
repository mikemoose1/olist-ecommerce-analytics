-- Rule (dashboard panels 1, 2 and 5, and the tiles): the columns that are worked out from other columns really are, on every row.
-- Found by the column sweep (verification/column_sweep.py): a wrong month_start, month label, month rank, ramp phase, summary
-- population count or latest-month label used to pass every test.
--   monthly: month_start is the first day of year_month; month_label is the month's name and year, written here from a list of
--     names (not the model's strftime); late_orders_rank, is_worst3_late_month, is_stable_month, late_rate and share_of_all_late
--     are recomputed for every month.
--   ramp: phase and bad_review_share are recomputed for every day.
--   summary: the population (judged orders, late orders, late rate) equals the monthly rows and facts.json; the latest month is the last
--     month and its label is its name.
-- One row per number that differs; passes when it returns nothing. The counts are of rows that differ, so each must be 0.
with m as (select * from {{ ref('export_dash_monthly') }}),
r as (select * from {{ ref('export_dash_review_ramp') }}),
s as (select * from {{ ref('export_dash_summary') }}),
f as (select * from read_json('story/data/facts.json', format = 'auto', columns = {judged_orders: 'BIGINT', late_orders: 'BIGINT', late_rate: 'DOUBLE'})),
names as (select ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as n),
mine as (
    select m.year_month,
           row_number() over (order by m.late_orders desc, m.year_month desc) as rk,
           names.n[cast(substr(m.year_month, 6, 2) as int)] || ' ' || substr(m.year_month, 1, 4) as label
    from m, names
),
tot as (select sum(orders) as orders, sum(late_orders) as late from m)
,
checks_ran as (
    select 'monthly: month_start is the first day of year_month (rows that differ)' as what,
           (select count(*) from m where month_start is distinct from cast(year_month || '-01' as date))::double as got, 0::double as expected, 0 as tolerance
    union all select 'monthly: month_label is the month name and year (rows that differ)', (select count(*) from m join mine using (year_month) where m.month_label is distinct from mine.label)::double, 0, 0
    union all select 'monthly: late_orders_rank orders the months by late orders, a tie to the later month (rows that differ)', (select count(*) from m join mine using (year_month) where m.late_orders_rank is distinct from mine.rk)::double, 0, 0
    union all select 'monthly: is_worst3_late_month is rank 3 or better (rows that differ)', (select count(*) from m where is_worst3_late_month is distinct from (late_orders_rank <= 3))::double, 0, 0
    union all select 'monthly: is_stable_month is not alarm and not thin (rows that differ)', (select count(*) from m where is_stable_month is distinct from (not is_alarm_month and not is_thin_month))::double, 0, 0
    union all select 'monthly: late_rate is late orders over orders (rows that differ)', (select count(*) from m where abs(late_rate - late_orders * 1.0 / orders) > 0.000000000001)::double, 0, 0
    union all select 'monthly: share_of_all_late is the month''s late orders over all late orders (rows that differ)', (select count(*) from m, tot where abs(m.share_of_all_late - m.late_orders * 1.0 / tot.late) > 0.000000000001)::double, 0, 0
    union all select 'ramp: phase is up to the promised day (day 0 or earlier), climbing (1 to 5) or levelled (6 on) (rows that differ)',
           (select count(*) from r where phase is distinct from (case when days_past_promise_capped <= 0 then 'up to the promised day' when days_past_promise_capped <= 5 then 'climbing' else 'levelled' end))::double, 0, 0
    union all select 'ramp: bad_review_share is bad reviews over reviewed orders (rows that differ)', (select count(*) from r where abs(bad_review_share - bad_reviews * 1.0 / nullif(reviewed_orders, 0)) > 0.000000000001)::double, 0, 0
    union all select 'ramp: orders and reviewed orders are not negative and reviews never exceed orders (rows that differ)', (select count(*) from r where reviewed_orders > orders or bad_reviews > reviewed_orders or bad_reviews < 0)::double, 0, 0
    union all select 'summary: judged orders equal the monthly rows', s.judged_orders::double, tot.orders::double, 0 from s, tot
    union all select 'summary: late orders equal the monthly rows', s.late_orders::double, tot.late::double, 0 from s, tot
    union all select 'summary: late rate is late orders over judged orders', s.late_rate, tot.late * 1.0 / tot.orders, 0.0000000001 from s, tot
    union all select 'summary: judged orders vs facts.json', s.judged_orders::double, f.judged_orders::double, 0 from s, f
    union all select 'summary: late orders vs facts.json', s.late_orders::double, f.late_orders::double, 0 from s, f
    union all select 'summary: late rate vs facts.json (5 places, as facts.json writes it)', round(s.late_rate, 5), f.late_rate, 0.000000001 from s, f
    union all select 'summary: latest month is the last month', (s.latest_month = (select max(year_month) from m))::int, 1, 0 from s
    union all select 'summary: latest month label is that month''s name and year', (s.latest_month_label = (select label from mine where year_month = s.latest_month))::int, 1, 0 from s
    union all select 'text: judged orders (94,931)', s.judged_orders::double, 94931, 0 from s
    union all select 'text: late orders (6,518)', s.late_orders::double, 6518, 0 from s
    union all select 'text: latest month label (Aug 2018)', (s.latest_month_label = 'Aug 2018')::int, 1, 0 from s
),
checks as (
    select * from checks_ran
    union all select 'checks that ran (expected 21; a check with no input row would otherwise vanish)', (select count(*) from checks_ran)::double, 21::double, 0
)
select what, got, expected from checks where got is null or expected is null or abs(got - expected) > tolerance
