"""Order-level table for the review-cost question, read straight from the built warehouse.
One row per judged order (94,931); reviewed_only=True keeps the 94,302 with a review and adds y = bad (1-2 stars).
x = days past the END of the promised day (late iff x >= 0)."""
import os, numpy as np, pandas as pd, duckdb
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(ROOT, "olist.duckdb"))

def load(reviewed_only=True, db=DB):
    c = duckdb.connect(db, read_only=True)
    d = c.sql("""
    with items as (
      select i.order_id, any_value(i.seller_id) seller_id, sum(i.price) price, sum(i.freight_value) freight,
             arg_max(p.category, i.price) category, arg_max(i.product_id, i.price) product_id, min(i.shipping_limit_at) ship_limit_at
      from marts.fct_order_items i left join marts.dim_product p using (product_id) group by 1)
    select o.order_id, strftime(o.purchase_date, '%Y-%m') ym, o.is_late, f.days_past_promise, f.promised_days,
           f.estimated_delivery_date, f.delivered_to_customer_at, f.delivered_to_carrier_at, f.purchased_at,
           date_diff('second', cast(f.estimated_delivery_date + interval 1 day as timestamp), f.delivered_to_customer_at) / 86400.0 as x,
           o.review_score, o.review_before_delivery, i.seller_id, i.price, i.freight, coalesce(i.category, 'unknown') category,
           i.product_id, i.ship_limit_at, o.ship_to_state, s.state seller_state, f.n_items
    from metrics.metric_late_rate_orders o
    join marts.fct_orders f using (order_id)
    left join items i using (order_id)
    left join marts.dim_seller s on s.seller_id = i.seller_id
    order by o.order_id""").df()
    d["late"] = d.is_late.astype(int); d["seller"] = d.seller_id
    d["lprice"] = np.log1p(d.price.astype(float)); d["lfreight"] = np.log1p(d.freight.astype(float))
    d["promised_days"] = d.promised_days.astype(float); d["reviewed"] = d.review_score.notna().astype(int)
    assert ((d.x >= 0) == d.is_late).all(), "late flag and days-past-promise disagree"
    if reviewed_only:
        d = d[d.reviewed == 1].copy(); d["y"] = (d.review_score <= 2).astype(int)
    return d.reset_index(drop=True)
