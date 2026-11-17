-- Rule: every reviewed order is represented by exactly one review, and fct_orders shows that review.
with per_order as (
    select order_id, count(*) filter (where is_chosen_for_order) as n_chosen
    from {{ ref('fct_reviews') }}
    group by order_id
)
select p.order_id, p.n_chosen, null as review_id
from per_order p
where p.n_chosen <> 1
union all
select o.order_id, null, o.review_id
from {{ ref('fct_orders') }} o
join per_order p using (order_id)
left join {{ ref('fct_reviews') }} r on r.order_id = o.order_id and r.review_id = o.review_id and r.is_chosen_for_order
where r.review_id is null
