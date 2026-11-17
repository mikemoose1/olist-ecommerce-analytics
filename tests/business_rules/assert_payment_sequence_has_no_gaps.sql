{{ config(severity = 'warn') }}
-- Known source quirk (warn only): 80 orders skip numbers in payment_sequential.
-- Kept visible as a warning so a change in the count is noticed.
select order_id, count(*) as n, max(payment_sequential) as max_seq
from {{ ref('fct_payments') }}
group by order_id
having max(payment_sequential) <> count(*)
