VERIFIED
Workbook: ../out_b1_v2.twb (the shipped file, wording version 3). Tableau Desktop 2026.3, macOS, 2026-11-19, about 21:55 ET.
Claim: clicking the seller 06a2c3af bar filters the shipped-late, region and month panels to that seller (the "Orders shipped after the ship-by date" panel moves off 5.4% / 21.2%), and clicking again undoes it. Trend and ramp stay all-order by design.

Images (downscaled to 1366 x 768 for this repo; md5 of the full-size exports in brackets):
 baseline.png      shipped by 5.4% / shipped after 21.2%, region 12.2% / 6.2%            [7ec795fb934e96f9cf3fc17100dbde11]
 click_seller.png  shipped by 3.0% / shipped after 54.5%, region 22.4% / 18.2%, months Feb 2, Mar 17, Aug 1; seller bar outlined, others dimmed   [33344d59a1ae0d5939c073d0ec082f47]
 clear (click again): the export has the same md5 as the baseline, so no separate image is kept.   [7ec795fb934e96f9cf3fc17100dbde11]

DuckDB (orders.csv built from the warehouse by export_orders.py), seller 06a2c3af: shipped by the ship-by date 8/267 = 3.0%, shipped after 66/121 = 54.5%; region North and northeast 22.4%, rest 18.2%; seller bar 66. All match the image.

Method: harness/click_probe.py (Presentation Mode centres the 1366 x 768 dashboard on the 1728 x 1117 pt screen, offset 181, 174.5), a real mouse click from harness/mclick.js at dashboard point (307, 510), which is screen (488, 685), then Esc and Dashboard > Export Image. Run from the harness/ folder on the Mac. The panel positions moved a little in this wording version (a closing line was added under the seller bars), so the click points differ from the previous version's.
Why earlier clicks failed: a System Events "click at" is an accessibility press on the window, not a mouse event.
Version note: the version-2 wording (handoff, alarm line) was click-tested the same way earlier on 2026-11-19 with the same filter results; those images were replaced by these.
