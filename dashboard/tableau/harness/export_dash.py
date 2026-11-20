#!/usr/bin/env python3
"""export_dash.py <twb> <out.png> [procname]: open twb in Tableau Desktop, wait for load or error, run Dashboard > Export Image..., save PNG, log UI state, quit app (discarding nothing: never saves). Mac only.
Settings (environment, current values are the defaults):
  TABLEAU_APP  path of the app          default '/Applications/Tableau Desktop (Apple silicon) 2026.3.app'
  EXPORT_DIR   where Tableau saves PNGs default ~/Documents
Needs macOS Accessibility permission for the app that runs this script."""
import sys,subprocess,time,os,re
twb,out=sys.argv[1:3]
APP=os.environ.get('TABLEAU_APP','/Applications/Tableau Desktop (Apple silicon) 2026.3.app')
APPNAME=os.path.basename(APP)[:-4]
EXPORT_DIR=os.path.expanduser(os.environ.get('EXPORT_DIR','~/Documents'))
proc=sys.argv[3] if len(sys.argv)>3 else 'Tableau'
log=out+'.log'; L=[]
def P(*a):
    s=' '.join(str(x) for x in a); L.append(s); print(s,flush=True)
def osa(s,js=False):
    cmd=['osascript']+(['-l','JavaScript'] if js else [])+['-e',s]
    r=subprocess.run(cmd,capture_output=True,text=True); return (r.stdout+r.stderr).strip()
def wins(): return osa('tell application "System Events" to tell process "%s" to get name of every window'%proc)
subprocess.run(['killall','-TERM',proc],capture_output=True); time.sleep(3)
if os.path.exists(out): os.remove(out)
subprocess.run(['open','-a',APP,twb])
state='NONE'; end=time.time()+60
while time.time()<end:
    time.sleep(2); w=wins()
    if 'Unable to complete action' in w: state='ERROR'; break
    if re.search(r'Tableau - (?!Book1)',w): state='OPENED'; break
P('state',state,'windows',wins())
if state=='ERROR':
    P(osa('tell application "System Events" to tell process "%s" to get entire contents of window "Unable to complete action"'%proc))
else:
    time.sleep(8)
    osa('tell application "%s" to activate'%APPNAME)
    time.sleep(1)
    P('menu click:',osa('tell application "System Events" to tell process "%s" to click menu item "Export Image..." of menu 1 of menu bar item "Dashboard" of menu bar 1'%proc))
    time.sleep(4)
    P('windows after menu:',wins())
    P('ui:',osa('tell application "System Events" to tell process "%s" to get {name, role} of every UI element of window 1'%proc)[:1500])
    P('panel:',osa('tell application "System Events" to tell process "%s" to get entire contents of window "Save Image"'%proc)[:4000])
    P('sheets:',osa('tell application "System Events" to tell process "%s" to get name of every sheet of window 1'%proc))
    P('set name:',osa('tell application "System Events" to tell process "%s" to set value of text field "Save As:" of splitter group 1 of window "Save Image" to "%s"'%(proc,os.path.basename(out))))
    time.sleep(1)
    P('pop2:',osa('tell application "System Events" to tell process "%s" to get {value, name} of pop up button 2 of splitter group 1 of window "Save Image"'%proc))
    P('save click:',osa('tell application "System Events" to tell process "%s" to click button "Save" of splitter group 1 of window "Save Image"'%proc))
    time.sleep(4)
    P('after save windows:',wins())
    P('after save sheets:',osa('tell application "System Events" to tell process "%s" to get name of every sheet of window 1'%proc))
    for i in range(10):
        if os.path.exists(out): break
        time.sleep(1)
    dd=os.path.join(EXPORT_DIR,os.path.basename(out))
    for i in range(10):
        if os.path.exists(dd): break
        time.sleep(1)
    if os.path.exists(dd): os.rename(dd,out)
    P('exists',os.path.exists(out), os.path.getsize(out) if os.path.exists(out) else 0)
open(log,'w').write('\n'.join(L)+'\n')
subprocess.run(['killall','-TERM',proc],capture_output=True)
time.sleep(2)
