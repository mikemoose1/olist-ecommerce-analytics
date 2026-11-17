-- METRIC POPULATION for late rate and review score (defined once; one row per order judged).
-- Grain: one row per order in the population. PK: order_id.
-- Population: orders delivered with a delivery date (delivery_state on_time/late), at least one item,
-- purchased inside the analysis window. Late = delivered on a later calendar day than promised.
-- Multi-seller orders follow C1 (var multi_seller_late_rule):
--   trust_order_date     use the order-level delivery date as recorded
--   exclude_multi_seller leave multi-seller orders out (their parcels' arrival is unobservable)
--   last_parcel_proxy    a multi-seller order cannot arrive before its last ship-by date plus the
--                        median carrier-to-customer time of single-parcel orders
{% set rule = var('multi_seller_late_rule') %}
with population as (
    select *
    from {{ ref('fct_orders') }}
    where delivery_state in ('delivered_on_time', 'delivered_late')
      and n_items > 0
      and in_analysis_window
      {% if rule == 'exclude_multi_seller' %}and delivery_evidence <> 'order_level_multi_parcel'{% endif %}
),
transit as (
    select median(date_diff('second', delivered_to_carrier_at, delivered_to_customer_at)) as median_transit_s
    from population
    where delivery_evidence = 'order_level_single_parcel' and delivered_to_carrier_at is not null
),
judged as (
    select
        p.*,
        {% if rule == 'last_parcel_proxy' %}
        case
            when p.delivery_evidence = 'order_level_multi_parcel' then
                cast(greatest(p.delivered_to_customer_at,
                              p.last_shipping_limit_at + to_seconds(cast(t.median_transit_s as bigint))) as date)
                    > p.estimated_delivery_date
            else p.delivery_state = 'delivered_late'
        end
        {% else %}
        p.delivery_state = 'delivered_late'
        {% endif %} as is_late
    from population p cross join transit t
)
select order_id, purchase_date, delivery_state, delivery_evidence, ship_to_state, review_score, review_before_delivery, is_late
from judged
