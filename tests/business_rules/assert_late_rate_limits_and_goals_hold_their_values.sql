-- Rule: the alarm line, the goal lines, sigma_z and the set of flagged months keep the values the control-limit
-- analysis found. The story reconcile test only checks counts, so a changed divisor (/1.128), a changed percentile,
-- a dropped thin-month filter or a moving range that counts set-aside months would pass it. This one fails on each.
-- Expected values are typed constants from the independent Python refit (late_rate_targets/spc.py, reported in
-- evidence/late_rate_targets_report.json, pchart section); assert_late_rate_targets_match_the_python_refit.sql
-- re-ties the same numbers to that file. Tolerances are tight: a rounding-level wobble passes, a changed method does not.
-- One row per number that is off; passes when it returns nothing.
with t as (select * from {{ ref('metric_late_rate_targets') }}),
c as (select * from {{ ref('metric_late_rate_control_chart') }}),
expected_flagged as (select unnest(['2017-11', '2018-02', '2018-03']) as year_month),
expected_thin as (select unnest(['2017-01', '2017-02']) as year_month),
checks as (
    select 'laney sigma_z (4.9313 +/- 0.0005)' as what, t.laney_sigma_z as got, 4.9313 as expected, 0.0005 as tolerance from t
    union all select 'stable centre rate (4.5305% +/- 0.0001 pp)', t.stable_centre_rate, 0.045305, 0.000001 from t
    union all select 'alarm line at the typical order count (8.385% +/- 0.001 pp)', t.alarm_line_late_rate, 0.08385, 0.00001 from t
    union all select 'safe goal, 25th percentile of stable months (3.036% +/- 0.001 pp)', t.safe_goal_late_rate, 0.03036, 0.00001 from t
    union all select 'goal line, median of the stable months (4.433% +/- 0.001 pp)', t.goal_late_rate, 0.04433, 0.00001 from t
    union all select 'stretch goal, median stable month with handoffs no later than on-time ones (3.425% +/- 0.001 pp)', t.stretch_goal_late_rate, 0.034251, 0.00001 from t
    union all select 'goal minus stretch, the what-if alone (1.007 pp +/- 0.001 pp)', t.goal_late_rate - t.stretch_goal_late_rate, 0.010074, 0.00001 from t
    union all select 'stable months (exactly 15)', t.stable_months, 15, 0 from t
    union all select 'months flagged by the Laney limits (exactly 3)', t.laney_signal_months, 3, 0 from t
    union all select 'months flagged by the plain limits (exactly 16)', t.plain_signal_months, 16, 0 from t
    union all select 'thin months (exactly 2)', t.thin_months, 2, 0 from t
    union all select 'typical order count (median of last 12 months)', t.typical_orders, 6372, 0 from t
),
number_problems as (
    select what, got, expected from checks where got is null or abs(got - expected) > tolerance
),
flagged_problems as (
    select 'flagged but not expected: ' || year_month as what, null::double as got, null::double as expected
    from (select year_month from c where laney_signal except select year_month from expected_flagged)
    union all
    select 'expected flagged but not: ' || year_month, null, null
    from (select year_month from expected_flagged except select year_month from c where laney_signal)
    union all
    select 'thin but not expected: ' || year_month, null, null
    from (select year_month from c where thin_month except select year_month from expected_thin)
    union all
    select 'expected thin but not: ' || year_month, null, null
    from (select year_month from expected_thin except select year_month from c where thin_month)
)
select * from number_problems
union all select * from flagged_problems
