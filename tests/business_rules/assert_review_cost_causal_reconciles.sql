-- Rule: the dbt review-cost number ties to the causal analysis (evidence/review_cost_causal_report.json) and to the
-- story's counts: 6,366 reviewed late orders, 11,635 bad reviews, 3,110 extra bad reviews (26.7% of them).
-- One row per number that differs; passes when it returns nothing.
with m as (select sum(reviewed_late_orders) as late_rev, sum(extra_bad_reviews) as extra from {{ ref('metric_review_cost_causal') }}),
t as (select bad_reviews from {{ ref('metric_late_rate_targets') }}),
checks as (
    select 'reviewed late orders' as what, m.late_rev::double as got, 6366::double as expected from m
    union all select 'extra bad reviews (whole number)', round(m.extra), 3110 from m
    union all select 'share of all bad reviews % (1 place)', round(100 * m.extra / t.bad_reviews, 1), 26.7 from m cross join t
    union all select 'bad reviews', t.bad_reviews, 11635 from t
)
select * from checks where got is distinct from expected
