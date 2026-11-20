#!/usr/bin/env python3
"""click_probe.py <tag> x,y [x,y..]  (Tableau already open on the twb). For each point: Presentation Mode -> click screen (x,y) -> Esc -> Export Image to click/<tag>_<i>.png. tag 'base' with no points = baseline."""
import sys,subprocess,time,os,hashlib
tag=sys.argv[1]; pts=[tuple(map(int,a.split(','))) for a in sys.argv[2:]]
def osa(s): r=subprocess.run(['osascript','-e',s],capture_output=True,text=True,timeout=60); return (r.stdout+r.stderr).strip()
SE='tell application "System Events" to tell process "Tableau" to '
def export(out):
    if os.path.exists(out): os.remove(out)
    osa('tell application "Tableau Desktop (Apple silicon) 2026.3" to activate'); time.sleep(1)
    osa(SE+'click menu item "Export Image..." of menu 1 of menu bar item "Dashboard" of menu bar 1'); time.sleep(4)
    osa(SE+'set value of text field "Save As:" of splitter group 1 of window "Save Image" to "%s"'%os.path.basename(out)); time.sleep(1)
    osa(SE+'click button "Save" of splitter group 1 of window "Save Image"')
    dd=os.path.expanduser('~/Documents/'+os.path.basename(out))
    for i in range(20):
        if os.path.exists(dd): break
        time.sleep(1)
    time.sleep(6)
    if os.path.exists(dd): os.rename(dd,out)
    h=hashlib.md5(open(out,'rb').read()).hexdigest()[:8] if os.path.exists(out) else None
    print(out,os.path.exists(out),h,flush=True)
os.makedirs(os.path.expanduser('~/tableau-experiments/olist_dash/click'),exist_ok=True)
base=os.path.expanduser('~/tableau-experiments/olist_dash/click/%s_'%tag)
osa('tell application "Tableau Desktop (Apple silicon) 2026.3" to activate'); time.sleep(2)
if not pts: export(base+'0.png')
for i,(x,y) in enumerate(pts):
    osa(SE+'click menu item "Presentation Mode" of menu 1 of menu bar item "Window" of menu bar 1'); time.sleep(3)
    print('click',subprocess.run(['osascript','-l','JavaScript',os.path.expanduser('~/tableau-experiments/olist_dash/mclick.js'),str(x),str(y)],capture_output=True,text=True,timeout=60).stdout.strip(),flush=True); time.sleep(3)
    osa('tell application "System Events" to key code 53'); time.sleep(3)
    export(base+'%d.png'%i)
