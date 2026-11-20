"""usage: export_orders.py <out orders.csv>
Slim order-level CSV for the interactive dashboard: one row per judged order (the same population as dash_order_base).
Public Olist data only: 8-char order prefix, month, 8-char seller code, ship-to state, region group, 0/1 flags."""
import duckdb,csv,sys,os
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB=os.environ.get('OLIST_DB_PATH',os.path.join(ROOT,'olist.duckdb'))
if not os.path.exists(DB): sys.exit('warehouse not found: '+DB+' (run make build, or set OLIST_DB_PATH)')
con=duckdb.connect(DB,read_only=True)
region={r['state']:r['region_group'] for r in csv.DictReader(open(os.path.join(ROOT,'seeds','dash_region_map.csv')))}
con.execute("create temp table rm(state varchar, region_group varchar)")
con.executemany("insert into rm values (?,?)",list(region.items()))
q="""
with judged as (
  select o.order_id, o.purchase_date, o.is_late, o.ship_to_state,
         f.delivered_to_carrier_at > f.last_shipping_limit_at as handed_over_late
  from metrics.metric_late_rate_orders o join marts.fct_orders f on f.order_id=o.order_id),
one_seller as (select order_id, min(seller_id) as seller_id from marts.fct_order_items group by 1),
mo as (select year_month as ym, is_worst3_late_month as w3, month_label from exports.export_dash_monthly),
rank as (select seller_id, left(seller_id,8) as seller_code, rank_by_late_after_late_handoff as seller_rank, is_top10 from exports.export_dash_sellers)
select left(j.order_id,8) as order_code,
       strftime(j.purchase_date,'%Y-%m') as year_month,
       strftime(date_trunc('month',j.purchase_date),'%Y-%m-%d') as month_start,
       left(s.seller_id,8) as seller_code,
       r.seller_rank, cast(r.is_top10 as varchar) as is_top10,
       case when r.is_top10 then lpad(cast(r.seller_rank as varchar),2,'0')||'   seller '||left(s.seller_id,8) else 'seller '||left(s.seller_id,8) end as seller_label,
       cast(mo.w3 as varchar) as is_worst3_month,
       case when mo.w3 or strftime(j.purchase_date,'%Y-%m')='2018-08' then left(mo.month_label,3) else '' end as month_tag,
       cast(case when (mo.w3 or strftime(j.purchase_date,'%Y-%m')='2018-08') and j.is_late then 1 end as int) as late_tag_n,
       j.ship_to_state as state, m.region_group,
       cast(j.is_late as int) as late, cast(j.is_late as int) as late_n,
       case when j.handed_over_late is null then 'No handoff time' when j.handed_over_late then 'Handed to carrier after ship-by' else 'Handed over on time' end as handoff_group,
       case when j.handed_over_late is null then 'false' else 'true' end as has_handoff,
       cast(coalesce(j.handed_over_late and j.is_late,false) as int) as late_after_late_handoff,
       cast(coalesce(j.handed_over_late and j.is_late,false) as int) as lalh_n,
       cast(coalesce(j.handed_over_late,false) as int) as late_handoff_n
from judged j left join one_seller s on s.order_id=j.order_id left join rank r on r.seller_id=s.seller_id left join rm m on m.state=j.ship_to_state left join mo on mo.ym=strftime(j.purchase_date,'%Y-%m')
order by j.order_id
"""
cur=con.execute(q); cols=[d[0] for d in cur.description]; rows=cur.fetchall()
out=sys.argv[1]
with open(out,'w',newline='') as f:
    w=csv.writer(f,lineterminator='\n'); w.writerow(cols)
    for r in rows: w.writerow(['' if v is None else v for v in r])
print(out,len(rows),'rows',cols)
