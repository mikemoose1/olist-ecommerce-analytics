-- Grain: one row per order. PK: order_id.
-- Business rule: what the customer paid should equal items + freight. Every order gets exactly one
-- recon_status: match (|diff| <= R$0.01) | minor (<= R$1) | overpaid | underpaid | no_items | no_payment.
with due as (
    select order_id, sum(price) + sum(freight_value) as amount_due, count(*) as n_items
    from {{ ref('stg_order_items') }}
    group by order_id
),
paid as (
    select order_id, sum(payment_value) as amount_paid, count(*) as n_payments,
           max(payment_installments) as max_installments, bool_or(payment_type = 'voucher') as used_voucher
    from {{ ref('stg_payments') }}
    group by order_id
)
select
    o.order_id,
    coalesce(due.n_items, 0)      as n_items,
    due.amount_due,
    paid.amount_paid,
    coalesce(paid.n_payments, 0)  as n_payments,
    paid.max_installments,
    coalesce(paid.used_voucher, false) as used_voucher,
    paid.amount_paid - due.amount_due as paid_minus_due,
    case
        when due.order_id is null then 'no_items'
        when paid.order_id is null then 'no_payment'
        when abs(paid.amount_paid - due.amount_due) <= 0.01 then 'match'
        when abs(paid.amount_paid - due.amount_due) <= 1 then 'minor'
        when paid.amount_paid > due.amount_due then 'overpaid'
        else 'underpaid'
    end as recon_status
from {{ ref('stg_orders') }} o
left join due using (order_id)
left join paid using (order_id)
