# Dashboard data

Tables for the late-delivery dashboard (layout B: six number tiles over six panels). Nothing here draws a chart. Tableau does that.

`make dashboard` (after `make build`) writes one CSV per export into `dashboard/data/`. The CSVs are committed, so Tableau can read them without running dbt. `make verify` fails if they drift from the warehouse.

| File | Rows | Grain | Feeds |
|---|---|---|---|
| `summary.csv` | 1 | the whole window | the six number tiles, the goal and alarm lines, the labels (including "Nov 2017, Feb 2018 and Mar 2018") |
| `review_ramp.csv` | 61 | days past the promised day, -30 to +30 | panel 1, share of reviews that are 1-2 stars |
| `monthly.csv` | 20 | purchase month | panel 2 (rate, each month's alarm line, goal, stretch what-if) and the monthly bars in panel 5 |
| `handoff.csv` | 2 | late or on-time handoff | panel 3 |
| `sellers.csv` | 2,925 | seller | panel 4; the chart shows `is_top10` |
| `region.csv` | 2 | north and northeast, rest of Brazil | panel 5 |
| `tests_example.csv` | 2 | test | not used by the shipped Tableau dashboard (`tableau/`, layout B1), whose bottom strip names two fixes to test and shows no numbers. If a strip with numbers is ever shown, these are **invented example numbers** |

## What the numbers mean

- **Review cost (about 3,110).** Extra 1-2 star reviews linked to late delivery. Each late order is compared with the same seller's orders that arrived just on time, in the same category and month. It is an estimate from past orders, not a controlled test. The likely range across six ways of estimating it is 2,880 to 3,350.
- **Late** means the order arrived on a later calendar day than promised. Population: 94,931 delivered single-seller orders bought January 2017 to August 2018.
- **Late handoff** means the seller gave the parcel to the carrier after the last ship-by time. One order has no handoff time and is in neither handoff bar. That is why the two handoff shares add up to just under 100%.
- **Late after a late handoff** is a late order whose handoff was late. Shares in `sellers.csv` divide by the 1,809 such orders.
- **Stretch line (a what-if, not a goal).** `stretch_whatif_late_rate` in `monthly.csv` and `summary.csv` is the middle month (median) of the stable months' late rate if late handoffs were late no more often than on-time ones, about 3.4%. The export reads it from `metric_late_rate_targets.stretch_goal_late_rate` and does not compute it. It pairs like for like with `goal_late_rate`, the median of the months as they were, so the gap between them is the handoff fix alone. The what-if is a mix-shift calculation, not a tested cause. `summary.csv` carries the label in `stretch_whatif_label`: "middle month if late seller handoffs were fixed, a what-if". The column is named `whatif` so a chart cannot show it as a target by mistake.
- **Alarm lines.** `own_month_alarm_line_late_rate` in `monthly.csv` is the alarm line for that month's own order count. `typical_month_alarm_line_late_rate` in `summary.csv` is the alarm line for the typical month's size (`typical_month_orders`). `latest_month_own_alarm_line_late_rate` is the first of those for the latest month.
- **Worst months** are the three with the most late orders (a tie goes to the later month). They hold 48.3% of all late orders, but also 21.7% of all orders (`worst3_share_of_orders`) and are 15% of the 20 months (`worst3_share_of_months`), so the 48.3% is about twice what their size alone would give. The 21.7% and the 15% come from the story's month table, not from the export.

## How each number is checked

Four layers, each proven able to fail:

1. dbt tests in the warehouse (`tests/business_rules/assert_dash_*`) recompute each number from the detail exports and compare it with `story/data/facts.json`, the evidence report and the story CSVs, at the rounding the dashboard prints. `assert_dash_columns_are_derived` recomputes the columns that are worked out from others (month start and label, rank, flags, rates, phase, shares) on every row. Cases `Dashboard exports (...)` in `evidence/mutation_report.md` plant a wrong value and require a test to fail.
2. `verification/verify_dash_exports.py` repeats the comparison on the CSV files Tableau reads, and checks that `seeds/dash_region_map.csv` has the same 16 north and northeast states as `story/story_data.py`. It prints the table; `evidence/dash_exports_report.json` keeps it. `verification/selftest_dash_exports.py` plants one wrong value for every row of that table (94 planted errors, including a nonexistent `OLIST_DB_PATH`) and requires that row to turn red.
3. `verification/dash_raw_rebuild.py` rebuilds the population, the late counts, every seller, month, handoff and region row from `data/raw/*.csv` with Python and DuckDB, with no dbt model in the path. The verifier compares the CSVs with that rebuild, cell by cell. The typed seller numbers (94,931 orders, 6,518 late, 1,809 late after a late handoff, 583 sellers, top 10 hold 19.1%, top seller `06a2c3af` with 66) are checked against it.
4. `dashboard/export_csv.py --check` fails if a committed CSV differs from the warehouse. Both it and the selftest read the warehouse named by `OLIST_DB_PATH`; a path that does not exist is an error.

**Every column is covered.** `verification/column_sweep.py` sets each cell of every column of every export wrong, one at a time (868 cells in 98 columns), and requires a dbt test or a verifier row to fail. `evidence/column_coverage.json` holds the result: every column has a check, and it names the checks that caught each one. `make verify` reruns the sweep in a quick form (the verifier first, dbt only for a cell the verifier misses) and fails if a column has an unchecked cell. Not covered by this: a change that is wrong in two cells at once in a way that leaves every rule true, and the number the tests cannot recompute (next paragraph).

**What is a consistency check, not evidence.** The review-cost range (2,880 to 3,350, six estimators in `review_cost_causal/`) is not recomputed here. The four rows that compare it with facts.json and the evidence report are labelled "consistency" in the tests and the verifier: they show the export carries the number the analysis wrote, not that the range is right. The 21.7% and 15% are read from the story's month table.

## The tests strip is an example

The shipped Tableau dashboard (`tableau/`) no longer shows these numbers; its bottom strip says "Two fixes to test next (nothing run yet)" and holds none. The file stays, still labelled, for any layout that shows a strip with numbers. `seeds/dash_tests_example.csv` holds invented numbers that show the layout. The export marks every row `is_example`, `not run`, "EXAMPLE" in both labels, an asterisk on both values, the banner and a footnote. `assert_dash_tests_are_labelled_example` fails if any row loses one of those. When the tests have run, a results model replaces the seed and that test goes with it.

## Not in these tables

These tables cover the whole window: the handoff, seller and region tables have no month column. The click filters (seller, region, month) in the Tableau dashboard do not use them. They work on a separate order-level file, `orders.csv`, built from the warehouse by `tableau/export_orders.py` (not committed). See `tableau/README.md`.
