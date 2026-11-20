#!/usr/bin/env python3
"""prep4.py <prep3 out dir> <out dir>  (default data3 data4)  six-chart page, step 2. Copies the prep3.py CSVs and adds only what the four reader fixes need.
  orders.csv  + tag_m / tag_y / tag_n : month, year and late-order count text for the tagged bars of the months chart
                (read from year_month and the orders' own late_n; left/right padding with no-break spaces only nudges the Feb and Mar labels apart)
  trend_e.csv trend_b.csv (late rate + warning line, checked against the warehouse) with the three past-warning dots as label series
                ('e Breach n', one centred dot character per month: it sits exactly on the line point) plus label-only series
                ('k ...': value is only the height the text is drawn at; month is only where it is drawn)
Every figure printed on the chart is read from trend_b.csv / orders.csv; nothing is typed."""
import csv,os,shutil,sys,collections
src,out=('data3','data4') if len(sys.argv)<3 else sys.argv[1:3]
E_=os.environ.get
NB=E_('PADCH','\u00a0')
os.makedirs(out,exist_ok=True)
for f in os.listdir(src):
    if f not in ('orders.csv',): shutil.copy(os.path.join(src,f),os.path.join(out,f))
MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
mname=lambda ym:'%s %s'%(MON[int(ym[5:7])-1],ym[:4])
# ---------------- orders: tag text
rd=list(csv.DictReader(open(os.path.join(src,'orders.csv'),encoding='utf-8')))
late=collections.Counter()
for r in rd:
    if r['month_tag']: late[r['year_month']]+=int(r['late_n'])
PM=int(E_('PADM','17')); PMF=int(E_('PADM_FEB','34')); PN=int(E_('PADN','3'))
def tag(ym,txt,k):
    # Feb label shifts left and Mar label shifts right (no-break spaces) so 'Feb 2018' and '1,324' stop colliding
    return (NB*k if ym=='2018-03' else '')+txt+(E_('FEBCH','\u3164')*(int(E_('FEBN','4')) if k==PM else 0) if ym=='2018-02' else '')+(E_('FEBCH','\u3164')*int(E_('NOVN','4')) if ym=='2017-11' and k==PM else '')
REN={'Many months (3 or more): 117 sellers':'Shipped late in 3 or more months: 117 sellers','Few months (1 to 2): 466 sellers':'Shipped late in 1 to 2 months: 466 sellers'}
for r in rd: r['seller_repeat']=REN.get(r['seller_repeat'],r['seller_repeat'])
cols=list(rd[0].keys())+['tag_m','tag_y','tag_n']
with open(os.path.join(out,'orders.csv'),'w',newline='',encoding='utf-8') as f:
    w=csv.writer(f,lineterminator='\n'); w.writerow(cols)
    for r in rd:
        t=bool(r['month_tag']); ym=r['year_month']
        w.writerow([r[c] for c in cols[:-3]]+([tag(ym,mname(ym),PM),ym[:4],tag(ym,format(late[ym],','),PN)] if t else ['','','']))
# ---------------- trend
T=list(csv.DictReader(open(os.path.join(src,'trend_b.csv'))))
bym={}
for r in T:
    if r['series'] in('g Late rate','c Alarm line'): bym.setdefault(r['year_month'],{})[r['series']]=float(r['value'])
breach=sorted({r['year_month'] for r in T if r['series'].startswith('e Breach')})
last=max(bym); pct=lambda x:'%.1f%%'%(x*100)
nextm=lambda ym,k:'%04d-%02d'%divmod(int(ym[:4])*12+int(ym[5:7])-1+k,12)[::1] if False else '%04d-%02d'%((int(ym[:4])*12+int(ym[5:7])-1+k)//12,(int(ym[:4])*12+int(ym[5:7])-1+k)%12+1)
cols2=['year_month','month_start','month_idx','series','value','lab','orders','late_orders','kind']
rows=[]
for r in T:
    if r['series'].startswith('e Breach') or r['series']=='f Latest month': continue
    rows.append(dict(r,lab='',kind='data'))
ordl={r['year_month']:(r['orders'],r['late_orders']) for r in T if r['series']=='g Late rate'}
def lab(series,ym,y,text,kind='label'):
    o,l=ordl.get(ym,('',''))
    rows.append(dict(year_month=ym,month_start=ym+'-01',month_idx=0,series=series,value=y,lab=text,orders=o,late_orders=l,kind=kind))
for i,ym in enumerate(breach,1): lab('e Breach %d'%i,ym,bym[ym]['g Late rate'],'\u25cf','dot')
lab('f Latest month',last,bym[last]['g Late rate'],'','dot')
# right-margin end labels (one month right of the last point), warning line text under the gray line, month names beside the dots
R_=lambda k,d:float(E_(k,d))
lab('k1 end late',nextm(last,int(E_('END_DX','1'))),bym[last]['g Late rate'],NB*int(E_('END_PAD','0'))+pct(bym[last]['g Late rate']))
lab('k2 end warn',nextm(last,int(E_('END_DX','1'))),bym[last]['c Alarm line'],NB*int(E_('END_PAD','0'))+pct(bym[last]['c Alarm line']))
wm=E_('WARN_MONTH','2017-07'); wy=bym[wm]['c Alarm line']
lab('k3 warn a',wm,wy-R_('WARN_DY1','0.015'),E_('WARN_T1','warning line:'))
lab('k4 warn b',wm,wy-R_('WARN_DY2','0.033'),E_('WARN_T2','varies by month'))
NM={'2017-11':('0','%+.3f'%R_('NOV_DY','0.0'),'-2'),}
nov,feb,mar=breach
lab('k5 name nov',nextm(nov,-int(E_('NOV_DX','2'))),bym[nov]['g Late rate']+R_('NOV_DY','0.0'),mname(nov))
lab('k6 name feb',nextm(feb,-int(E_('FEB_DX','2'))),bym[feb]['g Late rate']+R_('FEB_DY','0.008'),mname(feb))
lab('k7 name mar',nextm(mar,int(E_('MAR_DX','1'))),bym[mar]['g Late rate']+R_('MAR_DY','-0.012'),NB*int(E_('MAR_PAD','14'))+mname(mar))
rows.sort(key=lambda d:(d['series'],d['year_month']))
with open(os.path.join(out,'trend_e.csv'),'w',newline='',encoding='utf-8') as f:
    w=csv.writer(f,lineterminator='\n'); w.writerow(cols2); [w.writerow([d[c] for c in cols2]) for d in rows]
print('trend_e rows',len(rows),'breach',breach,'last',last,'orders rows',len(rd))
