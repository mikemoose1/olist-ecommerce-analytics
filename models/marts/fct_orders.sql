-- Grain: one row per order. PK: order_id. FK: customer_unique_id -> dim_customer, purchase_date -> dim_date.
-- Every order-level fact lives here once; metrics read from this table.
select
    d.order_id,
    co.customer_unique_id,
    cast(d.purchased_at as date)                as purchase_date,
    d.purchased_at,
    d.order_status,
    d.delivery_state,
    d.delivery_evidence,
    d.n_parcels,
    d.delivered_to_carrier_at,
    d.delivered_to_customer_at,
    d.estimated_delivery_date,
    d.last_shipping_limit_at,
    d.days_past_promise,
    date_diff('day', cast(d.purchased_at as date), d.estimated_delivery_date) as promised_days,
    r.n_items,
    r.amount_due,
    r.amount_paid,
    r.paid_minus_due,
    r.max_installments,
    r.recon_status,
    co.ship_to_zip_code_prefix,
    co.ship_to_city,
    co.ship_to_state,
    g.lat as ship_to_lat,
    g.lng as ship_to_lng,
    co.is_qualifying_order,
    co.customer_qualifying_order_seq,
    rv.review_id,
    rv.review_score,
    rv.review_before_delivery,
    coalesce(dt.in_analysis_window, false) as in_analysis_window
from {{ ref('int_order_delivery') }} d
join {{ ref('int_customer_orders') }} co using (order_id)
join {{ ref('int_order_payment_recon') }} r using (order_id)
left join {{ ref('int_order_review') }} rv on rv.order_id = d.order_id and rv.is_chosen_for_order
left join {{ ref('int_geo_zip') }} g on g.zip_code_prefix = co.ship_to_zip_code_prefix
-- left join so a purchase date missing from dim_date surfaces in the relationships test instead of dropping the order
left join {{ ref('dim_date') }} dt on dt.date_day = cast(d.purchased_at as date)
