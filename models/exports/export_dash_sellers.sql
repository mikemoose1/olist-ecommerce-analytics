-- Dashboard panel 4 (ranked bars): which sellers had late orders that followed a late handoff.
-- Grain: one row per seller with at least one judged order. PK: seller_id.
-- late_after_late_handoff_orders is the bar. Rank 1 is the most, ties broken by total late orders, then seller_id.
-- The chart shows the first 8 characters (seller_code); the full id stays for joins. Top 10 and the share of all
-- late-after-late-handoff orders they hold are columns, so the dashboard states "top 10 = 19%" without typing it.
with b as (select * from {{ ref('dash_order_base') }}),
per_seller as (
    select seller_id,
           count(*) as orders,
           count(*) filter (where handed_over_late) as late_handoff_orders,
           count(*) filter (where handed_over_late and is_late) as late_after_late_handoff_orders,
           count(*) filter (where is_late) as late_orders
    from b
    group by 1
),
ranked as (
    select *, row_number() over (order by late_after_late_handoff_orders desc, late_orders desc, seller_id) as rank_by_late_after_late_handoff,
           sum(late_after_late_handoff_orders) over () as all_late_after_late_handoff
    from per_seller
)
select
    seller_id,
    left(seller_id, 8) as seller_code,
    orders,
    late_handoff_orders,
    late_after_late_handoff_orders,
    late_orders,
    late_handoff_orders * 1.0 / orders as late_handoff_rate,
    late_orders * 1.0 / orders as late_rate,
    rank_by_late_after_late_handoff,
    rank_by_late_after_late_handoff <= 10 as is_top10,
    late_after_late_handoff_orders * 1.0 / all_late_after_late_handoff as share_of_late_after_late_handoff
from ranked
order by rank_by_late_after_late_handoff
