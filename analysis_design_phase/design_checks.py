# Design-phase grounding checks on the raw Olist CSVs (read-only). Output: analysis_design_phase/design_checks.json
import duckdb, json
import os; D=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"data","raw")
con=duckdb.connect()
T={"orders":"olist_orders_dataset","items":"olist_order_items_dataset","payments":"olist_order_payments_dataset",
   "reviews":"olist_order_reviews_dataset","customers":"olist_customers_dataset","sellers":"olist_sellers_dataset",
   "products":"olist_products_dataset","cat_tr":"product_category_name_translation","geo":"olist_geolocation_dataset"}
for k,v in T.items(): con.execute(f"create view {k} as select * from read_csv_auto('{D}/{v}.csv', header=true)")
q=lambda s: con.execute(s).fetchall()
def v(s):
    r=q(s)[0]; return r[0] if len(r)==1 else list(r)
R={}
R["rows"]={k:v(f"select count(*) from {k}") for k in T}
keys={"orders":"order_id","items":"order_id, order_item_id","payments":"order_id, payment_sequential","reviews":"review_id",
 "customers":"customer_id","sellers":"seller_id","products":"product_id","cat_tr":"product_category_name","geo":"geolocation_zip_code_prefix"}
R["key_distinct"]={k:v(f"select count(*) from (select distinct {c} from {k})") for k,c in keys.items()}
R["reviews_distinct_review_order"]=v("select count(*) from (select distinct review_id, order_id from reviews)")
R["reviews_distinct_order"]=v("select count(distinct order_id) from reviews")
R["orders_with_multiple_reviews"]=v("select count(*) from (select order_id from reviews group by 1 having count(*)>1)")
R["review_ids_on_multiple_orders"]=v("select count(*) from (select review_id from reviews group by 1 having count(distinct order_id)>1)")
R["orders_without_review"]=v("select count(*) from orders o where not exists(select 1 from reviews r where r.order_id=o.order_id)")
R["customers_unique_id"]=v("select count(distinct customer_unique_id) from customers")
R["customer_id_orders_1to1"]=v("select count(*) from (select customer_id from orders group by 1 having count(*)>1)")
R["orders_customer_missing"]=v("select count(*) from orders o where not exists(select 1 from customers c where c.customer_id=o.customer_id)")
R["unique_ids_multi_zip"]=v("select count(*) from (select customer_unique_id from customers group by 1 having count(distinct customer_zip_code_prefix)>1)")
R["unique_ids_multi_state"]=v("select count(*) from (select customer_unique_id from customers group by 1 having count(distinct customer_state)>1)")
R["order_status"]=q("select order_status, count(*) from orders group by 1 order by 2 desc")
R["purchase_range"]=[str(x) for x in q("select min(order_purchase_timestamp), max(order_purchase_timestamp) from orders")[0]]
R["orders_by_edge_month"]=q("select strftime(order_purchase_timestamp,'%Y-%m') m, count(*) from orders group by 1 order by 1")
R["orders_without_items"]=v("select count(*) from orders o where not exists(select 1 from items i where i.order_id=o.order_id)")
R["orders_without_items_by_status"]=q("select order_status,count(*) from orders o where not exists(select 1 from items i where i.order_id=o.order_id) group by 1 order by 2 desc")
R["orders_without_payments"]=v("select count(*) from orders o where not exists(select 1 from payments p where p.order_id=o.order_id)")
R["items_order_missing"]=v("select count(*) from items i where not exists(select 1 from orders o where o.order_id=i.order_id)")
R["items_product_missing"]=v("select count(*) from items i where not exists(select 1 from products p where p.product_id=i.product_id)")
R["items_seller_missing"]=v("select count(*) from items i where not exists(select 1 from sellers s where s.seller_id=i.seller_id)")
R["parcels_order_seller"]=v("select count(*) from (select distinct order_id, seller_id from items)")
R["orders_with_items"]=v("select count(distinct order_id) from items")
R["multi_seller_orders"]=v("select count(*) from (select order_id from items group by 1 having count(distinct seller_id)>1)")
R["parcel_shipping_limit_varies_within_parcel"]=v("select count(*) from (select order_id, seller_id from items group by 1,2 having count(distinct shipping_limit_date)>1)")
R["multi_seller_orders_shipping_limit_differs"]=v("select count(*) from (select order_id from items group by 1 having count(distinct seller_id)>1 and count(distinct shipping_limit_date)>1)")
R["multi_seller_status"]=q("select o.order_status,count(*) from orders o join (select order_id from items group by 1 having count(distinct seller_id)>1) m using(order_id) group by 1 order by 2 desc")
R["delivered_missing_customer_date"]=v("select count(*) from orders where order_status='delivered' and order_delivered_customer_date is null")
R["nondelivered_with_customer_date"]=v("select count(*) from orders where order_status<>'delivered' and order_delivered_customer_date is not null")
R["delivered_before_purchase"]=v("select count(*) from orders where order_delivered_customer_date<order_purchase_timestamp")
R["carrier_before_approval"]=v("select count(*) from orders where order_delivered_carrier_date<order_approved_at")
R["delivered_before_carrier"]=v("select count(*) from orders where order_delivered_customer_date<order_delivered_carrier_date")
R["estimated_date_has_time"]=v("select count(*) from orders where cast(order_estimated_delivery_date as time)<>'00:00:00'")
R["types"]=q("select column_name, column_type from (describe orders)")
# reviews vs delivery
R["reviews_with_delivered_date"]=v("select count(*) from reviews r join orders o using(order_id) where o.order_delivered_customer_date is not null")
R["reviews_created_before_delivery_ts"]=v("select count(*) from reviews r join orders o using(order_id) where o.order_delivered_customer_date is not null and r.review_creation_date<o.order_delivered_customer_date")
R["reviews_created_before_delivery_date"]=v("select count(*) from reviews r join orders o using(order_id) where o.order_delivered_customer_date is not null and r.review_creation_date::date<o.order_delivered_customer_date::date")
R["reviews_on_undelivered_orders"]=v("select count(*) from reviews r join orders o using(order_id) where o.order_delivered_customer_date is null")
R["review_answer_before_creation"]=v("select count(*) from reviews where review_answer_timestamp<review_creation_date")
R["review_creation_has_time"]=v("select count(*) from reviews where cast(review_creation_date as time)<>'00:00:00'")
R["review_score_dist"]=q("select review_score,count(*) from reviews group by 1 order by 1")
R["review_types"]=q("select column_name, column_type from (describe reviews)")
# payments
R["payment_types"]=q("select payment_type,count(*),sum(payment_value)::decimal(14,2) from payments group by 1 order by 2 desc")
R["payment_value_zero"]=v("select count(*) from payments where payment_value=0")
R["payment_installments_zero"]=v("select count(*) from payments where payment_installments=0")
R["payment_seq_gaps"]=v("select count(*) from (select order_id from payments group by 1 having max(payment_sequential)<>count(*))")
R["recon"]=list(q("""with i as (select order_id, sum(price)+sum(freight_value) due from items group by 1),
 p as (select order_id, sum(payment_value) paid from payments group by 1)
 select count(*), sum(case when abs(paid-due)<=0.01 then 1 else 0 end), sum(case when abs(paid-due)>0.01 then 1 else 0 end),
 sum(case when abs(paid-due)>1 then 1 else 0 end), sum(case when paid-due>1 then 1 else 0 end), sum(case when due-paid>1 then 1 else 0 end)
 from i join p using(order_id)""")[0])
R["recon_gt1_by_voucher"]=q("""with i as (select order_id, sum(price)+sum(freight_value) due from items group by 1),
 p as (select order_id, sum(payment_value) paid, bool_or(payment_type='voucher') v, max(payment_installments) inst from payments group by 1)
 select v, inst>1, count(*), sum(case when abs(paid-due)>1 then 1 else 0 end) from i join p using(order_id) group by 1,2 order by 1,2""")
# geo
R["geo_distinct_zip"]=v("select count(distinct geolocation_zip_code_prefix) from geo")
R["geo_exact_dup_rows"]=v("select count(*)-count(distinct (geolocation_zip_code_prefix,geolocation_lat,geolocation_lng,geolocation_city,geolocation_state)) from geo")
R["geo_zip_multi_state"]=v("select count(*) from (select geolocation_zip_code_prefix from geo group by 1 having count(distinct geolocation_state)>1)")
R["geo_outside_brazil"]=v("select count(*) from geo where geolocation_lat>5.3 or geolocation_lat<-33.8 or geolocation_lng<-74 or geolocation_lng>-34.7")
R["customer_zip_missing_in_geo"]=v("select count(*) from customers c where not exists (select 1 from geo g where g.geolocation_zip_code_prefix=c.customer_zip_code_prefix)")
R["seller_zip_missing_in_geo"]=v("select count(*) from sellers s where not exists (select 1 from geo g where g.geolocation_zip_code_prefix=s.seller_zip_code_prefix)")
# products
R["products_null_category"]=v("select count(*) from products where product_category_name is null")
R["product_categories_untranslated"]=q("select distinct product_category_name from products p where product_category_name is not null and not exists(select 1 from cat_tr t where t.product_category_name=p.product_category_name)")
R["products_cols"]=q("select column_name from (describe products)")
R["sellers_with_no_items"]=v("select count(*) from sellers s where not exists(select 1 from items i where i.seller_id=s.seller_id)")
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"design_checks.json"),"w"),indent=1,default=str)
print(json.dumps(R,indent=1,default=str))
