-- Rule: the dbt alarm line, goals, sigma_z and flagged months equal the independent Python refit that
-- late_rate_targets/analyze.py wrote to evidence/late_rate_targets_report.json (pchart section). The file is read here,
-- not retyped: change the SQL and this fails; regenerate the report from broken code and analyze.py itself fails first.
-- Path is relative to the dbt project root (where dbt runs, locally and in CI). One row per number that differs.
with j as (
    select json(pchart) as p
    from read_json('evidence/late_rate_targets_report.json', format = 'auto', columns = {pchart: 'JSON'})
),
t as (select * from {{ ref('metric_late_rate_targets') }}),
c as (select * from {{ ref('metric_late_rate_control_chart') }}),
ref_flagged as (
    select unnest(from_json(json_extract(p, '$.laney.months_flagged'), '["VARCHAR"]')) as year_month from j
),
checks as (
    select 'sigma_z' as what, t.laney_sigma_z as got, json_extract(p, '$.laney.sigma_z')::double as expected from t, j
    union all select 'stable centre', t.stable_centre_rate, json_extract(p, '$.laney.stable_centre')::double from t, j
    union all select 'alarm line', t.alarm_line_late_rate, json_extract(p, '$.laney.alarm_line')::double from t, j
    union all select 'safe goal', t.safe_goal_late_rate, json_extract(p, '$.goals.safe_25th_pct_of_stable')::double from t, j
    union all select 'stretch goal', t.stretch_goal_late_rate, json_extract(p, '$.goals.stretch_25th_pct_if_handoffs_ok')::double from t, j
    union all select 'stable months', t.stable_months, json_array_length(json_extract(p, '$.stable_months')) from t, j
    union all select 'flagged months', t.laney_signal_months, json_array_length(json_extract(p, '$.laney.months_flagged')) from t, j
),
problems as (
    select what, got, expected from checks where got is null or expected is null or abs(got - expected) > 1e-9
)
select * from problems
union all
select 'flagged month differs: ' || coalesce(a.year_month, b.year_month), null, null
from (select year_month from c where laney_signal) a
full join ref_flagged b on a.year_month = b.year_month
where a.year_month is null or b.year_month is null
