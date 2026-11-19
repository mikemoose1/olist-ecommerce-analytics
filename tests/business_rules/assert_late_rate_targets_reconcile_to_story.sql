-- Rule: the control chart, the targets and the days-late table tie back to the numbers the story already verified.
-- 94,931 judged orders, 6,518 late (6.87%), March 2018 at 19.152%, August 2018 at 6.3%, 11,635 bad (1-2 star) reviews,
-- late orders averaging 2.27 stars against 4.31, 8,530 late handoffs of which 1,809 were late.
-- The test returns one row per number that differs; it passes when it returns nothing.
with t as (select * from {{ ref('metric_late_rate_targets') }}),
c as (select * from {{ ref('metric_late_rate_control_chart') }}),
d as (select sum(orders) as orders, sum(reviewed_orders) as reviewed, sum(bad_reviews) as bad from {{ ref('metric_bad_review_by_days_late') }}),
checks as (
    select 'judged orders (targets)' as what, t.judged_orders::double as got, 94931::double as expected from t
    union all select 'judged orders (days-late table)', d.orders, 94931 from d
    union all select 'late orders', t.late_orders, 6518 from t
    union all select 'late rate % (2 places)', round(100 * t.late_rate, 2), 6.87 from t
    union all select 'March 2018 late rate % (3 places)', round(100 * late_rate, 3), 19.152 from c where year_month = '2018-03'
    union all select 'August 2018 late rate % (1 place)', round(100 * late_rate, 1), 6.3 from c where year_month = '2018-08'
    union all select 'bad reviews (targets)', t.bad_reviews, 11635 from t
    union all select 'bad reviews (days-late table)', d.bad, 11635 from d
    union all select 'reviewed orders (days-late table)', d.reviewed, t.reviewed_orders from t cross join d
    union all select 'average stars, late orders', round(t.avg_stars_late, 2), 2.27 from t
    union all select 'average stars, on-time orders', round(t.avg_stars_on_time, 2), 4.31 from t
    union all select 'orders handed over late', t.late_handoff_orders, 8530 from t
    union all select 'of those, late orders', t.late_handoff_late_orders, 1809 from t
)
select * from checks where got is distinct from expected
