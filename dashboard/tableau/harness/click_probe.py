#!/usr/bin/env python3
"""click_probe.py <tag> [x,y ...]   (Tableau already open on the workbook, Mac only)

For each screen point x,y (in points): Window > Presentation Mode, a real mouse click at (x,y) via mclick.js,
Esc, then Dashboard > Export Image to <work dir>/<tag>_<i>.png. With no points it exports one baseline image.
Presentation Mode centres the 1366x768 dashboard on screen, so screen = dashboard point + ((screen w - 1366)/2, (screen h - 768)/2).

Settings (environment, current values are the defaults):
  TABLEAU_APP_NAME  app name for AppleScript        default 'Tableau Desktop (Apple silicon) 2026.3'
  TABLEAU_PROC      System Events process name      default 'Tableau'
  EXPORT_DIR        folder where Tableau saves PNGs default ~/Documents
  WORK_DIR          where <tag>_<i>.png end up      default ~/tableau-experiments/olist_dash/click
Needs macOS Accessibility permission for the app that runs this script.
"""
import sys,subprocess,time,os,hashlib
here=os.path.dirname(os.path.abspath(__file__))
APPNAME=os.environ.get('TABLEAU_APP_NAME','Tableau Desktop (Apple silicon) 2026.3')
PROC=os.environ.get('TABLEAU_PROC','Tableau')
EXPORT_DIR=os.path.expanduser(os.environ.get('EXPORT_DIR','~/Documents'))
WORK_DIR=os.path.expanduser(os.environ.get('WORK_DIR','~/tableau-experiments/olist_dash/click'))
MCLICK=os.path.join(here,'mclick.js')
tag=sys.argv[1]; pts=[tuple(map(int,a.split(','))) for a in sys.argv[2:]]
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
    h=hashlib.md5(open(out,'rb').read()).hexdigest()[:8] if os.path.exists(out) else None
    print(out,os.path.exists(out),h,flush=True)
os.makedirs(WORK_DIR,exist_ok=True)
base=os.path.join(WORK_DIR,'%s_'%tag)
osa('tell application "%s" to activate'%APPNAME); time.sleep(2)
if not pts: export(base+'0.png')
for i,(x,y) in enumerate(pts):
    osa(SE+'click menu item "Presentation Mode" of menu 1 of menu bar item "Window" of menu bar 1'); time.sleep(3)
    print('click',subprocess.run(['osascript','-l','JavaScript',MCLICK,str(x),str(y)],capture_output=True,text=True,timeout=60).stdout.strip(),flush=True); time.sleep(3)
    osa('tell application "System Events" to key code 53'); time.sleep(3)
    export(base+'%d.png'%i)
