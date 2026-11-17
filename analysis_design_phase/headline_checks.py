# Recompute EDA headline numbers directly from raw CSVs in DuckDB (no pandas), to pin metric definitions.
import duckdb, json
import os; D=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"data","raw"); con=duckdb.connect()
for k,v in {"orders":"olist_orders_dataset","items":"olist_order_items_dataset","reviews":"olist_order_reviews_dataset","customers":"olist_customers_dataset"}.items():
    con.execute(f"create view {k} as select * from read_csv_auto('{D}/{v}.csv', header=true)")
con.execute("""create table ia as select order_id, count(distinct seller_id) n_sellers from items group by 1;
create table rev1 as select * from (select *, row_number() over (partition by order_id order by review_answer_timestamp desc) rn from reviews) where rn=1;
create table dl as select o.*, ia.n_sellers, (o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date) late,
  (o.order_delivered_customer_date > o.order_estimated_delivery_date) late_ts, r.review_score
 from orders o join ia using(order_id) left join rev1 r using(order_id)
 where o.order_status='delivered' and o.order_delivered_customer_date is not null
   and strftime(o.order_purchase_timestamp,'%Y-%m') between '2017-01' and '2018-08';""")
R={}
R["late"]=con.execute("select count(*), sum(late::int), round(100*avg(late::int),2), round(100*avg(late_ts::int),2) from dl").fetchone()
R["late_all_months"]=con.execute("""select round(100*avg((o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date)::int),2), count(*) from orders o
  where o.order_status='delivered' and o.order_delivered_customer_date is not null""").fetchone()
R["review_gap_raw"]=con.execute("select round(avg(review_score) filter (where not late) - avg(review_score) filter (where late),3), round(avg(review_score),3) from dl").fetchone()
R["multi_seller_in_dl"]=con.execute("select sum((n_sellers>1)::int), round(100*avg((n_sellers>1)::int),2) from dl").fetchone()
R["multi_seller_late_vs_single"]=con.execute("select n_sellers>1, round(100*avg(late::int),2), round(avg(review_score),3), count(*) from dl group by 1 order by 1").fetchall()
R["rev_before_delivery_rev1_delivered"]=con.execute("""select count(*), sum((r.review_creation_date < o.order_delivered_customer_date)::int),
  round(100*avg((r.review_creation_date < o.order_delivered_customer_date)::int),2),
  round(100*avg((r.review_creation_date::date < o.order_delivered_customer_date::date)::int),2)
  from rev1 r join orders o using(order_id) where o.order_status='delivered' and o.order_delivered_customer_date is not null""").fetchone()
R["rev_before_delivery_gap_days_pctiles"]=con.execute("""select quantile_cont(date_diff('hour', r.review_creation_date, o.order_delivered_customer_date)/24.0,[0.1,0.5,0.9])
  from rev1 r join orders o using(order_id) where o.order_status='delivered' and r.review_creation_date < o.order_delivered_customer_date""").fetchone()
R["rev_before_delivery_score"]=con.execute("""select (r.review_creation_date < o.order_delivered_customer_date) b, round(avg(review_score),3), count(*)
  from rev1 r join orders o using(order_id) where o.order_status='delivered' and o.order_delivered_customer_date is not null group by 1 order by 1""").fetchall()
con.execute("""create table co as select c.customer_unique_id cu, o.order_id, o.order_purchase_timestamp ts
  from orders o join customers c using(customer_id) join ia using(order_id) where o.order_status not in ('canceled','unavailable');
create table cf as select cu, min(ts) first_ts, count(*) n from co group by 1;
create table c2 as select cu, ts second_ts from (select *, row_number() over (partition by cu order by ts) k from co) where k=2;""")
R["repeat_ever"]=con.execute("select count(*), sum((n>1)::int), round(100*avg((n>1)::int),2) from cf").fetchone()
last=con.execute("select max(ts) from co").fetchone()[0]; R["last_ts"]=str(last)
R["repeat_90d"]=con.execute(f"""select count(*),
  round(100*avg(coalesce(date_diff('second',f.first_ts,c2.second_ts)/86400.0<=90,false)::int),2),
  round(100*avg(coalesce(date_diff('second',f.first_ts,c2.second_ts)/86400.0<=90 and date_diff('second',f.first_ts,c2.second_ts)/86400.0>=1,false)::int),2)
  from cf f left join c2 using(cu) where f.first_ts <= timestamp '{last}' - interval 90 day""").fetchone()
# "any later order on a different calendar day within 90d" (k=2 rule vs any-order rule)
R["repeat_90d_any_later_order_diff_day"]=con.execute(f"""select round(100*avg(hit::int),2) from (
  select f.cu, bool_or(co.ts::date > f.first_ts::date and co.ts <= f.first_ts + interval 90 day) hit
  from cf f join co using(cu) where f.first_ts <= timestamp '{last}' - interval 90 day group by 1)""").fetchone()
R["same_day_second_pct"]=con.execute("select round(100*avg((date_diff('second',f.first_ts,c2.second_ts)<86400)::int),2), count(*) from c2 join cf f using(cu)").fetchone()
print(json.dumps(R,indent=1,default=str)); json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"headline_checks.json"),"w"),indent=1,default=str)
R["repeat_90d_any_later_order_ge24h"]=con.execute(f"""select round(100*avg(hit::int),2), sum(hit::int) from (
  select f.cu, bool_or(co.ts >= f.first_ts + interval 1 day and co.ts <= f.first_ts + interval 90 day) hit
  from cf f join co using(cu) where f.first_ts <= timestamp '{last}' - interval 90 day group by 1)""").fetchone()
R["repeat_90d_k2_counts"]=con.execute(f"""select sum(coalesce(date_diff('second',f.first_ts,c2.second_ts)/86400.0 between 1 and 90,false)::int) from cf f left join c2 using(cu) where f.first_ts <= timestamp '{last}' - interval 90 day""").fetchone()
print(R["repeat_90d_any_later_order_ge24h"], R["repeat_90d_k2_counts"]); json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"headline_checks.json"),"w"),indent=1,default=str)
