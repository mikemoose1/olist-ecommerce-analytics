-- Rule: real payment gaps (over R$1 either way) stay rare. Fails if they exceed 0.5% of orders
-- that have both items and payments (observed 249 of 98,665 = 0.25% in the published data).
select
    count(*) filter (where recon_status in ('overpaid', 'underpaid')) as mismatched,
    count(*) filter (where recon_status not in ('no_items', 'no_payment')) as orders_with_money
from {{ ref('fct_orders') }}
having count(*) filter (where recon_status in ('overpaid', 'underpaid'))
     > 0.005 * count(*) filter (where recon_status not in ('no_items', 'no_payment'))
