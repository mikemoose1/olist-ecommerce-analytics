# Dashboard data

Tables for the late-delivery dashboard (layout B: six number tiles over six panels). Nothing here draws a chart. Tableau does that.

`make dashboard` (after `make build`) writes one CSV per export into `dashboard/data/`. The CSVs are committed, so Tableau can read them without running dbt. `make verify` fails if they drift from the warehouse.

| File | Rows | Grain | Feeds |
|---|---|---|---|
| `summary.csv` | 1 | the whole window | the six number tiles, the goal and alarm lines, the labels (including "Nov 2017, Feb 2018 and Mar 2018") |
| `review_ramp.csv` | 61 | days past the promised day, -30 to +30 | panel 1, share of reviews that are 1-2 stars |
| `monthly.csv` | 20 | purchase month | panel 2 (rate, each month's alarm line, goal, stretch, what-if median) and the monthly bars in panel 5 |
| `handoff.csv` | 2 | late or on-time handoff | panel 3 |
| `sellers.csv` | 2,925 | seller | panel 4; the chart shows `is_top10` |
| `region.csv` | 2 | north and northeast, rest of Brazil | panel 5 |
| `tests_example.csv` | 2 | test | panel 6, **invented example numbers** |

## What the numbers mean

- **Review cost (about 3,110).** Extra 1-2 star reviews linked to late delivery. Each late order is compared with the same seller's orders that arrived just on time, in the same category and month. It is an estimate from past orders, not a controlled test. The likely range across six ways of estimating it is 2,880 to 3,350.
- **Late** means the order arrived on a later calendar day than promised. Population: 94,931 delivered single-seller orders bought January 2017 to August 2018.
- **Late handoff** means the seller gave the parcel to the carrier after the last ship-by time. One order has no handoff time and is in neither handoff bar. That is why the two handoff shares add up to just under 100%.
- **Late after a late handoff** is a late order whose handoff was late. Shares in `sellers.csv` divide by the 1,809 such orders.
- **Stretch line.** `stretch_goal_late_rate` in `monthly.csv` and `summary.csv` is the middle month (median) of the stable months' late rate if late handoffs were late no more often than on-time ones, about 3.4%. It pairs like for like with `goal_late_rate`, the median of the months as they were, so the gap between them is the handoff fix alone. The what-if is a mix-shift calculation, not a tested cause. `summary.csv` carries the label in `stretch_goal_label`: "middle month if late seller handoffs were fixed, a what-if". This was chosen over the 25th-percentile line (about 2.3%), which mixed the handoff fix with a move from a middle month to a good month. The export computes the median itself for now; once the memo sync (PR #8) changes `metric_late_rate_targets.stretch_goal_late_rate` to the median, the export reads that column instead.
- **Worst months** are the three with the most late orders (a tie goes to the later month).

## How each number is checked

Three layers, each proven able to fail (cases `Dashboard exports (...)` in `evidence/mutation_report.md`, 49 planted errors in `verification/selftest_dash_exports.py`):

1. dbt tests in the warehouse recompute each number from the detail exports and compare it with `story/data/facts.json`, the evidence report and the story CSVs, at the rounding the dashboard prints.
2. `verification/verify_dash_exports.py` repeats the comparison on the CSV files Tableau reads, and checks that `seeds/dash_region_map.csv` has the same 16 north and northeast states as `story/story_data.py`. It prints the table; `evidence/dash_exports_report.json` keeps it.
3. `dashboard/export_csv.py --check` fails if a committed CSV differs from the warehouse.

The seller numbers (583 sellers, top 10 hold 19.1%, top seller `06a2c3af` with 66) have no analysis file to compare with. They are typed in the tests from the prototype run, and the tests also rebuild the seller counts by a separate query.

## Panel 6 is an example

`seeds/dash_tests_example.csv` holds invented numbers that show the layout. The export marks every row `is_example`, `not run`, "EXAMPLE" in both labels, an asterisk on both values, the banner and a footnote. `assert_dash_tests_are_labelled_example` fails if any row loses one of those. When the tests have run, a results model replaces the seed and that test goes with it.

## Not in these tables

The month filter (click a month to filter panels 3 to 5) is not wired: handoff, seller and region tables cover the whole window. Layout B shows no month filter. If the dashboard needs one, add a month column to those three tables.
