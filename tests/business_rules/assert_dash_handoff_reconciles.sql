-- Rule (dashboard panel 3): the two handoff bars match the story's handoff table (story/data/late_by_handoff.csv) and
-- the targets model, and add up. Late handoff 21.2% late (1,809 of 8,530) against 5.4% after an on-time handoff, and
-- late handoffs started 27.8% of all 6,518 late orders. One order has no handoff time and sits in neither bar.
-- The group totals are recomputed from the monthly export (a separate path from the handoff export's own source).
-- One row per number that differs; passes when it returns nothing.
with h as (select * from {{ ref('export_dash_handoff') }}),
s as (select * from {{ ref('export_dash_summary') }}),
t as (select * from {{ ref('metric_late_rate_targets') }}),
m as (select sum(late_handoff_orders) as lh_n, sum(late_handoff_late_orders) as lh_late, sum(on_time_handoff_orders) as ok_n,
             sum(on_time_handoff_late_orders) as ok_late, sum(orders) as judged, sum(late_orders) as late from {{ ref('export_dash_monthly') }}),
no_handoff as (select count(*) as n, count(*) filter (where is_late) as late from {{ ref('dash_order_base') }} where handed_over_late is null),
f as (select * from read_json('story/data/facts.json', format = 'auto', columns = {handoff_late_rate: 'DOUBLE', handoff_ok_rate: 'DOUBLE', handoff_late_share_of_late: 'DOUBLE'})),
story_h as (select * from read_csv('story/data/late_by_handoff.csv', header = true,
    columns = {segment: 'VARCHAR', orders: 'BIGINT', late: 'BIGINT', late_rate: 'DOUBLE', ci_low: 'DOUBLE', ci_high: 'DOUBLE', share_of_late: 'DOUBLE'})),
late_h as (select * from h where is_late_handoff),
ok_h as (select * from h where not is_late_handoff),
checks_ran as (
    select 'two groups in the export (2)' as what, (select count(*) from h)::double as got, 2::double as expected, 0 as tolerance
    union all select 'late handoff orders vs targets', late_h.orders::double, t.late_handoff_orders::double, 0 from late_h, t
    union all select 'late handoff late orders vs targets', late_h.late_orders::double, t.late_handoff_late_orders::double, 0 from late_h, t
    union all select 'on-time handoff orders vs targets', ok_h.orders::double, t.on_time_handoff_orders::double, 0 from ok_h, t
    union all select 'on-time handoff late orders vs targets', ok_h.late_orders::double, t.on_time_handoff_late_orders::double, 0 from ok_h, t
    union all select 'late handoff orders vs the monthly export', late_h.orders::double, m.lh_n::double, 0 from late_h, m
    union all select 'late handoff late orders vs the monthly export', late_h.late_orders::double, m.lh_late::double, 0 from late_h, m
    union all select 'on-time handoff orders vs the monthly export', ok_h.orders::double, m.ok_n::double, 0 from ok_h, m
    union all select 'on-time handoff late orders vs the monthly export', ok_h.late_orders::double, m.ok_late::double, 0 from ok_h, m
    union all select 'groups add up to judged orders minus orders with no handoff time', (select sum(orders) from h)::double, (m.judged - nd.n)::double, 0 from m, no_handoff nd
    union all select 'groups add up to late orders minus late orders with no handoff time', (select sum(late_orders) from h)::double, (m.late - nd.late)::double, 0 from m, no_handoff nd
    union all select 'late handoff late rate vs facts.json (6 places)', round(late_h.late_rate, 6), f.handoff_late_rate, 0.0000006 from late_h, f
    union all select 'on-time handoff late rate vs facts.json (6 places)', round(ok_h.late_rate, 6), f.handoff_ok_rate, 0.0000006 from ok_h, f
    union all select 'late handoff share of late vs facts.json (6 places)', round(late_h.share_of_all_late, 6), f.handoff_late_share_of_late, 0.0000006 from late_h, f
    union all select 'late handoff late rate vs story csv (6 places)', round(late_h.late_rate, 6), sh.late_rate, 0.0000006 from late_h, story_h sh where sh.segment = 'Handed over after ship-by'
    union all select 'on-time handoff late rate vs story csv (6 places)', round(ok_h.late_rate, 6), sh.late_rate, 0.0000006 from ok_h, story_h sh where sh.segment = 'Handed over on time'
    union all select 'late handoff orders vs story csv', late_h.orders::double, sh.orders::double, 0 from late_h, story_h sh where sh.segment = 'Handed over after ship-by'
    union all select 'on-time handoff orders vs story csv', ok_h.orders::double, sh.orders::double, 0 from ok_h, story_h sh where sh.segment = 'Handed over on time'
    union all select 'summary tiles equal the bars: late handoff late rate', s.late_handoff_late_rate, late_h.late_rate, 0.0000000001 from s, late_h
    union all select 'summary tiles equal the bars: on-time handoff late rate', s.on_time_handoff_late_rate, ok_h.late_rate, 0.0000000001 from s, ok_h
    union all select 'summary tiles equal the bars: share of late', s.late_handoff_share_of_late, late_h.share_of_all_late, 0.0000000001 from s, late_h
    union all select 'tile: late handoff late rate, % to 1 place (21.2)', round(100 * s.late_handoff_late_rate, 1), 21.2, 0 from s
    union all select 'tile: on-time handoff late rate, % to 1 place (5.4)', round(100 * s.on_time_handoff_late_rate, 1), 5.4, 0 from s
    union all select 'tile: late handoff share of late, % to 1 place (27.8)', round(100 * s.late_handoff_share_of_late, 1), 27.8, 0 from s
    union all select 'tile: late handoff orders (8,530)', s.late_handoff_orders::double, 8530, 0 from s
    union all select 'tile: late handoff late orders (1,809)', s.late_handoff_late_orders::double, 1809, 0 from s
),
checks as (
    select * from checks_ran
    union all select 'checks that ran (expected 26; a check with no input row would otherwise vanish)', (select count(*) from checks_ran)::double, 26::double, 0
)
select what, got, expected from checks where got is null or expected is null or abs(got - expected) > tolerance
