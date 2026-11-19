-- Rule: the dbt review-cost number ties to the causal analysis AND to the story's counts.
-- Part 1 reads evidence/review_cost_causal_report.json (written by review_cost_causal/analyze.py, the same run that wrote
-- seeds/review_cost_effects.csv): the dbt total must equal the report's headline to within 0.01 review, and the dbt
-- counts must equal the report's population counts. Edit the seed, the bins or the model and this fails.
-- Part 2 pins the story-facing numbers as typed constants: 6,366 reviewed late orders, 11,635 bad reviews,
-- 3,110 extra bad reviews (26.7% of them, about 27%), and the range across specifications the story quotes, 2,880 to 3,350
-- (rounded to the nearest 10). The path is relative to the dbt project root (where dbt runs, locally and in CI).
-- One row per number that differs; passes when it returns nothing.
with j as (
    select json(population) as pop, json(headline) as head
    from read_json('evidence/review_cost_causal_report.json', format = 'auto', columns = {population: 'JSON', headline: 'JSON'})
),
m as (select sum(reviewed_late_orders) as late_rev, sum(extra_bad_reviews) as extra from {{ ref('metric_review_cost_causal') }}),
t as (select bad_reviews from {{ ref('metric_late_rate_targets') }}),
checks as (
    select 'extra bad reviews vs report headline' as what, m.extra::double as got, json_extract(head, '$.extra_bad_reviews')::double as expected, 0.01 as tolerance from m, j
    union all select 'reviewed late orders vs report', m.late_rev, json_extract(pop, '$.reviewed_late')::double, 0 from m, j
    union all select 'bad reviews vs report', t.bad_reviews, json_extract(pop, '$.bad_reviews')::double, 0 from t, j
    union all select 'reviewed late orders (story)', m.late_rev::double, 6366::double, 0 from m
    union all select 'extra bad reviews, whole number (story)', round(m.extra), 3110, 0 from m
    union all select 'share of all bad reviews % (1 place)', round(100 * m.extra / t.bad_reviews, 1), 26.7, 0 from m cross join t
    union all select 'bad reviews (story)', t.bad_reviews, 11635, 0 from t
    union all select 'share of all bad reviews, whole % (story: about 27%)', round(100 * m.extra / t.bad_reviews), 27, 0 from m cross join t
    union all select 'range across specifications, low end to the nearest 10 (story)', round(json_extract(head, '$.range_across_specifications[0]')::double, -1), 2880, 0 from j
    union all select 'range across specifications, high end to the nearest 10 (story)', round(json_extract(head, '$.range_across_specifications[1]')::double, -1), 3350, 0 from j
    union all select 'dbt total inside the range across specifications', (m.extra between json_extract(head, '$.range_across_specifications[0]')::double and json_extract(head, '$.range_across_specifications[1]')::double)::int, 1, 0 from m, j
)
select what, got, expected from checks where got is null or expected is null or abs(got - expected) > tolerance
