VERIFIED
Workbook: ../out_b1_v2.twb (the shipped file). Tableau Desktop 2026.3, macOS, 2026-11-19, about 21:40 ET.
Claim: clicking the seller 06a2c3af bar filters the handoff, region and month panels to that seller (the handoff panel moves off 5.4% / 21.2%), and clicking again undoes it. Trend and ramp stay all-order by design.

Images (downscaled to 1366 x 768 for this repo; md5 of the full-size exports in brackets):
 baseline.png      handoff 5.4% / 21.2%, region 12.2% / 6.2%            [ff0f1e647cc5e96dc8d61a1d92395bd5]
 click_seller.png  handoff 3.0% / 54.5%, region 22.4% / 18.2%, months Feb 2, Mar 17, Aug 1; seller bar outlined, others dimmed   [7664f8463440272d14dd4f942a69bca9]
 clear (click again): the export has the same md5 as the baseline, so no separate image is kept.   [ff0f1e647cc5e96dc8d61a1d92395bd5]

DuckDB, seller 06a2c3af: handoff on time 8/267 = 3.0%, late 66/121 = 54.5%; region North and northeast 19/85 = 22.4%, rest 55/303 = 18.2%; month late orders Feb 2, Mar 17, Aug 1; late after a late handoff 66. All match the image.

Method: harness/click_probe.py (Presentation Mode centres the 1366 x 768 dashboard on the 1728 x 1117 pt screen, offset 181, 174.5), a real mouse click from harness/mclick.js at dashboard point (300, 526), which is screen (481, 700), then Esc and Dashboard > Export Image. Run from the committed harness/ folder on the Mac.
Why earlier clicks failed: a System Events "click at" is an accessibility press on the window, not a mouse event.
Re-run note: this is the second run on out_b1_v2.twb; an earlier run on the same file (about 20:53 ET) gave the same three md5s. The first seller test (about 20:50 ET) was on an earlier workbook without the reference-line change and is not used.
