#!/usr/bin/env python3
"""prep.py <repo dashboard/data dir> <out dir>   (writes ramp_b.csv and monthly_long.csv for the Tableau workbook)
Reshape/label step. Reads ONLY the committed dashboard CSVs. Writes the small helper CSVs Tableau reads next to
them. Numeric columns are copied unchanged; the only things made here are (a) a long (series, value) copy of the
monthly lines, (b) text labels formatted from the CSV values."""
import csv,sys,os
src,out=sys.argv[1:3]; os.makedirs(out,exist_ok=True)
def rd(n): return list(csv.DictReader(open(os.path.join(src,n+'.csv'))))
def wr(n,rows,cols=None):
    cols=cols or list(rows[0].keys())
    with open(os.path.join(out,n+'.csv'),'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,lineterminator='\n'); w.writeheader(); w.writerows(rows)
S=rd('summary')[0]; F=lambda k: float(S[k])
p1=lambda x:'%.1f%%'%(float(x)*100); p2=lambda x:'%.2f%%'%(float(x)*100); p0=lambda x:'%.0f%%'%(float(x)*100)
M=rd('monthly'); first,last=M[0]['month_label'],M[-1]['month_label']
# ---- ramp + labels
R=rd('review_ramp')
labs={'-15':'%s up to the promised day'%p1(F('ramp_share_up_to_promised_day')),'3':'+%d points per late day'%round(F('ramp_points_per_day')*100),'18':'≈%s from day 6'%p0(F('ramp_share_from_day_6'))}
RB=[]
for r in R:
    r=dict(r); r['lab']=''; RB.append(r)
    if r['days_past_promise_capped'] in labs:
        r2=dict(r); r2['phase']='label'; r2['lab']=labs[r['days_past_promise_capped']]; RB.append(r2)
wr('ramp_b',RB)
# ---- monthly long: same numbers, one row per (month, series)
rows=[]
SER=[('Late rate','late_rate'),('Alarm line (month own size)','own_month_alarm_line_late_rate'),('Goal','goal_late_rate'),('Stretch (what-if)','stretch_whatif_late_rate')]
REF=os.environ.get('REF')=='1'
RN={'Stretch (what-if)':'a Stretch','Stretch label':'d Stretch label','Goal':'b Goal','Goal label':'d Goal label','Alarm line (month own size)':'c Alarm line','Alarm label':'d Alarm label','Alarm month':'e Alarm month','Month label':'d Month label','Latest month':'f Latest month','Late rate':'g Late rate'}
def add(m,i,series,col,lab='',off=0.0):
    rows.append(dict(goal_c=F('goal_late_rate'),stretch_c=F('stretch_whatif_late_rate'),year_month=m['year_month'],month_start=m['month_start'],month_label=m['month_label'],month_idx=i+1,series=RN.get(series,series),value=float(m[col])+off,lab=lab,is_thin_month=m['is_thin_month'],orders=m['orders'],late_orders=m['late_orders']))
for i,m in enumerate(M):
    for name,col in SER:
        if REF and name in ('Goal','Stretch (what-if)'): continue
        add(m,i,name,col)
    if m['is_alarm_month']=='true':
        add(m,i,'Alarm month','late_rate','\u2003'*{'2017-11':1,'2018-02':2,'2018-03':3}.get(m['year_month'],4))
        add(m,i,'Month label','late_rate',m['month_label'].split()[0],{'2017-11':0.028,'2018-02':0.0,'2018-03':0.0}.get(m['year_month'],0.0))
    if m['year_month']==M[-1]['year_month']: add(m,i,'Latest month','late_rate','%s %s'%(m['month_label'],p1(m['late_rate'])))
    if m['year_month']=='2018-05': add(m,i,'Alarm label','own_month_alarm_line_late_rate','warning line %s'%p1(F('latest_month_own_alarm_line_late_rate')),0.03)
    if (not REF) and m['year_month']=='2017-02': add(m,i,'Goal label','goal_late_rate','Goal %s\n(a typical\nsteady month)'%p1(m['goal_late_rate']),0.003)
    if (not REF) and m['year_month']=='2018-01': add(m,i,'Stretch label','stretch_whatif_late_rate','If no seller shipped late: %s'%p1(m['stretch_whatif_late_rate']))
wr('monthly_long',rows)
