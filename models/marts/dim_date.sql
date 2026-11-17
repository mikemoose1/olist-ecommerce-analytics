-- Grain: one row per calendar day. PK: date_day. Covers every purchase date (2016-09-04 .. 2018-10-17).
-- in_analysis_window marks the full months used by every trend metric.
with days as (
    select cast(d as date) as date_day
    from generate_series(date '2016-09-01', date '2018-10-31', interval 1 day) as t(d)
)
select
    date_day,
    date_trunc('month', date_day)::date as month_start,
    strftime(date_day, '%Y-%m')          as year_month,
    dayofweek(date_day)                  as day_of_week,
    date_day between date '{{ var("analysis_window_start") }}' and date '{{ var("analysis_window_end") }}' as in_analysis_window
from days
