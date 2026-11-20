VERIFIED (region click) and VERIFIED (month click)
Workbook: ../out_b1_v2.twb (the shipped file). Tableau Desktop 2026.3, macOS, 2026-11-19, about 21:35 ET.
Harness: harness/click_probe.py with harness/mclick.js (Presentation Mode, real mouse click, Esc, Export Image). Screen points: region bar North and northeast (848, 714); month bar Mar 2018 (1413, 801).

Images (downscaled to 1366 x 768; md5 of the full-size exports in brackets):
 baseline.png      [ff0f1e647cc5e96dc8d61a1d92395bd5]
 click_region.png  [55e13bfc9b2bf41b3244272de9577a25]
 click_month.png   [35a42f02933435071b7d4494c54cd40a]
 clear after each click: the export has the baseline md5 (ff0f1e64...) both times, so no separate images are kept.

REGION click
  handoff 11.0% / 24.5%         DuckDB 10.96% / 24.47%   match
  sellers 16, 8, 4, 0, 4, 0, 6, 4, 1, 1   DuckDB identical   match
  month labels Nov 161, Feb 147, Mar 252, Aug 11   DuckDB identical   match
  region panel: North and northeast bar outlined, the other dimmed
MONTH click (Mar 2018)
  handoff 17.7% / 34.6%         DuckDB 1118/6317 = 17.7%, 206/596 = 34.6%   match
  region 33.6% / 17.4%          DuckDB 33.6 / 17.4   match
  sellers 13, 5, 2, 16, 5, 0, 7, 0 (ranks 9 and 10 absent)   DuckDB 13, 5, 2, 16, 5, 0, 7, 0, 0, 0; ranks 9 and 10 had no orders in March, so no row   match
  Mar 2018 bar 1,324 highlighted, the others dimmed   DuckDB 1,324   match
Trend and ramp stay all-order by design.
