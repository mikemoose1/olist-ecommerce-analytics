# Dashboard numbers and the semantic layer

Written by `verification/dashboard_semantic_audit.py`; `--check` fails if this file is out of date.

Tableau reads CSVs, so no dashboard number is read from the semantic layer directly. This table lists every numeric column of
every CSV in `dashboard/data/` and marks it **semantic** only when a metric in `models/semantic/_semantic.yml` defines it and
`mf query` returns the same value on every row. All other numbers are computed in SQL inside the export models and have no
semantic-layer definition. The order-level `orders.csv` that the Tableau scripts build (`dashboard/tableau/export_orders.py`)
is not listed: its rows come from `metric_late_rate_orders`, the table the `late_rate_orders` semantic model is built on, but
Tableau, not MetricFlow, adds them up.

**10 semantic, 66 not.**

| File | Column | Source |
|---|---|---|
| `handoff.csv` | `orders` | not in the semantic layer |
| `handoff.csv` | `late_orders` | not in the semantic layer |
| `handoff.csv` | `late_rate` | not in the semantic layer |
| `handoff.csv` | `share_of_all_late` | not in the semantic layer |
| `monthly.csv` | `orders` | semantic: judged_orders by month |
| `monthly.csv` | `late_orders` | semantic: late_orders by month |
| `monthly.csv` | `late_rate` | semantic: late_rate by month |
| `monthly.csv` | `late_rate_if_handoffs_ok` | not in the semantic layer |
| `monthly.csv` | `own_month_alarm_line_late_rate` | not in the semantic layer |
| `monthly.csv` | `late_handoff_orders` | not in the semantic layer |
| `monthly.csv` | `late_handoff_late_orders` | not in the semantic layer |
| `monthly.csv` | `on_time_handoff_orders` | not in the semantic layer |
| `monthly.csv` | `on_time_handoff_late_orders` | not in the semantic layer |
| `monthly.csv` | `share_of_all_late` | not in the semantic layer |
| `monthly.csv` | `late_orders_rank` | not in the semantic layer |
| `monthly.csv` | `typical_month_alarm_line_late_rate` | not in the semantic layer |
| `monthly.csv` | `goal_late_rate` | not in the semantic layer |
| `monthly.csv` | `stretch_whatif_late_rate` | not in the semantic layer |
| `region.csv` | `states` | not in the semantic layer |
| `region.csv` | `orders` | semantic: judged_orders by customer state, summed over the region's states |
| `region.csv` | `late_orders` | semantic: late_orders by customer state, summed over the region's states |
| `region.csv` | `late_rate` | semantic: late_orders / judged_orders by customer state, summed over the region's states |
| `region.csv` | `share_of_all_late` | not in the semantic layer |
| `review_ramp.csv` | `days_past_promise_capped` | not in the semantic layer |
| `review_ramp.csv` | `orders` | not in the semantic layer |
| `review_ramp.csv` | `reviewed_orders` | not in the semantic layer |
| `review_ramp.csv` | `bad_reviews` | not in the semantic layer |
| `review_ramp.csv` | `bad_review_share` | not in the semantic layer |
| `sellers.csv` | `orders` | not in the semantic layer |
| `sellers.csv` | `late_handoff_orders` | not in the semantic layer |
| `sellers.csv` | `late_after_late_handoff_orders` | not in the semantic layer |
| `sellers.csv` | `late_orders` | not in the semantic layer |
| `sellers.csv` | `late_handoff_rate` | not in the semantic layer |
| `sellers.csv` | `late_rate` | not in the semantic layer |
| `sellers.csv` | `rank_by_late_after_late_handoff` | not in the semantic layer |
| `sellers.csv` | `share_of_late_after_late_handoff` | not in the semantic layer |
| `summary.csv` | `judged_orders` | semantic: judged_orders |
| `summary.csv` | `late_orders` | semantic: late_orders |
| `summary.csv` | `late_rate` | semantic: late_rate |
| `summary.csv` | `extra_bad_reviews` | not in the semantic layer |
| `summary.csv` | `extra_bad_reviews_rounded` | not in the semantic layer |
| `summary.csv` | `reviewed_late_orders` | not in the semantic layer |
| `summary.csv` | `bad_reviews_all` | not in the semantic layer |
| `summary.csv` | `extra_share_of_bad_reviews` | not in the semantic layer |
| `summary.csv` | `extra_range_low` | not in the semantic layer |
| `summary.csv` | `extra_range_high` | not in the semantic layer |
| `summary.csv` | `extra_range_low_rounded` | not in the semantic layer |
| `summary.csv` | `extra_range_high_rounded` | not in the semantic layer |
| `summary.csv` | `ramp_share_up_to_promised_day` | not in the semantic layer |
| `summary.csv` | `ramp_share_from_day_6` | not in the semantic layer |
| `summary.csv` | `ramp_points_per_day` | not in the semantic layer |
| `summary.csv` | `latest_month_late_rate` | semantic: late_rate by month |
| `summary.csv` | `latest_month_own_alarm_line_late_rate` | not in the semantic layer |
| `summary.csv` | `typical_month_orders` | not in the semantic layer |
| `summary.csv` | `typical_month_alarm_line_late_rate` | not in the semantic layer |
| `summary.csv` | `goal_late_rate` | not in the semantic layer |
| `summary.csv` | `stretch_whatif_late_rate` | not in the semantic layer |
| `summary.csv` | `alarm_months` | not in the semantic layer |
| `summary.csv` | `late_handoff_orders` | not in the semantic layer |
| `summary.csv` | `late_handoff_late_orders` | not in the semantic layer |
| `summary.csv` | `late_handoff_late_rate` | not in the semantic layer |
| `summary.csv` | `on_time_handoff_late_rate` | not in the semantic layer |
| `summary.csv` | `late_handoff_share_of_late` | not in the semantic layer |
| `summary.csv` | `sellers_with_late_after_late_handoff` | not in the semantic layer |
| `summary.csv` | `top10_late_after_late_handoff_orders` | not in the semantic layer |
| `summary.csv` | `top10_share_of_late_after_late_handoff` | not in the semantic layer |
| `summary.csv` | `top_seller_late_after_late_handoff_orders` | not in the semantic layer |
| `summary.csv` | `nne_late_rate` | not in the semantic layer |
| `summary.csv` | `rest_late_rate` | not in the semantic layer |
| `summary.csv` | `nne_share_of_late` | not in the semantic layer |
| `summary.csv` | `worst3_share_of_late` | not in the semantic layer |
| `summary.csv` | `worst3_share_of_orders` | not in the semantic layer |
| `summary.csv` | `worst3_share_of_months` | not in the semantic layer |
| `tests_example.csv` | `test_id` | not in the semantic layer |
| `tests_example.csv` | `test_group_value` | not in the semantic layer |
| `tests_example.csv` | `no_change_group_value` | not in the semantic layer |
