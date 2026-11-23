#!/usr/bin/env python3
"""gen_workbook.py <data dir to read headers from> <data dir as Tableau will see it> <out.twb>

Builds the Tableau workbook XML for the late-delivery dashboard (layout B1, version 2). The workbook head comes from
ctrl_saved_desktop_free.twb in this folder, a workbook saved by Tableau Desktop (hand-written workbooks do not open).
Both data dirs hold orders.csv, ramp_b.csv, monthly_long.csv, summary.csv. The second path is
written into the workbook as the folder Tableau reads the CSVs from.

Settings (environment variables):
  VAR=b1|b2   top band: b1 = three KPI tiles (shipped), b2 = one-line strip
  TR=1|''     goal and stretch as parameter-driven reference lines (shipped); '' = old data lines
  GSZ, SSZ, PAT  goal line size (4), stretch line size (1), stretch pattern (dashed); only with TR=1
  FILT=col=value  build a copy filtered to that value (used for tests)
  ONLY=a|b    build only the named worksheets
  TIPV=a|b|off  Trend tooltip variant
  X=...       test switches (NODF, NORUNS, NOITAL)
  OPT         read but has no effect
"""
import re,sys,os,csv,uuid,hashlib
from xml.sax.saxutils import escape,quoteattr
boxdata,macdata,out=sys.argv[1:4]
OPT=set(os.environ.get('OPT','').split(','))
here=os.path.dirname(os.path.abspath(__file__))
ctrl=open(os.path.join(here,'ctrl_saved_desktop_free.twb')).read()
HEAD=ctrl[:ctrl.index('<datasources>')]
HEAD=re.sub(r" _\.fcp\.WorkbookFingerprinting\.true\.\.\.[a-z-]+='[^']*'",'',HEAD)
HEAD=HEAD.replace("    <_.fcp.WorkbookFingerprinting.true...WorkbookFingerprinting />\n",'')
def uid(s): return '{'+str(uuid.UUID(hashlib.md5(s.encode()).hexdigest())).upper()+'}'
def h32(s): return hashlib.md5(s.encode()).hexdigest().upper()
def q(s): return escape(s,{"'":'&apos;','"':'&quot;'})
OR='#D55E00'; BL='#0072B2'; LBL='#9DC8E6'; GR='#B3B3B3'; DG='#555555'; TX='#222222'
# ---------------------------------------------------------------- datasources
OVERRIDE={'days_past_promise_capped':('dimension','quantitative'),'month_idx':('dimension','quantitative')}
class DS:
    def __init__(s,key,caption,csvname,calcs=(),dfmt=None):
        s.dfmt=dfmt or {}; s.pal={}; s.key=key; s.caption=caption; s.csv=csvname
        s.name='federated.'+h32(key)[:26].lower(); s.conn='textscan.'+h32(key+'c')[:26].lower()
        rows=list(csv.reader(open(os.path.join(boxdata,csvname),encoding='utf-8')))
        hdr=rows[0]; data=rows[1:]; s.cols=[]
        for i,c in enumerate(hdr):
            vals=[r[i] for r in data if r[i]!='']
            def isint(v):
                try: int(v); return True
                except: return False
            def isfl(v):
                try: float(v); return True
                except: return False
            import re as _re
            t='date' if vals and all(_re.fullmatch(r'\d{4}-\d{2}-\d{2}',v) for v in vals) else 'integer' if vals and all(isint(v) for v in vals) else 'real' if vals and all(isfl(v) for v in vals) else 'string'
            s.cols.append((c,t))
        s.types=dict(s.cols); s.calcs=list(calcs)  # (name, caption, formula)
    def cap(s,c): return c.replace('_',' ').title()
    def role(s,c):
        if c in OVERRIDE: return OVERRIDE[c]
        t=s.types[c]
        if t=='date': return ('dimension','ordinal')
        return ('dimension','nominal') if t=='string' else ('measure','quantitative')
    def inst(s,c,kind):
        if kind=='nk': return '[none:%s:nk]'%c
        if kind=='qk': return '[none:%s:qk]'%c
        if kind=='sum': return '[sum:%s:qk]'%c
        if kind=='tmn': return '[tmn:%s:qk]'%c
        if kind=='avg': return '[avg:%s:qk]'%c
        if kind=='cnt': return '[cnt:%s:qk]'%c
        raise ValueError(kind)
    def q(s,c,kind): return '[%s].%s'%(s.name,s.inst(c,kind))
    def xml(s):
        obj='%s_%s'%(s.csv,h32(s.csv+s.key))
        L=[]; A=L.append
        A("    <datasource caption=%s inline='true' name='%s' version='18.1'>"%(quoteattr(s.caption),s.name))
        A("      <connection class='federated'>")
        A("        <named-connections>")
        A("          <named-connection caption=%s name='%s'>"%(quoteattr(s.caption),s.conn))
        A("            <connection class='textscan' directory=%s filename=%s password='' server='' />"%(quoteattr(macdata),quoteattr(s.csv)))
        A("          </named-connection>\n        </named-connections>")
        tbl='[%s]'%s.csv.replace('.','#')
        A("        <relation connection='%s' name=%s table=%s type='table'>"%(s.conn,quoteattr(s.csv),quoteattr(tbl)))
        A("          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>")
        for i,(c,t) in enumerate(s.cols): A("            <column datatype='%s' name=%s ordinal='%d' />"%(t,quoteattr(c),i))
        A("          </columns>\n        </relation>")
        A("        <metadata-records>")
        A("""          <metadata-record class='capability'>
            <remote-name />
            <remote-type>0</remote-type>
            <parent-name>[%s]</parent-name>
            <remote-alias />
            <aggregation>Count</aggregation>
            <contains-null>true</contains-null>
            <attributes>
              <attribute datatype='string' name='character-set'>&quot;UTF-8&quot;</attribute>
              <attribute datatype='string' name='collation'>&quot;en_US&quot;</attribute>
              <attribute datatype='string' name='field-delimiter'>&quot;,&quot;</attribute>
              <attribute datatype='string' name='header-row'>&quot;true&quot;</attribute>
              <attribute datatype='string' name='locale'>&quot;en_US&quot;</attribute>
              <attribute datatype='string' name='single-char'>&quot;&quot;</attribute>
            </attributes>
          </metadata-record>"""%s.csv)
        RT={'string':129,'integer':20,'real':5,'date':133}
        for i,(c,t) in enumerate(s.cols):
            A("          <metadata-record class='column'>")
            A("            <remote-name>%s</remote-name>\n            <remote-type>%d</remote-type>\n            <local-name>[%s]</local-name>\n            <parent-name>[%s]</parent-name>"%(q(c),RT[t],c,s.csv))
            A("            <remote-alias>%s</remote-alias>\n            <ordinal>%d</ordinal>\n            <local-type>%s</local-type>"%(q(c),i,t))
            A("            <aggregation>%s</aggregation>"%('Count' if t in ('string','date') else 'Sum'))
            if t=='string': A("            <scale>1</scale>\n            <width>1073741823</width>")
            A("            <contains-null>true</contains-null>")
            if t=='string': A("            <collation flag='0' name='LEN_RUS' />")
            A("            <object-id>[%s]</object-id>\n          </metadata-record>"%obj)
        A("        </metadata-records>\n      </connection>\n      <aliases enabled='yes' />")
        A("      <column caption=%s datatype='table' name='[__tableau_internal_object_id__].[%s]' role='measure' type='quantitative' />"%(quoteattr(s.csv),obj))
        for c,t in sorted(s.cols,key=lambda x:s.cap(x[0])):
            ro,ty=s.role(c); A("      <column caption=%s datatype='%s'%s name='[%s]' role='%s' type='%s' />"%(quoteattr(s.cap(c)),t,(" default-format='%s'"%s.dfmt[c] if c in s.dfmt else ''),c,ro,ty))
        for nm,cap,fm,dt in s.calcs:
            A("      <column caption=%s datatype='%s' name='[%s]' role='dimension' type='nominal'>\n        <calculation class='tableau' formula=%s />\n      </column>"%(quoteattr(cap),dt,nm,quoteattr(fm)))
        for fld in s.pal:
            m_=re.fullmatch(r'\[none:(.+):nk\]',fld); A("      <column-instance column='[%s]' derivation='None' name='%s' pivot='key' type='nominal' />"%(m_.group(1),fld))
        A("      <layout dim-ordering='alphabetic' measure-ordering='alphabetic' show-structure='true' />")
        if s.pal:
            A("      <style>\n        <style-rule element='mark'>")
            for fld,(mp,bq) in s.pal.items():
                A("          <encoding attr='color' field='%s' type='palette'>"%fld)
                for k,c in mp: A("            <map to='%s'>\n              <bucket>%s</bucket>\n            </map>"%(c,q('"%s"'%k if bq else k)))
                A("          </encoding>")
            A("        </style-rule>\n      </style>")
        A("      <semantic-values>\n        <semantic-value key='[Country].[Name]' value='&quot;United States&quot;' />\n      </semantic-values>")
        A("      <object-graph>\n        <objects>\n          <object caption=%s id='%s'>\n            <properties context=''>"%(quoteattr(s.csv),obj))
        A("              <relation connection='%s' name=%s table=%s type='table'>"%(s.conn,quoteattr(s.csv),quoteattr(tbl)))
        A("                <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>")
        for i,(c,t) in enumerate(s.cols): A("                  <column datatype='%s' name=%s ordinal='%d' />"%(t,quoteattr(c),i))
        A("                </columns>\n              </relation>\n            </properties>\n          </object>\n        </objects>\n      </object-graph>\n    </datasource>")
        return '\n'.join(L)+'\n'
    def dep(s,uses):
        """uses: list of (col,kind). returns <datasource-dependencies> block"""
        cols={}; insts=[]
        for c,k in uses:
            if (c,k) in insts: continue
            insts.append((c,k)); cols[c]=1
        L=["          <datasource-dependencies datasource='%s'>"%s.name]
        cn={c for c,_ in s.cols}
        for c in sorted(cols,key=lambda c:(c.lower())):
            if c in cn:
                ro,ty=s.role(c); L.append("            <column caption=%s datatype='%s'%s name='[%s]' role='%s' type='%s' />"%(quoteattr(s.cap(c)),s.types[c],(" default-format='%s'"%s.dfmt[c] if c in s.dfmt else ''),c,ro,ty))
            else:
                nm,cap,fm,dt=[x for x in s.calcs if x[0]==c][0]
                L.append("            <column caption=%s datatype='%s' name='[%s]' role='dimension' type='nominal'>\n              <calculation class='tableau' formula=%s />\n            </column>"%(quoteattr(cap),dt,c,quoteattr(fm)))
        for c,k in insts:
            if k=='nk': L.append("            <column-instance column='[%s]' derivation='None' name='[none:%s:nk]' pivot='key' type='nominal' />"%(c,c))
            elif k=='qk': L.append("            <column-instance column='[%s]' derivation='None' name='[none:%s:qk]' pivot='key' type='quantitative' />"%(c,c))
            elif k=='tmn': L.append("            <column-instance column='[%s]' derivation='Month-Trunc' name='[tmn:%s:qk]' pivot='key' type='quantitative' />"%(c,c))
            elif k=='cnt': L.append("            <column-instance column='[%s]' derivation='Count' name='[cnt:%s:qk]' pivot='key' type='quantitative' />"%(c,c))
            elif k=='avg': L.append("            <column-instance column='[%s]' derivation='Avg' name='[avg:%s:qk]' pivot='key' type='quantitative' />"%(c,c))
            elif k=='sum': L.append("            <column-instance column='[%s]' derivation='Sum' name='[sum:%s:qk]' pivot='key' type='quantitative' />"%(c,c))
        L.append("          </datasource-dependencies>")
        return '\n'.join(L)+'\n'
# ---------------------------------------------------------------- worksheet builder
WS=[]; USED=set()
ONLY=set(x for x in os.environ.get('ONLY','').split('|') if x)
def fmt(attr,value,field=None,scope=None,id=None):
    return "<format attr='%s'%s%s%s value=%s />"%(attr,(" field='%s'"%field if field else ''),(" id='%s'"%id if id else ''),(" scope='%s'"%scope if scope else ''),quoteattr(str(value)))
def rule(el,*items): return "          <style-rule element='%s'>\n%s\n          </style-rule>\n"%(el,'\n'.join('            '+i for i in items))
def palette(field,mapping,bq=True):
    return "            <encoding attr='color' field='%s' type='palette'>\n%s\n            </encoding>"%(field,'\n'.join("              <map to='%s'><bucket>%s</bucket></map>"%(c,q('"%s"'%k if bq else k)) for k,c in mapping))
def worksheet(name,d,uses=None,mark='Automatic',rows='',cols='',color=None,text=None,palette_map=None,runs=None,
              labels=True,filt=None,sort=None,extra_rules='',plain=True,pane_color=None,hide_axes=(),extra_uses=None,
              pct=(),axis_titles=None,header_w=None,header_font=None,dual=None,label_pos=None,xrange=None,palette_where='ds',bucket_q=True,pct_el='axis',pct_scope=None,cell_rules=(),tile_rules='',cell_w=None,hide_hdr=(),yfix=None,xspace=None,datefmt=None,header_h=(),datefmts=(),reflines=(),size=None,tip=None):
    uses=list(uses or [])+list(extra_uses or [])
    dsq=lambda c,k: d.q(c,k)
    enc=[]
    if color: enc.append("              <color column='%s' />"%dsq(*color)); uses.append(color)
    if size: enc.append("              <size column='%s' />"%dsq(*size)); uses.append(size)
    for t in (text if isinstance(text,list) else ([text] if text else [])):
        enc.append("              <text column='%s' />"%dsq(*t)); uses.append(t)
    tipx=''
    if tip:
        tr=[]
        for it in tip:
            if isinstance(it,str):
                for j,part in enumerate(it.split('\n')):
                    if j: tr.append("                <run>Æ&#10;</run>")
                    if part: tr.append("                <run>%s</run>"%q(part))
            else:
                enc.append("              <tooltip column='%s' />"%dsq(*it)); uses.append(it)
                tr.append("                <run bold='true'>%s</run>"%q('<'+dsq(*it)+'>'))
        tipx="            <customized-tooltip>\n              <formatted-text>\n"+'\n'.join(tr)+"\n              </formatted-text>\n            </customized-tooltip>\n"
    for ru in (runs or []):
        if ru[0]: uses.append(ru[0])
    if color and palette_map and palette_where=='ds': d.pal[d.inst(*color)]=(palette_map,bucket_q)
    if cell_w: cell_rules=list(cell_rules)+[('cell','width',cell_w,None)]
    # ---- pane-level style (mark colours, labels)
    mk=[]
    if pane_color: mk.append(fmt('mark-color',pane_color))
    if labels and (text or runs): mk.append(fmt('mark-labels-show','true'))
    if color and palette_map and palette_where in ('pane','both'): mk.append(palette(dsq(*color),palette_map,bucket_q).strip())
    pane_style=("            <style>\n"+rule('mark',*mk).replace('          <style-rule','              <style-rule').replace('          </style-rule>','              </style-rule>')+"            </style>\n") if mk else ''
    # ---- table-level style
    rules=rule('worksheet',fmt('display-field-labels','false',scope='cols'),fmt('display-field-labels','false',scope='rows'))
    rules+=extra_rules
    if color and palette_map and palette_where in ('table','both'): rules+=rule('mark',palette(dsq(*color),palette_map,bucket_q).strip())
    for el,at,val,fld in cell_rules: rules+=rule(el,fmt(at,val,field=fld))
    if plain:
        rules+=rule('gridline',fmt('line-visibility','off',scope='cols'),fmt('line-visibility','off',scope='rows'))
        rules+=rule('zeroline',fmt('line-visibility','off',scope='cols'),fmt('line-visibility','off',scope='rows'))
    ax=[]
    if xspace:
        fld,orig_,sp,un=xspace; ax.append("<encoding attr='space' class='0' field='%s' field-type='quantitative' major-origin='%s' major-spacing='%s' major-units='%s' scope='cols' type='space' />"%(dsq(*fld),orig_,sp,un))
    if datefmt:
        rules+=rule('cell',fmt('text-format',datefmt[1],field=dsq(*datefmt[0])))
        ax.append(fmt('text-format',datefmt[1],field=dsq(*datefmt[0])))
    datefmt_field=xspace[0] if xspace else None
    for el_,val_,sc_ in datefmts:
        if el_=='axis': ax.append(fmt('text-format',val_,field=dsq(*datefmt_field),scope=sc_))
        else: rules+=rule(el_,fmt('text-format',val_,field=dsq(*datefmt_field),scope=sc_))
    refx=''
    if reflines:
        uses.extend((vc,'avg') for _,vc,*_r in reflines)
        rr_=[]
        for i_,(axc,vc,lab_,col_,size_) in enumerate(reflines):
            rr_+= [fmt('stroke-color',col_,id='refline%d'%i_),fmt('stroke-size',size_,id='refline%d'%i_),fmt('color',col_,id='refline%d'%i_),fmt('text-align',"left",id='refline%d'%i_),fmt('vertical-align','bottom',id='refline%d'%i_)]
        rules+=rule('refline',*rr_)
        refx=''.join("            <reference-line axis-column='%s' enable-instant-analytics='false' formula='average' id='refline%d' label='%s' label-type='custom' scope='per-pane' value-column='%s' z-order='%d' />\n"%(dsq(*reflines[0][0]),i_,q(l_),dsq(vc,'avg'),i_+1) for i_,(axc,vc,l_,c_,s_) in enumerate(reflines))
    for c,k in hide_axes: ax.append(fmt('display','false',field=dsq(c,k)))
    pctx=[]
    for (c,k),f in pct:
        if pct_el=='axis': ax.append(fmt('text-format',f,field=dsq(c,k),scope=pct_scope))
        else: pctx.append(rule(pct_el,fmt('text-format',f,field=dsq(c,k),scope=pct_scope)))
    rules+=''.join(pctx)
    for (c,k,sc),t in (axis_titles or {}).items(): ax.append(fmt('title',t,field=dsq(c,k),scope=sc))
    if ax: rules+=rule('axis',*ax)
    hd=[]
    if hide_hdr: rules+=rule('label',*[fmt('display','false',field=dsq(c,k)) for c,k in hide_hdr])
    if header_w: hd.append(fmt('width',header_w[1],field=dsq(*header_w[0])))
    hd+=[fmt('height',v,field=dsq(*f)) for f,v in header_h]
    if header_font: hd+= [fmt('font-size',header_font[0]),fmt('font-weight',header_font[1])]
    if hd: rules+=rule('header',*hd)
    sty="        <style>\n"+rules+"        </style>\n"
    label=''
    if runs:
        rr=[]
        for inst,size_,bold,color_ in runs:
            if inst is None: rr.append("                <run>Æ&#10;</run>"); continue
            rr.append("                <run bold='%s' fontcolor='%s' fontsize='%s'>%s</run>"%('true' if bold else 'false',color_,size_,q('<'+dsq(*inst)+'>')))
        label="            <customized-label>\n              <formatted-text>\n"+'\n'.join(rr)+"\n              </formatted-text>\n            </customized-label>\n"
    viewx=(filt or '')+(sort or '')
    encx=('            <encodings>'+chr(10)+chr(10).join(enc)+chr(10)+'            </encodings>'+chr(10)) if enc else ''
    if dual:
        v1,v2,rmax=dual   # (value inst col, flag inst col, axis max)
        uses+= [(v2,'sum')]
        panes=f"""          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Automatic' />
          </pane>
          <pane id='2' selection-relaxation-option='selection-relaxation-allow' y-axis-name='{dsq(v1,"sum")}' y-index='0'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Line' />
{encx}{refx}{tipx}{label}{pane_style}          </pane>
          <pane id='3' selection-relaxation-option='selection-relaxation-allow' y-axis-name='{dsq(v2,"sum")}' y-index='1'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Circle' />
            <style>
              <style-rule element='mark'>
                <format attr='mark-color' value='{OR}' />
              </style-rule>
            </style>
          </pane>
"""
        rows="(%s + %s)"%(dsq(v1,'sum'),dsq(v2,'sum'))
        enc2=["<encoding attr='space' class='%d' field='%s' field-type='quantitative' fold='true' max='%s' min='0' range-type='fixed' scope='rows' type='space' />"%(i,dsq(v,'sum'),rmax) for i,v in enumerate((v1,v2))]
        sty=sty.replace("        </style>\n","")+rule('axis',*enc2,fmt('display','false',field=dsq(v2,'sum')))+"        </style>\n"
    else:
        panes=f"""          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='{mark}' />
{encx}{refx}{tipx}{label}{pane_style}          </pane>
"""
    xml=f"""    <worksheet name={quoteattr(name)}>
      <table>
        <view>
          <datasources>
            <datasource caption={quoteattr(d.caption)} name='{d.name}' />
          </datasources>
{d.dep(uses)}{viewx}          <aggregation value='true' />
        </view>
{sty}        <panes>
{panes}        </panes>
        <rows>{rows}</rows>
        <cols>{cols}</cols>
      </table>
      <simple-id uuid='{uid('ws'+name)}' />
    </worksheet>
"""
    if not ONLY or name in ONLY: WS.append((name,xml)); USED.add(d.key)
    return name

# ======================================================================= Dashboard layout B (interactive)
VAR=os.environ.get('VAR','b1')             # b1 = three KPI tiles, b2 = one-line answer strip
SUM=list(csv.DictReader(open(os.path.join(boxdata,'summary.csv'))))[0]
F=lambda k: float(SUM[k])
def p0(x): return '%d%%'%round(x*100)
def p1(x): return '%.1f%%'%(x*100)
def p2(x): return '%.2f%%'%(x*100)
def n0(x): return format(int(round(float(x))),',')
ACC=OR; INK='#222222'; MID='#555555'; LIGHT='#B5B5B5'; PALE='#D0D0D0'
ORD=D_ord=DS('ord','orders','orders.csv'); D={'ord':ORD}
D['ramp']=DS('ramp','ramp_b','ramp_b.csv'); D['ml']=DS('ml','monthly_long','monthly_long.csv')
R=D['ramp']; M=D['ml']
ORD.dfmt['late']='p0.0%'; R.dfmt['bad_review_share']='p0%'; M.dfmt['value']='p0%'
def fmember(d,col,val): return "          <filter class='categorical' column='[%s].[none:%s:nk]'>\n            <groupfilter function='member' level='[none:%s:nk]' member='&quot;%s&quot;' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />\n          </filter>\n"%(d.name,col,col,val)
FILT=os.environ.get('FILT')
FILTF=tuple(FILT.split('=',1)) if FILT else None
def ows(name,d,uses=None,**k):
    if FILTF:
        k['filt']=(k.get('filt') or '')+fmember(d,FILTF[0],FILTF[1]); k['extra_uses']=list(k.get('extra_uses') or [])+[(FILTF[0],'nk')]
    return worksheet(name,d,uses,**k)
# ---- 1 cost ramp
worksheet('Review ramp',R,None,mark='Line',cols=R.q('days_past_promise_capped','qk'),rows=R.q('bad_review_share','sum'),
    extra_uses=[('days_past_promise_capped','qk'),('bad_review_share','sum')],color=('phase','nk'),text=('lab','nk'),
    palette_map=[('up to the promised day','#8C8C8C'),('climbing',INK),('levelled',INK),('label',MID)],
    axis_titles={('days_past_promise_capped','qk','cols'):'days past the promised day',('bad_review_share','sum','rows'):''})
# ---- 2 trend (company-wide, never filtered)
xk=('month_start','tmn')
TR=os.environ.get('TR','1')   # 1 = goal/stretch as parameter-driven reference lines (the final design); '' = old data lines
GOALC,STRC=('#FFFFFF00','#FFFFFF00') if TR else (MID,PALE)
PAL=[('g Late rate',INK),('c Alarm line',LIGHT),('b Goal',GOALC),('a Stretch',STRC),('e Alarm month',INK),('f Latest month',INK),('d Alarm label','#FFFFFF00'),('d Month label','#FFFFFF00'),('d Goal label','#FFFFFF00'),('d Stretch label','#FFFFFF00')]
TIPS={'off':None,'a':['Orders in the month: ',('orders','avg'),'\nLate orders in the month: ',('late_orders','avg')],'b':['Month: ',xk,'\nValue: ',('value','sum')]}
worksheet('Trend',M,[('value','sum'),xk],mark='Line',cols=M.q(*xk),rows=M.q('value','sum'),color=('series','nk'),text=('lab','nk'),palette_map=PAL,
    axis_titles={('value','sum','rows'):'',(xk[0],xk[1],'cols'):''},xspace=(xk,'#2017-01-01#','6.0','months'),datefmts=[('label','*mmm yyyy',None)],
    tip=TIPS.get(os.environ.get('TIPV','a')))
# ---- 3 why: handoff
ows('Handoff',ORD,[('has_handoff','nk')],mark='Bar',rows=ORD.q('handoff_group','nk'),cols=ORD.q('late','avg'),color=('handoff_group','nk'),text=('late','avg'),
    palette_map=[('Shipped after the ship-by date',ACC),('Shipped by the ship-by date',LIGHT)],hide_axes=[('late','avg')],extra_uses=[('late','avg'),('handoff_group','nk')],
    filt=fmember(ORD,'has_handoff','true'),header_w=(('handoff_group','nk'),215),header_font=(10,'normal'),cell_rules=[('cell','height',58,ORD.q('handoff_group','nk'))],
    tip=['Orders: ',('order_code','cnt'),'\nLate orders: ',('late_n','sum'),'\nLate rate: ',('late','avg')])
# ---- 4 who: sellers (top 10 overall)
ows('Sellers',ORD,[('is_top10','nk')],mark='Bar',rows=ORD.q('seller_label','nk'),cols=ORD.q('lalh_n','sum'),text=('lalh_n','sum'),pane_color=MID,
    hide_axes=[('lalh_n','sum')],extra_uses=[('lalh_n','sum'),('seller_label','nk')],filt=fmember(ORD,'is_top10','true'),header_w=(('seller_label','nk'),210),header_font=(11,'bold'),cell_rules=[('cell','height',15,ORD.q('seller_label','nk'))],
    tip=['Orders: ',('order_code','cnt'),'\nOrders shipped late: ',('late_handoff_n','sum'),'\nLate orders that were shipped late: ',('lalh_n','sum'),'\nLate orders (all): ',('late_n','sum'),'\nLate rate: ',('late','avg')])
# ---- 5 where / when
ows('Region',ORD,None,mark='Bar',rows=ORD.q('region_group','nk'),cols=ORD.q('late','avg'),color=('region_group','nk'),text=('late','avg'),
    palette_map=[('North and northeast',MID),('Rest of Brazil',LIGHT)],hide_axes=[('late','avg')],extra_uses=[('late','avg'),('region_group','nk')],
    header_w=(('region_group','nk'),150),header_font=(10,'normal'),cell_rules=[('cell','height',44,ORD.q('region_group','nk'))],
    tip=['Orders: ',('order_code','cnt'),'\nLate orders: ',('late_n','sum'),'\nLate rate: ',('late','avg')])
BK=('month_start','tmn')
ows('Months',ORD,[BK],mark='Bar',cols=ORD.q(*BK),rows=ORD.q('late_n','sum'),color=('is_worst3_month','nk'),text=[('month_tag','nk'),('late_tag_n','sum')],runs=None if 'NORUNS' in os.environ.get('X','') else [(('month_tag','nk'),8,True,INK),(None,0,0,''),(('late_tag_n','sum'),8,False,MID)],
    palette_map=[('true',MID),('false',PALE)],hide_axes=[('late_n','sum')],extra_uses=[('late_n','sum'),('late_tag_n','sum'),BK],
    axis_titles={(BK[0],BK[1],'cols'):'Click a month to filter, click again to clear',('late_n','sum','rows'):''},xspace=(BK,'#2017-01-01#','6.0','months'),datefmts=[('label','*mmm yyyy',None)],
    tip=['Orders: ',('order_code','cnt'),'\nLate orders: ',('late_n','sum'),'\nLate rate: ',('late','avg')])
# ----------------------------------------------------------------------- dashboard
W,Hh=1366,768
zid=[10]
def nid(): zid[0]+=1; return zid[0]
def P(v,tot=0): return int(round(v*1000))
def zone_sheet(name,x,y,w,h,style=''):
    return "        <zone h='%d' id='%d' name=%s show-title='false' w='%d' x='%d' y='%d'>%s</zone>\n"%(P(h),nid(),quoteattr(name),P(w),P(x),P(y),style or '')
def zstyle(bg=None,border=None,bstyle='solid',bw=1,margin=0):
    it=[]
    if border: it+=["<format attr='border-color' value='%s' />"%border,"<format attr='border-style' value='%s' />"%bstyle,"<format attr='border-width' value='%d' />"%bw]
    else: it+=["<format attr='border-style' value='none' />"]
    if bg: it.append("<format attr='background-color' value='%s' />"%bg)
    it.append("<format attr='margin' value='%d' />"%margin)
    return "<zone-style>"+''.join(it)+"</zone-style>"
def ztxt(runs,x,y,w,h,style=''):
    """runs: list of (text,size,bold,color); text '\\n' = line break."""
    rr=[]
    for t,sz,b,c in runs:
        if t=='\n': rr.append("<run>Æ&#10;</run>")
        else: rr.append("<run bold='%s' fontcolor='%s' fontsize='%d'%s>%s</run>"%('true' if b else 'false',c,sz,'',q(t)))
    return "        <zone h='%d' id='%d' type='text' w='%d' x='%d' y='%d'><formatted-text>%s</formatted-text>%s</zone>\n"%(P(h),nid(),P(w),P(x),P(y),''.join(rr),style or zstyle())
NL=('\n',0,0,'')
fin_a='Late deliveries are linked to about %s bad reviews; '%n0(F('extra_bad_reviews_rounded'))
fin_b='sellers shipping late is the biggest linked source'
CX=[1,34,67]; CW=32
Z=''
Z+=ztxt([(fin_a,20,True,INK),(fin_b,20,True,ACC),NL,('Orders bought Jan 2017 to Aug 2018  ·  %s delivered orders  ·  %s late (%s)  ·  late = arrived after the promised day'%(n0(F('judged_orders')),n0(F('late_orders')),p2(F('late_rate'))),11,False,MID)],1,0.4,98,9.6)
kpi=[('1  COST',INK,'≈'+n0(F('extra_bad_reviews_rounded')),'1-2 star reviews linked to late delivery','estimate, range %s to %s  ·  %s of all %s 1-2 star reviews'%(n0(F('extra_range_low_rounded')),n0(F('extra_range_high_rounded')),p1(F('extra_share_of_bad_reviews')),n0(F('bad_reviews_all')))),
     ('2  THIS MONTH VS GOAL',INK,p1(F('latest_month_late_rate')),'%s late rate, %.1f points %s the %s goal'%(SUM['latest_month_label'],abs(F('latest_month_late_rate')-F('goal_late_rate'))*100,'over' if F('latest_month_late_rate')>=F('goal_late_rate') else 'under',p1(F('goal_late_rate'))),'(%s the warning line)'%('under' if F('latest_month_late_rate')<F('latest_month_own_alarm_line_late_rate') else 'over')),
     ('3  SELLER SHIPS LATE',ACC,p1(F('late_handoff_late_rate')),'of orders shipped after the ship-by date arrive late, vs %s shipped by it'%p1(F('on_time_handoff_late_rate')),'%s of all late orders were shipped late by the seller'%p1(F('late_handoff_share_of_late')))]
if VAR=='b1':
    for i,(h,c,big,s1,s2) in enumerate(kpi):
        Z+=ztxt([(h,10,True,MID),NL,(big,27,True,c),NL,(s1,9,False,MID),NL,(s2,9,False,MID)],CX[i],10.2,CW,14.6,zstyle(bg='#F2F2F2',margin=4))
    R1T=25.0
else:
    runs=[]
    segs=[('≈'+n0(F('extra_bad_reviews_rounded')),INK,' extra bad reviews linked to late delivery'),(p1(F('latest_month_late_rate')),INK,' late in %s, goal %s'%(SUM['latest_month_label'],p1(F('goal_late_rate')))),(p1(F('late_handoff_late_rate')),ACC,' late when shipped late, vs %s'%p1(F('on_time_handoff_late_rate')))]
    for j,(b,c,t) in enumerate(segs):
        if j: runs.append(('      |      ',14,False,LIGHT))
        runs+= [(b,24,True,c),(t,12,False,MID)]
    Z+=ztxt(runs,1,10.6,98,7.2,zstyle(bg='#F2F2F2',margin=6))
    R1T=19.0
TH=9.0
def title(n,head,note,x,y,w,hh=TH,hc=INK):
    runs=[('%s  '%n,12,True,MID),(head,12,True,hc)]
    if note: runs+=[NL,(note,9,False,MID)]
    return ztxt(runs,x,y,w,hh)
r1c=R1T+TH; r1h=(55.6-r1c)
r2T=r1c+r1h+0.6; r2c=r2T+TH; r2h=89.5-r2c
Z+=title('1','Reviews turn bad fast: %s are 1-2 stars up to the promised day, about %s from day 6 late'%(p1(F('ramp_share_up_to_promised_day')),p0(F('ramp_share_from_day_6'))),'share of reviews that are 1-2 stars, by days past the promised day',CX[0],R1T,CW)
Z+=zone_sheet('Review ramp',CX[0],r1c,CW,r1h,zstyle(margin=2))
Z+=title('2','Late rate sits above the %s goal; %s went past the warning line'%(p1(F('goal_late_rate')),SUM['worst3_months_label']),'gray line = warning line: above it is more than random swings',CX[1],R1T,CW)
Z+=zone_sheet('Trend',CX[1],r1c,CW,r1h,zstyle(margin=2))
Z+=title('3','Orders shipped after the ship-by date: %s arrive late, vs %s when shipped by it'%(p1(F('late_handoff_late_rate')),p1(F('on_time_handoff_late_rate'))),'%s of %s arrived late  ·  %s of all %s late orders'%(n0(F('late_handoff_late_orders')),n0(F('late_handoff_orders')),p1(F('late_handoff_share_of_late')),n0(F('late_orders'))),CX[2],R1T,CW,hc=ACC)
Z+=zone_sheet('Handoff',CX[2],r1c,CW,r1h,zstyle(margin=4))
N_SELL=int(round(F('sellers_with_late_after_late_handoff')))
CLOSE_H=2.6
T4=1.8   # room for the one-line note under the seller panel title; seller rows are 15 px so all 10 fit
Z+=title('4',"Calling the top 10 sellers won't fix it: they account for only %s of the %s late orders that were shipped late"%(p0(F('top10_share_of_late_after_late_handoff')),n0(F('late_handoff_late_orders'))),'Seller (anonymized ID), late orders  ·  Click a seller to filter the other charts\nNot a target list: flagged sellers were not late more often afterward',CX[0],r2T,CW,TH+T4)
Z+=zone_sheet('Sellers',CX[0],r2c+T4,CW,r2h-CLOSE_H-T4,zstyle(margin=2))
Z+=ztxt([('The other %d sellers account for the remaining %s.'%(N_SELL-10,p0(1-F('top10_share_of_late_after_late_handoff'))),10,False,MID)],CX[0],r2c+r2h-CLOSE_H,CW,CLOSE_H,zstyle(margin=2))
Z+=title('5','North and northeast run %s late vs %s elsewhere'%(p1(F('nne_late_rate')),p1(F('rest_late_rate'))),'late rate by region  ·  Click a region to filter',CX[1],r2T,CW)
Z+=zone_sheet('Region',CX[1],r2c,CW,min(r2h,14),zstyle(margin=2))
Z+=ztxt([('6  ',12,True,MID),('%s of late orders came in 3 months: %s'%(p1(F('worst3_share_of_late')),SUM['worst3_months_label']),12,True,INK),NL,('those 3 months held %s of all orders (%s of months)'%(p1(F('worst3_share_of_orders')),p0(F('worst3_share_of_months'))),9,False,MID)],CX[2],r2T,CW,TH)
Z+=zone_sheet('Months',CX[2],r2c,CW,r2h,zstyle(margin=2))
# The bottom strip states the case study's two recommendations (docs/CASE_STUDY.md, Recommendation); it holds no numbers.
REC_MODEL="Per-order delivery-date model: not adopted yet. Keep building it; launch only once checkout conversion by promised days and a second peak season show the longer date is worth it."
REC_SELLER="No seller penalty list: sellers flagged for repeated late shipping were not late more often afterward."
Z+=ztxt([('Next step (nothing launched yet)',11,True,MID),NL,(REC_MODEL,10,False,MID),NL,(REC_SELLER,10,False,MID)],1,90.2,98,9.7,zstyle(border=MID,bstyle='dashed',bw=1,margin=4))
ACTIONS=''
def action(cap,src,exclude):
    return ("    <action caption='%s' name='[Action_%s]'>\n      <activation auto-clear='true' type='on-select' />\n      <source dashboard='%s' type='sheet' worksheet='%s' />\n      <command command='tsc:tsl-filter'>\n        <param name='exclude' value='%s' />\n        <param name='special-fields' value='all' />\n        <param name='target' value='%s' />\n      </command>\n    </action>\n")%(cap,h32(cap)[:16],DASH,src,exclude,DASH)
DASH='Dashboard layout B (%s)'%VAR
ACTIONS="  <actions>\n"+action('Filter by seller','Sellers','Sellers,Trend,Review ramp')+action('Filter by region','Region','Region,Trend,Review ramp')+action('Filter by month','Months','Months,Trend,Review ramp')+"  </actions>\n"

dash=f"""  <dashboards>
    <dashboard name={quoteattr(DASH)}>
      <style />
      <size maxheight='{Hh}' maxwidth='{W}' minheight='{Hh}' minwidth='{W}' />
      <zones>
        <zone h='100000' id='4' type='layout-basic' w='100000' x='0' y='0'>
{Z}        </zone>
      </zones>
      <simple-id uuid='{uid('dash')}' />
    </dashboard>
  </dashboards>
"""
CARDS="""      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
        <edge name='top'>
          <strip size='31'>
            <card type='columns' />
          </strip>
          <strip size='31'>
            <card type='rows' />
          </strip>
          <strip size='31'>
            <card type='title' />
          </strip>
        </edge>
      </cards>
"""
wins=''.join(f"    <window class='worksheet' hidden='true' name={quoteattr(n)}>\n{CARDS}      <viewpoint>\n        <zoom type='entire-view' />\n      </viewpoint>\n      <simple-id uuid='{uid('win'+n)}' />\n    </window>\n" for n,_ in WS)
wins+=f"    <window class='dashboard' maximized='true' name={quoteattr(DASH)}>\n      <viewpoints />\n      <active id='-1' />\n      <simple-id uuid='{uid('windash')}' />\n    </window>\n"

if TR:
    GS=os.environ.get('GSZ','4'); SS=os.environ.get('SSZ','1')
    GP=F('goal_late_rate'); SP=F('stretch_whatif_late_rate')
    PARAMS="    <datasource hasconnection='false' inline='true' name='Parameters' version='18.1'>\n      <aliases enabled='yes' />\n"
    for i,(cap,v) in enumerate([('Goal (a typical steady month)',GP),('If late-shipped orders were late as rarely as the rest (what-if)',SP)],1):
        PARAMS+="      <column caption='%s' datatype='real' default-format='p1%%' name='[Parameter %d]' param-domain-type='range' role='measure' type='quantitative' value='%r'>\n        <calculation class='tableau' formula='%r' />\n        <range granularity='0.001' max='0.2' min='0.0' />\n      </column>\n"%(cap,i,v,v)
    PARAMS+="    </datasource>\n"
    PDEP="          <datasource-dependencies datasource='Parameters'>\n"
    for i,(cap,v) in enumerate([('Goal (a typical steady month)',GP),('If late-shipped orders were late as rarely as the rest (what-if)',SP)],1):
        PDEP+="            <column caption='%s' datatype='real' default-format='p1%%' name='[Parameter %d]' param-domain-type='range' role='measure' type='quantitative' value='%r'>\n              <calculation class='tableau' formula='%r' />\n              <range granularity='0.001' max='0.2' min='0.0' />\n            </column>\n"%(cap,i,v,v)
    PDEP+="          </datasource-dependencies>\n"
    ax=M.q('value','sum')
    PAT=os.environ.get('PAT','dashed')
    RL=("            <reference-line axis-column='%s' enable-instant-analytics='true' formula='average' id='refline0' label-type='none' scope='per-pane' value-column='[Parameters].[Parameter 1]' z-order='1' />\n"
        "            <reference-line axis-column='%s' enable-instant-analytics='true' formula='average' id='refline1' label-type='none' scope='per-pane' value-column='[Parameters].[Parameter 2]' z-order='2' />\n")%(ax,ax)
    RS=("          <style-rule element='refline'>\n            <format attr='stroke-size' id='refline0' value='%s' />\n            <format attr='stroke-color' id='refline0' value='%s' />\n            <format attr='line-pattern-only' id='refline0' value='solid' />\n"
        "            <format attr='stroke-size' id='refline1' value='%s' />\n            <format attr='stroke-color' id='refline1' value='%s' />\n            <format attr='line-pattern-only' id='refline1' value='%s' />\n          </style-rule>\n")%(GS,MID,SS,'#A0A0A0',PAT)
    for k,(n_,x_) in enumerate(WS):
        if n_=='Trend':
            x_=x_.replace("          </datasources>\n","            <datasource name='Parameters' />\n          </datasources>\n",1)
            x_=x_.replace("          <datasource-dependencies datasource='%s'>"%M.name,PDEP+"          <datasource-dependencies datasource='%s'>"%M.name,1)
            assert "            </encodings>\n" in x_
            x_=x_.replace("            </encodings>\n","            </encodings>\n"+RL,1)
            x_=x_.replace("        </style>\n        <panes>","%s        </style>\n        <panes>"%RS,1)
            WS[k]=(n_,x_)

doc=HEAD+"<datasources>\n"+(PARAMS if TR else '')+''.join(d.xml() for d in D.values())+"  </datasources>\n"+ACTIONS+"  <worksheets>\n"+''.join(x for _,x in WS)+"  </worksheets>\n"+dash+"  <windows source-height='30'>\n"+wins+"  </windows>\n</workbook>\n"
open(out,'w',encoding='utf-8').write(doc)
print('wrote',out,len(doc))
