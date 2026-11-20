VERIFIED
Claim: In Tableau Desktop, clicking the seller 06a2c3af bar in out_b1_final.twb filters the Handoff, Region and Months panels to that seller; handoff panel moves off 21.2%/5.4%; filtering is undone by clicking again. Trend and ramp stay all-order by design.
Evidence (Tableau Desktop 2026.3, 2026-11-19 ~20:50 ET):
 baseline click/base_0.png md5 8f7536e2 (handoff 5.4% / 21.2%, region 12.2% / 6.2%)
 treatment click/m481_0.png md5 9161bf3a (handoff 3.0% / 54.5%, region 22.4% / 18.2%, months Feb 2, Mar 17, Aug 1; seller bar outlined, others dimmed)
 DuckDB seller 06a2c3af%: handoff on-time 8/267=3.0%, late 66/121=54.5%; region NNE 19/85=22.4%, rest 55/303=18.2%; months Feb 2, Mar 17, Aug 1; late after late handoff 66.  MATCH.
 clear click/clr_0.png md5 8f7536e2 == baseline (byte-identical).
Method: Presentation Mode centers the 1366x768 dashboard on the 1728x1117-pt screen (offset 181,174.5); real CGEvent mouse click (osascript -l JavaScript mclick.js) at dashboard point (300,526) = screen (481,700); Esc; Dashboard > Export Image.
Why earlier clicks failed: System Events 'click at' does an accessibility press on the window, not a mouse event.
Not tested: clicking a region or month bar (same action mechanism, separate actions).
Confound: none seen; screencapture still blocked (Screen Recording not granted) but not needed.
