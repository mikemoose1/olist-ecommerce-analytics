# Headline reconciliation

**Part A** rebuilds the metric layer with the first pass's rules and must reproduce the first pass AND an independent raw-CSV recomputation. **Part B** checks the shipped numbers (rules picked by experiment) against the independent recomputation under the same rules. **Part C** checks every count behind a story chart against the raw CSVs (story count and raw count in the Mart column).

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
| C | story comment_delay_share | story 2499/3747 raw 2499/3747 | - | - | **VERIFIED** |
| C | story late_by_handoff:Handed over after ship-by | story 1809/8530 raw 1809/8530 | - | - | **VERIFIED** |
| C | story late_by_handoff:Handed over on time | story 4708/86400 raw 4708/86400 | - | - | **VERIFIED** |
| C | story late_by_month:2017-01 | story 22/746 raw 22/746 | - | - | **VERIFIED** |
| C | story late_by_month:2017-02 | story 49/1641 raw 49/1641 | - | - | **VERIFIED** |
| C | story late_by_month:2017-03 | story 116/2541 raw 116/2541 | - | - | **VERIFIED** |
| C | story late_by_month:2017-04 | story 150/2285 raw 150/2285 | - | - | **VERIFIED** |
| C | story late_by_month:2017-05 | story 106/3513 raw 106/3513 | - | - | **VERIFIED** |
| C | story late_by_month:2017-06 | story 95/3110 raw 95/3110 | - | - | **VERIFIED** |
| C | story late_by_month:2017-07 | story 108/3808 raw 108/3808 | - | - | **VERIFIED** |
| C | story late_by_month:2017-08 | story 121/4135 raw 121/4135 | - | - | **VERIFIED** |
| C | story late_by_month:2017-09 | story 182/4106 raw 182/4106 | - | - | **VERIFIED** |
| C | story late_by_month:2017-10 | story 187/4414 raw 187/4414 | - | - | **VERIFIED** |
| C | story late_by_month:2017-11 | story 902/7195 raw 902/7195 | - | - | **VERIFIED** |
| C | story late_by_month:2017-12 | story 408/5454 raw 408/5454 | - | - | **VERIFIED** |
| C | story late_by_month:2018-01 | story 403/6967 raw 403/6967 | - | - | **VERIFIED** |
| C | story late_by_month:2018-02 | story 925/6505 raw 925/6505 | - | - | **VERIFIED** |
| C | story late_by_month:2018-03 | story 1324/6913 raw 1324/6913 | - | - | **VERIFIED** |
| C | story late_by_month:2018-04 | story 306/6670 raw 306/6670 | - | - | **VERIFIED** |
| C | story late_by_month:2018-05 | story 442/6641 raw 442/6641 | - | - | **VERIFIED** |
| C | story late_by_month:2018-06 | story 71/5989 raw 71/5989 | - | - | **VERIFIED** |
| C | story late_by_month:2018-07 | story 208/6059 raw 208/6059 | - | - | **VERIFIED** |
| C | story late_by_month:2018-08 | story 393/6239 raw 393/6239 | - | - | **VERIFIED** |
| C | story late_by_region:North and northeast | story 1302/10707 raw 1302/10707 | - | - | **VERIFIED** |
| C | story late_by_region:Rest of Brazil | story 5216/84224 raw 5216/84224 | - | - | **VERIFIED** |
| C | story late_by_state:AC | story 3/80 raw 3/80 | - | - | **VERIFIED** |
| C | story late_by_state:AL | story 85/394 raw 85/394 | - | - | **VERIFIED** |
| C | story late_by_state:AM | story 4/145 raw 4/145 | - | - | **VERIFIED** |
| C | story late_by_state:AP | story 2/67 raw 2/67 | - | - | **VERIFIED** |
| C | story late_by_state:BA | story 396/3217 raw 396/3217 | - | - | **VERIFIED** |
| C | story late_by_state:CE | story 176/1262 raw 176/1262 | - | - | **VERIFIED** |
| C | story late_by_state:DF | story 118/2050 raw 118/2050 | - | - | **VERIFIED** |
| C | story late_by_state:ES | story 214/1965 raw 214/1965 | - | - | **VERIFIED** |
| C | story late_by_state:GO | story 128/1920 raw 128/1920 | - | - | **VERIFIED** |
| C | story late_by_state:MA | story 124/702 raw 124/702 | - | - | **VERIFIED** |
| C | story late_by_state:MG | story 517/11157 raw 517/11157 | - | - | **VERIFIED** |
| C | story late_by_state:MS | story 68/694 raw 68/694 | - | - | **VERIFIED** |
| C | story late_by_state:MT | story 52/869 raw 52/869 | - | - | **VERIFIED** |
| C | story late_by_state:PA | story 105/933 raw 105/933 | - | - | **VERIFIED** |
| C | story late_by_state:PB | story 54/512 raw 54/512 | - | - | **VERIFIED** |
| C | story late_by_state:PE | story 153/1579 raw 153/1579 | - | - | **VERIFIED** |
| C | story late_by_state:PI | story 66/473 raw 66/473 | - | - | **VERIFIED** |
| C | story late_by_state:PR | story 199/4843 raw 199/4843 | - | - | **VERIFIED** |
| C | story late_by_state:RJ | story 1490/12154 raw 1490/12154 | - | - | **VERIFIED** |
| C | story late_by_state:RN | story 44/466 raw 44/466 | - | - | **VERIFIED** |
| C | story late_by_state:RO | story 7/241 raw 7/241 | - | - | **VERIFIED** |
| C | story late_by_state:RR | story 5/40 raw 5/40 | - | - | **VERIFIED** |
| C | story late_by_state:RS | story 325/5241 raw 325/5241 | - | - | **VERIFIED** |
| C | story late_by_state:SC | story 291/3497 raw 291/3497 | - | - | **VERIFIED** |
| C | story late_by_state:SE | story 51/329 raw 51/329 | - | - | **VERIFIED** |
| C | story late_by_state:SP | story 1814/39834 raw 1814/39834 | - | - | **VERIFIED** |
| C | story late_by_state:TO | story 27/267 raw 27/267 | - | - | **VERIFIED** |
| C | story late_orders | story 6518/94931 raw 6518/94931 | - | - | **VERIFIED** |
| C | story late_sales_window | story 1148081.0/None raw 1148081.0/None | - | - | **VERIFIED** |

Part A rules: {'multi_seller_late_rule': 'trust_order_date', 'repeat_same_day_rule': 'second_order_only'}. Part B rules: {'analysis_window_start': '2017-01-01', 'analysis_window_end': '2018-08-31', 'multi_seller_late_rule': 'exclude_multi_seller', 'review_before_delivery_compare': 'calendar_day', 'review_pick_rule': 'latest_answer', 'repeat_same_day_rule': 'any_later_order_24h'}.
