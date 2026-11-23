#!/usr/bin/env python3
"""gen_v4.py <data dir to read headers from> <data dir as Tableau will see it> <out.twb>

Builds the Tableau workbook XML for the six-chart late-delivery dashboard (version 4; B1 is gen_workbook.py). It is built on the same
code as gen_workbook.py. The workbook head comes from
ctrl_saved_desktop_free.twb in this folder, a workbook saved by Tableau Desktop (hand-written workbooks do not open).
Both data dirs hold the CSVs written by prep3.py and prep4.py (orders.csv, ramp_b.csv, trend_e.csv, summary.csv, v3_scalars.csv,
seller_groups.csv, ...). The second path is written into the workbook as the folder Tableau reads the CSVs from.

The shipped page is built with   PROTO=P2 NCH=6 TREND=e SELL=repeat YEARTAG=1
Settings (environment variables, defaults in the code): PROTO, NCH, TREND, SELL, YEARTAG select the page; GOALPOS (where the goal
label sits), TICK, TICKFS, TORIG, TFMT, XMIN, XMAX (trend axis), WGRAY, RMAX, DOTSZ, FILT=col=value (build a copy filtered to
that value, for tests), ONLY=a|b (only the named worksheets). Settings that belong to earlier layouts are left in and are not used by
the shipped page.
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
DLS=9; DEXTRA=''
TORIG=os.environ.get('TORIG','#2017-02-01#'); TFMT=os.environ.get('TFMT','*mmm \u2019yy'); XMIN=os.environ.get('XMIN','#2016-12-15#'); XMAX=os.environ.get('XMAX','#2018-10-20#')
YEARTAG=os.environ.get('YEARTAG','')=='1'
WGRAY=os.environ.get('WGRAY','#9A9A9A'); TICK=os.environ.get('TICK','3.0'); TICKFS=os.environ.get('TICKFS','10'); RMAX=os.environ.get('RMAX','0.21'); DOTSZ=os.environ.get('DOTSZ','1'); GOALPOS=tuple(os.environ.get('GOALPOS','right,bottom').split(','))
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
              pct=(),axis_titles=None,header_w=None,header_font=None,dual=None,label_pos=None,xrange=None,palette_where='ds',bucket_q=True,pct_el='axis',pct_scope=None,cell_rules=(),tile_rules='',cell_w=None,hide_hdr=(),yfix=None,xspace=None,datefmt=None,header_h=(),datefmts=(),reflines=(),size=None,tip=None,axis_font=None,xfix=None,center_labels=False):
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
    LA=[x for x in os.environ.get('LALIGN','').split(';') if x]; LAP=os.environ.get('LAPOS','pane')
    if LA and name=='Trend' and LAP=='pane': mk+= [fmt(*x.split('=')) for x in LA]
    if color and palette_map and palette_where in ('pane','both'): mk.append(palette(dsq(*color),palette_map,bucket_q).strip())
    pane_style=("            <style>\n"+rule('mark',*mk).replace('          <style-rule','              <style-rule').replace('          </style-rule>','              </style-rule>')+"            </style>\n") if mk else ''
    # ---- table-level style
    rules=rule('worksheet',fmt('display-field-labels','false',scope='cols'),fmt('display-field-labels','false',scope='rows'))
    rules+=extra_rules
    if LA and name=='Trend' and LAP=='table': rules+=rule('mark',*[fmt(*x.split('=')) for x in LA])
    if center_labels: rules+=rule('cell',fmt('text-align','center'),fmt('vertical-align','center'))
    if color and palette_map and palette_where in ('table','both'): rules+=rule('mark',palette(dsq(*color),palette_map,bucket_q).strip())
    for el,at,val,fld in cell_rules: rules+=rule(el,fmt(at,val,field=fld))
    if plain:
        rules+=rule('gridline',fmt('line-visibility','off',scope='cols'),fmt('line-visibility','off',scope='rows'))
        rules+=rule('zeroline',fmt('line-visibility','off',scope='cols'),fmt('line-visibility','off',scope='rows'))
    ax=[]
    if xspace:
        fld,orig_,sp,un=xspace; ax.append("<encoding attr='space' class='0' field='%s' field-type='quantitative' major-origin='%s' major-spacing='%s' major-units='%s'%s scope='cols' type='space' />"%(dsq(*fld),orig_,sp,un,(" max='%s' min='%s' range-type='fixed'"%(xfix[1],xfix[0])) if xfix else ''))
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
    if axis_font: ax.append(fmt('font-size',axis_font))
    if dual:
        _v1,_v2,_rmax=dual[:3]
        ax+=["<encoding attr='space' class='%d' field='%s' field-type='quantitative' fold='true' max='%s' min='0' range-type='fixed' scope='rows' type='space' />"%(i_,dsq(v_,'sum'),_rmax) for i_,v_ in enumerate((_v1,_v2))]+[fmt('display','false',field=dsq(_v2,'sum'))]
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
        v1,v2,rmax,dlab,dcol,dsz=dual   # value col, circle value col, axis max, circle label col, circle colour, circle size
        uses+= [(v2,'sum'),dlab]
        dl=("            <customized-label>\n              <formatted-text>\n                <run bold='true' fontcolor='%s' fontsize='%s'>%s</run>\n              </formatted-text>\n            </customized-label>\n"%(dcol,DLS,q('<'+dsq(*dlab)+'>')))
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
            <encodings>
              <text column='{dsq(*dlab)}' />
            </encodings>
{dl}            <style>
              <style-rule element='mark'>
                <format attr='mark-color' value='{dcol}' />
                <format attr='mark-labels-show' value='true' />
                <format attr='size' value='{dsz}' />{DEXTRA}
              </style-rule>
            </style>
          </pane>
"""
        rows="(%s + %s)"%(dsq(v1,'sum'),dsq(v2,'sum'))
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

# ======================================================================= page layouts (the shipped one is P2 with six charts)
PROTO=os.environ.get('PROTO','P1'); PAGE=os.environ.get('PAGE','both'); STAT=os.environ.get('STAT','chip'); SELL=os.environ.get('SELL','codes')
TREND=os.environ.get('TREND','a'); NCH=os.environ.get('NCH','6'); ACTIVE=os.environ.get('ACTIVE','')
need1=PROTO=='P1' and PAGE in ('1','both'); need2=PROTO=='P2' or PAGE in ('2','both')
SUM=list(csv.DictReader(open(os.path.join(boxdata,'summary.csv'))))[0]
SC=list(csv.DictReader(open(os.path.join(boxdata,'v3_scalars.csv'))))[0]
SG=list(csv.DictReader(open(os.path.join(boxdata,'seller_groups.csv'))))
F=lambda k: float(SUM[k]); FS=lambda k: float(SC[k])
def p0(x): return '%d%%'%round(x*100)
def p1(x): return '%.1f%%'%(x*100)
def p2(x): return '%.2f%%'%(x*100)
def n0(x): return format(int(round(float(x))),',')
ACC=OR; INK='#222222'; MID='#555555'; LIGHT='#B5B5B5'; PALE='#D0D0D0'; TILE='#F2F2F2'
RED='#C0392B'; AMBER='#F2B01E'; GREEN='#3A8F5C'; STC={'red':RED,'amber':AMBER,'green':GREEN}
D={}
def reg(key,cap,name):
    d=DS(key,cap,name); D[key]=d; return d
def fmember(d,col,val): return "          <filter class='categorical' column='[%s].[none:%s:nk]'>\n            <groupfilter function='member' level='[none:%s:nk]' member='&quot;%s&quot;' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />\n          </filter>\n"%(d.name,col,col,val)
def sortx(d,col,by): return "          <sort class='computed' column='%s' direction='DESC' using='%s' />\n"%(d.q(col,'nk'),d.q(by,'sum'))
xk=('month_start','tmn')
# ---------------- parameters + reference lines
GP=FS('goal'); WP=FS('alarm'); SP_=F('stretch_whatif_late_rate')
PNAMES=[('Goal (a typical steady month)',GP),('If late-shipped orders were late as rarely as the rest (what-if)',SP_),('Warning line, latest month',WP)]
PARAMS="    <datasource hasconnection='false' inline='true' name='Parameters' version='18.1'>\n      <aliases enabled='yes' />\n"
PDEP="          <datasource-dependencies datasource='Parameters'>\n"
for i,(cap,v) in enumerate(PNAMES,1):
    col="      <column caption='%s' datatype='real' default-format='p1%%' name='[Parameter %d]' param-domain-type='range' role='measure' type='quantitative' value='%r'>\n        <calculation class='tableau' formula='%r' />\n        <range granularity='0.001' max='0.2' min='0.0' />\n      </column>\n"%(cap,i,v,v)
    PARAMS+=col; PDEP+=col.replace('      <column','            <column',1).replace('\n        <','\n              <').replace('\n      </column>','\n            </column>')
PARAMS+="    </datasource>\n"; PDEP+="          </datasource-dependencies>\n"
REFS={}   # sheet -> (axis col, [(param, size, color, pattern, label)])
def addrefs(name,ax,refs): REFS[name]=(ax,refs)
def apply_refs():
    for k,(n_,x_) in enumerate(WS):
        if n_ not in REFS: continue
        ax,refs=REFS[n_]
        x_=x_.replace("          </datasources>\n","            <datasource name='Parameters' />\n          </datasources>\n",1)
        dsn=re.search(r"<datasource-dependencies datasource='([^']+)'>",x_).group(1)
        x_=x_.replace("          <datasource-dependencies datasource='%s'>"%dsn,PDEP+"          <datasource-dependencies datasource='%s'>"%dsn,1)
        RL=''.join("            <reference-line axis-column='%s' enable-instant-analytics='true' formula='average' id='refline%d' %s scope='per-pane' value-column='[Parameters].[Parameter %d]' z-order='%d' />\n"%(ax,i,("label='%s' label-type='custom'"%q(lab)) if lab else "label-type='none'",pi,i+1) for i,(pi,sz,col,pat,lab,al) in enumerate(refs))
        RS="          <style-rule element='refline'>\n"
        for i,(pi,sz,col,pat,lab,al) in enumerate(refs):
            RS+="            <format attr='stroke-size' id='refline%d' value='%s' />\n            <format attr='stroke-color' id='refline%d' value='%s' />\n            <format attr='line-pattern-only' id='refline%d' value='%s' />\n"%(i,sz,i,col,i,pat)
            if lab: RS+="            <format attr='color' id='refline%d' value='%s' />\n            <format attr='text-align' id='refline%d' value='%s' />\n            <format attr='vertical-align' id='refline%d' value='%s' />\n"%(i,col,i,al[0],i,al[1])
        RS+="          </style-rule>\n"
        assert "            </encodings>\n" in x_
        x_=x_.replace("            </encodings>\n","            </encodings>\n"+RL,1)
        x_=x_.replace("        </style>\n        <panes>","%s        </style>\n        <panes>"%RS,1)
        WS[k]=(n_,x_)
# ---------------- datasources and sheets
if need2:
    ORD=reg('ord','orders','orders.csv'); ORD.dfmt['late']='p0.0%'
    if PROTO=='P2' and NCH=='6' or TREND=='orig': pass
    R=reg('ramp','ramp_b','ramp_b.csv'); R.dfmt['bad_review_share']='p0%'
if need1:
    SP=reg('spark','spark_long','spark_long.csv'); SP.dfmt['value']='p0%'; NOW=reg('now','status_now','status_now.csv'); NOW.dfmt['value']='p0.0%'
STAT_LAB={'red':'ABOVE THE WARNING LINE','amber':'ABOVE GOAL','green':'AT OR BELOW GOAL'}
def ows(name,d,uses=None,**k): return worksheet(name,d,uses,**k)
BLANK={('value','sum','rows'):'',(xk[0],xk[1],'cols'):''}
if need2:
    if PROTO=='P2' and NCH=='6' or PROTO=='P1' and False:
        worksheet('Review ramp',R,None,mark='Line',cols=R.q('days_past_promise_capped','qk'),rows=R.q('bad_review_share','sum'),
            extra_uses=[('days_past_promise_capped','qk'),('bad_review_share','sum')],color=('phase','nk'),text=('lab','nk'),
            palette_map=[('up to the promised day','#8C8C8C'),('climbing',INK),('levelled',INK),('label',MID)],
            axis_titles={('days_past_promise_capped','qk','cols'):'days past the promised day',('bad_review_share','sum','rows'):''})
    if PROTO=='P2':
        TIPS=['Orders in the month: ',('orders','avg'),'\nLate orders in the month: ',('late_orders','avg')]
        if TREND=='orig':
            M=reg('ml','monthly_long','monthly_long.csv'); M.dfmt['value']='p0%'
            PAL=[('g Late rate',INK),('c Alarm line',LIGHT),('b Goal','#FFFFFF00'),('a Stretch','#FFFFFF00'),('e Alarm month',INK),('f Latest month',INK),('d Alarm label','#FFFFFF00'),('d Month label','#FFFFFF00'),('d Goal label','#FFFFFF00'),('d Stretch label','#FFFFFF00')]
            worksheet('Trend',M,[('value','sum'),xk],mark='Line',cols=M.q(*xk),rows=M.q('value','sum'),color=('series','nk'),text=('lab','nk'),palette_map=PAL,
                axis_titles=BLANK,xspace=(xk,'#2017-01-01#','6.0','months'),datefmts=[('label','*mmm yyyy',None)],tip=TIPS)
            addrefs('Trend',M.q('value','sum'),[(1,4,MID,'solid',None,None),(2,1,'#A0A0A0','dashed',None,None)])
        elif TREND=='e':
            T=reg('tr','trend','trend_e.csv'); T.dfmt['value']='p0%'
            CLR='#FFFFFF00'
            PAL=[('g Late rate',INK),('c Alarm line',WGRAY),('e Breach 1',INK),('e Breach 2',INK),('e Breach 3',INK),('f Latest month',INK)]+[(k,CLR) for k in ('k1 end late','k2 end warn','k3 warn a','k4 warn b','k5 name nov','k6 name feb','k7 name mar')]
            worksheet('Trend',T,[('value','sum'),xk],mark='Line',cols=T.q(*xk),rows=T.q('value','sum'),color=('series','nk'),text=('lab','nk'),palette_map=PAL,
                axis_titles=BLANK,xspace=(xk,TORIG,TICK,'months'),datefmts=[('label',TFMT,None)],tip=['Orders in the month: ',('orders','avg'),'\nLate orders in the month: ',('late_orders','avg')],
                axis_font=TICKFS,xfix=(XMIN,XMAX),center_labels=True)
            addrefs('Trend',T.q('value','sum'),[(1,3,MID,'solid','Goal %s'%p1(GP),GOALPOS)])
        elif TREND=='d':
            T=reg('tr','trend','trend_d.csv'); T.dfmt['value']='p0%'; T.dfmt['breach_v']='p0%'
            PAL=[('g Late rate',INK),('c Alarm line',WGRAY),('f Latest month',INK),('d Goal label','#FFFFFF00')]
            worksheet('Trend',T,[('value','sum'),xk],mark='Line',cols=T.q(*xk),rows='',color=('series','nk'),text=('lab','nk'),palette_map=PAL,
                axis_titles={('value','sum','rows'):'',(xk[0],xk[1],'cols'):''},xspace=(xk,'#2017-01-01#',TICK,'months'),datefmts=[('label','*mmm yyyy',None)],tip=TIPS,
                dual=('value','breach_v',RMAX,('blab','nk'),INK,DOTSZ),axis_font=TICKFS)
            addrefs('Trend',T.q('value','sum'),[(1,3,MID,'solid','Goal %s'%p1(GP),GOALPOS)])
        else:
            T=reg('tr','trend','trend_%s.csv'%TREND); T.dfmt['value']='p0%'
            PAL=[('g Late rate',INK),('c Alarm line',PALE if TREND=='b' else LIGHT)]+[('e Breach %d'%i,INK) for i in range(1,6)]+[('f Latest month',INK),('d Goal label','#FFFFFF00')]
            worksheet('Trend',T,[('value','sum'),xk],mark='Line',cols=T.q(*xk),rows=T.q('value','sum'),color=('series','nk'),text=('lab','nk'),palette_map=PAL,
                axis_titles=BLANK,xspace=(xk,'#2017-01-01#','6.0','months'),datefmts=[('label','*mmm yyyy',None)],tip=TIPS)
            addrefs('Trend',T.q('value','sum'),[(1,3,MID,'solid',('Goal %s'%p1(GP)) if TREND in ('a','b') else None,('right','bottom'))])
    ows('Handoff',ORD,[('has_handoff','nk')],mark='Bar',rows=ORD.q('handoff_group','nk'),cols=ORD.q('late','avg'),color=('handoff_group','nk'),text=('late','avg'),
        palette_map=[('Shipped after the ship-by date',ACC),('Shipped by the ship-by date',LIGHT)],hide_axes=[('late','avg')],extra_uses=[('late','avg'),('handoff_group','nk')],
        filt=fmember(ORD,'has_handoff','true'),header_w=(('handoff_group','nk'),215),header_font=(10,'normal'),cell_rules=[('cell','height',58,ORD.q('handoff_group','nk'))],
        tip=['Orders: ',('order_code','cnt'),'\nLate orders: ',('late_n','sum'),'\nLate rate: ',('late','avg')])
    if SELL=='codes':
        ows('Sellers',ORD,[('is_top10','nk')],mark='Bar',rows=ORD.q('seller_label','nk'),cols=ORD.q('lalh_n','sum'),text=('lalh_n','sum'),pane_color=MID,
            hide_axes=[('lalh_n','sum')],extra_uses=[('lalh_n','sum'),('seller_label','nk')],filt=fmember(ORD,'is_top10','true'),header_w=(('seller_label','nk'),210),header_font=(13,'bold'),cell_rules=[('cell','height',17,ORD.q('seller_label','nk'))],
            tip=['Orders: ',('order_code','cnt'),'\nOrders shipped late: ',('late_handoff_n','sum'),'\nLate orders that were shipped late: ',('lalh_n','sum'),'\nLate orders (all): ',('late_n','sum'),'\nLate rate: ',('late','avg')])
    else:
        col={'size':'seller_size','state':'seller_state','repeat':'seller_repeat'}[SELL]
        ows('Sellers',ORD,[('seller_in_scope','nk')],mark='Bar',rows=ORD.q(col,'nk'),cols=ORD.q('lalh_n','sum'),text=('lalh_n','sum'),pane_color=MID,
            hide_axes=[('lalh_n','sum')],extra_uses=[('lalh_n','sum'),(col,'nk')],filt=fmember(ORD,'seller_in_scope','true')+sortx(ORD,col,'lalh_n'),header_w=((col,'nk'),(190 if PROTO=='P2' else 330)),header_font=(11 if PROTO!='P2' else 10,'bold'),cell_rules=[('cell','height',(34 if SELL=='state' else 46),ORD.q(col,'nk'))],
            tip=['Late orders that were shipped late: ',('lalh_n','sum'),'\nOrders: ',('order_code','cnt')])
    ows('Region',ORD,None,mark='Bar',rows=ORD.q('region_group','nk'),cols=ORD.q('late','avg'),color=('region_group','nk'),text=('late','avg'),
        palette_map=[('North and northeast',MID),('Rest of Brazil',LIGHT)],hide_axes=[('late','avg')],extra_uses=[('late','avg'),('region_group','nk')],
        header_w=(('region_group','nk'),150),header_font=(10,'normal'),cell_rules=[('cell','height',44,ORD.q('region_group','nk'))],
        tip=['Orders: ',('order_code','cnt'),'\nLate orders: ',('late_n','sum'),'\nLate rate: ',('late','avg')])
    if (PROTO=='P2' and NCH=='6') or PROTO=='P1':
        BK=('month_start','tmn')
        ows('Months',ORD,[BK],mark='Bar',cols=ORD.q(*BK),rows=ORD.q('late_n','sum'),color=('is_worst3_month','nk'),text=[('tag_m','nk'),('late_tag_n','sum')]+([('tag_pad','nk')] if YEARTAG else []),runs=[(('tag_m','nk'),8,True,INK),(None,0,0,''),(('late_tag_n','sum'),8,False,MID),(('tag_pad','nk'),8,False,MID)] if YEARTAG else [(('month_tag','nk'),8,True,INK),(None,0,0,''),(('late_tag_n','sum'),8,False,MID)],
            palette_map=[('true',MID),('false',PALE)],hide_axes=[('late_n','sum')],extra_uses=[('late_n','sum'),('late_tag_n','sum'),BK],
            axis_titles={(BK[0],BK[1],'cols'):'Click a month to filter, click again to clear',('late_n','sum','rows'):''},xspace=(BK,TORIG if YEARTAG else '#2017-01-01#',TICK if YEARTAG else '6.0','months'),datefmts=[('label',TFMT if YEARTAG else '*mmm yyyy',None)],axis_font=(TICKFS if YEARTAG else None),
            tip=['Orders: ',('order_code','cnt'),'\nLate orders: ',('late_n','sum'),'\nLate rate: ',('late','avg')])
if need1:
    def spark(name,metric,pal,refs=None):
        worksheet(name,SP,[('value','sum'),xk],mark='Line',cols=SP.q(*xk),rows=SP.q('value','sum'),color=('series','nk'),text=('lab','nk'),palette_map=pal,
            filt=fmember(SP,'metric',metric),extra_uses=[('metric','nk')],hide_axes=[('value','sum')],hide_hdr=[xk],axis_titles=BLANK,xspace=(xk,'#2017-01-01#','6.0','months'),
            tip=['Value: ',('value','sum')])
        if refs: addrefs(name,SP.q('value','sum'),refs)
    SPAL=[('a Late rate',MID)]+[('b Breach %d'%i,INK) for i in range(1,6)]+[('c Latest '+k,v) for k,v in STC.items()]+[('d Share',MID),('e Share latest',INK),('f Shipped after the ship-by date',ACC),('g Shipped by the ship-by date',LIGHT),('h Gap latest',ACC)]
    spark('Spark rate','late_rate',SPAL,[(1,2,INK,'solid',None,None)])
    spark('Spark share','ship_late_share',SPAL)
    spark('Spark gap','gap',SPAL)
    if STAT=='bullet':
        worksheet('Bullet',NOW,[('value','sum')],mark='Bar',cols=NOW.q('value','sum'),rows=NOW.q('label','nk'),color=('status','nk'),palette_map=[(k,v) for k,v in STC.items()],
            extra_uses=[('value','sum'),('label','nk'),('status','nk')],hide_hdr=[('label','nk')],pct=[(('value','sum'),'p0%')],axis_titles={('value','sum','cols'):'',('label','nk','rows'):''},cell_rules=[('cell','height',180,NOW.q('label','nk'))],
            tip=['Late rate: ',('value','sum')])
        addrefs('Bullet',NOW.q('value','sum'),[(1,4,INK,'solid','Goal %s'%p1(GP),('center','top')),(3,2,MID,'dashed','Warning line %s'%p1(WP),('center','bottom'))])
apply_refs()
# ----------------------------------------------------------------------- dashboards
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
    rr=[]
    for t,sz,b,c in runs:
        if t=='\n': rr.append("<run>Æ&#10;</run>")
        else: rr.append("<run bold='%s' fontcolor='%s' fontsize='%d'>%s</run>"%('true' if b else 'false',c,sz,q(t)))
    return "        <zone h='%d' id='%d' type='text' w='%d' x='%d' y='%d'><formatted-text>%s</formatted-text>%s</zone>\n"%(P(h),nid(),P(w),P(x),P(y),''.join(rr),style or zstyle())
NL=('\n',0,0,'')
def title(n,head,note,x,y,w,hh=9.0,hc=INK):
    runs=[('%s  '%n,12,True,MID)] if n else []
    runs+=[(head,12,True,hc)]
    if note: runs+=[NL,(note,9,False,MID)]
    return ztxt(runs,x,y,w,hh)
CX=[1,34,67]; CW=32
LAT=SC['latest_label']; ST=SC['status']; LR=FS('latest_rate'); AL=FS('alarm')
arrow='\u25b2' if LR>GP else '\u25bc'
dpts=abs(LR-GP)*100
LH=F('late_handoff_late_rate'); OK_=F('on_time_handoff_late_rate')
N_SELL=int(round(F('sellers_with_late_after_late_handoff'))); NLL=n0(F('late_handoff_late_orders'))
grp=lambda kind:[g for g in SG if g['kind']==kind]
# The bottom strip states the case study's two recommendations (docs/CASE_STUDY.md, Recommendation); it holds no numbers.
REC_MODEL="Per-order delivery-date model: not adopted yet. Keep building it; launch only once checkout conversion by promised days and a second peak season show the longer date is worth it."
REC_SELLER="No seller penalty list: sellers flagged for repeated late shipping were not late more often afterward."
def seller_title():
    if SELL=='codes': return ('Calling the 10 worst sellers won\'t fix it: they account for only %s of the %s late orders that were shipped late'%(p0(F('top10_share_of_late_after_late_handoff')),NLL),'Seller (anonymized ID), late orders  \u00b7  Click a seller to filter the other charts')
    g=grp(SELL)[0]; nm=g['grp'].split(':')[0]; ns=int(g['grp'].split(': ')[1].split()[0].replace(',','')); sh=float(g['share_of_late_shipped_late'])
    if SELL=='size': return ('By seller size: large sellers are %s of the %d sellers behind these late orders and account for %s of the %s that were shipped late'%(p0(ns/N_SELL),N_SELL,p0(sh),NLL),'Late orders that were shipped late, by seller size (sellers with at least one)  \u00b7  Click a bar to filter the other charts')
    if SELL=='state': return ('By seller state: %s are %s of the %d sellers behind these late orders and account for %s of the %s that were shipped late'%(nm.replace('State ','sellers in '),p0(ns/N_SELL),N_SELL,p0(sh),NLL),'Late orders that were shipped late, by seller state (top 5 states)  \u00b7  Click a bar to filter the other charts')
    if PROTO=='P2': return ('%d sellers (%s of the %d) shipped late in 3 or more months and account for %s of the %s late orders that were shipped late'%(ns,p0(ns/N_SELL),N_SELL,p0(sh),NLL),'by number of months the seller shipped late  \u00b7  Click a bar to filter\nNot a target list: these sellers were not late more often afterward')
    return ('%d sellers (%s of the %d) had late-shipped late orders in 3 or more months, and they account for %s of the %s that were shipped late'%(ns,p0(ns/N_SELL),N_SELL,p0(sh),NLL),'Late orders that were shipped late, by how many months the seller did it  \u00b7  Click a bar to filter the other charts')
def mk_actions(DASH,srcs):
    def action(cap,src,exclude):
        return ("    <action caption='%s' name='[Action_%s]'>\n      <activation auto-clear='true' type='on-select' />\n      <source dashboard=%s type='sheet' worksheet='%s' />\n      <command command='tsc:tsl-filter'>\n        <param name='exclude' value='%s' />\n        <param name='special-fields' value='all' />\n        <param name='target' value=%s />\n      </command>\n    </action>\n")%(cap,h32(cap+DASH)[:16],quoteattr(DASH),src,exclude,quoteattr(DASH))
    ex=lambda s:','.join([s]+[n for n in ('Trend','Review ramp') if n in [w[0] for w in WS]])
    return ''.join(action(c,s,ex(s)) for c,s in srcs)
DASHES=[]   # (name, zones xml, actions xml)
if need1:
    zid[0]=10; Z=''
    d1='Late-delivery status board, %s'%LAT
    Z+=ztxt([(d1,20,True,INK),NL,('Orders that sellers ship late are the biggest linked source of lateness',20,True,ACC),NL,('Status board  \u00b7  page 1 of 2  \u00b7  orders bought %s to %s  \u00b7  %s delivered orders  \u00b7  late = arrived after the promised day'%(SC['first_label'],LAT,n0(F('judged_orders'))),11,False,MID)],1,0.4,98,13.2)
    Y0=14.4; chip=STAT=='chip'; arr=STAT=='chip'
    def tile(i,head,big,bigc,sub1,sub2,chiptxt,chipbg,chipfg,sheet,cap,bulletsheet=None):
        z=''; x=CX[i]
        z+=ztxt([(head,10,True,MID),NL,(big,34,True,bigc)],x,Y0,CW,12.2,zstyle(bg=TILE,margin=5))
        y=Y0+12.2
        if chip and chiptxt: z+=ztxt([(chiptxt,12,True,chipfg)],x,y,CW,4.6,zstyle(bg=chipbg,margin=6)); y+=4.6
        z+=ztxt([(sub1,11,True,INK),NL,(sub2,9,False,MID)],x,y,CW,7.4,zstyle(bg=TILE,margin=5)); y+=7.4
        sh=(Y0+50.8)-y-3.2
        z+=zone_sheet(bulletsheet or sheet,x,y,CW,sh,zstyle(bg=TILE,margin=3)); y+=sh
        z+=ztxt([(cap,9,False,MID)],x,y,CW,3.2,zstyle(bg=TILE,margin=4))
        return z
    a=(arrow+' ') if arr else ''
    t1sub1='%s%.1f points %s the %s goal'%(a,dpts,'above' if LR>GP else 'below',p1(GP))
    t1chip='%s %s'%(arrow,STAT_LAB[ST])+('  \u00b7  under the warning line (%s)'%p1(AL) if ST=='amber' else '')
    bl=STAT=='bullet'
    Z+=tile(0,'1  LATE RATE, %s'%LAT.upper(),p1(LR),INK,t1sub1,'warning line this month: %s  \u00b7  goal = a typical steady month'%p1(AL),t1chip,STC[ST],INK if ST=='amber' else '#FFFFFF','Spark rate','Late rate by month  \u00b7  dots = past the warning line  \u00b7  line = goal' if not bl else 'bar = %s late rate  \u00b7  solid line = goal  \u00b7  dashed line = warning line'%LAT,bulletsheet='Bullet' if bl else None)
    ds_=FS('latest_ship_late_share')-FS('period_ship_late_share')
    Z+=tile(1,'2  ORDERS SELLERS SHIPPED LATE, %s'%LAT.upper(),p1(FS('latest_ship_late_share')),INK,'%s%.1f points %s the all-months average (%s)'%(a,abs(ds_)*100,'above' if ds_>0 else 'below',p1(FS('period_ship_late_share'))),'share of orders shipped after the ship-by date',
        'NO GOAL SET  \u00b7  compared with the average','#D9D9D9',INK,'Spark share','Share of orders shipped late by month  \u00b7  dot = latest month')
    Z+=tile(2,'3  ARRIVE LATE WHEN SHIPPED LATE (ALL MONTHS)',p1(LH),ACC,'%s%.1f points worse than shipped by the ship-by date (%s)'%(a,(LH-OK_)*100,p1(OK_)),'%s of all %s late orders were shipped late by the seller'%(p1(F('late_handoff_share_of_late')),n0(F('late_orders'))),
        'NO GOAL SET  \u00b7  compared with on-time shipping','#D9D9D9',INK,'Spark gap','Late rate by month: orange = shipped late, gray = shipped by the date')
    Z+=ztxt([('Act first: orders that sellers ship late',14,True,ACC),NL,('%s of orders shipped after the ship-by date arrive late, vs %s when shipped by it. Late deliveries are linked to about %s extra 1-2 star reviews (estimate, %s to %s).'%(p1(LH),p1(OK_),n0(F('extra_bad_reviews_rounded')),n0(F('extra_range_low_rounded')),n0(F('extra_range_high_rounded'))),12,False,INK),NL,('Page 2 (second tab at the bottom): why it happens, which sellers, which region, which months.',11,False,MID)],1,Y0+52.6,98,15.0,zstyle(border=MID,bstyle='solid',bw=1,margin=8))
    DASHES.append(('Status board',Z,''))
if need2:
    zid[0]=10; Z=''
    if PROTO=='P2':
        DNAME='Story (%s charts)'%NCH
        fin_a='Late deliveries are linked to about %s bad reviews; '%n0(F('extra_bad_reviews_rounded')); fin_b='sellers shipping late is the biggest linked source'
        Z+=ztxt([(fin_a,20,True,INK),(fin_b,20,True,ACC),NL,('Orders bought %s to %s  \u00b7  %s delivered orders  \u00b7  %s late (%s)  \u00b7  late = arrived after the promised day'%(SC['first_label'],LAT,n0(F('judged_orders')),n0(F('late_orders')),p2(F('late_rate'))),11,False,MID)],1,0.4,98,9.6)
        Z+=ztxt([('1  COST',10,True,MID),NL,('\u2248'+n0(F('extra_bad_reviews_rounded')),27,True,INK),NL,('1-2 star reviews linked to late delivery',9,False,MID),NL,('estimate, range %s to %s  \u00b7  %s of all %s 1-2 star reviews'%(n0(F('extra_range_low_rounded')),n0(F('extra_range_high_rounded')),p1(F('extra_share_of_bad_reviews')),n0(F('bad_reviews_all'))),9,False,MID)],CX[0],10.2,CW,14.6,zstyle(bg=TILE,margin=4))
        Z+=ztxt([('2  THIS MONTH VS GOAL',10,True,MID),NL,(p1(LR),22,True,INK),NL,('%s %s late rate, %.1f points %s the %s goal'%(arrow,LAT,dpts,'over' if LR>GP else 'under',p1(GP)),9,False,MID)],CX[1],10.2,CW,11.4,zstyle(bg=TILE,margin=4))
        Z+=ztxt([('%s %s%s'%(arrow,STAT_LAB[ST],'  \u00b7  under the warning line (%s)'%p1(AL) if ST=='amber' else ''),11,True,INK if ST=='amber' else '#FFFFFF')],CX[1],21.6,CW,3.2,zstyle(bg=STC[ST],margin=4))
        Z+=ztxt([('3  SELLER SHIPS LATE',10,True,MID),NL,(p1(LH),27,True,ACC),NL,('of orders shipped after the ship-by date arrive late, vs %s shipped by it'%p1(OK_),9,False,MID),NL,('%s of all late orders were shipped late by the seller'%p1(F('late_handoff_share_of_late')),9,False,MID)],CX[2],10.2,CW,14.6,zstyle(bg=TILE,margin=4))
        TOP=25.0
        wk_note=os.environ.get('WKNOTE','gray line = warning line, set for each month  \u00b7  dots = months past it') if TREND in ('d','e') else 'dots = months past the warning line' if TREND in ('a','b') else 'gray line = warning line: above it is more than random swings'
        trend_head='Late rate sits above the %s goal; %s went past the warning line'%(p1(GP),SUM['worst3_months_label'])
        foot_t=("What-if: if late-shipped orders were late as rarely",'as the rest, the rate would be %s.'%p1(SP_)) if TREND!='orig' else None
        if NCH=='6':
            TH=9.0; r1c=TOP+TH; r1h=55.6-r1c; r2T=r1c+r1h+0.6; r2c=r2T+TH; r2h=89.5-r2c
            Z+=title('1','Reviews turn bad fast: %s are 1-2 stars up to the promised day, about %s from day 6 late'%(p1(F('ramp_share_up_to_promised_day')),p0(F('ramp_share_from_day_6'))),'share of reviews that are 1-2 stars, by days past the promised day',CX[0],TOP,CW)
            Z+=zone_sheet('Review ramp',CX[0],r1c,CW,r1h,zstyle(margin=2))
            FT=0
            Z+=title('2',trend_head,wk_note,CX[1],TOP,CW)
            Z+=zone_sheet('Trend',CX[1],r1c,CW,r1h-FT,zstyle(margin=2))
            Z+=title('3','Orders shipped after the ship-by date: %s arrive late, vs %s when shipped by it'%(p1(LH),p1(OK_)),'%s of %s arrived late  \u00b7  %s of all %s late orders'%(n0(F('late_handoff_late_orders')),n0(F('late_handoff_orders')),p1(F('late_handoff_share_of_late')),n0(F('late_orders'))),CX[2],TOP,CW,hc=ACC)
            Z+=zone_sheet('Handoff',CX[2],r1c,CW,r1h,zstyle(margin=4))
            st_,sn_=seller_title(); CLOSE=2.6
            T4=5.0 if SELL=='repeat' else 0
            Z+=title('4',st_,sn_,CX[0],r2T,CW,TH+T4)
            Z+=zone_sheet('Sellers',CX[0],r2c+T4,CW,r2h-T4-(CLOSE if SELL=='codes' else 0),zstyle(margin=2))
            if SELL=='codes': Z+=ztxt([('The other %d sellers account for the remaining %s.'%(N_SELL-10,p0(1-F('top10_share_of_late_after_late_handoff'))),10,False,MID)],CX[0],r2c+r2h-CLOSE,CW,CLOSE,zstyle(margin=2))
            Z+=title('5','North and northeast run %s late vs %s elsewhere'%(p1(F('nne_late_rate')),p1(F('rest_late_rate'))),'late rate by region  \u00b7  Click a region to filter',CX[1],r2T,CW)
            Z+=zone_sheet('Region',CX[1],r2c,CW,min(r2h,14),zstyle(margin=2))
            Z+=ztxt([('6  ',12,True,MID),('%s of late orders came in 3 months: %s'%(p1(F('worst3_share_of_late')),SUM['worst3_months_label']),12,True,INK),NL,('those 3 months held %s of all orders (%s of months)'%(p1(F('worst3_share_of_orders')),p0(F('worst3_share_of_months'))),9,False,MID)],CX[2],r2T,CW,TH)
            Z+=zone_sheet('Months',CX[2],r2c,CW,r2h,zstyle(margin=2))
            BOT=90.2
        else:
            TH=9.0; HW=49; X2=51; TOP=25.4
            rowh=31.0; rowh2=35.8; r1c=TOP+TH; r1h=rowh-TH; r2T=TOP+rowh+0.6; r2c=r2T+TH; r2h=rowh2-TH-0.4
            FT=0
            Z+=title('1',trend_head,wk_note,1,TOP,HW)
            Z+=zone_sheet('Trend',1,r1c,HW,r1h-FT,zstyle(margin=2))
            Z+=title('2','Orders shipped after the ship-by date: %s arrive late, vs %s when shipped by it'%(p1(LH),p1(OK_)),'%s of %s arrived late  \u00b7  %s of all %s late orders'%(n0(F('late_handoff_late_orders')),n0(F('late_handoff_orders')),p1(F('late_handoff_share_of_late')),n0(F('late_orders'))),X2,TOP,HW,hc=ACC)
            Z+=zone_sheet('Handoff',X2,r1c,HW,r1h,zstyle(margin=4))
            st_,sn_=seller_title(); CLOSE=2.6
            Z+=title('3',st_,sn_,1,r2T,HW)
            Z+=zone_sheet('Sellers',1,r2c,HW,r2h-(CLOSE if SELL=='codes' else 0),zstyle(margin=2))
            if SELL=='codes': Z+=ztxt([('The other %d sellers account for the remaining %s.'%(N_SELL-10,p0(1-F('top10_share_of_late_after_late_handoff'))),10,False,MID)],1,r2c+r2h-CLOSE,HW,CLOSE,zstyle(margin=2))
            Z+=title('4','North and northeast run %s late vs %s elsewhere'%(p1(F('nne_late_rate')),p1(F('rest_late_rate'))),'late rate by region  \u00b7  Click a region to filter',X2,r2T,HW)
            Z+=zone_sheet('Region',X2,r2c,HW,min(r2h,24),zstyle(margin=2))
            BOT=93.1
        whatif=('      \u00b7      What-if, not a result: if late-shipped orders were late as rarely as the rest, the rate would be %s.'%p1(SP_)) if foot_t else ''
        Z+=ztxt([('Next step (nothing launched yet)',11,True,MID),(whatif,10,False,MID),NL,(REC_MODEL,10,False,MID),NL,(REC_SELLER,10,False,MID)],1,BOT,98,99.9-BOT,zstyle(border=MID,bstyle='dashed',bw=1,margin=4))
        srcs=[('Filter by seller','Sellers'),('Filter by region','Region')]+([('Filter by month','Months')] if NCH=='6' else [])
    else:
        DNAME='Diagnosis'
        Z+=ztxt([('Why orders are late, and where to act',20,True,INK),NL,('Orders that sellers ship late are the biggest linked source of lateness',16,True,ACC),NL,('Diagnosis  \u00b7  page 2 of 2  \u00b7  first tab = status board  \u00b7  click a seller, region or month bar to filter the other charts',11,False,MID)],1,0.4,98,13.2)
        TOP=14.4; TH=9.0; HW=49; X2=51; rowh=38.4; r1c=TOP+TH; r1h=rowh-TH; r2T=TOP+rowh+0.6; r2c=r2T+TH; r2h=rowh-TH
        Z+=title('1','Orders shipped after the ship-by date: %s arrive late, vs %s when shipped by it'%(p1(LH),p1(OK_)),'%s of %s arrived late  \u00b7  %s of all %s late orders'%(n0(F('late_handoff_late_orders')),n0(F('late_handoff_orders')),p1(F('late_handoff_share_of_late')),n0(F('late_orders'))),1,TOP,HW,hc=ACC)
        Z+=zone_sheet('Handoff',1,r1c,HW,r1h,zstyle(margin=4))
        st_,sn_=seller_title(); CLOSE=2.6
        Z+=title('2',st_,sn_,X2,TOP,HW)
        Z+=zone_sheet('Sellers',X2,r1c,HW,r1h-(CLOSE if SELL=='codes' else 0),zstyle(margin=2))
        if SELL=='codes': Z+=ztxt([('The other %d sellers account for the remaining %s.'%(N_SELL-10,p0(1-F('top10_share_of_late_after_late_handoff'))),10,False,MID)],X2,r1c+r1h-CLOSE,HW,CLOSE,zstyle(margin=2))
        Z+=title('3','North and northeast run %s late vs %s elsewhere'%(p1(F('nne_late_rate')),p1(F('rest_late_rate'))),'late rate by region  \u00b7  Click a region to filter',1,r2T,HW)
        Z+=zone_sheet('Region',1,r2c,HW,min(r2h,24),zstyle(margin=2))
        Z+=ztxt([('4  ',12,True,MID),('%s of late orders came in 3 months: %s'%(p1(F('worst3_share_of_late')),SUM['worst3_months_label']),12,True,INK),NL,('those 3 months held %s of all orders (%s of months)'%(p1(F('worst3_share_of_orders')),p0(F('worst3_share_of_months'))),9,False,MID)],X2,r2T,HW,TH)
        Z+=zone_sheet('Months',X2,r2c,HW,r2h,zstyle(margin=2))
        Z+=ztxt([('Next step (nothing launched yet)',11,True,MID),NL,("Keep building the per-order delivery-date model; launch only once checkout conversion by promised days and a second peak season show the longer date is worth it.      No seller penalty list: flagged sellers did not run late more often.",10,False,MID)],1,93.1,98,6.8,zstyle(border=MID,bstyle='dashed',bw=1,margin=4))
        srcs=[('Filter by seller','Sellers'),('Filter by region','Region'),('Filter by month','Months')]
    DASHES.append((DNAME,Z,mk_actions(DNAME,srcs)))
ACTIONS="  <actions>\n"+''.join(a for _,_,a in DASHES)+"  </actions>\n" if any(a for _,_,a in DASHES) else ''
dash="  <dashboards>\n"+''.join(f"""    <dashboard name={quoteattr(n)}>
      <style />
      <size maxheight='{Hh}' maxwidth='{W}' minheight='{Hh}' minwidth='{W}' />
      <zones>
        <zone h='100000' id='4' type='layout-basic' w='100000' x='0' y='0'>
{Z}        </zone>
      </zones>
      <simple-id uuid='{uid('dash'+n)}' />
    </dashboard>
""" for n,Z,_ in DASHES)+"  </dashboards>\n"
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
act=ACTIVE or DASHES[0][0]
for n,_,_ in DASHES:
    wins+=f"    <window class='dashboard' {'maximized=%s '%quoteattr('true') if n==act else ''}name={quoteattr(n)}>\n      <viewpoints />\n      <active id='-1' />\n      <simple-id uuid='{uid('windash'+n)}' />\n    </window>\n"
doc=HEAD+"<datasources>\n"+PARAMS+''.join(d.xml() for d in D.values())+"  </datasources>\n"+ACTIONS+"  <worksheets>\n"+''.join(x for _,x in WS)+"  </worksheets>\n"+dash+"  <windows source-height='30'>\n"+wins+"  </windows>\n</workbook>\n"
open(out,'w',encoding='utf-8').write(doc)
print('wrote',out,len(doc),'dashboards',[n for n,_,_ in DASHES])
