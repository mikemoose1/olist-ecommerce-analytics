VERIFIED (region click) and VERIFIED (month click)
Workbook: ../out_b1_v2.twb (the shipped file, wording version 3). Tableau Desktop 2026.3, macOS, 2026-11-19, about 21:56 ET.
Harness: harness/click_probe.py with harness/mclick.js (Presentation Mode, real mouse click, Esc, Export Image). Screen points: region bar North and northeast (915, 699); month bar Mar 2018 (1412, 802).

Images (downscaled to 1366 x 768; md5 of the full-size exports in brackets):
 baseline.png      [7ec795fb934e96f9cf3fc17100dbde11]
 click_region.png  [c831b96d1f38e22ae3eb88d98fabb5d5]
 click_month.png   [f69491e92ddfd6fc369a158afb1387a7]
 clear after each click: the export has the baseline md5 (7ec795fb...) both times, so no separate images are kept.

"shipped after / by" below = the bars "Orders shipped after the ship-by date" and "Orders shipped by the ship-by date" in panel 3.

REGION click
  shipped by 11.0% / after 24.5%   DuckDB 1069/9755 = 11.0%, 233/952 = 24.5%   match
  sellers 16, 8, 4, 0, 4, 0, 6, 4, 1, 1   DuckDB identical   match
  month labels Nov 161, Feb 147, Mar 252, Aug 11   DuckDB identical   match
  region panel: North and northeast bar outlined, the other dimmed
MONTH click (Mar 2018)
  shipped by 17.7% / after 34.6%   DuckDB 1118/6317 = 17.7%, 206/596 = 34.6%   match
  region 33.6% / 17.4%          DuckDB 33.6 / 17.4   match
  sellers 13, 5, 2, 16, 5, 0, 7, 0 (ranks 9 and 10 absent)   DuckDB 13, 5, 2, 16, 5, 0, 7, 0, 0, 0; ranks 9 and 10 had no orders in March, so no row   match
  Mar 2018 bar 1,324 highlighted, the others dimmed   DuckDB 1,324   match
Trend and ramp stay all-order by design.
