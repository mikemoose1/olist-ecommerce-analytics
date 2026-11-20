VERIFIED (region click) and VERIFIED (month click)  -- workbook out_b1_v2.twb, Tableau Desktop 2026.3, 2026-11-19 ~21:35 ET
Harness: build/click_probe.py + mclick.js (Presentation Mode, CGEvent mouse click, Esc, Export Image). Click points (screen): region bar North/NE (848,714); month bar Mar 2018 (1413,801).
Baseline v2_baseline.png md5 ff0f1e64.
REGION click -> region_click.png md5 55e13bfc; clear -> region_clear.png md5 ff0f1e64 (== baseline, byte-identical)
  handoff 11.0% / 24.5%        DuckDB NNE 10.96% / 24.47%  MATCH
  sellers 16,8,4,0,4,0,6,4,1,1 DuckDB identical             MATCH
  months Nov 161, Feb 147, Mar 252, Aug 11   DuckDB identical MATCH
  region panel: NNE bar outlined, rest dimmed (12.2% / 6.2% unchanged, as expected for the clicked panel's own bars)
MONTH click (Mar 2018) -> month_click.png md5 35a42f02; clear -> month_clear.png md5 ff0f1e64 (== baseline)
  handoff 17.7% / 34.6%        DuckDB Mar 2018: 1118/6317=17.7%, 206/596=34.6%  MATCH
  region 33.6% / 17.4%         DuckDB 33.6 / 17.4  MATCH
  sellers 13,5,2,16,5,0,7,0 (ranks 9,10 absent)  DuckDB lalh in Mar: 13,5,2,16,5,0,7,0,0,0; ranks 9 and 10 had 0 orders that month so no row  MATCH
  month bar: Mar 2018 = 1,324 highlighted, others dimmed   DuckDB 1,324 MATCH
Trend and ramp stay all-order by design. Autosave recovery: after this session Tableau offered no File Recovery dialog (nothing to delete); earlier one was deleted.
