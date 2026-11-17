-- Rule: repeat behavior is measured on people (customer_unique_id), never on the per-order customer_id.
-- Fails if dim_customer does not hold exactly one row per distinct person in the source,
-- or if any order's person key is actually a customer_id surrogate.
with source_people as (
    select count(distinct customer_unique_id) as n from {{ ref('stg_customers') }}
),
dim_people as (
    select count(*) as n from {{ ref('dim_customer') }}
)
select 'dim_customer row count differs from distinct people' as problem, null as order_id
from source_people, dim_people
where source_people.n <> dim_people.n
union all
select 'order keyed by customer_id surrogate', o.order_id
from {{ ref('fct_orders') }} o
join {{ ref('stg_customers') }} c on c.customer_id = o.customer_unique_id
