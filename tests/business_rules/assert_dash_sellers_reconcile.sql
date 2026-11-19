-- Rule (dashboard panel 4): the seller list adds up to the whole window and is cut the way the chart says.
-- Part 1, totals: late orders after a late handoff over all sellers = 1,809 (the targets model's late_handoff_late_orders),
-- orders = judged orders, late orders = all late orders. One row per seller, one seller per order, 8-character codes unique.
-- Part 2, independent recompute: the per-seller counts are rebuilt here straight from fct_order_items + metric_late_rate_orders + fct_orders
-- (not through dash_order_base) and must match the export row for row.
-- Part 3, the panel's words, computed here from the seller export and not copied from the summary: top 10 hold 19.1% (about 19%)
-- of the 1,809, 583 sellers had at least one, the top seller is 06a2c3af with 66. Those four are typed from the prototype run
-- (proto/build_data.py); the analysis scripts do not produce a seller table. 
-- One row per number that differs; passes when it returns nothing.
with e as (select * from {{ ref('export_dash_sellers') }}),
s as (select * from {{ ref('export_dash_summary') }}),
t as (select * from {{ ref('metric_late_rate_targets') }}),
base as (select * from {{ ref('dash_order_base') }}),
mine as (
    select i.seller_id,
           count(*) as orders,
           count(*) filter (where f.delivered_to_carrier_at > f.last_shipping_limit_at) as late_handoff_orders,
           count(*) filter (where f.delivered_to_carrier_at > f.last_shipping_limit_at and o.is_late) as late_after_late_handoff_orders,
           count(*) filter (where o.is_late) as late_orders
    from (select distinct order_id, seller_id from {{ ref('fct_order_items') }}) i
    join {{ ref('metric_late_rate_orders') }} o on o.order_id = i.order_id
    join {{ ref('fct_orders') }} f on f.order_id = i.order_id
    group by 1
),
top10 as (select * from e order by late_after_late_handoff_orders desc, late_orders desc, seller_id limit 10),
totals as (select count(*) as sellers, count(distinct seller_id) as distinct_sellers, count(distinct seller_code) as distinct_codes,
                  sum(orders) as orders, sum(late_orders) as late, sum(late_after_late_handoff_orders) as lhl,
                  count(*) filter (where late_after_late_handoff_orders > 0) as sellers_with_any,
                  count(*) filter (where is_top10) as top10_flagged from e),
checks_ran as (
    select 'sum of late-after-late-handoff over sellers vs targets (1,809)' as what, tt.lhl::double as got, t.late_handoff_late_orders::double as expected, 0 as tolerance from totals tt, t
    union all select 'sum of orders over sellers vs judged orders', tt.orders::double, t.judged_orders::double, 0 from totals tt, t
    union all select 'sum of late orders over sellers vs late orders', tt.late::double, t.late_orders::double, 0 from totals tt, t
    union all select 'one row per seller', tt.sellers::double, tt.distinct_sellers::double, 0 from totals tt
    union all select '8-character seller codes are unique', tt.distinct_codes::double, tt.distinct_sellers::double, 0 from totals tt
    union all select 'sellers in the export vs sellers recomputed', tt.sellers::double, (select count(*) from mine)::double, 0 from totals tt
    union all select 'every judged order has exactly one seller', (select count(*) from base where n_sellers is distinct from 1)::double, 0, 0
    union all select 'exactly 10 sellers are flagged top 10', tt.top10_flagged::double, 10, 0 from totals tt
    union all select 'shares of late-after-late-handoff add up to 1', (select sum(share_of_late_after_late_handoff) from e), 1, 0.000000001
    union all select 'summary: sellers with at least one vs the seller export', s.sellers_with_late_after_late_handoff::double, tt.sellers_with_any::double, 0 from s, totals tt
    union all select 'summary: top 10 share vs the seller export', s.top10_share_of_late_after_late_handoff, (select sum(late_after_late_handoff_orders) from top10) * 1.0 / tt.lhl, 0.0000000001 from s, totals tt
    union all select 'summary: top seller code vs the seller export', (s.top_seller_code = (select seller_code from top10 order by late_after_late_handoff_orders desc, late_orders desc, seller_id limit 1))::int, 1, 0 from s
    union all select 'text: sellers with at least one late order after a late handoff (583)', tt.sellers_with_any::double, 583, 0 from totals tt
    union all select 'text: top 10 hold, % to 1 place (19.1)', round(100 * (select sum(late_after_late_handoff_orders) from top10) * 1.0 / tt.lhl, 1), 19.1, 0 from totals tt
    union all select 'text: top 10 hold, whole % (about 19)', round(100 * (select sum(late_after_late_handoff_orders) from top10) * 1.0 / tt.lhl), 19, 0 from totals tt
    union all select 'text: top seller is 06a2c3af', ((select seller_code from top10 order by late_after_late_handoff_orders desc, late_orders desc, seller_id limit 1) = '06a2c3af')::int, 1, 0
    union all select 'text: top seller count (66)', (select max(late_after_late_handoff_orders) from e)::double, 66, 0
),
checks as (
    select * from checks_ran
    union all select 'checks that ran (expected 17; a check with no input row would otherwise vanish)', (select count(*) from checks_ran)::double, 17::double, 0
),
problems as (select what, got, expected from checks where got is null or expected is null or abs(got - expected) > tolerance),
row_problems as (
    select 'seller ' || coalesce(e.seller_id, m.seller_id) || ': counts differ from the recompute or the seller is missing' as what,
           e.late_after_late_handoff_orders::double as got, m.late_after_late_handoff_orders::double as expected
    from e full outer join mine m on m.seller_id = e.seller_id
    where e.seller_id is null or m.seller_id is null
       or e.orders <> m.orders or e.late_handoff_orders <> m.late_handoff_orders
       or e.late_after_late_handoff_orders <> m.late_after_late_handoff_orders or e.late_orders <> m.late_orders
)
select * from problems union all select * from row_problems
