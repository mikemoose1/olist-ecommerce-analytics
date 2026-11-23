"""Numbers check for the six-chart page. Every figure shown (tiles, titles, labels, seller groups, status) recomputed from the warehouse
by queries independent of prep3.py/prep4.py, then compared with what is on the image text (from the workbook XML) and the CSVs. Exit 1 on any mismatch."""
import duckdb,csv,sys,re,glob,os
DATA=os.environ.get('DATA','data4'); TW=os.environ.get('TWB_DIR','.')   # DATA: prep4.py output folder. TWB_DIR: folder holding out_v4_six_chart.twb
con=duckdb.connect(os.environ['OLIST_DB'],read_only=True)   # OLIST_DB: the warehouse file
q=lambda s: con.execute(s).fetchall()
S=list(csv.DictReader(open(DATA+'/summary.csv')))[0]; V=list(csv.DictReader(open(DATA+'/v3_scalars.csv')))[0]
rows=[]; f=float
def chk(name,shown,duck,fmt=lambda x:x):
    ok=fmt(duck)==shown; rows.append((name,str(shown),str(fmt(duck)),'OK' if ok else 'MISMATCH'))
P1=lambda x:'%.1f%%'%(f(x)*100); P0=lambda x:'%d%%'%round(f(x)*100); N=lambda x:format(int(round(f(x))),',')
con.execute("create temp table b as select o.order_id,o.is_late,o.purchase_date pd,strftime(o.purchase_date,'%Y-%m') ym,f.delivered_to_carrier_at>f.last_shipping_limit_at hl,s.seller_id from metrics.metric_late_rate_orders o join marts.fct_orders f using(order_id) left join (select order_id,min(seller_id) seller_id from marts.fct_order_items group by 1) s using(order_id)")
# ---- monthly status, independent of export_dash_monthly's own columns where possible
m=q("select ym,count(*),sum(is_late::int),avg(is_late::int),sum((hl is true)::int),sum((hl is true and is_late)::int),sum((hl is false)::int),sum((hl is false and is_late)::int) from b group by 1 order by 1")
mm=q("select year_month,goal_late_rate,own_month_alarm_line_late_rate from exports.export_dash_monthly order by 1")
last=m[-1]; goal=mm[-1][1]; alarm=mm[-1][2]
chk('tile: late rate, latest month','6.3%',last[3],P1); chk('goal','4.4%',goal,P1); chk('warning line, latest month','8.4%',alarm,P1)
stat=lambda r,g,a:'red' if r[3]>a else 'amber' if r[3]>g else 'green'
chk('status, latest month (amber = above goal, under the warning line)','amber',stat(last,goal,alarm))
sts=[stat(r,g[1],g[2]) for r,g in zip(m,mm)]
chk('months red / amber / green','3 / 7 / 10','%d / %d / %d'%(sts.count('red'),sts.count('amber'),sts.count('green')))
chk('breach months (dots)','2017-11,2018-02,2018-03',','.join(r[0] for r,s in zip(m,sts) if s=='red'))
chk('arrow glyph on tile 2 (up = above goal)','\u25b2','\u25b2' if last[3]>goal else '\u25bc')
chk('points above goal','1.9','%.1f'%((last[3]-goal)*100))
chk('stretch what-if footnote','3.4%',S['stretch_whatif_late_rate'],P1)
# ---- shipped-late share tile and gap tile
chk('tile P1-2: share of orders shipped late, latest month','9.2%',last[4]/last[1],P1)
tot=q("select count(*),sum((hl is true)::int) from b")[0]; avg=tot[1]/tot[0]
chk('tile P1-2: all-months average','9.0%',avg,P1)
chk('tile P1-2: points vs average','0.2','%.1f'%(abs(last[4]/last[1]-avg)*100))
hl=q("select hl,count(*),sum(is_late::int) from b where hl is not null group by 1 order by 1")
chk('tile P1-3: late when shipped late','21.2%',hl[1][2]/hl[1][1],P1); chk('tile P1-3: late when shipped by ship-by date','5.4%',hl[0][2]/hl[0][1],P1)
chk('tile P1-3: points worse','15.8','%.1f'%((hl[1][2]/hl[1][1]-hl[0][2]/hl[0][1])*100))
chk('share of all late shipped late','27.8%',hl[1][2]/tot[0] if False else hl[1][2]/q("select sum(is_late::int) from b")[0][0],P1)
chk('cost estimate (strip)','3,110',q("select sum(extra_bad_reviews) from metrics.metric_review_cost_causal")[0][0],N)
# ---- spark_long vs independent monthly
SP=list(csv.DictReader(open(DATA+'/spark_long.csv')))
def sv(metric,series): return {r['month_start'][:7]:f(r['value']) for r in SP if r['metric']==metric and r['series']==series}
d1=sv('late_rate','a Late rate'); d2=sv('ship_late_share','d Share'); d3=sv('gap','f Shipped after the ship-by date'); d4=sv('gap','g Shipped by the ship-by date')
mx=max(max(abs(d1[r[0]]-r[3]),abs(d2[r[0]]-r[4]/r[1]),abs(d3[r[0]]-r[5]/r[4]),abs(d4[r[0]]-r[7]/r[6])) for r in m)
chk('sparkline values, 20 months x 4 series, max abs diff vs warehouse','0.0',mx,lambda x:'0.0' if x<1e-9 else 'nonzero %g'%x)
chk('sparkline months','20',len(d1),str)
TRN=list(csv.DictReader(open(DATA+'/trend_e.csv')))
tv=lambda name:{r['month_start'][:7]:f(r['value']) for r in TRN if r['series']==name}
t1=tv('g Late rate'); t2=tv('c Alarm line'); al={r[0]:r[2] for r in mm}
mx2=max(max(abs(t1[r[0]]-r[3]) for r in m),max(abs(t2[k]-al[k]) for k in al))
chk('trend chart values (rate and warning line, 20 months) max abs diff vs warehouse','0.0',mx2,lambda x:'0.0' if x<1e-9 else 'nonzero %g'%x)
chk('trend breach dots (series e Breach n)','2017-11,2018-02,2018-03',','.join(r['month_start'][:7] for r in TRN if r['series'].startswith('e Breach')))
# ================= v4 (final page): the four reader fixes and the repeat-seller panel
MN=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']; mname=lambda ym:'%s %s'%(MN[int(ym[5:7])-1],ym[:4]); NB='\u00a0'
brm=[r[0] for r,s_ in zip(m,sts) if s_=='red']
# fix 4: each dot is a label drawn at exactly (month, rate) of a point on the late-rate line
dots=[r for r in TRN if r['series'].startswith('e Breach')]
chk('fix 4: breach dots, one per past-warning month, text is a dot','3 / \u25cf',' / '.join([str(len(dots)),set(r['lab'] for r in dots).pop()]))
exact=all(any(r2['series']=='g Late rate' and r2['month_start']==d['month_start'] and r2['value']==d['value'] for r2 in TRN) for d in dots)
chk('fix 4: every dot has the same month and the same value as a late-rate line point (exact string match)','True',exact,str)
chk('fix 4: dot heights equal the warehouse late rate of those months (max abs diff)','0.0',max(abs(f(d['value'])-[r[3] for r in m if r[0]==d['year_month']][0]) for d in dots),lambda x:'0.0' if x<1e-9 else 'nonzero %g'%x)
# fix 2: month names beside the dots, tick format
nm={r['series']:r for r in TRN if r['series'].startswith('k')}
chk('fix 2: month name labels beside the dots (warehouse months)','Nov 2017,Feb 2018,Mar 2018',','.join(mname(y) for y in brm))
chk('fix 2: month name label text as drawn (padding removed)','Nov 2017,Feb 2018,Mar 2018',','.join(nm[k]['lab'].replace(NB,'') for k in ('k5 name nov','k6 name feb','k7 name mar')))
chk('fix 2: month name labels sit at or next to their own month (within 2 months of the dot)','True',all(abs((int(nm[k]['year_month'][:4])*12+int(nm[k]['year_month'][5:7]))-(int(b[:4])*12+int(b[5:7])))<=2 for k,b in zip(('k5 name nov','k6 name feb','k7 name mar'),brm)),str)
# fix 1 + 3: warning line direct label, current value, goal; labels at their own heights
chk('fix 1: warning line label at the line end = warehouse value of the latest month','8.4%',nm['k2 end warn']['lab'].replace(NB,''))
chk('fix 1: late-rate label at the line end = warehouse latest rate','6.3%',nm['k1 end late']['lab'].replace(NB,''))
chk('fix 1: warning line label height = line end height','True',f(nm['k2 end warn']['value'])==t2[max(t2)],str)
chk('fix 1: warning line text on the chart','warning line: / varies by month',nm['k3 warn a']['lab']+' / '+nm['k4 warn b']['lab'])
first6=[(r[2],r[1]) for r in m[:6]]; AL=[mm[i][2] for i in range(6)]
chk('fix 1: "varies by month, higher early on": all of the first 6 warning lines are above the latest (8.4%)','True',all(a>alarm for a in AL),str)
chk('fix 1: ... because those months had fewer orders than the latest month','True',all(r[1]<last[1] for r in m[:6]),str)
chk('fix 1: the gray warning line is a solid line, not dashed (varies by month)','solid','dashed' if re.search(r"line-pattern[^>]*dashed",open(TW+'/out_v4_six_chart.twb',encoding='utf8').read().replace('&apos;',"'")) else 'solid')
chk('fix 3: end labels (8.4%, 6.3%) are 1 month right of the last data month, goal label is a reference-line label','2018-09 / 2018-09',nm['k2 end warn']['year_month']+' / '+nm['k1 end late']['year_month'])
chk('fix 3: heights of end labels differ by at least 1.5 points (no overlap)','True',abs(f(nm['k2 end warn']['value'])-f(nm['k1 end late']['value']))>=0.015,str)

# ---- seller groups, independent of prep3: seller attributes from dim_seller / order counts
con.execute("""create temp table sl as select s.seller_id,count(*) orders,sum((hl is true and is_late)::int) lalh,count(distinct case when hl is true and is_late then ym end) lm from b s join marts.dim_seller d on d.seller_id=s.seller_id group by 1""")
tl=q("select sum(lalh),count(*) filter(where lalh>0) from sl")[0]
chk('late orders that were shipped late (1,809)','1,809',tl[0],N); chk('sellers with at least one (583)','583',tl[1],N)
G=list(csv.DictReader(open(DATA+'/seller_groups.csv')))
g=lambda kind:{r['grp']:r for r in G if r['kind']==kind}
rep=q("select count(*) filter(where lm>=3),sum(lalh) filter(where lm>=3),count(*) filter(where lm between 1 and 2),sum(lalh) filter(where lm between 1 and 2) from sl")[0]
chk('repeat: sellers in 3+ months','117',rep[0],N); chk('repeat: their share of 1,809','56%',rep[1]/tl[0],P0); chk('repeat: share of the 583 sellers','20%',rep[0]/tl[1],P0)
chk('repeat: one-off sellers','466',rep[2],N); chk('repeat: one-off late orders','791',rep[3],N)
sz=q("select case when orders<20 then 'S' when orders<100 then 'M' else 'L' end,count(*) filter(where lalh>0),sum(lalh) from sl group by 1 order by 1")
szd={r[0]:r for r in sz}
chk('size: large sellers behind these orders','148',szd['L'][1],N); chk('size: large share of 1,809','53%',szd['L'][2]/tl[0],P0); chk('size: large share of the 583 sellers','25%',szd['L'][1]/tl[1],P0)
chk('size: mid late orders','519',szd['M'][2],N); chk('size: small late orders','339',szd['S'][2],N)
st=q("select d.state,count(distinct s.seller_id) filter(where lalh>0),sum(lalh) from sl s join marts.dim_seller d using(seller_id) group by 1 order by 3 desc limit 5")
chk('state: top 5 by late-shipped late orders','SP,PR,MG,MA,RJ',','.join(r[0] for r in st))
chk('state: SP share of 1,809','72%',st[0][2]/tl[0],P0); chk('state: SP share of the 583 sellers','68%',st[0][1]/tl[1],P0)
chk('state: SP sellers','394',st[0][1],N)
gcsv=lambda kind,pre:[r for r in G if r['kind']==kind and r['grp'].startswith(pre)][0]
chk('seller_groups.csv: large late orders (CSV vs warehouse)',szd['L'][2],int(gcsv('size','Large')['late_shipped_late_orders']),lambda x:x)
chk('seller_groups.csv: SP late orders (CSV vs warehouse)',st[0][2],int(gcsv('state','State SP')['late_shipped_late_orders']),lambda x:x)
chk('seller_groups.csv: many-months late orders (CSV vs warehouse)',rep[1],int(gcsv('repeat','Many')['late_shipped_late_orders']),lambda x:x)
# the order-level CSV must carry the same totals the bars sum
oo=duckdb.connect(); oo.execute("create table o as select * from read_csv('%s/orders.csv',header=true,all_varchar=true)"%DATA)
chk('orders.csv rows','94,931',oo.execute("select count(*) from o").fetchone()[0],N)
chk('orders.csv sum lalh_n','1,809',oo.execute("select sum(cast(lalh_n as int)) from o").fetchone()[0],N)
for col in ('seller_size','seller_state','seller_repeat'):
    chk('orders.csv %s bars add to 1,809'%col,'1,809',oo.execute("select sum(s) from (select sum(cast(lalh_n as int)) s from o where seller_in_scope='true' group by %s)"%col).fetchone()[0],N)
# months chart: bar labels with year (tag_m / tag_y / tag_n from orders.csv)
PADS="chr(160),'')"
tg=oo.execute("select year_month,max(replace(replace(tag_m,chr(160),''),chr(12644),'')),sum(cast(late_tag_n as int)) from o where tag_m<>'' group by 1 order by 1").fetchall()
chk('fix 2: months chart bar labels (month year, count = sum of the filterable late_tag_n), 4 tagged bars','Nov 2017 902 / Feb 2018 925 / Mar 2018 1,324 / Aug 2018 393',' / '.join('%s %s'%(a[1],N(a[2])) for a in tg))
wcnt={r[0]:r[2] for r in m}
chk('fix 2: bar label counts = warehouse late orders of those months','902 / 925 / 1,324 / 393',' / '.join(N(wcnt[a[0]]) for a in tg))
chk('fix 2: bar labels follow the click filters (label is a sum, not typed text)','late_tag_n sum','late_tag_n sum' if "('late_tag_n','sum')" in open(TW+'/out_v4_six_chart.twb',encoding='utf8').read().replace('&apos;',"'") or 'sum:late_tag_n' in open(TW+'/out_v4_six_chart.twb',encoding='utf8').read() else 'typed text')
chk('fix 2: bar label month and year = warehouse month','Nov 2017,Feb 2018,Mar 2018,Aug 2018',','.join(mname(a[0]) for a in tg))
chk('fix 2: bar label month and year as drawn','Nov 2017,Feb 2018,Mar 2018,Aug 2018',','.join(a[1] for a in tg))
# repeat-seller panel as drawn (labels come from orders.csv seller_repeat)
rl=oo.execute("select seller_repeat,count(distinct seller_code) filter(where lalh_n='1'),sum(cast(lalh_n as int)) from o where seller_in_scope='true' group by 1 order by 3 desc").fetchall()
chk('repeat panel: bar labels as drawn','Shipped late in 3 or more months: 117 sellers / Shipped late in 1 to 2 months: 466 sellers',' / '.join(r[0] for r in rl))
chk('repeat panel: bar values as drawn (late orders that were shipped late)','1,018 / 791',' / '.join(N(r[2]) for r in rl))
chk('repeat panel: sellers in each bar as counted in orders.csv (the numbers in the labels)','117 / 466',' / '.join(N(r[1]) for r in rl))
chk('repeat panel: the two bars add up to all 1,809','1,809',N(sum(r[2] for r in rl)))
chk('repeat panel: 1,018 of 1,809 and 791 of 1,809 (warehouse)','1,018 / 791',N(rep[1])+' / '+N(rep[3]))
# ---- header, tile 1, panel 1, panel 3 and panel 6 subtitles: counts recomputed from the warehouse where the base table allows,
# the rest read from summary.csv (verification/verify_dash_exports.py ties every summary.csv value to the warehouse and facts.json)
nlate=q("select sum(is_late::int) from b")[0][0]
P2=lambda x:'%.2f%%'%(f(x)*100)
chk('header: delivered orders','94,931',tot[0],N); chk('header: late orders','6,518',nlate,N); chk('header: late rate','6.87%',nlate/tot[0],P2)
chk('panel 3: orders shipped after the ship-by date','8,530',hl[1][1],N); chk('panel 3: of those, arrived late','1,809',hl[1][2],N)
chk('tile 1: range low (summary.csv)','2,880',S['extra_range_low_rounded'],N); chk('tile 1: range high (summary.csv)','3,350',S['extra_range_high_rounded'],N)
chk('tile 1: all 1-2 star reviews (summary.csv)','11,635',S['bad_reviews_all'],N); chk('tile 1: share of them (summary.csv)','26.7%',S['extra_share_of_bad_reviews'],P1)
chk('panel 1: share up to the promised day (summary.csv)','8.7%',S['ramp_share_up_to_promised_day'],P1); chk('panel 1: share from day 6 (summary.csv)','78%',S['ramp_share_from_day_6'],P0)
chk('panel 1: points per late day (summary.csv)','11','%d'%round(f(S['ramp_points_per_day'])*100))
chk('panel 6: worst 3 months share of orders (summary.csv)','21.7%',S['worst3_share_of_orders'],P1); chk('panel 6: share of months (summary.csv)','15%',S['worst3_share_of_months'],P0)
RL=sorted(r['lab'] for r in csv.DictReader(open(DATA+'/ramp_b.csv',encoding='utf8')) if r['lab'])
chk('panel 1: ramp labels as drawn (ramp_b.csv)',' / '.join(sorted(['8.7% up to the promised day','+11 points per late day','\u224878% from day 6'])),' / '.join(RL))
RB_=list(csv.DictReader(open(DATA+'/ramp_b.csv',encoding='utf8')))
chk('panel 1: line unbroken (day 0 and day 5 bridge rows repeat the next phase)','climbing@0 levelled@5',' '.join('%s@%s'%(r['phase'],r['days_past_promise_capped']) for r in RB_ if (r['days_past_promise_capped'],r['phase']) in (('0','climbing'),('5','levelled'))))
# ---- text on the workbooks
need={'out_v4_six_chart':['Goal 4.4%','What-if, not a result: if late-shipped orders were late as rarely as the rest, the rate would be 3.4%.','ABOVE GOAL','under the warning line (8.4%)','gray line = warning line, set for each month','dots = months past it',
      '117 sellers (20% of the 583) shipped late in 3 or more months and account for 56% of the 1,809 late orders that were shipped late','Late rate sits above the 4.4% goal; Nov 2017, Feb 2018 and Mar 2018 went past the warning line',
      '48.3% of late orders came in 3 months: Nov 2017, Feb 2018 and Mar 2018','North and northeast run 12.2% late vs 6.2% elsewhere','Aug 2018 late rate, 1.9 points over the 4.4% goal',
      'Not a target list: these sellers were not late more often afterward',
      '94,931 delivered orders','6,518 late (6.87%)','range 2,880 to 3,350','26.7% of all 11,635 1-2 star reviews','8.7% are 1-2 stars up to the promised day, about 78% from day 6 late',
      '1,809 of 8,530 arrived late','27.8% of all 6,518 late orders','those 3 months held 21.7% of all orders (15% of months)','Next step (nothing launched yet)',
      'Per-order delivery-date model: not adopted yet. Keep building it; launch only once checkout conversion by promised days and a second peak season show the longer date is worth it.',
      'No seller penalty list: sellers flagged for repeated late shipping were not late more often afterward.']}
for wb,ts in need.items():
    p=TW+'/%s.twb'%wb
    assert os.path.exists(p),p
    x=open(p,encoding='utf8').read().replace('&apos;',"'")
    for t in ts: chk('%s text: %s'%(wb,t[:46]),'present','present' if t in x else 'MISSING')
# wording retired with the old recommendations (seller ship-by reminders, buffer days, "fixable cause") must be gone too
OLD_REC=['Two fixes to test','Remind sellers','ship-by date. We','buffer days','fixable cause','test next']
bad=[w for w in ['handoff gap','Handed','alarm line','e.g.','EXAMPLE','invented']+OLD_REC if any(w.lower() in re.sub(r'c Alarm line','',open(p,encoding='utf8').read()).lower() for p in [TW+'/out_v4_six_chart.twb'])]
chk('old/invented wording absent from every workbook','none',','.join(bad) or 'none')
w=max(len(r[0]) for r in rows)
print('%-*s | %-30s | %-30s | %s'%(w,'item','on image / csv','warehouse','result'))
for r in rows: print('%-*s | %-30s | %-30s | %s'%(w,*r))
bad_=[r for r in rows if r[3]!='OK']; print('\n%d checks, %d mismatches'%(len(rows),len(bad_))); sys.exit(1 if bad_ else 0)
