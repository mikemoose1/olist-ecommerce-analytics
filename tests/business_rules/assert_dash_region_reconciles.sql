-- Rule (dashboard panel 5, region bars): the north and northeast against the rest of Brazil.
-- The region map seed lists the 27 states exactly once, in two groups of 16 and 11; the two bars add up to every judged
-- order and every late order; and they match the story's region table (story/data/late_by_region.csv: orders, late, rate and
-- share to 6 places). Printed: 12.2% against 6.2%, and the north and northeast hold 20.0% of late orders.
-- (That the seed's 16 states are the ones in story/story_data.py NNE is checked in verification/verify_dash_exports.py.)
-- One row per number that differs; passes when it returns nothing.
with r as (select * from {{ ref('export_dash_region') }}),
s as (select * from {{ ref('export_dash_summary') }}),
seed as (select * from {{ ref('dash_region_map') }}),
m as (select sum(orders) as orders, sum(late_orders) as late from {{ ref('export_dash_monthly') }}),
unmapped as (select count(*) as n from {{ ref('dash_order_base') }} b left join seed on seed.state = b.ship_to_state where seed.state is null),
nne as (select * from r where region_group = 'North and northeast'),
rest as (select * from r where region_group = 'Rest of Brazil'),
story_r as (select * from read_csv('story/data/late_by_region.csv', header = true,
    columns = {segment: 'VARCHAR', orders: 'BIGINT', late: 'BIGINT', late_rate: 'DOUBLE', ci_low: 'DOUBLE', ci_high: 'DOUBLE', share_of_late: 'DOUBLE'})),
checks_ran as (
    select 'seed lists 27 states' as what, (select count(*) from seed)::double as got, 27::double as expected, 0 as tolerance
    union all select 'seed lists each state once', (select count(distinct state) from seed)::double, 27, 0
    union all select 'seed has two groups', (select count(distinct region_group) from seed)::double, 2, 0
    union all select 'seed: north and northeast has 16 states', (select count(*) from seed where region_group = 'North and northeast')::double, 16, 0
    union all select 'seed: rest of Brazil has 11 states', (select count(*) from seed where region_group = 'Rest of Brazil')::double, 11, 0
    union all select 'two region rows in the export', (select count(*) from r)::double, 2, 0
    union all select 'no judged order has a state the seed lacks', un.n::double, 0, 0 from unmapped un
    union all select 'regions add up to judged orders', (select sum(orders) from r)::double, m.orders::double, 0 from m
    union all select 'regions add up to late orders', (select sum(late_orders) from r)::double, m.late::double, 0 from m
    union all select 'export states column: north and northeast (16)', nne.states::double, 16, 0 from nne
    union all select 'export states column: rest of Brazil (11)', rest.states::double, 11, 0 from rest
    union all select 'north and northeast vs story csv: orders', nne.orders::double, sr.orders::double, 0 from nne, story_r sr where sr.segment = 'North and northeast'
    union all select 'north and northeast vs story csv: late', nne.late_orders::double, sr.late::double, 0 from nne, story_r sr where sr.segment = 'North and northeast'
    union all select 'north and northeast vs story csv: rate (6 places)', round(nne.late_rate, 6), sr.late_rate, 0.000000001 from nne, story_r sr where sr.segment = 'North and northeast'
    union all select 'north and northeast vs story csv: share of late (6 places)', round(nne.share_of_all_late, 6), sr.share_of_late, 0.000000001 from nne, story_r sr where sr.segment = 'North and northeast'
    union all select 'rest of Brazil vs story csv: orders', rest.orders::double, sr.orders::double, 0 from rest, story_r sr where sr.segment = 'Rest of Brazil'
    union all select 'rest of Brazil vs story csv: late', rest.late_orders::double, sr.late::double, 0 from rest, story_r sr where sr.segment = 'Rest of Brazil'
    union all select 'rest of Brazil vs story csv: rate (6 places)', round(rest.late_rate, 6), sr.late_rate, 0.000000001 from rest, story_r sr where sr.segment = 'Rest of Brazil'
    union all select 'rest of Brazil vs story csv: share of late (6 places)', round(rest.share_of_all_late, 6), sr.share_of_late, 0.000000001 from rest, story_r sr where sr.segment = 'Rest of Brazil'
    union all select 'summary tile equals the bar: north and northeast rate', s.nne_late_rate, nne.late_rate, 0.0000000001 from s, nne
    union all select 'summary tile equals the bar: rest of Brazil rate', s.rest_late_rate, rest.late_rate, 0.0000000001 from s, rest
    union all select 'summary tile equals the bar: north and northeast share of late', s.nne_share_of_late, nne.share_of_all_late, 0.0000000001 from s, nne
    union all select 'tile: north and northeast late rate, % to 1 place (12.2)', round(100 * s.nne_late_rate, 1), 12.2, 0 from s
    union all select 'tile: rest of Brazil late rate, % to 1 place (6.2)', round(100 * s.rest_late_rate, 1), 6.2, 0 from s
    union all select 'text: north and northeast share of late, % to 1 place (20.0)', round(100 * s.nne_share_of_late, 1), 20.0, 0 from s
),
checks as (
    select * from checks_ran
    union all select 'checks that ran (expected 25; a check with no input row would otherwise vanish)', (select count(*) from checks_ran)::double, 25::double, 0
)
select what, got, expected from checks where got is null or expected is null or abs(got - expected) > tolerance
