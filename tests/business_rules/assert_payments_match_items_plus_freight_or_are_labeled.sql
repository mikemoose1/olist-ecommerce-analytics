-- Rule: what the customer paid equals items + freight, or the order carries a label explaining the gap.
-- Recomputes paid and due from fct_payments and fct_order_items (not from the recon model) and fails
-- on any order whose recon_status contradicts the money.
with due as (
    select order_id, sum(price + freight_value) as due from {{ ref('fct_order_items') }} group by 1
),
paid as (
    select order_id, sum(payment_value) as paid from {{ ref('fct_payments') }} group by 1
)
select o.order_id, o.recon_status, due.due, paid.paid
from {{ ref('fct_orders') }} o
left join due using (order_id)
left join paid using (order_id)
where case
        when due.due is null then o.recon_status <> 'no_items'
        when paid.paid is null then o.recon_status <> 'no_payment'
        when abs(paid.paid - due.due) <= 0.01 then o.recon_status <> 'match'
        when abs(paid.paid - due.due) <= 1 then o.recon_status <> 'minor'
        when paid.paid > due.due then o.recon_status <> 'overpaid'
        else o.recon_status <> 'underpaid'
      end
