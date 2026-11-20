#!/usr/bin/env python3
"""prep3.py <out dir>   DuckDB -> the CSVs the six-chart page reads (step 1; prep4.py adds the label series). Nothing typed: all values computed here.
Needs: OLIST_DB (the warehouse file, required), SEEDS (folder holding dash_region_map.csv, default seeds), and
B1DATA (folder with summary.csv, ramp_b.csv, monthly_long.csv from prep.py, default /tmp/olist_tableau)."""
import duckdb,csv,sys,os,shutil
out=sys.argv[1]; os.makedirs(out,exist_ok=True)
DB=os.environ['OLIST_DB']; SEEDS=os.environ.get('SEEDS','seeds')
SRC=os.environ.get('B1DATA','/tmp/olist_tableau')
con=duckdb.connect(DB,read_only=True)
for f in ('summary.csv','ramp_b.csv','monthly_long.csv'): shutil.copy(os.path.join(SRC,f),os.path.join(out,f))
region={r['state']:r['region_group'] for r in csv.DictReader(open(os.path.join(SEEDS,'dash_region_map.csv')))}
con.execute("create temp table rm(state varchar, region_group varchar)"); con.executemany("insert into rm values (?,?)",list(region.items()))
def wr(name,cols,rows):
    with open(os.path.join(out,name),'w',newline='') as f:
        w=csv.writer(f,lineterminator='\n'); w.writerow(cols); [w.writerow(['' if v is None else v for v in r]) for r in rows]
    print(name,len(rows))
# ---------------- order-level (same as export_orders.py plus seller size / state / repeat group)
q="""
with judged as (
  select o.order_id, o.purchase_date, o.is_late, o.ship_to_state,
         f.delivered_to_carrier_at > f.last_shipping_limit_at as handed_over_late
  from metrics.metric_late_rate_orders o join marts.fct_orders f on f.order_id=o.order_id),
one_seller as (select order_id, min(seller_id) as seller_id from marts.fct_order_items group by 1),
mo as (select year_month as ym, is_worst3_late_month as w3, month_label from exports.export_dash_monthly),
rank as (select seller_id, orders as seller_orders, rank_by_late_after_late_handoff as seller_rank, is_top10 from exports.export_dash_sellers),
lm as (select s.seller_id, count(distinct strftime(j.purchase_date,'%Y-%m')) as late_months
       from judged j join one_seller s using(order_id) where coalesce(j.handed_over_late and j.is_late,false) group by 1)
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
       case when j.handed_over_late is null then 'No shipping time' when j.handed_over_late then 'Shipped after the ship-by date' else 'Shipped by the ship-by date' end as handoff_group,
       case when j.handed_over_late is null then 'false' else 'true' end as has_handoff,
       cast(coalesce(j.handed_over_late and j.is_late,false) as int) as late_after_late_handoff,
       cast(coalesce(j.handed_over_late and j.is_late,false) as int) as lalh_n,
       cast(coalesce(j.handed_over_late,false) as int) as late_handoff_n,
       case when r.seller_orders is null then 'Unknown' when r.seller_orders<20 then 'Small seller (under 20 orders)' when r.seller_orders<100 then 'Mid-size seller (20 to 99 orders)' else 'Large seller (100+ orders)' end as seller_size,
       coalesce(d.state,'??') as seller_state,
       case when lm.late_months>=3 then '3 months or more' when lm.late_months>=1 then '1 to 2 months' else 'Never' end as seller_repeat
from judged j left join one_seller s on s.order_id=j.order_id left join rank r on r.seller_id=s.seller_id left join rm m on m.state=j.ship_to_state
     left join mo on mo.ym=strftime(j.purchase_date,'%Y-%m') left join marts.dim_seller d on d.seller_id=s.seller_id left join lm on lm.seller_id=s.seller_id
order by j.order_id
"""
cur=con.execute(q); cols=[d[0] for d in cur.description]; R=cur.fetchall()
import collections
ix={c:i for i,c in enumerate(cols)}
R=[list(r) for r in R]
# seller-group labels carry the number of sellers in the group (computed from these rows)
top5=[r[0] for r in con.execute("""select d.state from (select order_id, min(seller_id) sid from marts.fct_order_items group by 1) s join marts.dim_seller d on d.seller_id=s.sid join metrics.metric_late_rate_orders o on o.order_id=s.order_id join marts.fct_orders f on f.order_id=s.order_id where o.is_late and f.delivered_to_carrier_at>f.last_shipping_limit_at group by 1 order by count(*) desc limit 5""").fetchall()]
nsell=collections.defaultdict(set)
for r in R:
    code=r[ix['seller_code']]
    if r[ix['seller_repeat']]=='Never': continue   # only sellers with a late order that was shipped late
    if r[ix['seller_size']]!='Unknown': nsell['size',r[ix['seller_size']]].add(code)
    nsell['state',r[ix['seller_state']] if r[ix['seller_state']] in top5 else 'All other states'].add(code)
    nsell['rep',r[ix['seller_repeat']]].add(code)
cols+=['seller_in_scope']
for r in R:
    rp=r[ix['seller_repeat']]
    if rp=='Never' or r[ix['seller_size']]=='Unknown':
        r[ix['seller_size']]=r[ix['seller_state']]=r[ix['seller_repeat']]='None'; r.append('false'); continue
    st=r[ix['seller_state']] if r[ix['seller_state']] in top5 else 'All other states'
    ns=len(nsell['state',st])
    r[ix['seller_size']]='%s: %s sellers'%(r[ix['seller_size']],format(len(nsell['size',r[ix['seller_size']]]),','))
    r[ix['seller_state']]='%s: %s seller%s'%(('State '+st) if st!='All other states' else st,format(ns,','),'' if ns==1 else 's')
    r[ix['seller_repeat']]='%s: %d sellers'%({'1 to 2 months':'Few months (1 to 2)','3 months or more':'Many months (3 or more)'}[rp],len(nsell['rep',rp]))
    r.append('true')
wr('orders.csv',cols,R)
# ---------------- monthly status + sparklines
M=con.execute("""select year_month,month_start,month_label,orders,late_orders,late_rate,goal_late_rate,own_month_alarm_line_late_rate,
  late_handoff_orders,late_handoff_late_orders,on_time_handoff_orders,on_time_handoff_late_orders from exports.export_dash_monthly order by 1""").fetchall()
def status(r): return 'red' if r[5]>r[7] else 'amber' if r[5]>r[6] else 'green'
rows=[]; last=M[-1]
for r in M:
    d=str(r[1]); islast=r==last
    rows.append(('late_rate','a Late rate',d,r[5],'')); 
    if status(r)=='red': rows.append(('late_rate','b Breach %d'%(sum(status(x)=='red' for x in M[:M.index(r)+1])),d,r[5],'\u25cf'))
    if islast: rows.append(('late_rate','c Latest %s'%status(r),d,r[5],''))
    rows.append(('ship_late_share','d Share',d,r[8]/r[3],''))
    if islast: rows.append(('ship_late_share','e Share latest',d,r[8]/r[3],'\u25cf'))
    rows.append(('gap','f Shipped after the ship-by date',d,r[9]/r[8],'')); rows.append(('gap','g Shipped by the ship-by date',d,r[11]/r[10],''))
    if islast: rows.append(('gap','h Gap latest',d,r[9]/r[8],'\u25cf'))
wr('spark_long.csv',['metric','series','month_start','value','lab'],rows)
# status_now + scalars
tot=con.execute("select sum(orders),sum(late_handoff_orders) from exports.export_dash_monthly").fetchone()
lh=con.execute("select sum(late_handoff_late_orders)*1.0/sum(late_handoff_orders), sum(on_time_handoff_late_orders)*1.0/sum(on_time_handoff_orders) from exports.export_dash_monthly").fetchone()
sc=dict(latest_label=last[2],latest_rate=last[5],goal=last[6],alarm=last[7],status=status(last),latest_orders=last[3],latest_late_orders=last[4],
  latest_ship_late_share=last[8]/last[3],period_ship_late_share=tot[1]/tot[0],latest_gap_rate_late=last[9]/last[8],latest_gap_rate_ok=last[11]/last[10],
  n_months=len(M),n_red=sum(status(r)=='red' for r in M),n_amber=sum(status(r)=='amber' for r in M),n_green=sum(status(r)=='green' for r in M),
  red_months=', '.join(r[2] for r in M if status(r)=='red'),first_label=M[0][2])
wr('v3_scalars.csv',list(sc),[list(sc.values())])
wr('status_now.csv',['label','value','status'],[('Late rate, %s'%last[2],last[5],status(last))])
# seller group tables for checks

# ---------------- trend variants (declutter). One CSV per variant, same columns.
p1=lambda x:'%.1f%%'%(x*100)
def trend(name,warn,breach_lab,goal_lab):
    rows=[]
    for r in M:
        base=dict(year_month=r[0],month_start=str(r[1]),orders=r[3],late_orders=r[4])
        rows.append(dict(base,month_idx=0,series='g Late rate',value=r[5],lab=''))
        if warn: rows.append(dict(base,month_idx=0,series='c Alarm line',value=r[7],lab=''))
        if status(r)=='red': rows.append(dict(base,month_idx=0,series='e Breach %d'%(sum(status(x)=='red' for x in M[:M.index(r)+1])),value=r[5],lab=(r[2][:3] if breach_lab else '\u25cf')))
        if r==last:
            rows.append(dict(base,month_idx=0,series='f Latest month',value=r[5],lab='%s %s'%(r[2][:3],p1(r[5]))))
            if goal_lab: rows.append(dict(base,month_idx=0,series='d Goal label',value=r[6],lab='Goal %s'%p1(r[6])))
    cols=['year_month','month_start','month_idx','series','value','lab','orders','late_orders']
    wr('trend_%s.csv'%name,cols,[[d[c] for c in cols] for d in rows])
trend('a',False,False,False)   # no warning line, unlabeled breach dots, goal labelled by the reference line
trend('b',True,False,False)    # a + light warning line
trend('c',True,True,True)      # minimal change: stretch gone, warning line kept, month labels kept, goal label at right end as a series
# ---------------- seller group table (for titles and the numbers check)
con.execute("create temp table oo as select * from read_csv(?,header=true,all_varchar=true)",[os.path.join(out,'orders.csv')])
G=[]
for kind,col in (('size','seller_size'),('state','seller_state'),('repeat','seller_repeat')):
    for g,n,lalh in con.execute("select %s,count(*),sum(cast(lalh_n as int)) from oo where seller_in_scope='true' group by 1 order by 3 desc"%col).fetchall():
        G.append((kind,g,n,lalh,lalh/con.execute("select sum(cast(lalh_n as int)) from oo").fetchone()[0]))
# share of ALL orders for the same groups needs all rows: recompute with the underlying seller attributes
wr('seller_groups.csv',['kind','grp','orders_in_scope','late_shipped_late_orders','share_of_late_shipped_late'],G)
