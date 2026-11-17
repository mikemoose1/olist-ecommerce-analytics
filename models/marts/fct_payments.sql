-- Grain: one row per payment instrument. PK: (order_id, payment_sequential). FK: order_id -> fct_orders.
select order_id, payment_sequential, payment_type, payment_installments, payment_value
from {{ ref('stg_payments') }}
