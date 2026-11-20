#!/usr/bin/env python3
"""click_probe4.py <tag> <group> [<group> ...]   (Tableau already open on the workbook, Mac only)
A group is one or more screen points x,y joined with '+', e.g. 481,727+481,727 (select, then click the same mark again 2.5 s later to clear).
For each group: Window > Presentation Mode, the clicks (real mouse events via mclick.js, 2.5 s apart so they are not a double-click), Esc,
then Dashboard > Export Image to <WORK_DIR>/<tag>_<i>.png. With no group it exports one baseline image <tag>_0.png.
Screen = dashboard point + ((1728-1366)/2, (1117-768)/2) = + (181, 174.5) on this Mac."""
import sys,subprocess,time,os,hashlib
here=os.path.dirname(os.path.abspath(__file__))
APPNAME=os.environ.get('TABLEAU_APP_NAME','Tableau Desktop (Apple silicon) 2026.3'); PROC=os.environ.get('TABLEAU_PROC','Tableau')
EXPORT_DIR=os.path.expanduser(os.environ.get('EXPORT_DIR','~/Documents')); WORK_DIR=os.path.expanduser(os.environ.get('WORK_DIR','~/olist_dash/click'))
MCLICK=os.path.join(here,'mclick.js'); tag=sys.argv[1]; groups=[[tuple(map(float,p.split(','))) for p in g.split('+')] for g in sys.argv[2:]]
def osa(s): r=subprocess.run(['osascript','-e',s],capture_output=True,text=True,timeout=60); return (r.stdout+r.stderr).strip()
SE='tell application "System Events" to tell process "%s" to '%PROC
def export(out):
    if os.path.exists(out): os.remove(out)
    osa('tell application "%s" to activate'%APPNAME); time.sleep(1)
    osa(SE+'click menu item "Export Image..." of menu 1 of menu bar item "Dashboard" of menu bar 1'); time.sleep(4)
    osa(SE+'set value of text field "Save As:" of splitter group 1 of window "Save Image" to "%s"'%os.path.basename(out)); time.sleep(1)
    osa(SE+'click button "Save" of splitter group 1 of window "Save Image"')
    dd=os.path.join(EXPORT_DIR,os.path.basename(out))
    for i in range(20):
        if os.path.exists(dd): break
        time.sleep(1)
    time.sleep(6)
    if os.path.exists(dd): os.rename(dd,out)
    print(out,os.path.exists(out),hashlib.md5(open(out,'rb').read()).hexdigest()[:8] if os.path.exists(out) else None,flush=True)
os.makedirs(WORK_DIR,exist_ok=True); base=os.path.join(WORK_DIR,'%s_'%tag)
osa('tell application "%s" to activate'%APPNAME); time.sleep(2)
if not groups: export(base+'0.png')
for i,g in enumerate(groups):
    osa(SE+'click menu item "Presentation Mode" of menu 1 of menu bar item "Window" of menu bar 1'); time.sleep(3)
    for (x,y) in g:
        print('click',subprocess.run(['osascript','-l','JavaScript',MCLICK,str(x),str(y)],capture_output=True,text=True,timeout=60).stdout.strip(),flush=True); time.sleep(2.5)
    time.sleep(0.5); osa('tell application "System Events" to key code 53'); time.sleep(3)
    export(base+'%d.png'%i)
