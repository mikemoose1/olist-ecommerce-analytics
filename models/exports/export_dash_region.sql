-- Dashboard panel 5 (two bars): late rate in the north and northeast vs the rest of Brazil.
-- Grain: one row per region group (2 rows). PK: region_group.
-- The groups come from seed dash_region_map (27 states, each once), which repeats story/story_data.py NNE;
-- verification/verify_dash_exports.py checks the two lists agree. share_of_all_late: the north and northeast hold about 20%.
with b as (select * from {{ ref('dash_order_base') }}),
m as (select state, region_group from {{ ref('dash_region_map') }}),
all_late as (select count(*) filter (where is_late) as n from b),
grouped as (
    select m.region_group,
           count(*) as orders,
           count(*) filter (where b.is_late) as late_orders
    from b left join m on m.state = b.ship_to_state
    group by 1
)
select g.region_group,
       (select count(*) from m where m.region_group = g.region_group) as states,
       g.orders, g.late_orders,
       g.late_orders * 1.0 / g.orders as late_rate,
       g.late_orders * 1.0 / a.n as share_of_all_late
from grouped g cross join all_late a
order by g.late_orders * 1.0 / g.orders desc
