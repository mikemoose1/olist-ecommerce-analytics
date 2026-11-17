-- Rule: an order with no items never contributes order value; it is labeled no_items, and only it is.
select o.order_id, o.n_items, o.recon_status
from {{ ref('fct_orders') }} o
where (coalesce(o.n_items, 0) = 0) <> (o.recon_status = 'no_items')
