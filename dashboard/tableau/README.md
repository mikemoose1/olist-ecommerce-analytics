# Tableau dashboard (layout B1, version 2)

The late-delivery dashboard as a Tableau Desktop workbook, with the script that builds it and the checks that show its clicks work. Tableau draws it. The numbers come from `dashboard/data/` and the dbt warehouse, nothing is typed by hand.

![dashboard](B1_v2.png)

The title says the finding: late deliveries cost about 3,110 bad reviews, and late seller handoffs are the biggest fixable cause. Three tiles (cost, this month against the 4.4% goal, handoff gap 21.2% vs 5.4%), then trend, why, and where. Gray everywhere, orange only for the handoff gap. Panel 6 is an invented example, as in the data README.

## Files

| File | What it is |
|---|---|
| `out_b1_v2.twb` | the workbook. It reads its CSVs from `/path/to/olist_dash/data` (a placeholder: regenerate for your own folder, below, or repoint the data source in Tableau). |
| `B1_v2.png` | the exported image of the dashboard |
| `gen_workbook.py`, `ctrl_saved_desktop_free.twb` | builds the workbook XML from a control file saved by Tableau Desktop (hand-written workbooks do not open) |
| `prep.py` | makes `ramp_b.csv` and `monthly_long.csv` from `dashboard/data/` |
| `export_orders.py` | writes `orders.csv`, one row per delivered order, from the warehouse |
| `harness/` | Mac-only tools: `export_dash.py` (open a workbook and export the image), `click_probe.py` + `mclick.js` (click a mark and export) |
| `evidence/` | the click tests and their results |

`orders.csv` is about 12 MB, so it is not committed. It is rebuilt byte for byte by `export_orders.py`.

## Regenerate

```bash
make build dashboard                      # warehouse and dashboard/data
mkdir -p /tmp/olist_tableau && cp dashboard/data/summary.csv dashboard/data/tests_example.csv /tmp/olist_tableau/
python3 dashboard/tableau/prep.py dashboard/data /tmp/olist_tableau
python3 dashboard/tableau/export_orders.py /tmp/olist_tableau/orders.csv      # needs the duckdb package; OLIST_DB_PATH picks the warehouse
python3 dashboard/tableau/gen_workbook.py /tmp/olist_tableau /tmp/olist_tableau out_b1_v2.twb   # 2nd path = folder as Tableau sees it
```

With the second path set to `/path/to/olist_dash/data`, the output is identical to `out_b1_v2.twb`. `prep.py` and `export_orders.py` were checked to reproduce the CSVs used for the committed workbook, byte for byte.

## Clicking filters the other panels

Clicking a seller, a region bar or a month bar filters the sellers, handoff, region and months panels. The tiles, the chart titles and the trend panel always show all orders. Tableau, not an image, is needed for this: run it in Tableau Desktop.

Tested in Tableau Desktop 2026.3 with a real mouse click, then Dashboard, Export Image, and compared with a DuckDB query on the same filter. After each click, clicking again gave an image byte-identical to the unfiltered one.

| Click | Result | Matches DuckDB |
|---|---|---|
| seller `06a2c3af` | handoff 3.0% / 54.5% (was 5.4% / 21.2%), region 22.4% / 18.2%, month labels Feb 2, Mar 17, Aug 1 | yes |
| region North and northeast | handoff 11.0% / 24.5%, sellers 16, 8, 4, 0, 4, 0, 6, 4, 1, 1, month labels Nov 161, Feb 147, Mar 252, Aug 11 | yes |
| month Mar 2018 | handoff 17.7% / 34.6%, region 33.6% / 17.4%, sellers 13, 5, 2, 16, 5, 0, 7, 0 (ranks 9 and 10 had no orders that month), Mar bar 1,324 | yes |

Details and image fingerprints: `evidence/`. The harness needs macOS Accessibility permission for the app that runs it. It puts Tableau in Presentation Mode, which centres the 1366 x 768 dashboard, and works out the click position from the layout. A click that comes from `System Events` is an accessibility press, not a mouse click, and does not select a mark.

## Goal and stretch lines

The 4.4% goal and the 3.4% stretch line are Tableau reference lines whose value comes from a parameter, so each gets its own thickness: the goal is a heavy solid line, the stretch line a thin dashed one. An earlier try pointed the line at a data column and did not draw.

**The alarm line cannot be dashed.** It changes with each month's order count (small early months get a higher line), so it is a data line, not a constant. In the Tableau files and notes checked, only reference lines, reference bands, trend lines and gridlines carry a dash setting. A data line has one thickness and one style for the whole chart. This was not proven impossible by every route in Desktop.

## Other limits found

- A workbook with italic text runs does not open, so the example numbers in the bottom strip are gray, not italic.
- Tableau Public is not used. Nothing here publishes anything.
