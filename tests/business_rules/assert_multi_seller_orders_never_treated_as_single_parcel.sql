-- Rule: an order shipped by more than one seller is never presented as a fully observed,
-- single-parcel delivery. Its delivery date is order-level only, so delivery_evidence must say so.
-- Seller counts are recomputed from fct_order_items, independently of how fct_orders derived them.
with sellers as (
    select order_id, count(distinct seller_id) as n_sellers
    from {{ ref('fct_order_items') }}
    group by order_id
)
select o.order_id, o.delivery_evidence, coalesce(s.n_sellers, 0) as n_sellers
from {{ ref('fct_orders') }} o
left join sellers s using (order_id)
where (coalesce(s.n_sellers, 0) > 1 and o.delivery_evidence <> 'order_level_multi_parcel')
   or (coalesce(s.n_sellers, 0) = 1 and o.delivery_evidence <> 'order_level_single_parcel')
   or (coalesce(s.n_sellers, 0) = 0 and o.delivery_evidence <> 'no_parcels')
