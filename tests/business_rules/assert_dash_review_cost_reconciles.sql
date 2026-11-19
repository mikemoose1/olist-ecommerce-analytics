-- Rule (dashboard panel 1): the review-cost tile and the ramp chart show what the causal analysis and the story found.
-- Sources of truth, all written by the analysis scripts and committed: story/data/facts.json (review_cost_causal, ramp,
-- low_star_all), evidence/review_cost_causal_report.json (range across specifications) and story/data/bad_review_by_days_late.csv.
-- Part 1: the summary export equals facts.json at facts.json's own rounding (extra to 0.1 review, shares to 6 places).
-- Part 2: the numbers the dashboard prints, as typed constants at the rounding it prints them: about 3,110 extra reviews,
-- 26.7% (about 27%) of 11,635, range 2,880 to 3,350, 8.7% up to the promised day, about 11 points a day, about 78% from day 6.
-- Part 3: the ramp export has the same 61 days as the story's CSV, reviewed and bad counts day for day.
-- Part 4: the ramp numbers are recomputed from the ramp export itself, not read from the summary, and must agree with the summary.
-- One row per number that differs; passes when it returns nothing.
with f as (
    select * from read_json('story/data/facts.json', format = 'auto',
        columns = {review_cost_causal: 'JSON', ramp: 'JSON', low_star_all: 'BIGINT'})
),
e as (
    select json_extract(headline, '$.range_across_specifications[0]')::double as lo, json_extract(headline, '$.range_across_specifications[1]')::double as hi
    from read_json('evidence/review_cost_causal_report.json', format = 'auto', columns = {headline: 'JSON'})
),
s as (select * from {{ ref('export_dash_summary') }}),
r as (select * from {{ ref('export_dash_review_ramp') }}),
rr as (
    select sum(bad_reviews) filter (where days_past_promise_capped <= 0) * 1.0 / sum(reviewed_orders) filter (where days_past_promise_capped <= 0) as on_time_share,
           sum(bad_reviews) filter (where days_past_promise_capped >= 6) * 1.0 / sum(reviewed_orders) filter (where days_past_promise_capped >= 6) as plateau_share,
           regr_slope(bad_review_share, days_past_promise_capped) filter (where days_past_promise_capped between 0 and 6) as slope,
           sum(bad_reviews) as bad_total
    from r
),
story_ramp as (select * from read_csv('story/data/bad_review_by_days_late.csv', header = true, columns = {segment: 'INTEGER', orders: 'BIGINT', reviewed: 'BIGINT', bad: 'BIGINT', bad_share: 'DOUBLE'})),
checks_ran as (
    -- part 1: summary vs the analysis files
    select 'extra bad reviews vs facts.json (0.1)' as what, s.extra_bad_reviews as got, json_extract(f.review_cost_causal, '$.extra')::double as expected, 0.05 as tolerance from s, f
    union all select 'reviewed late orders vs facts.json', s.reviewed_late_orders::double, json_extract(f.review_cost_causal, '$.reviewed_late')::double, 0 from s, f
    union all select 'share of all bad reviews vs facts.json (6 places)', round(s.extra_share_of_bad_reviews, 5), json_extract(f.review_cost_causal, '$.share')::double, 0.000006 from s, f
    union all select 'all 1-2 star reviews vs facts.json', s.bad_reviews_all::double, f.low_star_all::double, 0 from s, f
    union all select 'range low vs facts.json (0.1)', s.extra_range_low, json_extract(f.review_cost_causal, '$.range[0]')::double, 0.05 from s, f
    union all select 'range high vs facts.json (0.1)', s.extra_range_high, json_extract(f.review_cost_causal, '$.range[1]')::double, 0.05 from s, f
    union all select 'range low vs evidence report', s.extra_range_low, e.lo, 0.000001 from s, e
    union all select 'range high vs evidence report', s.extra_range_high, e.hi, 0.000001 from s, e
    union all select 'ramp share up to the promised day vs facts.json (6 places)', round(s.ramp_share_up_to_promised_day, 6), json_extract(f.ramp, '$.on_time_share')::double, 0.0000006 from s, f
    union all select 'ramp share from day 6 vs facts.json (6 places)', round(s.ramp_share_from_day_6, 6), json_extract(f.ramp, '$.plateau_share')::double, 0.0000006 from s, f
    union all select 'ramp points a day vs facts.json (6 places)', round(s.ramp_points_per_day, 6), json_extract(f.ramp, '$.slope_per_day')::double, 0.0000006 from s, f
    -- part 2: what the dashboard prints
    union all select 'tile: extra reviews, whole number (about 3,110)', s.extra_bad_reviews_rounded, 3110, 0 from s
    union all select 'tile: share of all bad reviews, % to 1 place (26.7)', round(100 * s.extra_share_of_bad_reviews, 1), 26.7, 0 from s
    union all select 'tile: share of all bad reviews, whole % (about 27)', round(100 * s.extra_share_of_bad_reviews), 27, 0 from s
    union all select 'tile: all 1-2 star reviews (11,635)', s.bad_reviews_all::double, 11635, 0 from s
    union all select 'tile: range low to the nearest 10 (2,880)', s.extra_range_low_rounded, 2880, 0 from s
    union all select 'tile: range high to the nearest 10 (3,350)', s.extra_range_high_rounded, 3350, 0 from s
    union all select 'ramp label: share up to the promised day, % to 1 place (8.7)', round(100 * s.ramp_share_up_to_promised_day, 1), 8.7, 0 from s
    union all select 'ramp label: points a day, whole (11)', round(100 * s.ramp_points_per_day), 11, 0 from s
    union all select 'ramp label: share from day 6, whole % (78)', round(100 * s.ramp_share_from_day_6), 78, 0 from s
    -- part 4: recomputed from the ramp export, must equal the summary
    union all select 'ramp export: bad reviews add up to the summary total', rr.bad_total::double, s.bad_reviews_all::double, 0 from rr, s
    union all select 'ramp export: share up to the promised day equals the summary', rr.on_time_share, s.ramp_share_up_to_promised_day, 0.0000001 from rr, s
    union all select 'ramp export: share from day 6 equals the summary', rr.plateau_share, s.ramp_share_from_day_6, 0.0000001 from rr, s
    union all select 'ramp export: points a day equals the summary', rr.slope, s.ramp_points_per_day, 0.0000001 from rr, s
),
checks as (
    select * from checks_ran
    union all select 'checks that ran (expected 24; a check with no input row would otherwise vanish)', (select count(*) from checks_ran)::double, 24::double, 0
),
problems as (select what, got, expected from checks where got is null or expected is null or abs(got - expected) > tolerance),
-- part 3: the ramp rows, day for day
ramp_problems as (
    select 'ramp day ' || coalesce(r.days_past_promise_capped, c.segment)::varchar || ': reviewed/bad differ from the story csv or the day is missing' as what,
           r.bad_reviews::double as got, c.bad::double as expected
    from r full outer join story_ramp c on c.segment = r.days_past_promise_capped
    where r.days_past_promise_capped is null or c.segment is null
       or r.orders <> c.orders or r.reviewed_orders <> c.reviewed or r.bad_reviews <> c.bad
       or abs(r.bad_review_share - c.bad_share) > 0.0000006
)
select * from problems
union all select * from ramp_problems
