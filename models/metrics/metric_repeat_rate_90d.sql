-- METRIC (headline): 90-day repeat rate, excluding same-day reorders (defined once).
-- Population: people (customer_unique_id) whose first qualifying order (not canceled/unavailable,
-- >= 1 item) was at least 90 days before the last qualifying purchase in the data (so everyone
-- had a full 90 days to come back). Numerator per C6 (var repeat_same_day_rule):
--   any_later_order_24h     another qualifying order > = 24h and <= 90 days after the first
--   different_calendar_day  another qualifying order on a later calendar day, within 90 days
--   second_order_only       the person's 2nd qualifying order falls 24h..90 days after the first
{% set rule = var('repeat_same_day_rule') %}
with q as (
    select customer_unique_id, purchased_at, customer_qualifying_order_seq as seq
    from {{ ref('fct_orders') }}
    where is_qualifying_order
),
firsts as (
    select customer_unique_id, purchased_at as first_at from q where seq = 1
),
eligible as (
    select f.* from firsts f
    where f.first_at <= (select max(purchased_at) from q) - interval 90 day
),
hits as (
    select e.customer_unique_id,
        bool_or(
        {% if rule == 'different_calendar_day' %}
            cast(q.purchased_at as date) > cast(e.first_at as date) and q.purchased_at <= e.first_at + interval 90 day
        {% elif rule == 'second_order_only' %}
            q.seq = 2 and q.purchased_at >= e.first_at + interval 1 day and q.purchased_at <= e.first_at + interval 90 day
        {% else %}
            q.purchased_at >= e.first_at + interval 1 day and q.purchased_at <= e.first_at + interval 90 day
        {% endif %}
        ) as repeated
    from eligible e
    join q using (customer_unique_id)
    group by e.customer_unique_id
)
select
    'repeat_rate_90d' as metric_name,
    '{{ rule }}' as rule,
    count(*) filter (where repeated) as numerator,
    count(*) as denominator,
    round(100.0 * count(*) filter (where repeated) / count(*), 2) as value_pct
from hits
