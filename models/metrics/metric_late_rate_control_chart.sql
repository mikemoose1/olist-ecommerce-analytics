-- Late rate by purchase month with p-chart control limits (3 sigma, limits move with each month's order count).
-- Grain: one row per purchase month in the analysis window. PK: year_month.
-- Population and "late" come from metric_late_rate_orders (the one definition); nothing is redefined here.
-- Two charts sit side by side:
--   plain  : classic p-chart, centre = overall late rate, limits = centre +/- 3 * sqrt(p(1-p)/n).
--   laney  : Laney p-prime. Month-to-month swings are larger than chance alone explains, so the plain limits are
--            stretched by sigma_z (the typical size of a month's standardised swing, from moving ranges / 1.128,
--            never below 1). It is fitted in passes: a month outside the limits is set aside, the centre and
--            sigma_z are refitted on the months left, and this repeats (laney_pass_count passes; a test checks
--            the last pass changed nothing). A moving range only counts two months that sit side by side and
--            are both still in.
-- thin_month: fewer than 2,000 judged orders (under a third of a 2018 month). Shown, flagged, kept out of goals.
-- Handoff columns use the repo's own definition: handed to the carrier after the last ship-by time.
{% set passes = 6 %}
with base as (
    select
        o.order_id,
        strftime(f.purchase_date, '%Y-%m') as year_month,
        o.is_late,
        o.review_score,
        f.delivered_to_carrier_at > f.last_shipping_limit_at as handed_over_late
    from {{ ref('metric_late_rate_orders') }} o
    join {{ ref('fct_orders') }} f on f.order_id = o.order_id
),
monthly as (
    select
        year_month,
        count(*) as orders,
        count(*) filter (where is_late) as late_orders,
        count(*) filter (where review_score is not null) as reviewed_orders,
        count(*) filter (where review_score <= 2) as bad_reviews,
        sum(review_score) filter (where is_late) as stars_sum_late,
        count(*) filter (where is_late and review_score is not null) as reviewed_late,
        sum(review_score) filter (where not is_late) as stars_sum_on_time,
        count(*) filter (where not is_late and review_score is not null) as reviewed_on_time,
        count(*) filter (where handed_over_late) as late_handoff_orders,
        count(*) filter (where handed_over_late and is_late) as late_handoff_late_orders,
        count(*) filter (where not handed_over_late) as on_time_handoff_orders,
        count(*) filter (where not handed_over_late and is_late) as on_time_handoff_late_orders
    from base
    group by 1
),
pass0 as (
    select *, 1.0 * late_orders / orders as late_rate, true as in_fit, true as prev_in_fit,
           null::double as centre, null::double as z, null::double as sigma_z, null::double as ucl, null::double as lcl
    from monthly
)
{% for i in range(1, passes + 1) %}
, centred{{ i }} as (
    select
        * exclude (prev_in_fit, centre, z, sigma_z, ucl, lcl),
        in_fit as prev_in_fit,
        sum(late_orders) filter (where in_fit) over () * 1.0 / sum(orders) filter (where in_fit) over () as centre
    from pass{{ i - 1 }}
),
z{{ i }} as (
    select
        *,
        (late_rate - centre) / sqrt(centre * (1 - centre) / orders) as z
    from centred{{ i }}
),
lagged{{ i }} as (
    select
        *,
        lag(z) over (order by year_month) as z_before,
        lag(prev_in_fit) over (order by year_month) as before_in_fit
    from z{{ i }}
),
widened{{ i }} as (
    select
        *,
        greatest(1.0, avg(case when prev_in_fit and before_in_fit then abs(z - z_before) end) over () / 1.128) as sigma_z
    from lagged{{ i }}
),
pass{{ i }} as (
    select
        * exclude (z_before, before_in_fit, in_fit),
        centre + 3 * sigma_z * sqrt(centre * (1 - centre) / orders) as ucl,
        greatest(0, centre - 3 * sigma_z * sqrt(centre * (1 - centre) / orders)) as lcl,
        late_rate between greatest(0, centre - 3 * sigma_z * sqrt(centre * (1 - centre) / orders))
                      and centre + 3 * sigma_z * sqrt(centre * (1 - centre) / orders) as in_fit
    from widened{{ i }}
)
{% endfor %}
, plain_centre as (
    select *, sum(late_orders) over () * 1.0 / sum(orders) over () as plain_centre_rate
    from pass{{ passes }}
)
select
    year_month,
    orders,
    late_orders,
    late_rate,
    orders < 2000 as thin_month,
    plain_centre_rate,
    greatest(0, plain_centre_rate - 3 * sqrt(plain_centre_rate * (1 - plain_centre_rate) / orders)) as plain_lcl,
    plain_centre_rate + 3 * sqrt(plain_centre_rate * (1 - plain_centre_rate) / orders) as plain_ucl,
    late_rate not between greatest(0, plain_centre_rate - 3 * sqrt(plain_centre_rate * (1 - plain_centre_rate) / orders))
                      and plain_centre_rate + 3 * sqrt(plain_centre_rate * (1 - plain_centre_rate) / orders) as plain_signal,
    centre as laney_centre_rate,
    sigma_z as laney_sigma_z,
    lcl as laney_lcl,
    ucl as laney_ucl,
    not in_fit as laney_signal,
    case when late_rate > ucl then 'above' when late_rate < lcl then 'below' else 'inside' end as laney_side,
    in_fit <> prev_in_fit as fit_changed_in_last_pass,
    reviewed_orders,
    bad_reviews,
    1.0 * bad_reviews / nullif(reviewed_orders, 0) as bad_review_rate,
    stars_sum_late,
    reviewed_late,
    stars_sum_on_time,
    reviewed_on_time,
    late_handoff_orders,
    late_handoff_late_orders,
    on_time_handoff_orders,
    on_time_handoff_late_orders,
    -- same month, if late handoffs were late only as often as on-time handoffs in that month
    (late_orders - late_handoff_late_orders
        + late_handoff_orders * 1.0 * on_time_handoff_late_orders / on_time_handoff_orders) / orders as late_rate_if_handoffs_ok
from plain_centre
order by year_month
