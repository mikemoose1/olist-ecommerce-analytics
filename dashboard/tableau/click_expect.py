#!/usr/bin/env python3
"""click_expect.py : what every filtered chart on the final page must show for each click, computed from the warehouse
(independent of orders.csv). Prints a markdown table. Charts that follow the filter: shipped-late bars (late rate), sellers
bars (late-shipped late orders by repeat group), region bars (late rate), months bars (late orders in the tagged months).
Charts that do not follow it (excluded in the actions): review ramp, trend, the three tiles."""
import duckdb,csv,sys
import os
con=duckdb.connect(os.environ['OLIST_DB'],read_only=True)   # OLIST_DB: the warehouse file; seeds folder from SEEDS (default seeds)
reg={r['state']:r['region_group'] for r in csv.DictReader(open(os.path.join(os.environ.get('SEEDS','seeds'),'dash_region_map.csv')))}
con.execute("create temp table rm(st varchar, rg varchar)"); con.executemany("insert into rm values (?,?)",list(reg.items()))
con.execute("""create temp table b as select o.order_id,o.is_late l,strftime(o.purchase_date,'%Y-%m') ym,f.delivered_to_carrier_at>f.last_shipping_limit_at hl,s.seller_id,o.ship_to_state st
 from metrics.metric_late_rate_orders o join marts.fct_orders f using(order_id) left join (select order_id,min(seller_id) seller_id from marts.fct_order_items group by 1) s using(order_id)""")
con.execute("""create temp table lm as select seller_id,count(distinct ym) m from b where hl is true and l group by 1""")
con.execute("""create temp table x as select b.*,rm.rg, case when lm.m>=3 then 'many' when lm.m>=1 then 'few' else 'never' end grp from b left join rm on rm.st=b.st left join lm using(seller_id)""")
def show(title,where):
    w=('where '+where) if where else ''
    h=con.execute(f"select hl,count(*),sum(l::int),avg(l::int) from x {w}{' and' if w else 'where'} hl is not null group by 1 order by 1").fetchall()
    r=con.execute(f"select rg,count(*),avg(l::int) from x {w} group by 1 order by 1").fetchall()
    mo=con.execute(f"select ym,sum(l::int) from x {w}{' and' if w else 'where'} ym in ('2017-11','2018-02','2018-03','2018-08') group by 1 order by 1").fetchall()
    sl=con.execute(f"select grp,sum((hl is true and l)::int) from x {w}{' and' if w else 'where'} grp in ('many','few') group by 1 order by 1").fetchall()
    f1=lambda v:'%.1f%%'%(v*100)
    print('| %s | by ship-by date %s, shipped late %s | N/NE %s, rest %s | %s | %s |'%(title,
      f1(h[0][3]) if h else '-', f1(h[1][3]) if len(h)>1 else '-',
      f1([x for x in r if x[0]=='North and northeast'][0][2]) if any(x[0]=='North and northeast' for x in r) else '-',
      f1([x for x in r if x[0]=='Rest of Brazil'][0][2]) if any(x[0]=='Rest of Brazil' for x in r) else '-',
      ' / '.join('%s %s'%(a[2:] if False else a,format(int(c),',')) for a,c in mo) or '-',
      ' / '.join('%s %s'%({'many':'3+ months','few':'1-2 months'}[a],format(int(c),',')) for a,c in sl) or '-'))
print('| click | shipped-late chart | region chart | late orders in months chart | sellers chart (late-shipped late orders) |\n|---|---|---|---|---|')
show('baseline (no click)','')
show('seller bar: 3 or more months',"grp='many'")
show('seller bar: 1 to 2 months',"grp='few'")
show('region bar: North and northeast',"rg='North and northeast'")
show('month bar: Nov 2017',"ym='2017-11'")
