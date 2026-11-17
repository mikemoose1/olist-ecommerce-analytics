# Headline reconciliation

**Part A** rebuilds the metric layer with the first pass's rules and must reproduce the first pass AND an independent raw-CSV recomputation. **Part B** checks the shipped numbers (rules picked by experiment) against the independent recomputation under the same rules.

| Part | Metric | Mart | Independent (raw CSVs) | First pass | Verdict |
|---|---|---|---|---|---|
| A | repeat_rate_90d | 1.24 (961/77560) | 1.24 (961/77560) | 1.24 | **VERIFIED** |
| A | repeat_rate_ever | 3.04 (2887/94983) | 3.04 (2887/94983) | 3.04 | **VERIFIED** |
| A | late_rate | 6.79 (6531/96203) | 6.79 (6531/96203) | 6.79 | **VERIFIED** |
| A | review_score | 4.156 (397176/95560) | 4.156 (397176/95560) | 4.156 | **VERIFIED** |
| A | late_review_gap_raw | 2.021 | 2.021 | 2.021 | **VERIFIED** |
| A | late_penalty_controlled (OLS) | -1.992 CI [-2.023, -1.962] | - | -1.992 | **VERIFIED** |
| B | repeat_rate_90d (HEADLINE) | 1.28 (991/77560) | 1.28 (991/77560) | - | **VERIFIED** |
| B | repeat_rate_ever (secondary) | 3.04 (2887/94983) | 3.04 (2887/94983) | - | **VERIFIED** |
| B | late_rate | 6.87 (6518/94931) | 6.87 (6518/94931) | - | **VERIFIED** |
| B | review_score | 4.156 (397176/95560) | 4.156 (397176/95560) | - | **VERIFIED** |
| B | late_review_gap_raw | 2.04 | 2.04 | - | **VERIFIED** |
| B | late_penalty_controlled (OLS) | -2.012 CI [-2.042, -1.982] | - | - | **REPORTED** |

Part A rules: {'multi_seller_late_rule': 'trust_order_date', 'repeat_same_day_rule': 'second_order_only'}. Part B rules: {'analysis_window_start': '2017-01-01', 'analysis_window_end': '2018-08-31', 'multi_seller_late_rule': 'exclude_multi_seller', 'review_before_delivery_compare': 'calendar_day', 'review_pick_rule': 'latest_answer', 'repeat_same_day_rule': 'any_later_order_24h'}.
