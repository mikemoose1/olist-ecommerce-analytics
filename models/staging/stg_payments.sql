-- Grain: one row per payment instrument on an order. PK: (order_id, payment_sequential). 1:1 with raw.
-- payment_type 'not_defined' (3 rows, all R$0.00) is kept and labeled, not dropped.
select
    order_id,
    cast(payment_sequential as integer)     as payment_sequential,
    payment_type,
    cast(payment_installments as integer)   as payment_installments,
    cast(payment_value as decimal(12, 2))   as payment_value
from {{ source('olist_raw', 'olist_order_payments_dataset') }}
