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
| C | story bad_review_by_days_late:-1 | story 157/1441 raw 157/1441 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-10 | story 368/4576 raw 368/4576 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-11 | story 394/4542 raw 394/4542 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-12 | story 367/4473 raw 367/4473 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-13 | story 448/5854 raw 448/5854 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-14 | story 596/6990 raw 596/6990 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-15 | story 413/5229 raw 413/5229 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-16 | story 287/3812 raw 287/3812 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-17 | story 259/3342 raw 259/3342 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-18 | story 255/3066 raw 255/3066 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-19 | story 191/2636 raw 191/2636 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-2 | story 180/1536 raw 180/1536 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-20 | story 205/2884 raw 205/2884 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-21 | story 217/2724 raw 217/2724 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-22 | story 150/1781 raw 150/1781 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-23 | story 123/1213 raw 123/1213 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-24 | story 101/1037 raw 101/1037 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-25 | story 81/880 raw 81/880 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-26 | story 62/766 raw 62/766 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-27 | story 80/777 raw 80/777 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-28 | story 64/720 raw 64/720 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-29 | story 47/465 raw 47/465 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-3 | story 181/1705 raw 181/1705 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-30 | story 230/2436 raw 230/2436 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-4 | story 204/1891 raw 204/1891 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-5 | story 230/2195 raw 230/2195 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-6 | story 330/3584 raw 330/3584 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-7 | story 431/4774 raw 431/4774 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-8 | story 459/4770 raw 459/4770 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:-9 | story 397/4562 raw 397/4562 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:0 | story 156/1275 raw 156/1275 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:1 | story 159/817 raw 159/817 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:10 | story 172/207 raw 172/207 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:11 | story 140/177 raw 140/177 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:12 | story 124/155 raw 124/155 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:13 | story 148/189 raw 148/189 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:14 | story 139/169 raw 139/169 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:15 | story 122/155 raw 122/155 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:16 | story 76/94 raw 76/94 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:17 | story 69/89 raw 69/89 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:18 | story 56/72 raw 56/72 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:19 | story 64/74 raw 64/74 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:2 | story 184/535 raw 184/535 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:20 | story 73/86 raw 73/86 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:21 | story 64/76 raw 64/76 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:22 | story 51/64 raw 51/64 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:23 | story 31/34 raw 31/34 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:24 | story 41/52 raw 41/52 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:25 | story 32/39 raw 32/39 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:26 | story 30/33 raw 30/33 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:27 | story 34/40 raw 34/40 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:28 | story 35/46 raw 35/46 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:29 | story 32/37 raw 32/37 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:3 | story 248/493 raw 248/493 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:30 | story 234/342 raw 234/342 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:4 | story 243/435 raw 243/435 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:5 | story 279/431 raw 279/431 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:6 | story 311/406 raw 311/406 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:7 | story 345/470 raw 345/470 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:8 | story 259/330 raw 259/330 | - | - | **VERIFIED** |
| C | story bad_review_by_days_late:9 | story 177/219 raw 177/219 | - | - | **VERIFIED** |
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
| C | story late_first_last12 | story 5586/None raw 5586/None | - | - | **VERIFIED** |
| C | story late_orders | story 6518/94931 raw 6518/94931 | - | - | **VERIFIED** |
| C | story late_sales_last12 | story 998816.62/11619769.11 raw 998816.62/11619769.11 | - | - | **VERIFIED** |
| C | story late_sales_window | story 1148081.0/None raw 1148081.0/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-1 | story 1453/None raw 1453/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-10 | story 4603/None raw 4603/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-11 | story 4569/None raw 4569/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-12 | story 4502/None raw 4502/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-13 | story 5890/None raw 5890/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-14 | story 7024/None raw 7024/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-15 | story 5255/None raw 5255/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-16 | story 3827/None raw 3827/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-17 | story 3355/None raw 3355/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-18 | story 3078/None raw 3078/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-19 | story 2654/None raw 2654/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-2 | story 1546/None raw 1546/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-20 | story 2895/None raw 2895/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-21 | story 2729/None raw 2729/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-22 | story 1789/None raw 1789/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-23 | story 1223/None raw 1223/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-24 | story 1042/None raw 1042/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-25 | story 885/None raw 885/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-26 | story 767/None raw 767/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-27 | story 783/None raw 783/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-28 | story 726/None raw 726/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-29 | story 468/None raw 468/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-3 | story 1720/None raw 1720/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-30 | story 2452/None raw 2452/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-4 | story 1904/None raw 1904/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-5 | story 2206/None raw 2206/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-6 | story 3606/None raw 3606/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-7 | story 4796/None raw 4796/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-8 | story 4798/None raw 4798/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:-9 | story 4582/None raw 4582/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:0 | story 1286/None raw 1286/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:1 | story 822/None raw 822/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:10 | story 207/None raw 207/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:11 | story 181/None raw 181/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:12 | story 160/None raw 160/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:13 | story 196/None raw 196/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:14 | story 171/None raw 171/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:15 | story 159/None raw 159/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:16 | story 98/None raw 98/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:17 | story 89/None raw 89/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:18 | story 76/None raw 76/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:19 | story 77/None raw 77/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:2 | story 544/None raw 544/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:20 | story 89/None raw 89/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:21 | story 80/None raw 80/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:22 | story 67/None raw 67/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:23 | story 37/None raw 37/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:24 | story 53/None raw 53/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:25 | story 39/None raw 39/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:26 | story 33/None raw 33/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:27 | story 40/None raw 40/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:28 | story 47/None raw 47/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:29 | story 39/None raw 39/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:3 | story 497/None raw 497/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:30 | story 359/None raw 359/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:4 | story 452/None raw 452/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:5 | story 444/None raw 444/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:6 | story 418/None raw 418/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:7 | story 482/None raw 482/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:8 | story 336/None raw 336/None | - | - | **VERIFIED** |
| C | story orders_by_days_late:9 | story 226/None raw 226/None | - | - | **VERIFIED** |

Part A rules: {'multi_seller_late_rule': 'trust_order_date', 'repeat_same_day_rule': 'second_order_only'}. Part B rules: {'analysis_window_start': '2017-01-01', 'analysis_window_end': '2018-08-31', 'multi_seller_late_rule': 'exclude_multi_seller', 'review_before_delivery_compare': 'calendar_day', 'review_pick_rule': 'latest_answer', 'repeat_same_day_rule': 'any_later_order_24h'}.
