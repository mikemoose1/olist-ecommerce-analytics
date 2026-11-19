-- Dashboard panel 3 (two bars): late rate after a late handoff vs after an on-time handoff.
-- Grain: one row per handoff group (2 rows). PK: handoff_group.
-- share_of_all_late divides by ALL late orders, including the one late order with no handoff time, so the two shares
-- add up to just under 100%. Late handoffs start about 27.8% of late orders.
with b as (select * from {{ ref('dash_order_base') }}),
all_late as (select count(*) filter (where is_late) as n from b),
grouped as (
    select case when handed_over_late then 'Handed to carrier after ship-by' else 'Handed over on time' end as handoff_group,
           handed_over_late as is_late_handoff,
           count(*) as orders,
           count(*) filter (where is_late) as late_orders
    from b
    where handed_over_late is not null
    group by 1, 2
)
select g.handoff_group, g.is_late_handoff, g.orders, g.late_orders,
       g.late_orders * 1.0 / g.orders as late_rate,
       g.late_orders * 1.0 / a.n as share_of_all_late
from grouped g cross join all_late a
order by g.is_late_handoff desc
