-- Rule: every order has exactly one delivery state, and it agrees with the facts:
-- on time / late need status 'delivered' AND a delivery date; not_delivered has neither;
-- anything else is a status/date conflict and is never counted as on time or late.
select order_id, order_status, delivered_to_customer_at, delivery_state
from {{ ref('fct_orders') }}
where delivery_state is null
   or (delivery_state in ('delivered_on_time', 'delivered_late')
        and (order_status <> 'delivered' or delivered_to_customer_at is null))
   or (delivery_state = 'delivered_late'
        and cast(delivered_to_customer_at as date) <= estimated_delivery_date)
   or (delivery_state = 'delivered_on_time'
        and cast(delivered_to_customer_at as date) > estimated_delivery_date)
   or (delivery_state = 'not_delivered'
        and (order_status = 'delivered' or delivered_to_customer_at is not null))
   or (delivery_state = 'status_date_conflict'
        and (order_status = 'delivered') = (delivered_to_customer_at is not null))
